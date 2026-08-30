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

        with patch('handlers.books.api_client.save_cover_bytes'):
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
