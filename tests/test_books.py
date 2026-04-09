import pytest
from unittest.mock import patch

from tests.conftest import make_update, make_context
from tests.fixtures import get_books_by_status


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
# /add — добавление книги
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_add_book_starts_conversation():
    """/add запрашивает название книги."""
    from handlers.books import addBook

    update = make_update()
    context = make_context()

    await addBook(update, context)

    update.message.reply_text.assert_called_once()
    call_text = update.message.reply_text.call_args[0][0]
    assert "название" in call_text.lower()


@pytest.mark.asyncio
async def test_add_book_title_saves_to_user_data():
    """После ввода названия оно сохраняется в context.user_data['title']."""
    from handlers.books import addBook_title

    update = make_update(text="Дюна")
    context = make_context()

    await addBook_title(update, context)

    assert context.user_data["title"] == "Дюна"


@pytest.mark.asyncio
async def test_add_book_title_asks_for_author():
    """После ввода названия бот спрашивает автора."""
    from handlers.books import addBook_title

    update = make_update(text="Пикник на обочине")
    context = make_context()

    await addBook_title(update, context)

    call_text = update.message.reply_text.call_args[0][0]
    assert "автор" in call_text.lower()


@pytest.mark.asyncio
async def test_add_book_author_known_confirms():
    """Если автор есть в базе — бот подтверждает добавление."""
    from handlers.books import addBook_author

    update = make_update(text="Аркадий и Борис Стругацкие")
    context = make_context(user_data={"title": "Улитка на склоне"})

    with patch("handlers.books.author_name_exists", return_value=True):
        await addBook_author(update, context)

    call_text = update.message.reply_text.call_args[0][0]
    assert "улитка на склоне" in call_text.lower()


@pytest.mark.asyncio
async def test_add_book_author_unknown_warns():
    """Если автор не найден — бот предупреждает, но не блокирует."""
    from handlers.books import addBook_author

    update = make_update(text="Несуществующий Автор")
    context = make_context(user_data={"title": "Неизвестная книга"})

    with patch("handlers.books.author_name_exists", return_value=False):
        await addBook_author(update, context)

    call_text = update.message.reply_text.call_args[0][0]
    assert call_text


# ---------------------------------------------------------------------------
# /remove — удаление книги
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_remove_book_confirms_removal():
    """/remove с существующей книгой — бот подтверждает удаление."""
    from handlers.books import removeBook

    existing_book = get_books_by_status("to_read")[0]
    update = make_update(text=existing_book["title"])
    context = make_context()

    with patch("handlers.books.get_book_by_title", return_value=existing_book):
        await removeBook(update, context)

    update.message.reply_text.assert_called_once()


@pytest.mark.asyncio
async def test_remove_book_not_found():
    """/remove с несуществующей книгой — бот сообщает, что не нашёл."""
    from handlers.books import removeBook

    update = make_update(text="Нет такой книги")
    context = make_context()

    with patch("handlers.books.get_book_by_title", return_value=None):
        await removeBook(update, context)

    call_text = update.message.reply_text.call_args[0][0]
    assert call_text
