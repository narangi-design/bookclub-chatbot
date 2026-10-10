from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import make_context, make_poll_update

META = {'year': 2026, 'deadline': '2027-01-10T23:59:59+00:00', 'candidate_count': 12, 'is_closed': False}
META_CLOSED = {**META, 'is_closed': True}


# ---------------------------------------------------------------------------
# /survey_start
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_survey_start_announces_deadline_and_link():
    from handlers.survey import surveyStart
    update = make_poll_update()
    with patch('handlers.survey.api_client.get_survey_meta', return_value=META):
        await surveyStart(update, make_context())
    text = update.message.reply_text.call_args[0][0]
    assert '2026' in text
    assert '10.01.2027' in text
    assert '/survey' in text


@pytest.mark.asyncio
async def test_survey_start_api_error():
    from handlers.survey import surveyStart
    update = make_poll_update()
    with patch('handlers.survey.api_client.get_survey_meta', side_effect=Exception('timeout')):
        await surveyStart(update, make_context())
    text = update.message.reply_text.call_args[0][0]
    assert 'Не удалось' in text


# ---------------------------------------------------------------------------
# /finalize
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_finalize_api_error():
    from handlers.survey import finalizeSurvey
    update = make_poll_update()
    with patch('handlers.survey.api_client.finalize_survey', side_effect=Exception('timeout')):
        await finalizeSurvey(update, make_context())
    text = update.message.reply_text.call_args[0][0]
    assert 'Не удалось' in text


@pytest.mark.asyncio
async def test_finalize_no_ties_announces_results():
    from handlers.survey import finalizeSurvey
    update = make_poll_update()
    result = {'status': 'finalized', 'total_voters': 15, 'books_counted': 10, 'tiebreak_categories_opened': [], 'tiebreak_deadline': None}
    with patch('handlers.survey.api_client.finalize_survey', return_value=result):
        await finalizeSurvey(update, make_context())
    text = update.message.reply_text.call_args[0][0]
    assert 'подведены' in text
    assert '/survey/results' in text


@pytest.mark.asyncio
async def test_finalize_tie_invites_second_round():
    from handlers.survey import finalizeSurvey
    update = make_poll_update()
    result = {
        'status': 'finalized', 'total_voters': 15, 'books_counted': 10,
        'tiebreak_categories_opened': ['favorite'], 'tiebreak_deadline': '2027-01-12T23:59:59+00:00',
    }
    with patch('handlers.survey.api_client.finalize_survey', return_value=result):
        await finalizeSurvey(update, make_context())
    text = update.message.reply_text.call_args[0][0]
    assert 'Книга года' in text
    assert '12.01.2027' in text
    assert '/survey' in text
    assert '/survey/results' not in text


@pytest.mark.asyncio
async def test_finalize_already_closed_announces_results():
    # Someone ran /finalize a second time after it was already computed.
    from handlers.survey import finalizeSurvey
    update = make_poll_update()
    with patch('handlers.survey.api_client.finalize_survey', return_value={'status': 'already_closed'}):
        await finalizeSurvey(update, make_context())
    text = update.message.reply_text.call_args[0][0]
    assert 'подведены' in text
    assert '/survey/results' in text


@pytest.mark.asyncio
async def test_finalize_pending_tiebreaks_reinvites():
    # Called again while a tiebreak from an earlier /finalize is still open.
    from handlers.survey import finalizeSurvey
    update = make_poll_update()
    result = {'status': 'pending_tiebreaks', 'unresolved_categories': ['favorite']}
    tiebreaks = [
        {'category': 'favorite', 'deadline': '2027-01-12T23:59:59+00:00', 'candidate_book_ids': [4, 6], 'resolved': False},
    ]
    with patch('handlers.survey.api_client.finalize_survey', return_value=result), \
         patch('handlers.survey.api_client.get_survey_tiebreaks', return_value=tiebreaks):
        await finalizeSurvey(update, make_context())
    text = update.message.reply_text.call_args[0][0]
    assert 'Книга года' in text
    assert '12.01.2027' in text


@pytest.mark.asyncio
async def test_finalize_pending_tiebreaks_fetch_error():
    from handlers.survey import finalizeSurvey
    update = make_poll_update()
    result = {'status': 'pending_tiebreaks', 'unresolved_categories': ['favorite']}
    with patch('handlers.survey.api_client.finalize_survey', return_value=result), \
         patch('handlers.survey.api_client.get_survey_tiebreaks', side_effect=Exception('timeout')):
        await finalizeSurvey(update, make_context())
    text = update.message.reply_text.call_args[0][0]
    assert 'Не удалось' in text


# ---------------------------------------------------------------------------
# announceDeadlineWhenReached
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_announce_deadline_no_chat_id_configured():
    from handlers.survey import announceDeadlineWhenReached
    bot = MagicMock(send_message=AsyncMock())
    with patch('handlers.survey._TELEGRAM_CHAT_ID', ''):
        await announceDeadlineWhenReached(bot)
    bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_announce_deadline_already_closed_stays_quiet():
    # Process started after the deadline already passed — don't spam on restart.
    from handlers.survey import announceDeadlineWhenReached
    bot = MagicMock(send_message=AsyncMock())
    with patch('handlers.survey._TELEGRAM_CHAT_ID', '-100123'), \
         patch('handlers.survey.api_client.get_survey_meta', return_value=META_CLOSED):
        await announceDeadlineWhenReached(bot)
    bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_announce_deadline_meta_error_stays_quiet():
    from handlers.survey import announceDeadlineWhenReached
    bot = MagicMock(send_message=AsyncMock())
    with patch('handlers.survey._TELEGRAM_CHAT_ID', '-100123'), \
         patch('handlers.survey.api_client.get_survey_meta', side_effect=Exception('timeout')):
        await announceDeadlineWhenReached(bot)
    bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_announce_deadline_sleeps_then_announces():
    from datetime import datetime, timedelta, timezone
    from handlers.survey import announceDeadlineWhenReached
    bot = MagicMock(send_message=AsyncMock())
    future_deadline = (datetime.now(timezone.utc) + timedelta(seconds=30)).isoformat()
    meta = {**META, 'deadline': future_deadline}
    with patch('handlers.survey._TELEGRAM_CHAT_ID', '-100123'), \
         patch('handlers.survey.api_client.get_survey_meta', return_value=meta), \
         patch('handlers.survey.asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
        await announceDeadlineWhenReached(bot)
    mock_sleep.assert_called_once()
    assert 0 < mock_sleep.call_args[0][0] <= 30
    bot.send_message.assert_called_once()
    assert bot.send_message.call_args.kwargs['chat_id'] == '-100123'
    assert 'finalize' in bot.send_message.call_args.kwargs['text'].lower()


@pytest.mark.asyncio
async def test_announce_deadline_already_past_at_startup_skips():
    # is_closed is False but the deadline timestamp itself is already behind
    # now() — a defensive edge case, shouldn't sleep a negative duration.
    from datetime import datetime, timedelta, timezone
    from handlers.survey import announceDeadlineWhenReached
    bot = MagicMock(send_message=AsyncMock())
    past_deadline = (datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat()
    meta = {**META, 'deadline': past_deadline, 'is_closed': False}
    with patch('handlers.survey._TELEGRAM_CHAT_ID', '-100123'), \
         patch('handlers.survey.api_client.get_survey_meta', return_value=meta), \
         patch('handlers.survey.asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
        await announceDeadlineWhenReached(bot)
    mock_sleep.assert_not_called()
    bot.send_message.assert_not_called()
