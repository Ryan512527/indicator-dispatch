import os
import asyncio
import logging
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from app.core.config import settings

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".csv", ".json", ".xlsx", ".xls", ".xml"}

# 同一文件触发重解析的最小间隔（秒），防止源文件持续写入导致无限重解析
REPARSE_COOLDOWN = 300  # 5 分钟

# ── 专用报表配置 ──
# 按关键词长度降序排列，避免短关键词误匹配长关键词
# key: 文件名匹配关键词  →  value: 专用 reparse API 路径段
SPECIALIZED_REPORTS = [
    # 按关键词长度降序排列，避免短关键词误匹配长关键词
    ("质差小区弱光工单处理完成率", "poor-quality-work-order"),   # 13字
    ("2200000及时率",           "complaint-2200000"),          # 10字
    ("五类工单退撤单",          "five-category-withdrawal"),     # 8字
    ("重投预警工单梳理",         "retry-warning"),               # 8字
    ("投诉积压通报新",           "complaint-10086"),             # 7字
    ("宽带在途投诉",            "complaint-backlog"),            # 6字
    ("家宽重投2次",            "broadband-redelivery2"),        # 6字 新增
    ("装维工作量",              "city-workload"),                # 5字
    ("企宽故障率",              "enterprise-broadband-fault"),    # 5字
    ("企宽装机",               "enterprise-broadband"),          # 4字
    ("企宽弱光",               "enterprise-broadband-low-light"),# 4字 新增
    ("无线退服",               "wireless-outage"),               # 4字
    ("皮站故障",               "pisite-fault"),                 # 4字
    ("线下派单",               "offline-dispatch"),              # 4字
    ("接入层",                 "access-layer"),                  # 3字
    ("日报",                  "daily-report"),                  # 2字
]


class IndicatorFileHandler(FileSystemEventHandler):
    def __init__(self, loop: asyncio.AbstractEventLoop):
        self.loop = loop
        self.queue = asyncio.Queue()

    def on_created(self, event):
        if not event.is_directory and self._is_supported(event.src_path):
            fname = os.path.basename(event.src_path)
            if not fname.startswith("~$") and not fname.startswith("."):
                self.loop.call_soon_threadsafe(self.queue.put_nowait, event.src_path)

    def on_modified(self, event):
        if not event.is_directory and self._is_supported(event.src_path):
            fname = os.path.basename(event.src_path)
            if not fname.startswith("~$") and not fname.startswith("."):
                self.loop.call_soon_threadsafe(self.queue.put_nowait, event.src_path)

    def on_moved(self, event):
        if not event.is_directory and self._is_supported(event.dest_path):
            fname = os.path.basename(event.dest_path)
            if not fname.startswith("~$") and not fname.startswith("."):
                self.loop.call_soon_threadsafe(self.queue.put_nowait, event.dest_path)

    @staticmethod
    def _is_supported(path):
        return any(path.lower().endswith(ext) for ext in SUPPORTED_EXTENSIONS)


