import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ─── helpers ─────────────────────────────────────────────────────────────────

def make_query(message_id: int = 42, bot_data: dict | None = None):
    message = MagicMock()
    message.message_id = message_id
    query = MagicMock()
    query.message = message
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    update = MagicMock()
    update.callback_query = query
    ctx = MagicMock()
    ctx.bot_data = bot_data if bot_data is not None else {}
    return update, ctx


def make_photo_update(reply_message_id: int | None = None, has_photo: bool = True):
    photo = MagicMock()
    photo.get_file = AsyncMock()
    file = MagicMock()
    file.download_as_bytearray = AsyncMock(return_value=bytearray(b'fake-image'))
    photo.get_file.return_value = file

    reply = MagicMock()
    reply.message_id = reply_message_id

    message = MagicMock()
    message.photo = [photo] if has_photo else []
    message.reply_to_message = reply if reply_message_id is not None else None
    message.reply_text = AsyncMock()

    update = MagicMock()
    update.message = message
    ctx = MagicMock()
    ctx.bot_data = {}
    return update, ctx


# ─── _title_from_label ────────────────────────────────────────────────────────

class TestTitleFromLabel:
    def test_extracts_title_with_author(self):
        from handlers.books import _title_from_label
        assert _title_from_label('«Дюна», Фрэнк Герберт') == '«Дюна»'

    def test_extracts_title_without_author(self):
        from handlers.books import _title_from_label
        assert _title_from_label('«Мастер и Маргарита»') == '«Мастер и Маргарита»'

    def test_fallback_when_no_brackets(self):
        from handlers.books import _title_from_label
        assert _title_from_label('#42') == '#42'


# ─── coverCallback ─────────────────────────────────────────────────────────────

def make_cover_query(callback_data: str):
    message = MagicMock()
    message.reply_markup = None
    query = MagicMock()
    query.data = callback_data
    query.message = message
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    update = MagicMock()
    update.callback_query = query
    ctx = MagicMock()
    ctx.user_data = {}
    return update, ctx


class TestCoverCallback:
    @pytest.mark.asyncio
    async def test_success_uses_title_from_api_response(self):
        from handlers.books import coverCallback, COVER_GOOGLE
        update, ctx = make_cover_query(f'{COVER_GOOGLE}:7:abc123')
        with patch('handlers.books.api_client.save_cover_url', return_value={'ok': True, 'title': 'Анна Каренина'}):
            await coverCallback(update, ctx)
        text = update.callback_query.edit_message_text.call_args[0][0]
        assert '«Анна Каренина»' in text

    @pytest.mark.asyncio
    async def test_success_ignores_stale_user_data(self):
        # Regression test: the confirmation must name the book the callback_data
        # actually points at, not a title cached from an unrelated /add or /cover
        # flow for the same Telegram user.
        from handlers.books import coverCallback, COVER_GOOGLE
        update, ctx = make_cover_query(f'{COVER_GOOGLE}:7:abc123')
        ctx.user_data['cover_book_title'] = '«Война и мир»'
        with patch('handlers.books.api_client.save_cover_url', return_value={'ok': True, 'title': 'Анна Каренина'}):
            await coverCallback(update, ctx)
        text = update.callback_query.edit_message_text.call_args[0][0]
        assert '«Анна Каренина»' in text
        assert 'Война и мир' not in text

    @pytest.mark.asyncio
    async def test_api_error_falls_back_to_book_id(self):
        from handlers.books import coverCallback, COVER_GOOGLE
        update, ctx = make_cover_query(f'{COVER_GOOGLE}:7:abc123')
        with patch('handlers.books.api_client.save_cover_url', side_effect=Exception('boom')):
            await coverCallback(update, ctx)
        text = update.callback_query.edit_message_text.call_args[0][0]
        assert '#7' in text
        assert 'Не удалось' in text


# ─── pickCoverCallback ───────────────────────────────────────────────────────

