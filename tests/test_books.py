import pytest
from unittest.mock import patch

from tests.conftest import make_update, make_context


def make_add_update(first_name='Алёна'):
    update = make_update()
    update.effective_user.first_name = first_name
    update.effective_user.username = 'alyona_reads'
    return update


def make_add_context(text: str):
    context = make_context()
    context.args = text.split() if text else []
    return context

@pytest.mark.asyncio
async def test_start_sends_greeting():
    from bot import start

    update = make_update()
    context = make_context()
    await start(update, context)

    context.bot.send_message.assert_called_once()
    _, kwargs = context.bot.send_message.call_args
    assert 'привет' in kwargs.get('text', '').lower()

@pytest.mark.asyncio
async def test_add_no_args_shows_help():
    """/add без аргументов показывает подсказку."""
    from handlers.books import addBook, HELP_TEXT

    update = make_add_update()
    await addBook(update, make_add_context(''))

    update.message.reply_text.assert_called_once_with(HELP_TEXT)


@pytest.mark.asyncio
@pytest.mark.parametrize('text', [
    'Просто текст без разделителя',
    'Слово-с-дефисом-в-одном-месте',
    'Автор',
])
async def test_add_invalid_format_shows_help(text):
    """Текст без разделителя показывает подсказку."""
    from handlers.books import addBook, HELP_TEXT

    update = make_add_update()
    await addBook(update, make_add_context(text))

    update.message.reply_text.assert_called_once_with(HELP_TEXT)

@pytest.mark.asyncio
@pytest.mark.parametrize('text,expected_author,expected_title', [
    ('Михаил Булгаков — Мастер и Маргарита',       'Михаил Булгаков',               'Мастер и Маргарита'),
    ('Михаил Булгаков – Мастер и Маргарита',        'Михаил Булгаков',               'Мастер и Маргарита'),
    ('Михаил Булгаков - Мастер и Маргарита',        'Михаил Булгаков',               'Мастер и Маргарита'),
    ('Аркадий и Борис Стругацкие — Пикник на обочине', 'Аркадий и Борис Стругацкие', 'Пикник на обочине'),
    ('Булгаков Михаил — Мастер и Маргарита',        'Булгаков Михаил',               'Мастер и Маргарита'),
])
async def test_add_valid_format_calls_api(text, expected_author, expected_title):
    """Верный формат вызывает api_client.add_book с правильными аргументами."""
    from handlers.books import addBook

    update = make_add_update()
    with patch('handlers.books.api_client.add_book') as mock_add:
        await addBook(update, make_add_context(text))

    mock_add.assert_called_once_with(
        title=expected_title,
        author_name=expected_author,
        telegram_id=update.effective_user.id,
    )

@pytest.mark.asyncio
async def test_add_success_message_contains_user_name():
    """Сообщение об успехе содержит имя пользователя."""
    from handlers.books import addBook

    update = make_add_update(first_name='Алёна')
    with patch('handlers.books.api_client.add_book'):
        await addBook(update, make_add_context('Михаил Булгаков — Мастер и Маргарита'))

    text = update.message.reply_text.call_args[0][0]
    assert 'Алёна' in text


@pytest.mark.asyncio
async def test_add_success_message_contains_title_and_author():
    """Сообщение об успехе содержит название и автора."""
    from handlers.books import addBook

    update = make_add_update()
    with patch('handlers.books.api_client.add_book'):
        await addBook(update, make_add_context('Михаил Булгаков — Мастер и Маргарита'))

    text = update.message.reply_text.call_args[0][0]
    assert 'Мастер и Маргарита' in text
    assert 'Михаил Булгаков' in text


@pytest.mark.asyncio
async def test_add_api_error_shows_error_message():
    """Ошибка API показывает сообщение об ошибке."""
    from handlers.books import addBook

    update = make_add_update()
    with patch('handlers.books.api_client.add_book', side_effect=Exception('API error')):
        await addBook(update, make_add_context('Михаил Булгаков — Мастер и Маргарита'))

    text = update.message.reply_text.call_args[0][0]
    assert 'не удалось' in text.lower()


# ---------------------------------------------------------------------------
# /add — дубликат книги
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_add_duplicate_book_shows_existing_title():
    """Если книга уже есть в базе — бот сообщает об этом с точным названием из БД."""
    from handlers.books import addBook

    update = make_add_update()
    with patch('handlers.books.api_client.add_book', return_value={'exists': True, 'existing_title': 'Мастер и Маргарита'}):
        await addBook(update, make_add_context('Михаил Булгаков — Мастер и Маргарита'))

    text = update.message.reply_text.call_args[0][0]
    assert 'Мастер и Маргарита' in text


@pytest.mark.asyncio
async def test_add_duplicate_book_does_not_send_success():
    """При дубликате не должно быть сообщения об успешном добавлении."""
    from handlers.books import addBook

    update = make_add_update()
    with patch('handlers.books.api_client.add_book', return_value={'exists': True, 'existing_title': 'Мастер и Маргарита'}):
        await addBook(update, make_add_context('Михаил Булгаков — Мастер и Маргарита'))

    text = update.message.reply_text.call_args[0][0]
    assert 'в списке, ' not in text  # нет приветствия из success-сообщения


@pytest.mark.asyncio
async def test_remove_no_args_shows_hint():
    """/remove без аргументов показывает подсказку."""
    from handlers.books import removeBook

    update = make_update()
    context = make_add_context('')
    await removeBook(update, context)

    text = update.message.reply_text.call_args[0][0]
    assert '/remove' in text


@pytest.mark.asyncio
async def test_remove_found_confirms():
    """/remove с существующей книгой подтверждает удаление."""
    from handlers.books import removeBook

    update = make_update()
    with patch('handlers.books.api_client.remove_book', return_value=True):
        await removeBook(update, make_add_context('Мастер и Маргарита'))

    text = update.message.reply_text.call_args[0][0]
    assert 'удален' in text.lower()


@pytest.mark.asyncio
async def test_remove_not_found_notifies():
    """/remove с несуществующей книгой сообщает, что не нашлось."""
    from handlers.books import removeBook

    update = make_update()
    with patch('handlers.books.api_client.remove_book', return_value=False):
        await removeBook(update, make_add_context('Нет такой книги'))

    text = update.message.reply_text.call_args[0][0]
    assert 'не найден' in text.lower()


@pytest.mark.asyncio
async def test_remove_api_error_shows_error_message():
    """Ошибка API при удалении показывает сообщение об ошибке."""
    from handlers.books import removeBook

    update = make_update()
    with patch('handlers.books.api_client.remove_book', side_effect=Exception('API error')):
        await removeBook(update, make_add_context('Мастер и Маргарита'))

    text = update.message.reply_text.call_args[0][0]
    assert 'не удалось' in text.lower()
