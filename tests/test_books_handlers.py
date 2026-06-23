import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def make_update(user_id: int = 123, args: list[str] | None = None):
    user = MagicMock()
    user.id = user_id
    user.first_name = 'Тест'
    user.username = 'testuser'
    user.full_name = 'Тест Юзер'

    message = MagicMock()
    message.reply_text = AsyncMock()

    update = MagicMock()
    update.effective_user = user
    update.message = message
    return update


def make_context(args: list[str] | None = None):
    ctx = MagicMock()
    ctx.args = args or []
    return ctx


# ─── removeBook ──────────────────────────────────────────────────────────────

class TestRemoveBook:
    @pytest.mark.asyncio
    async def test_no_args_shows_help(self):
        from handlers.books import removeBook
        update = make_update()
        await removeBook(update, make_context([]))
        update.message.reply_text.assert_called_once()
        text = update.message.reply_text.call_args[0][0]
        assert '/remove' in text
        assert 'название' in text

    @pytest.mark.asyncio
    async def test_match_found_shows_inline_keyboard(self):
        from handlers.books import removeBook
        matches = [{'id': 1, 'title': 'Дюна', 'author_name':'Фрэнк Герберт'}]
        with patch('handlers.books.api_client.search_books_to_remove', return_value=matches):
            update = make_update()
            await removeBook(update, make_context(['Дюна']))
        update.message.reply_text.assert_called_once()
        _, kwargs = update.message.reply_text.call_args
        markup = kwargs['reply_markup']
        buttons = [btn for row in markup.inline_keyboard for btn in row]
        labels = [b.text for b in buttons]
        assert any('Дюна' in l for l in labels)
        assert any('Отмена' in l for l in labels)

    @pytest.mark.asyncio
    async def test_multiple_matches_show_all_as_buttons(self):
        from handlers.books import removeBook
        matches = [
            {'id': 1, 'title': 'Дюна', 'author_name':'Фрэнк Герберт'},
            {'id': 2, 'title': 'Дюна Мессия', 'author_name':'Фрэнк Герберт'},
        ]
        with patch('handlers.books.api_client.search_books_to_remove', return_value=matches):
            update = make_update()
            await removeBook(update, make_context(['Дюна']))
        _, kwargs = update.message.reply_text.call_args
        book_buttons = [
            btn
            for row in kwargs['reply_markup'].inline_keyboard
            for btn in row
            if 'Отмена' not in btn.text
        ]
        assert len(book_buttons) == 2

    @pytest.mark.asyncio
    async def test_no_match_without_user_books(self):
        from handlers.books import removeBook
        with patch('handlers.books.api_client.search_books_to_remove', return_value=[]), \
             patch('handlers.books.api_client.get_member_books', return_value=[]):
            update = make_update()
            await removeBook(update, make_context(['Гарри Поттер']))
        text = update.message.reply_text.call_args[0][0]
        assert 'нет такой книги' in text

    @pytest.mark.asyncio
    async def test_no_match_shows_user_books(self):
        from handlers.books import removeBook
        my_books = [
            {'id': 5, 'title': 'Мастер и Маргарита', 'author_name':'Булгаков'},
            {'id': 6, 'title': 'Процесс', 'author_name':'Кафка'},
        ]
        with patch('handlers.books.api_client.search_books_to_remove', return_value=[]), \
             patch('handlers.books.api_client.get_member_books', return_value=my_books):
            update = make_update()
            await removeBook(update, make_context(['Гарри Поттер']))
        text = update.message.reply_text.call_args[0][0]
        assert 'Мастер и Маргарита' in text
        assert 'Процесс' in text

    @pytest.mark.asyncio
    async def test_api_error_shows_error_message(self):
        from handlers.books import removeBook
        with patch('handlers.books.api_client.search_books_to_remove', side_effect=Exception('timeout')):
            update = make_update()
            await removeBook(update, make_context(['Дюна']))
        text = update.message.reply_text.call_args[0][0]
        assert 'Не удалось' in text


# ─── myBooks ─────────────────────────────────────────────────────────────────

class TestMyBooks:
    @pytest.mark.asyncio
    async def test_no_books_shows_empty_message(self):
        from handlers.books import myBooks
        with patch('handlers.books.api_client.get_member_books', return_value=[]):
            update = make_update()
            await myBooks(update, make_context())
        text = update.message.reply_text.call_args[0][0]
        assert 'ничего нет' in text
        assert '/add' in text

    @pytest.mark.asyncio
    async def test_one_book_shows_singular_message(self):
        from handlers.books import myBooks
        books = [{'id': 1, 'title': 'Дюна', 'author_name':'Фрэнк Герберт'}]
        with patch('handlers.books.api_client.get_member_books', return_value=books):
            update = make_update()
            await myBooks(update, make_context())
        text = update.message.reply_text.call_args[0][0]
        assert 'только одна книга' in text
        assert 'Дюна' in text
        assert '/add' in text

    @pytest.mark.asyncio
    async def test_one_book_without_author(self):
        from handlers.books import myBooks
        books = [{'id': 1, 'title': 'Дюна', 'author_name':None}]
        with patch('handlers.books.api_client.get_member_books', return_value=books):
            update = make_update()
            await myBooks(update, make_context())
        text = update.message.reply_text.call_args[0][0]
        assert '«Дюна»' in text

    @pytest.mark.asyncio
    async def test_multiple_books_shows_list(self):
        from handlers.books import myBooks
        books = [
            {'id': 1, 'title': 'Дюна', 'author_name':'Фрэнк Герберт'},
            {'id': 2, 'title': 'Мастер и Маргарита', 'author_name':'Булгаков'},
        ]
        with patch('handlers.books.api_client.get_member_books', return_value=books):
            update = make_update()
            await myBooks(update, make_context())
        text = update.message.reply_text.call_args[0][0]
        assert 'Дюна' in text
        assert 'Мастер и Маргарита' in text
        assert '/add' in text

    @pytest.mark.asyncio
    async def test_api_error_shows_error_message(self):
        from handlers.books import myBooks
        with patch('handlers.books.api_client.get_member_books', side_effect=Exception('timeout')):
            update = make_update()
            await myBooks(update, make_context())
        text = update.message.reply_text.call_args[0][0]
        assert 'Не удалось' in text
