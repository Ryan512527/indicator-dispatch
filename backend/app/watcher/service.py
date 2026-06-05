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
    ("五类工单退撤单", "five-category-withdrawal"),
    ("装维工作量",     "city-workload"),
    ("无线退服",       "wireless-outage"),
    ("企宽装机",       "enterprise-broadband"),
    ("皮站故障",       "pisite-fault"),
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

    async def start(self):
        os.makedirs(self.watch_dir, exist_ok=True)
        loop = asyncio.get_running_loop()
        handler = IndicatorFileHandler(loop)

        self._observer.schedule(handler, self.watch_dir, recursive=True)
        self._observer.start()
        self._running = True
        logger.info(f"File watcher started (recursive): {self.watch_dir}")

        # No scan of existing files - already imported via batch_import.py.
        # Only watches for NEW files going forward.

        import httpx
        from app.parser.service import parse_file as _parse_file_sync
        from app.classifier.service import classify_and_store

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
                                else:
                                    logger.warning(
                                        f"[Watcher] 专用解析返回非200 [{api_name}]: {resp.status_code} {resp.text[:200]}"
                                    )
                            except Exception as e:
                                logger.error(f"[Watcher] 专用解析调用失败 [{api_name}]: {e}", exc_info=True)
                            matched_specialized = True
                            break  # 只触发第一个匹配的专用报表

                    # ── 2. 未匹配专用报表的，走通用解析 ──
                    if not matched_specialized:
                        records = await loop.run_in_executor(None, _parse_file_sync, filepath)
                        if records:
                            n = await classify_and_store(records)
                            logger.info(f"Stored {n} records from {fname}")

                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    logger.error(f"Watcher: {e}", exc_info=True)

    async def stop(self):
        self._running = False
        self._observer.stop()
        self._observer.join()