class FileWatcher:
    def __init__(self, watch_dir):
        self.watch_dir = watch_dir
        self._observer = Observer()
        self._running = False
        # 记录已处理的文件路径及其修改时间，用于轮询兜底
        self._known_files: dict[str, float] = {}
        # 记录每个文件最后一次触发解析的时间戳（用于冷却期去重）
        self._last_dispatch: dict[str, float] = {}
        # 记录每个报表类型最后一次触发解析的时间戳（同一类型的新文件在冷却期内不应重复全量解析）
        self._last_dispatch_by_type: dict[str, float] = {}

    def _should_dispatch(self, fpath: str) -> bool:
        """检查文件是否在冷却期内，防止同一文件被反复触发解析"""
        now = time.time()
        last = self._last_dispatch.get(fpath, 0)
        if now - last < REPARSE_COOLDOWN:
            return False
        return True

    def _mark_dispatched(self, fpath: str):
        """记录文件已被派发解析（同时清理过期条目防止无限增长）"""
        self._last_dispatch[fpath] = time.time()
        # 每标记约 100 次清理一次过期条目（>3倍冷却期 = 已无关紧要）
        if len(self._last_dispatch) % 100 == 0:
            self._prune_dispatch_records()

    def _prune_dispatch_records(self):
        """移除冷却期已远超的过期记录，防止 _last_dispatch 无限增长"""
        cutoff = time.time() - REPARSE_COOLDOWN * 3
        before = len(self._last_dispatch)
        self._last_dispatch = {k: v for k, v in self._last_dispatch.items() if v >= cutoff}
        after = len(self._last_dispatch)
        if before != after:
            logger.debug(f"[Watcher] _last_dispatch 清理: {before} → {after}")

    def _should_dispatch_by_type(self, report_type: str) -> bool:
        """检查同一报表类型是否在冷却期内（同一类型无论来多少新文件，只触发一次全量解析）"""
        now = time.time()
        last = self._last_dispatch_by_type.get(report_type, 0)
        if now - last < REPARSE_COOLDOWN:
            return False
        return True

    def _mark_dispatched_by_type(self, report_type: str):
        """记录报表类型已被派发解析"""
        self._last_dispatch_by_type[report_type] = time.time()

    def _scan_files(self, handler: IndicatorFileHandler,
                    trigger_reparse: bool = True):
        """轮询扫描：发现新增或修改的文件，加入处理队列（watchdog 兜底）
        
        Args:
            trigger_reparse: False 时仅记录 mtime 不入队（启动初始化用）
        
        Returns:
            list[str]: 新发现的需要处理的文件路径列表（仅在 trigger_reparse=True 时有值）
        """
        new_files = []
        for root, dirs, files in os.walk(self.watch_dir):
            for f in files:
                fpath = os.path.join(root, f)
                if not handler._is_supported(fpath):
                    continue
                if f.startswith("~$") or f.startswith("."):
                    continue
                try:
                    mtime = os.path.getmtime(fpath)
                except OSError:
                    continue
                if fpath not in self._known_files or self._known_files[fpath] < mtime:
                    self._known_files[fpath] = mtime
                    if trigger_reparse and self._should_dispatch(fpath):
                        # 不在此处 _mark_dispatched，由消费者在处理时标记
                        new_files.append(fpath)
        return new_files

    async def start(self):
        os.makedirs(self.watch_dir, exist_ok=True)
        loop = asyncio.get_running_loop()
        handler = IndicatorFileHandler(loop)

        self._observer.schedule(handler, self.watch_dir, recursive=True)
        self._observer.start()
        self._running = True
        logger.info(f"File watcher started (recursive): {self.watch_dir}")

        # ── 启动时初始化已知文件列表（不入队，仅记录 mtime 用于后续监听）──
        self._scan_files(handler, trigger_reparse=False)
        initial_count = len(self._known_files)
        if initial_count:
            logger.info(f"[Watcher] 发现 {initial_count} 个已有文件（跳过重解析，仅记录 mtime）")

        # ── 启动消费协程，处理后续 watchdog 事件和轮询发现的新文件 ──
        consumer_task = asyncio.create_task(self._consumer_loop(handler, loop))

        # 等待消费协程结束（服务停止时）
        try:
            await consumer_task
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.critical("[Watcher] 消费协程崩溃！", exc_info=True)
            raise

    async def _consumer_loop(self, handler, loop):
        """消费队列中的文件路径，逐个触发解析（专用/通用）"""
        import httpx
        from app.parser.service import parse_file as _parse_file_sync
        from app.classifier.service import classify_and_store

        POLL_INTERVAL = 15
        poll_counter = 0
        processed_count = 0

        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
            while self._running:
                try:
                    filepath = await asyncio.wait_for(handler.queue.get(), timeout=2.0)
                    fname = os.path.basename(filepath)

                    # ── 冷却期检查：同一文件在 REPARSE_COOLDOWN 秒内不重复解析 ──
                    if not self._should_dispatch(filepath):
                        logger.debug(f"[Watcher] 跳过（冷却期内）: {fname}")
                        continue

                    # ── 乐观标记 + 进度日志 ──
                    processed_count += 1
                    remaining = handler.queue.qsize()
                    if processed_count % 20 == 0 or processed_count <= 3:
                        logger.info(f"[Watcher] 进度: 已处理 {processed_count}/{processed_count + remaining} 个文件, "
                                    f"当前: {fname}, 剩余队列: {remaining}")

                    self._mark_dispatched(filepath)

                    # ── 限流保护：逐文件间短暂休眠，防止大量文件瞬间涌入耗尽资源 ──
                    await asyncio.sleep(0.5)

                    # ── 1. 专用报表识别与触发 ──
                    matched_specialized = False
                    for keyword, api_name in SPECIALIZED_REPORTS:
                        if keyword in fname:
                            # report_type 级冷却：同一类型无论来多少新文件，冷却期内只触发一次
                            if not self._should_dispatch_by_type(api_name):
                                logger.debug(f"[Watcher] 跳过（类型冷却期内）: [{api_name}] {fname}")
                                matched_specialized = True
                                break

                            logger.info(f"[Watcher] 检测到专用报表 '{keyword}'，触发专用解析: {fname}")
                            try:
                                resp = await client.post(
                                    f"http://localhost:8000/api/v1/reports/{api_name}/reparse"
                                )
                                if resp.status_code == 200:
                                    logger.info(f"[Watcher] 专用解析成功 [{api_name}]: {resp.json()}")
                                    self._mark_dispatched_by_type(api_name)
                                    matched_specialized = True
                                    break
                                else:
                                    logger.warning(
                                        f"[Watcher] 专用解析返回非200 [{api_name}]: {resp.status_code} {resp.text[:200]}，将尝试通用解析"
                                    )
                            except Exception as e:
                                logger.error(f"[Watcher] 专用解析调用失败 [{api_name}]: {e}，将尝试通用解析", exc_info=True)

                    # ── 2. 未匹配专用报表的，走通用解析 ──
                    if not matched_specialized:
                        records = await loop.run_in_executor(None, _parse_file_sync, filepath)
                        if records:
                            n = await classify_and_store(records)
                            logger.info(f"Stored {n} records from {fname}")

                except asyncio.TimeoutError:
                    # 每 POLL_INTERVAL 秒做一次轮询扫描
                    poll_counter += 2
                    if poll_counter >= POLL_INTERVAL:
                        poll_counter = 0
                        try:
                            before = len(self._known_files)
                            poll_new_files = self._scan_files(handler)
                            new_count = len(poll_new_files)
                            if new_count:
                                logger.info(f"[Watcher] 轮询发现 {new_count} 个新文件")
                                for fpath in poll_new_files:
                                    handler.queue.put_nowait(fpath)
                        except Exception as e:
                            logger.error(f"[Watcher] 轮询扫描异常: {e}", exc_info=True)
                    continue
                except Exception as e:
                    logger.error(f"Watcher: {e}", exc_info=True)

    async def stop(self):
        self._running = False
        self._observer.stop()
        self._observer.join()
