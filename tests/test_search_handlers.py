import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from handlers.search import searchBooks, format_book, format_results, MAX_RESULTS


def make_update():
    update = MagicMock()
    update.message.reply_text = AsyncMock()
    return update


def make_context(args):
    ctx = MagicMock()
    ctx.args = args
    return ctx


BOOK = {
    'id': 1, 'title': 'Бойцовский клуб', 'author_name': 'Чак Паланик', 'status': 'read',
    'added_at': '2024-01-12', 'elected_at': '2024-03-05',
    'discussion_url': 'https://t.me/c/1/2',
    'added_by_fullname': 'Даша Гросс', 'added_by_username': 'dasha',
}


class TestFormatBook:
    def test_read_book_full_details(self):
        text = format_book(BOOK)
        assert '«Бойцовский клуб», Чак Паланик' in text
        assert 'прочитали в марте 2024' in text
        assert '<a href="https://t.me/c/1/2">запись заседания</a>' in text
        assert 'Инициатива: Даша Гросс, 12.01.2024' in text

    def test_username_without_at_when_no_fullname(self):
        text = format_book({**BOOK, 'added_by_fullname': None})
        assert 'Инициатива: dasha,' in text
        assert '@' not in text

    def test_queued_and_removed_statuses(self):
        assert 'в очереди' in format_book({**BOOK, 'status': 'to_read'})
        assert 'убрали из списка' in format_book({**BOOK, 'status': 'removed'})

    def test_missing_optional_fields(self):
        text = format_book({'title': 'X', 'author_name': None, 'status': 'read',
                            'added_at': None, 'elected_at': None, 'discussion_url': None,
                            'added_by_fullname': None, 'added_by_username': None})
        assert text == '«X»\n✅ прочитали'

    def test_html_escaped(self):
        assert '«A &lt;b&gt;»' in format_book({**BOOK, 'title': 'A <b>'})


class TestFormatResults:
    def test_intro(self):
        assert format_results([BOOK]).startswith('Вот что я нашёл по запросу:')

    def test_truncates_with_remainder(self):
        text = format_results([BOOK] * (MAX_RESULTS + 3))
        assert text.count('Бойцовский клуб') == MAX_RESULTS
        assert 'и ещё 3' in text


class TestSearchBooks:
    @pytest.mark.asyncio
    async def test_no_args_shows_help(self):
        update = make_update()
        await searchBooks(update, make_context([]))
        assert '/search паланик' in update.message.reply_text.call_args[0][0]

    @pytest.mark.asyncio
    async def test_not_found(self):
        update = make_update()
        with patch('handlers.search.api_client.lookup_books', AsyncMock(return_value=[])):
            await searchBooks(update, make_context(['толстой']))
        assert 'Ничего не нашёл' in update.message.reply_text.call_args[0][0]

    @pytest.mark.asyncio
    async def test_found_sends_html(self):
        update = make_update()
        lookup = AsyncMock(return_value=[BOOK])
        with patch('handlers.search.api_client.lookup_books', lookup):
            await searchBooks(update, make_context(['чак', 'паланик']))
        lookup.assert_called_once_with('чак паланик')
        args, kwargs = update.message.reply_text.call_args
        assert 'Бойцовский клуб' in args[0]
        assert kwargs['parse_mode'] == 'HTML'

    @pytest.mark.asyncio
    async def test_api_error(self):
        update = make_update()
        with patch('handlers.search.api_client.lookup_books', AsyncMock(side_effect=Exception)):
            await searchBooks(update, make_context(['x']))
        assert 'Не удалось' in update.message.reply_text.call_args[0][0]
