import pytest
from unittest.mock import patch

from tests.conftest import make_context, make_poll_update
from tests.fixtures import poll_candidates, few_poll_candidates, empty_books

TWENTY_FOUR_HOURS = 86400


# ---------------------------------------------------------------------------
# /create_poll_test — тестовая команда (mock_db)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_poll_test_sends_exactly_4_options():
    """Тестовый опрос содержит ровно 4 варианта."""
    from handlers.polls import createPollTest

    context = make_context()
    with patch("handlers.polls.mock_db.get_poll_candidates", return_value=poll_candidates):
        await createPollTest(make_poll_update(), context)

    _, kwargs = context.bot.send_poll.call_args
    assert len(kwargs["options"]) == 4


@pytest.mark.asyncio
async def test_create_poll_test_fewer_than_4_uses_all():
    """Тестовый опрос: если кандидатов меньше 4 — берём все."""
    from handlers.polls import createPollTest

    assert len(few_poll_candidates) < 4
    context = make_context()

    with patch("handlers.polls.mock_db.get_poll_candidates", return_value=few_poll_candidates):
        await createPollTest(make_poll_update(), context)

    _, kwargs = context.bot.send_poll.call_args
    assert len(kwargs["options"]) == len(few_poll_candidates)


@pytest.mark.asyncio
async def test_create_poll_test_no_candidates():
    """Тестовый опрос: нет кандидатов — сообщение вместо опроса."""
    from handlers.polls import createPollTest

    context = make_context()
    with patch("handlers.polls.mock_db.get_poll_candidates", return_value=empty_books):
        await createPollTest(make_poll_update(), context)

    context.bot.send_poll.assert_not_called()
    context.bot.send_message.assert_called_once()


# ---------------------------------------------------------------------------
# /create_poll — боевая команда (api_client)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_poll_calls_api_client():
    """Боевой опрос вызывает api_client.get_poll_candidates, не mock_db."""
    from handlers.polls import createPoll

    context = make_context()
    with patch("handlers.polls.api_client.get_poll_candidates", return_value=poll_candidates) as mock_api:
        await createPoll(make_poll_update(), context)

    mock_api.assert_called_once_with(n=12)
    context.bot.send_poll.assert_called_once()


@pytest.mark.asyncio
async def test_create_poll_no_candidates():
    """Боевой опрос: бэк вернул пустой список — сообщение вместо опроса."""
    from handlers.polls import createPoll

    context = make_context()
    with patch("handlers.polls.api_client.get_poll_candidates", return_value=[]):
        await createPoll(make_poll_update(), context)

    context.bot.send_poll.assert_not_called()
    context.bot.send_message.assert_called_once()


# ---------------------------------------------------------------------------
# Формат опций
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_poll_option_format():
    """Опция форматируется как «Название», Автор — Участник."""
    from handlers.polls import createPollTest

    context = make_context()
    with patch("handlers.polls.mock_db.get_poll_candidates", return_value=poll_candidates):
        await createPollTest(make_poll_update(), context)

    _, kwargs = context.bot.send_poll.call_args
    first_option = kwargs["options"][0]
    candidate = poll_candidates[0]

    assert f'«{candidate["title"]}»' in first_option
    assert candidate["author_name"] in first_option
    assert candidate["member_display_name"] in first_option


# ---------------------------------------------------------------------------
# Параметры опроса
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_poll_is_public():
    """Опрос публичный — is_anonymous=False."""
    from handlers.polls import createPollTest

    context = make_context()
    with patch("handlers.polls.mock_db.get_poll_candidates", return_value=poll_candidates):
        await createPollTest(make_poll_update(), context)

    _, kwargs = context.bot.send_poll.call_args
    assert kwargs.get("is_anonymous") is False


@pytest.mark.asyncio
async def test_poll_allows_multiple_answers():
    """Опрос с мультивыбором — allows_multiple_answers=True."""
    from handlers.polls import createPollTest

    context = make_context()
    with patch("handlers.polls.mock_db.get_poll_candidates", return_value=poll_candidates):
        await createPollTest(make_poll_update(), context)

    _, kwargs = context.bot.send_poll.call_args
    assert kwargs.get("allows_multiple_answers") is True


@pytest.mark.asyncio
async def test_poll_lasts_24_hours():
    """Опрос закрывается через 24 часа — open_period=86400."""
    from handlers.polls import createPollTest

    context = make_context()
    with patch("handlers.polls.mock_db.get_poll_candidates", return_value=poll_candidates):
        await createPollTest(make_poll_update(), context)

    _, kwargs = context.bot.send_poll.call_args
    assert kwargs.get("open_period") == TWENTY_FOUR_HOURS
