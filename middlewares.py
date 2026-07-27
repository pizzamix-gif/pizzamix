import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery

logger = logging.getLogger("mix_bot")


class LoggingMiddleware(BaseMiddleware):
    """Logs who did what. Cheap insurance for a bot that has to run unattended
    on Render — when something goes wrong you want a trail in the logs."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        uid = user.id if user else "?"
        if isinstance(event, Message):
            logger.info("msg from %s: %r", uid, event.text)
        elif isinstance(event, CallbackQuery):
            logger.info("callback from %s: %r", uid, event.data)
        try:
            return await handler(event, data)
        except Exception:
            logger.exception("Unhandled error while processing update from %s", uid)
            raise
