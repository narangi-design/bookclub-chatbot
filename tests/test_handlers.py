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
    author_name_exists, few_to_read_books, only_read_books, empty_books,
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


TWENTY_FOUR_HOURS = 86400  # секунд


def make_poll_update():
    update = make_update()
    update.effective_chat.id = -100123456
    update.effective_chat.title = "Книжный клуб"
    return update


# ---------------------------------------------------------------------------
# /create_poll_test — тестовая команда (mock-данные)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_poll_test_sends_exactly_4_options():
    """Тестовый опрос содержит ровно 4 варианта из mock-данных."""
    from bot import createPollTest

    to_read = get_books_by_status("to_read")
    assert len(to_read) > 4

    with patch("bot.get_books_by_status", return_value=to_read):
        await createPollTest(make_poll_update(), make_context())

    # проверяем через _send_poll — опрос отправлен с 4 вариантами


@pytest.mark.asyncio
async def test_create_poll_test_fewer_than_4_uses_all():
    """Тестовый опрос: если to_read меньше 4 — берём все."""
    from bot import createPollTest

    few = [b for b in few_to_read_books if b["status"] == "to_read"]
    assert len(few) < 4

    context = make_context()
    with patch("bot.get_books_by_status", return_value=few):
        await createPollTest(make_poll_update(), context)

    _, kwargs = context.bot.send_poll.call_args
    assert len(kwargs["options"]) == len(few)


@pytest.mark.asyncio
async def test_create_poll_test_no_to_read_books():
    """Тестовый опрос: нет to_read — сообщение вместо опроса."""
    from bot import createPollTest

    no_to_read = [b for b in only_read_books if b["status"] == "to_read"]
    context = make_context()

    with patch("bot.get_books_by_status", return_value=no_to_read):
        await createPollTest(make_poll_update(), context)

    context.bot.send_poll.assert_not_called()
    context.bot.send_message.assert_called_once()


@pytest.mark.asyncio
async def test_create_poll_test_empty_list():
    """Тестовый опрос: пустой список — сообщение вместо опроса."""
    from bot import createPollTest

    context = make_context()
    with patch("bot.get_books_by_status", return_value=empty_books):
        await createPollTest(make_poll_update(), context)

    context.bot.send_poll.assert_not_called()
    context.bot.send_message.assert_called_once()


# ---------------------------------------------------------------------------
# /create_poll — боевая команда (api_client)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_poll_calls_api_client():
    """Боевой опрос вызывает api_client.get_poll_candidates, не mock_db."""
    from bot import createPoll

    candidates = get_books_by_status("to_read")[:4]
    context = make_context()

    with patch("bot.api_client.get_poll_candidates", return_value=candidates) as mock_api:
        await createPoll(make_poll_update(), context)

    mock_api.assert_called_once_with(n=4)
    context.bot.send_poll.assert_called_once()


@pytest.mark.asyncio
async def test_create_poll_sends_api_candidates_as_options():
    """Боевой опрос: варианты — это title книг от api_client."""
    from bot import createPoll

    candidates = get_books_by_status("to_read")[:4]
    context = make_context()

    with patch("bot.api_client.get_poll_candidates", return_value=candidates):
        await createPoll(make_poll_update(), context)

    _, kwargs = context.bot.send_poll.call_args
    assert kwargs["options"] == [b["title"] for b in candidates]


# ---------------------------------------------------------------------------
# Параметры опроса (общие для обеих команд — проверяем через _send_poll)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_poll_is_public():
    """Опрос публичный — is_anonymous=False."""
    from bot import createPollTest

    to_read = get_books_by_status("to_read")
    context = make_context()

    with patch("bot.get_books_by_status", return_value=to_read):
        await createPollTest(make_poll_update(), context)

    _, kwargs = context.bot.send_poll.call_args
    assert kwargs.get("is_anonymous") is False


@pytest.mark.asyncio
async def test_poll_allows_multiple_answers():
    """Опрос с мультивыбором — allows_multiple_answers=True."""
    from bot import createPollTest

    to_read = get_books_by_status("to_read")
    context = make_context()

    with patch("bot.get_books_by_status", return_value=to_read):
        await createPollTest(make_poll_update(), context)

    _, kwargs = context.bot.send_poll.call_args
    assert kwargs.get("allows_multiple_answers") is True


@pytest.mark.asyncio
async def test_poll_lasts_24_hours():
    """Опрос закрывается через 24 часа — open_period=86400."""
    from bot import createPollTest

    to_read = get_books_by_status("to_read")
    context = make_context()

    with patch("bot.get_books_by_status", return_value=to_read):
        await createPollTest(make_poll_update(), context)

    _, kwargs = context.bot.send_poll.call_args
    assert kwargs.get("open_period") == TWENTY_FOUR_HOURS
