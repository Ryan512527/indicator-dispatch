import logging
from typing import Optional
from app.core.config import settings

logger = logging.getLogger(__name__)


class WxPusherNotifier:
    def __init__(self):
        self.app_token = settings.wxpusher_app_token
        self._client = None

    def _ensure_client(self):
        if self._client is None and self.app_token:
            try:
                from wxpusher import WxPusher
                self._client = WxPusher()
                logger.info("WxPusher client initialized")
            except ImportError:
                logger.warning("wxpusher package not installed")

    async def send_message(
        self,
        content: str,
        uids: Optional[list[str]] = None,
        topic_ids: Optional[list[int]] = None,
        summary: Optional[str] = None,
    ) -> bool:
        self._ensure_client()
        if not self._client:
            logger.warning("WxPusher not configured, message not sent")
            return False

        try:
            # Use sync client in thread pool
            import asyncio
            return await asyncio.to_thread(
                self._sync_send,
                content=content,
                uids=uids or [],
                topic_ids=topic_ids or [],
                summary=summary or content[:100],
            )
        except Exception as e:
            logger.error(f"Failed to send WxPusher message: {e}")
            return False

    def _sync_send(self, content: str, uids: list[str], topic_ids: list[int], summary: str) -> bool:
        from wxpusher import WxPusher
        result = WxPusher.send_message(
            content=content,
            uids=uids,
            topic_ids=topic_ids,
            summary=summary,
            content_type=1,  # 1=HTML, 2=Text
        )
        return result.get("code") == 1000


# Singleton
notifier = WxPusherNotifier()
