import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from tests.conftest import make_context, make_poll_update


def make_tg_poll(options_votes: list[int], poll_id: str = 'tg_poll_123'):
    poll = MagicMock()
    poll.id = poll_id
    poll.total_voter_count = sum(options_votes)
    poll.options = [MagicMock(voter_count=v) for v in options_votes]
    return poll


def make_reply_update(options_votes: list[int], poll_id: str = 'tg_poll_123'):
    update = make_poll_update()
    reply = MagicMock()
    reply.poll = make_tg_poll(options_votes, poll_id)
    update.message.reply_to_message = reply
    return update


WINNER = {
    'book_id': 6,
    'book_title': 'Дюна',
    'author_name': 'Фрэнк Герберт',
    'member_username': 'pavlik99',
    'votes': 3,
}

TIED_BOOKS = [
    {'id': 4, 'title': 'Пикник на обочине', 'author_name': 'Стругацкие', 'votes': 2},
    {'id': 6, 'title': 'Дюна',              'author_name': 'Фрэнк Герберт', 'votes': 2},
]


# ---------------------------------------------------------------------------
# _poll_vote_options
# ---------------------------------------------------------------------------

def test_poll_vote_options_maps_index_and_count():
    from handlers.polls import _poll_vote_options
    poll = make_tg_poll([5, 3, 0])
    result = _poll_vote_options(poll)
    assert result == [
        {'option_index': 0, 'votes_count': 5},
        {'option_index': 1, 'votes_count': 3},
        {'option_index': 2, 'votes_count': 0},
    ]


# ---------------------------------------------------------------------------
# _poll_options
# ---------------------------------------------------------------------------

def test_poll_options_full_format():
    from handlers.polls import _poll_options
    books = [{'title': 'Дюна', 'author_name': 'Фрэнк Герберт', 'member_display_name': 'Павел'}]
    assert _poll_options(books) == ['«Дюна», Фрэнк Герберт — Павел']


def test_poll_options_without_member():
    from handlers.polls import _poll_options
    books = [{'title': 'Дюна', 'author_name': 'Фрэнк Герберт'}]
    assert _poll_options(books) == ['«Дюна», Фрэнк Герберт']


def test_poll_options_without_author():
    from handlers.polls import _poll_options
    books = [{'title': 'Дюна'}]
    assert _poll_options(books) == ['«Дюна»']


def test_poll_options_multiple_books():
    from handlers.polls import _poll_options
    books = [
        {'title': 'Дюна', 'author_name': 'Герберт', 'member_display_name': 'Павел'},
        {'title': 'Пикник', 'author_name': 'Стругацкие'},
    ]
    result = _poll_options(books)
    assert len(result) == 2
    assert 'Павел' in result[0]
    assert 'Павел' not in result[1]


# ---------------------------------------------------------------------------
# /results — pollResults
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_poll_results_no_reply():
    from handlers.polls import pollResults
    update = make_poll_update()
    update.message.reply_to_message = None
    await pollResults(update, make_context())
    update.message.reply_text.assert_called_once()
    assert 'Реплайни' in update.message.reply_text.call_args[0][0]


@pytest.mark.asyncio
async def test_poll_results_reply_not_poll():
    from handlers.polls import pollResults
    update = make_poll_update()
    reply = MagicMock()
    reply.poll = None
    update.message.reply_to_message = reply
    await pollResults(update, make_context())
    assert 'Реплайни' in update.message.reply_text.call_args[0][0]


@pytest.mark.asyncio
async def test_poll_results_api_error():
    from handlers.polls import pollResults
    update = make_reply_update([3, 2, 1])
    with patch('handlers.polls.api_client.save_poll_results', side_effect=Exception('timeout')):
        await pollResults(update, make_context())
    text = update.message.reply_text.call_args[0][0]
    assert 'Не удалось' in text


@pytest.mark.asyncio
async def test_poll_results_winner_announces_book():
    from handlers.polls import pollResults
    update = make_reply_update([3, 2, 1])
    result = {'ok': True, 'poll_id': 1, 'winner': WINNER, 'tied_books': None, 'total_voters': 6}
    with patch('handlers.polls.api_client.save_poll_results', return_value=result):
        await pollResults(update, make_context())
    text = update.message.reply_text.call_args[0][0]
    assert 'Дюна' in text
    assert 'Фрэнк Герберт' in text
    assert '@pavlik99' in text


