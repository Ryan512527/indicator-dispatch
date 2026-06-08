import os
import asyncio
import logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from app.core.config import settings

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".csv", ".json", ".xlsx", ".xls", ".xml"}

# ── 专用报表配置 ──
# 按关键词长度降序排列，避免短关键词误匹配长关键词
# key: 文件名匹配关键词  →  value: 专用 reparse API 路径段
SPECIALIZED_REPORTS = [
    ("宽带在途投诉",   "complaint-backlog"),
    ("投诉积压通报新", "complaint-10086"),
    ("2200000及时率",  "complaint-2200000"),
    ("五类工单退撤单", "five-category-withdrawal"),
    ("装维工作量",     "city-workload"),
    ("无线退服",       "wireless-outage"),
    ("企宽故障率",     "enterprise-broadband-fault"),
    ("企宽装机",       "enterprise-broadband"),
    ("皮站故障",       "pisite-fault"),
    ("线下派单",       "offline-dispatch"),
    ("重投预警工单梳理", "retry-warning"),
    ("质差小区弱光工单处理完成率", "poor-quality-work-order"),
    ("接入层",         "access-layer"),
    ("日报",           "daily-report"),
]


class IndicatorFileHandler(FileSystemEventHandler):
    def __init__(self, loop: asyncio.AbstractEventLoop):
        self.loop = loop
        self.queue = asyncio.Queue()

    def on_created(self, event):
        if not event.is_directory and self._is_supported(event.src_path):
            self.loop.call_soon_threadsafe(self.queue.put_nowait, event.src_path)

    def on_modified(self, event):
        if not event.is_directory and self._is_supported(event.src_path):
            fname = os.path.basename(event.src_path)
            if not fname.startswith("~$") and not fname.startswith("."):
                self.loop.call_soon_threadsafe(self.queue.put_nowait, event.src_path)

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

    def _scan_files(self, handler: IndicatorFileHandler):
        """轮询扫描：发现新增或修改的文件，加入处理队列（watchdog 兜底）"""
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
                    handler.queue.put_nowait(fpath)

    async def start(self):
        os.makedirs(self.watch_dir, exist_ok=True)
        loop = asyncio.get_running_loop()
        handler = IndicatorFileHandler(loop)

        self._observer.schedule(handler, self.watch_dir, recursive=True)
        self._observer.start()
        self._running = True
        logger.info(f"File watcher started (recursive): {self.watch_dir}")

        # ── 启动时扫描已有文件，初始化已知文件列表 ──
        self._scan_files(handler)
        initial_count = len(self._known_files)
        if initial_count:
            logger.info(f"[Watcher] 发现 {initial_count} 个已有文件，加入处理队列")

        import httpx
        from app.parser.service import parse_file as _parse_file_sync
        from app.classifier.service import classify_and_store

        # 轮询间隔（秒），用于兜底 watchdog 未触发的事件
        POLL_INTERVAL = 15
        poll_counter = 0

        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
            while self._running:
                try:
                    filepath = await asyncio.wait_for(handler.queue.get(), timeout=2.0)
                    fname = os.path.basename(filepath)

                    # ── 1. 专用报表识别与触发 ──
                    matched_specialized = False
                    for keyword, api_name in SPECIALIZED_REPORTS:
                        if keyword in fname:
                            logger.info(f"[Watcher] 检测到专用报表 '{keyword}'，触发专用解析: {fname}")
                            try:
                                resp = await client.post(
                                    f"http://localhost:8000/api/v1/reports/{api_name}/reparse"
                                )
                                if resp.status_code == 200:
                                    logger.info(f"[Watcher] 专用解析成功 [{api_name}]: {resp.json()}")
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
                            self._scan_files(handler)
                            new_count = len(self._known_files) - before
                            if new_count:
                                logger.info(f"[Watcher] 轮询发现 {new_count} 个新文件")
                        except Exception as e:
                            logger.error(f"[Watcher] 轮询扫描异常: {e}", exc_info=True)
                    continue
                except Exception as e:
                    logger.error(f"Watcher: {e}", exc_info=True)

    async def stop(self):
        self._running = False
        self._observer.stop()
        self._observer.join()