class TestPickCoverCallback:
    @pytest.mark.asyncio
    async def test_not_found_uses_title_from_keyboard_label(self):
        from handlers.books import pickCoverCallback, PICK_COVER

        button = MagicMock()
        button.callback_data = f'{PICK_COVER}:7'
        button.text = '«Анна Каренина», Лев Толстой'
        markup = MagicMock()
        markup.inline_keyboard = [[button]]

        message = MagicMock()
        message.reply_markup = markup
        message.reply_text = AsyncMock(return_value=MagicMock(message_id=55))

        query = MagicMock()
        query.data = f'{PICK_COVER}:7'
        query.message = message
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()

        update = MagicMock()
        update.callback_query = query
        ctx = MagicMock()
        ctx.bot_data = {}
        ctx.user_data = {}

        with patch('handlers.books.api_client.get_book_covers', return_value=[]):
            await pickCoverCallback(update, ctx)

        text = message.reply_text.call_args[0][0]
        assert '«Анна Каренина»' in text
        assert ctx.bot_data['pending_cover_55']['book_title'] == '«Анна Каренина»'


# ─── cancelCoverUploadCallback ────────────────────────────────────────────────

class TestCancelCoverUploadCallback:
    @pytest.mark.asyncio
    async def test_removes_pending_and_mentions_book(self):
        from handlers.books import cancelCoverUploadCallback
        bot_data = {
            'pending_cover_42': {'book_id': 1, 'book_title': '«Дюна»'},
        }
        update, ctx = make_query(message_id=42, bot_data=bot_data)
        await cancelCoverUploadCallback(update, ctx)
        assert 'pending_cover_42' not in ctx.bot_data
        text = update.callback_query.edit_message_text.call_args[0][0]
        assert '«Дюна»' in text

    @pytest.mark.asyncio
    async def test_no_pending_uses_fallback(self):
        from handlers.books import cancelCoverUploadCallback
        update, ctx = make_query(message_id=99, bot_data={})
        await cancelCoverUploadCallback(update, ctx)
        text = update.callback_query.edit_message_text.call_args[0][0]
        assert text  # что-то написал, не упал


# ─── uploadCoverPhoto ─────────────────────────────────────────────────────────

class TestUploadCoverPhoto:
    @pytest.mark.asyncio
    async def test_saves_cover_and_replies_with_title(self):
        from handlers.books import uploadCoverPhoto
        update, ctx = make_photo_update(reply_message_id=10)
        ctx.bot_data['pending_cover_10'] = {'book_id': 7, 'book_title': '«Пиранези»'}

        with patch('handlers.books.api_client.save_cover_bytes', return_value={'ok': True, 'title': 'Пиранези'}):
            await uploadCoverPhoto(update, ctx)

        text = update.message.reply_text.call_args[0][0]
        assert '«Пиранези»' in text
        assert 'обложкой' in text
        assert 'pending_cover_10' not in ctx.bot_data

    @pytest.mark.asyncio
    async def test_ignores_message_without_reply(self):
        from handlers.books import uploadCoverPhoto
        update, ctx = make_photo_update(reply_message_id=None)
        await uploadCoverPhoto(update, ctx)
        update.message.reply_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_ignores_reply_to_non_pending_message(self):
        from handlers.books import uploadCoverPhoto
        update, ctx = make_photo_update(reply_message_id=999)
        ctx.bot_data = {}
        await uploadCoverPhoto(update, ctx)
        update.message.reply_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_api_error_replies_with_error_and_book_title(self):
        from handlers.books import uploadCoverPhoto
        update, ctx = make_photo_update(reply_message_id=10)
        ctx.bot_data['pending_cover_10'] = {'book_id': 7, 'book_title': '«Пиранези»'}

        with patch('handlers.books.api_client.save_cover_bytes', side_effect=Exception('timeout')):
            await uploadCoverPhoto(update, ctx)

        text = update.message.reply_text.call_args[0][0]
        assert 'Не удалось' in text
        assert '«Пиранези»' in text