@pytest.mark.asyncio
async def test_poll_results_winner_without_username():
    from handlers.polls import pollResults
    update = make_reply_update([3, 2])
    winner = {**WINNER, 'member_username': None}
    result = {'ok': True, 'poll_id': 1, 'winner': winner, 'tied_books': None, 'total_voters': 5}
    with patch('handlers.polls.api_client.save_poll_results', return_value=result):
        await pollResults(update, make_context())
    text = update.message.reply_text.call_args[0][0]
    assert 'Участник' in text


@pytest.mark.asyncio
async def test_poll_results_tie_suggests_second_round():
    from handlers.polls import pollResults
    update = make_reply_update([2, 2, 1])
    result = {'ok': True, 'poll_id': 1, 'winner': None, 'tied_books': TIED_BOOKS, 'total_voters': 5}
    with patch('handlers.polls.api_client.save_poll_results', return_value=result):
        await pollResults(update, make_context())
    text = update.message.reply_text.call_args[0][0]
    assert '/second_round' in text
    assert 'Дюна' in text or 'Пикник' in text


# ---------------------------------------------------------------------------
# /second_round — secondRound
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_second_round_no_reply():
    from handlers.polls import secondRound
    update = make_poll_update()
    update.message.reply_to_message = None
    await secondRound(update, make_context())
    assert 'Реплайни' in update.message.reply_text.call_args[0][0]


@pytest.mark.asyncio
async def test_second_round_reply_not_poll():
    from handlers.polls import secondRound
    update = make_poll_update()
    reply = MagicMock()
    reply.poll = None
    update.message.reply_to_message = reply
    await secondRound(update, make_context())
    assert 'Реплайни' in update.message.reply_text.call_args[0][0]


@pytest.mark.asyncio
async def test_second_round_api_error():
    from handlers.polls import secondRound
    update = make_reply_update([2, 2])
    with patch('handlers.polls.api_client.save_poll_results', side_effect=Exception('not found')):
        await secondRound(update, make_context())
    text = update.message.reply_text.call_args[0][0]
    assert 'не нашёл опрос' in text.lower()


@pytest.mark.asyncio
async def test_second_round_no_tie():
    from handlers.polls import secondRound
    update = make_reply_update([3, 1])
    result = {'ok': True, 'poll_id': 1, 'winner': WINNER, 'tied_books': None, 'total_voters': 4}
    with patch('handlers.polls.api_client.save_poll_results', return_value=result):
        await secondRound(update, make_context())
    text = update.message.reply_text.call_args[0][0]
    assert 'не нужен второй тур' in text.lower()


@pytest.mark.asyncio
async def test_second_round_creates_poll_with_tied_books():
    from handlers.polls import secondRound
    update = make_reply_update([2, 2])
    result = {'ok': True, 'poll_id': 7, 'winner': None, 'tied_books': TIED_BOOKS, 'total_voters': 4}
    context = make_context()
    with patch('handlers.polls.api_client.save_poll_results', return_value=result), \
         patch('handlers.polls.api_client.create_poll') as mock_create:
        await secondRound(update, context)
    _, kwargs = context.bot.send_poll.call_args
    assert kwargs['allows_multiple_answers'] is False
    assert len(kwargs['options']) == 2
    mock_create.assert_called_once()
    call_kwargs = mock_create.call_args[1]
    assert call_kwargs['stage'] == 2
    assert call_kwargs['parent_poll_id'] == 7
    assert set(call_kwargs['book_ids']) == {4, 6}


@pytest.mark.asyncio
async def test_second_round_create_poll_db_error_sends_warning():
    from handlers.polls import secondRound
    update = make_reply_update([2, 2])
    result = {'ok': True, 'poll_id': 7, 'winner': None, 'tied_books': TIED_BOOKS, 'total_voters': 4}
    context = make_context()
    with patch('handlers.polls.api_client.save_poll_results', return_value=result), \
         patch('handlers.polls.api_client.create_poll', side_effect=Exception('db error')):
        await secondRound(update, context)
    context.bot.send_poll.assert_called_once()
    context.bot.send_message.assert_called_once()
    warning = context.bot.send_message.call_args[1]['text']
    assert '⚠️' in warning
