from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import make_context, make_poll_update

BOOKS = [
    {'id': 1, 'title': 'Старая', 'status': 'read', 'elected_poll_id': 3, 'author_id': 10},
    {'id': 2, 'title': 'Пикник на обочине', 'status': 'read', 'elected_poll_id': 5, 'author_id': 11},
    {'id': 3, 'title': 'В списке', 'status': 'to_read', 'elected_poll_id': None, 'author_id': 12},
]
AUTHORS = [{'id': 11, 'name': 'Аркадий и Борис Стругацкие'}]
TODAY = date.today()
POLLS = [{'id': i, 'date': '2026-01-01', 'winner_book_id': None} for i in range(1, 6)]


def _new_poll(days_ago: int, winner_book_id=None):
    return {'id': 6, 'date': (TODAY - timedelta(days=days_ago)).isoformat(), 'winner_book_id': winner_book_id}


def _member(name: str = 'Алёна', is_bot: bool = False):
    user = MagicMock()
    user.is_bot = is_bot
    user.mention_html.return_value = f'<a href="tg://user?id=1">{name}</a>'
    return user


def _join_update(*members):
    update = make_poll_update()
    update.message.new_chat_members = list(members)
    return update


def _patch_api(books=BOOKS, polls=POLLS, authors=AUTHORS):
    return (
        patch('handlers.welcome.api_client.get_books', return_value=books),
        patch('handlers.welcome.api_client.get_polls', return_value=polls),
        patch('handlers.welcome.api_client.get_authors', return_value=authors),
    )


# ---------------------------------------------------------------------------
# _club_status
# ---------------------------------------------------------------------------

def test_reading_last_elected_book():
    from handlers.welcome import _club_status
    kind, book = _club_status(BOOKS, POLLS, TODAY)
    assert kind == 'reading'
    assert book['id'] == 2


@pytest.mark.parametrize('days_ago', [0, 1])
def test_choosing_while_newer_poll_is_running(days_ago):
    from handlers.welcome import _club_status
    assert _club_status(BOOKS, POLLS + [_new_poll(days_ago)], TODAY) == ('choosing', None)


def test_nothing_to_say_when_newer_poll_is_old():
    from handlers.welcome import _club_status
    assert _club_status(BOOKS, POLLS + [_new_poll(2)], TODAY) is None


def test_nothing_to_say_when_newer_poll_already_has_winner():
    from handlers.welcome import _club_status
    assert _club_status(BOOKS, POLLS + [_new_poll(0, winner_book_id=3)], TODAY) is None


def test_choosing_even_before_first_book_elected():
    from handlers.welcome import _club_status
    assert _club_status([BOOKS[2]], [_new_poll(0)], TODAY) == ('choosing', None)


def test_nothing_to_say_when_nothing_elected():
    from handlers.welcome import _club_status
    assert _club_status([BOOKS[2]], [], TODAY) is None


# ---------------------------------------------------------------------------
# welcomeNewMembers
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_welcome_has_greeting_rules_book_and_pins():
    from handlers.welcome import welcomeNewMembers
    update = _join_update(_member('Алёна'))
    books, polls, authors = _patch_api()
    with books, polls, authors, patch('handlers.welcome._TELEGRAM_CHAT_ID', ''), \
            patch('handlers.welcome._FRONTEND_URL', 'https://club.example'):
        await welcomeNewMembers(update, make_context())
    text = update.message.reply_text.call_args[0][0]
    assert 'Алёна' in text
    assert '<a href="https://t.me/c/1562235079/35000">Правила клуба</a>' in text
    assert '<a href="https://club.example">Наш сайт</a>' in text
    assert 'авторизацией' in text
    assert 'Сейчас клуб читает: «Пикник на обочине», Аркадий и Борис Стругацкие' in text
    assert 'закрепах' in text


@pytest.mark.asyncio
async def test_welcome_says_choosing_during_running_poll():
    from handlers.welcome import welcomeNewMembers
    update = _join_update(_member())
    books, polls, authors = _patch_api(polls=POLLS + [_new_poll(0)])
    with books, polls, authors, patch('handlers.welcome._TELEGRAM_CHAT_ID', ''):
        await welcomeNewMembers(update, make_context())
    text = update.message.reply_text.call_args[0][0]
    assert 'Сейчас клуб читает' not in text
    assert 'Сейчас клуб выбирает, что читать дальше!' in text
    assert 'закрепах' in text


@pytest.mark.asyncio
async def test_welcome_still_sent_when_api_fails():
    from handlers.welcome import welcomeNewMembers
    update = _join_update(_member())
    with patch('handlers.welcome.api_client.get_books', side_effect=Exception('timeout')), \
            patch('handlers.welcome._TELEGRAM_CHAT_ID', ''):
        await welcomeNewMembers(update, make_context())
    text = update.message.reply_text.call_args[0][0]
    assert 'Привет' in text
    assert 'Сейчас клуб читает' not in text


@pytest.mark.asyncio
async def test_welcome_ignores_bots():
    from handlers.welcome import welcomeNewMembers
    update = _join_update(_member(is_bot=True))
    with patch('handlers.welcome._TELEGRAM_CHAT_ID', ''):
        await welcomeNewMembers(update, make_context())
    update.message.reply_text.assert_not_called()


@pytest.mark.asyncio
async def test_welcome_ignores_other_chats():
    from handlers.welcome import welcomeNewMembers
    update = _join_update(_member())
    with patch('handlers.welcome._TELEGRAM_CHAT_ID', '-100999'):
        await welcomeNewMembers(update, make_context())
    update.message.reply_text.assert_not_called()


@pytest.mark.asyncio
async def test_welcome_without_known_member_uses_plain_greeting():
    from handlers.welcome import welcomeNewMembers
    update = _join_update()
    books, polls, authors = _patch_api()
    with books, polls, authors, patch('handlers.welcome._TELEGRAM_CHAT_ID', ''):
        await welcomeNewMembers(update, make_context())
    text = update.message.reply_text.call_args[0][0]
    assert text.startswith('👋 Добро пожаловать в элитный книжный клуб 📚')
