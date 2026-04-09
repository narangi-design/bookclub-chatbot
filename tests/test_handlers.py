"""
TDD-тесты для хэндлеров бота.
Все вызовы к бэку замокированы через fixtures.py.

Паттерн перехода на реальный бэк:
  1. Тест работает с mock-функцией из fixtures
  2. Когда готов реальный эндпоинт — заменяем mock на patch('api_client.get_books')
  3. Тест не меняется — меняется только источник данных
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from tests.fixtures import (
    authors, members, books,
    get_books_by_status, get_author_by_id, get_member_by_telegram_id,
    author_name_exists,
)


# --- Фабрики объектов Telegram ---

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


# ---------------------------------------------------------------------------
# /start
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_start_sends_greeting():
    """Бот отвечает на /start приветственным сообщением."""
    from bot import start

    update = make_update()
    context = make_context()

    await start(update, context)

    context.bot.send_message.assert_called_once()
    args, kwargs = context.bot.send_message.call_args
    assert "привет" in kwargs.get("text", "").lower() or "привет" in (args[1] if len(args) > 1 else "").lower()


# ---------------------------------------------------------------------------
# /add — добавление книги (ConversationHandler)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_add_book_starts_conversation():
    """/add запрашивает название книги."""
    from bot import addBook

    update = make_update()
    context = make_context()

    result = await addBook(update, context)

    update.message.reply_text.assert_called_once()
    call_text = update.message.reply_text.call_args[0][0]
    assert "название" in call_text.lower()


@pytest.mark.asyncio
async def test_add_book_title_saves_to_user_data():
    """После ввода названия оно сохраняется в context.user_data['title']."""
    from bot import addBook_title

    update = make_update(text="Дюна")
    context = make_context()

    await addBook_title(update, context)

    assert context.user_data["title"] == "Дюна"


@pytest.mark.asyncio
async def test_add_book_title_asks_for_author():
    """После ввода названия бот спрашивает автора."""
    from bot import addBook_title

    update = make_update(text="Пикник на обочине")
    context = make_context()

    await addBook_title(update, context)

    update.message.reply_text.assert_called_once()
    call_text = update.message.reply_text.call_args[0][0]
    assert "автор" in call_text.lower()


@pytest.mark.asyncio
async def test_add_book_author_known_confirms():
    """
    Если автор есть в базе — книга добавляется, бот подтверждает.
    МОКИРУЕМ: author_name_exists возвращает True (из fixtures).
    """
    from bot import addBook_author

    update = make_update(text="Аркадий и Борис Стругацкие")
    context = make_context(user_data={"title": "Улитка на склоне"})

    with patch("bot.author_name_exists", return_value=True):
        await addBook_author(update, context)

    update.message.reply_text.assert_called_once()
    call_text = update.message.reply_text.call_args[0][0]
    assert "улитка на склоне" in call_text.lower()


@pytest.mark.asyncio
async def test_add_book_author_unknown_warns():
    """
    Если автор НЕ найден в базе — бот предупреждает, но не блокирует добавление.
    МОКИРУЕМ: author_name_exists возвращает False.
    """
    from bot import addBook_author

    update = make_update(text="Несуществующий Автор")
    context = make_context(user_data={"title": "Неизвестная книга"})

    with patch("bot.author_name_exists", return_value=False):
        await addBook_author(update, context)

    update.message.reply_text.assert_called_once()
    call_text = update.message.reply_text.call_args[0][0]
    # Бот должен как-то отреагировать на незнакомого автора
    assert call_text  # не пустой ответ


# ---------------------------------------------------------------------------
# /remove — удаление книги
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_remove_book_confirms_removal():
    """
    /remove с названием существующей книги — бот подтверждает удаление.
    МОКИРУЕМ: get_book_by_title возвращает книгу из fixtures.
    """
    from bot import removeBook

    existing_book = get_books_by_status("to_read")[0]  # "Пикник на обочине"
    update = make_update(text=existing_book["title"])
    context = make_context()

    with patch("bot.get_book_by_title", return_value=existing_book):
        await removeBook(update, context)

    update.message.reply_text.assert_called_once()


@pytest.mark.asyncio
async def test_remove_book_not_found():
    """
    /remove с несуществующим названием — бот сообщает, что книга не найдена.
    МОКИРУЕМ: get_book_by_title возвращает None.
    """
    from bot import removeBook

    update = make_update(text="Нет такой книги")
    context = make_context()

    with patch("bot.get_book_by_title", return_value=None):
        await removeBook(update, context)

    update.message.reply_text.assert_called_once()
    call_text = update.message.reply_text.call_args[0][0]
    assert call_text  # бот что-то ответил


# ---------------------------------------------------------------------------
# /create_poll — создание опроса
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_poll_uses_to_read_books():
    """
    /create_poll отправляет poll с книгами со статусом to_read.
    МОКИРУЕМ: get_books_by_status возвращает список из fixtures.
    """
    from bot import createPoll

    to_read = get_books_by_status("to_read")  # 5 книг из fixtures
    update = make_update()
    update.effective_chat.id = -100123456
    update.effective_chat.title = "Книжный клуб"
    context = make_context()

    with patch("bot.get_books_by_status", return_value=to_read):
        await createPoll(update, context)

    context.bot.send_poll.assert_called_once()
    _, kwargs = context.bot.send_poll.call_args
    assert len(kwargs["options"]) == len(to_read)


@pytest.mark.asyncio
async def test_create_poll_no_books():
    """
    Если книг to_read нет — бот сообщает об этом вместо создания пустого опроса.
    МОКИРУЕМ: get_books_by_status возвращает [].
    """
    from bot import createPoll

    update = make_update()
    update.effective_chat.id = -100123456
    update.effective_chat.title = "Книжный клуб"
    context = make_context()

    with patch("bot.get_books_by_status", return_value=[]):
        await createPoll(update, context)

    context.bot.send_poll.assert_not_called()
    context.bot.send_message.assert_called_once()
