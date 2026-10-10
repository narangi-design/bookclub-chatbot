import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import handlers.recommendations as rec

CHAT_ID = -1001234


def make_user(uid, username='u', full_name='Имя Фамилия', is_bot=False):
    user = MagicMock()
    user.id = uid
    user.username = username
    user.full_name = full_name
    user.is_bot = is_bot
    return user


def make_update(reply=True, text='Посмотрите «Сталкер»', caption=None, author=None):
    update = MagicMock()
    update.effective_chat.id = CHAT_ID
    update.effective_user = make_user(1, 'saver', 'Сохраняющий')
    update.message.reply_text = AsyncMock()
    update.message.set_reaction = AsyncMock()
    if not reply:
        update.message.reply_to_message = None
        return update
    target = MagicMock()
    target.message_id = 42
    target.text = text
    target.caption = caption
    target.entities = ()
    target.caption_entities = ()
    target.from_user = author or make_user(2, 'author', 'Автор Сообщения')
    target.date = datetime(2025, 5, 1, 12, 0, tzinfo=timezone.utc)
    target.set_reaction = AsyncMock()
    update.message.reply_to_message = target
    return update


@pytest.fixture(autouse=True)
def club_chat(monkeypatch):
    monkeypatch.setattr(rec, '_TELEGRAM_CHAT_ID', str(CHAT_ID))


class TestAddRecommendation:
    @pytest.mark.asyncio
    async def test_other_chat_rejected(self):
        update = make_update()
        update.effective_chat.id = 999
        add = AsyncMock()
        with patch('handlers.recommendations.api_client.add_recommendation', add):
            await rec.addRecommendation(update, MagicMock())
        add.assert_not_called()
        assert 'только из чата клуба' in update.message.reply_text.call_args[0][0]

    @pytest.mark.asyncio
    async def test_no_reply_shows_help(self):
        update = make_update(reply=False)
        await rec.addRecommendation(update, MagicMock())
        assert '/recommend' in update.message.reply_text.call_args[0][0]

    @pytest.mark.asyncio
    async def test_no_text_rejected(self):
        update = make_update(text=None, caption=None)
        await rec.addRecommendation(update, MagicMock())
        assert 'нет текста' in update.message.reply_text.call_args[0][0]

    @pytest.mark.asyncio
    async def test_bot_author_rejected(self):
        update = make_update(author=make_user(3, is_bot=True))
        await rec.addRecommendation(update, MagicMock())
        assert 'ботов' in update.message.reply_text.call_args[0][0]

    @pytest.mark.asyncio
    async def test_saves_with_original_author_and_date_then_reacts(self):
        update = make_update()
        add = AsyncMock(return_value=True)
        with patch('handlers.recommendations.api_client.add_recommendation', add):
            await rec.addRecommendation(update, MagicMock())
        kwargs = add.call_args.kwargs
        assert kwargs['message_id'] == 42
        assert kwargs['text'] == 'Посмотрите «Сталкер»'
        assert kwargs['message_date'] == '2025-05-01T12:00:00+00:00'
        assert kwargs['author']['telegram_id'] == 2
        assert kwargs['saved_by']['telegram_id'] == 1
        assert update.message.reply_to_message.set_reaction.call_args[0][0].emoji == '✍'
        assert update.message.set_reaction.call_args[0][0].emoji == '👌'
        update.message.reply_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_caption_used_for_photo(self):
        update = make_update(text=None, caption='Подпись к фото')
        add = AsyncMock(return_value=True)
        with patch('handlers.recommendations.api_client.add_recommendation', add):
            await rec.addRecommendation(update, MagicMock())
        assert add.call_args.kwargs['text'] == 'Подпись к фото'

    @pytest.mark.asyncio
    async def test_duplicate(self):
        update = make_update()
        with patch('handlers.recommendations.api_client.add_recommendation', AsyncMock(return_value=False)):
            await rec.addRecommendation(update, MagicMock())
        assert 'уже в рекомендациях' in update.message.reply_text.call_args[0][0]
        update.message.reply_to_message.set_reaction.assert_not_called()

    @pytest.mark.asyncio
    async def test_reaction_failure_falls_back_to_text(self):
        update = make_update()
        update.message.reply_to_message.set_reaction.side_effect = Exception('REACTION_INVALID')
        with patch('handlers.recommendations.api_client.add_recommendation', AsyncMock(return_value=True)):
            await rec.addRecommendation(update, MagicMock())
        assert 'Сохранил' in update.message.reply_text.call_args[0][0]

    @pytest.mark.asyncio
    async def test_api_error(self):
        update = make_update()
        with patch('handlers.recommendations.api_client.add_recommendation', AsyncMock(side_effect=Exception)):
            await rec.addRecommendation(update, MagicMock())
        assert 'Не удалось' in update.message.reply_text.call_args[0][0]
