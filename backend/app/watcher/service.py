import os
import asyncio
import logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from app.core.config import settings

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".csv", ".json", ".xlsx", ".xls", ".xml"}


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

        from app.parser.service import parse_file as _parse_file_sync
        from app.classifier.service import classify_and_store

        while self._running:
            try:
                filepath = await asyncio.wait_for(handler.queue.get(), timeout=2.0)
                # Run parse in thread pool to avoid blocking event loop
                records = await loop.run_in_executor(None, _parse_file_sync, filepath)
                if records:
                    n = await classify_and_store(records)
                    logger.info(f"Stored {n} records from {os.path.basename(filepath)}")
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Watcher: {e}", exc_info=True)

    async def stop(self):
        self._running = False
        self._observer.stop()
        self._observer.join()
