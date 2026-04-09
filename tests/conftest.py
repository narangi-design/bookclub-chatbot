from unittest.mock import AsyncMock, MagicMock


def make_update(text: str = "", telegram_id: int = 111001, username: str = "alyona_reads"):
    update = MagicMock()
    update.effective_user.id = telegram_id
    update.effective_user.username = username
    update.effective_user.name = username
    update.message = AsyncMock()
    update.message.text = text
    update.callback_query = None
    return update


def make_context(user_data: dict | None = None):
    context = MagicMock()
    context.user_data = user_data or {}
    context.bot = AsyncMock()
    return context


def make_poll_update():
    update = make_update()
    update.effective_chat.id = -100123456
    update.effective_chat.title = "Книжный клуб"
    return update
