import pytest
from unittest.mock import patch

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
# /survey_close
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_survey_close_before_close_survey_script_ran():
    # award_events has no row for the year yet — close_survey.py hasn't run.
    from handlers.survey import surveyClose
    update = make_poll_update()
    with patch('handlers.survey.api_client.get_survey_meta', return_value=META_CLOSED), \
         patch('handlers.survey.api_client.get_award_events', return_value=[{'year': 2025, 'total_voters': 10}]):
        await surveyClose(update, make_context())
    text = update.message.reply_text.call_args[0][0]
    assert 'close_survey.py' in text


@pytest.mark.asyncio
async def test_survey_close_no_tiebreaks_announces_results():
    from handlers.survey import surveyClose
    update = make_poll_update()
    award_events = [{'year': 2026, 'total_voters': 15}]
    with patch('handlers.survey.api_client.get_survey_meta', return_value=META_CLOSED), \
         patch('handlers.survey.api_client.get_award_events', return_value=award_events), \
         patch('handlers.survey.api_client.get_survey_tiebreaks', return_value=[]):
        await surveyClose(update, make_context())
    text = update.message.reply_text.call_args[0][0]
    assert 'подведены' in text
    assert '/survey/results' in text


@pytest.mark.asyncio
async def test_survey_close_unresolved_tiebreak_invites_second_round():
    from handlers.survey import surveyClose
    update = make_poll_update()
    award_events = [{'year': 2026, 'total_voters': 15}]
    tiebreaks = [
        {'category': 'favorite', 'deadline': '2027-01-12T23:59:59+00:00', 'candidate_book_ids': [4, 6], 'resolved': False},
    ]
    with patch('handlers.survey.api_client.get_survey_meta', return_value=META_CLOSED), \
         patch('handlers.survey.api_client.get_award_events', return_value=award_events), \
         patch('handlers.survey.api_client.get_survey_tiebreaks', return_value=tiebreaks):
        await surveyClose(update, make_context())
    text = update.message.reply_text.call_args[0][0]
    assert 'Книга года' in text
    assert '12.01.2027' in text
    assert '/survey' in text
    assert '/survey/results' not in text


@pytest.mark.asyncio
async def test_survey_close_resolved_tiebreak_ignored():
    # A resolved tiebreak shouldn't block the "results ready" message.
    from handlers.survey import surveyClose
    update = make_poll_update()
    award_events = [{'year': 2026, 'total_voters': 15}]
    tiebreaks = [
        {'category': 'favorite', 'deadline': '2027-01-12T23:59:59+00:00', 'candidate_book_ids': [4, 6], 'resolved': True},
    ]
    with patch('handlers.survey.api_client.get_survey_meta', return_value=META_CLOSED), \
         patch('handlers.survey.api_client.get_award_events', return_value=award_events), \
         patch('handlers.survey.api_client.get_survey_tiebreaks', return_value=tiebreaks):
        await surveyClose(update, make_context())
    text = update.message.reply_text.call_args[0][0]
    assert 'подведены' in text


@pytest.mark.asyncio
async def test_survey_close_meta_api_error():
    from handlers.survey import surveyClose
    update = make_poll_update()
    with patch('handlers.survey.api_client.get_survey_meta', side_effect=Exception('timeout')):
        await surveyClose(update, make_context())
    text = update.message.reply_text.call_args[0][0]
    assert 'Не удалось' in text


@pytest.mark.asyncio
async def test_survey_close_tiebreaks_api_error():
    from handlers.survey import surveyClose
    update = make_poll_update()
    award_events = [{'year': 2026, 'total_voters': 15}]
    with patch('handlers.survey.api_client.get_survey_meta', return_value=META_CLOSED), \
         patch('handlers.survey.api_client.get_award_events', return_value=award_events), \
         patch('handlers.survey.api_client.get_survey_tiebreaks', side_effect=Exception('timeout')):
        await surveyClose(update, make_context())
    text = update.message.reply_text.call_args[0][0]
    assert 'Не удалось' in text
