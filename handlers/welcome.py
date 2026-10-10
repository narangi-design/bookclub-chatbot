import html
import logging
import os
from datetime import date, timedelta

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import api_client

logger = logging.getLogger(__name__)

_FRONTEND_URL = os.getenv('FRONTEND_URL', '').rstrip('/')
_RULES_URL = 'https://t.me/c/1562235079/35000'
_TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')


_CHOOSING_LINE = '🗳 Сейчас клуб выбирает, что читать дальше! Смотри последние закрепы, чтобы найти голосование'


def _is_poll_running(poll: dict, today: date) -> bool:
    # Голосование открыто ровно сутки (open_period в handlers/polls.py), но
    # в базе есть только дата создания, без времени — так что «сутки не
    # прошли» ≈ создано сегодня или вчера и итоги ещё не подведены.
    if poll.get('winner_book_id'):
        return False
    return date.fromisoformat(str(poll['date'])[:10]) >= today - timedelta(days=1)


def _club_status(books: list[dict], polls: list[dict], today: date) -> tuple[str, dict | None] | None:
    # Текущая = последняя выбранная, если после неё ещё не запускали новое
    # голосование. Сравниваем по id голосования, а не по дате: polls.date —
    # это DATE, и новое голосование в тот же день по дате не отличить.
    # Возвращает ('reading', книга), ('choosing', None) или None, если
    # сказать нечего (новое голосование было, но уже закончилось).
    elected = [b for b in books if b.get('status') == 'read' and b.get('elected_poll_id')]
    last_poll_id = max((b['elected_poll_id'] for b in elected), default=0)
    newer = [p for p in polls if p['id'] > last_poll_id]
    if any(_is_poll_running(p, today) for p in newer):
        return 'choosing', None
    if newer or not elected:
        return None
    return 'reading', max(elected, key=lambda b: b['elected_poll_id'])


async def _club_status_line() -> str | None:
    # Приветствие важнее инфы о книге — если API лежит, просто пропускаем строку.
    try:
        books = await api_client.get_books()
        polls = await api_client.get_polls()
        status = _club_status(books, polls, date.today())
        if not status:
            return None
        kind, book = status
        if kind == 'choosing':
            return _CHOOSING_LINE
        authors = await api_client.get_authors() if book.get('author_id') else []
    except Exception:
        logger.warning('Failed to fetch club status for welcome message', exc_info=True)
        return None
    title = html.escape(book['title'])
    author = next((a['name'] for a in authors if a['id'] == book['author_id']), None)
    if author:
        return f'📖 Сейчас клуб читает: «{title}», {html.escape(author)}'
    return f'📖 Сейчас клуб читает: «{title}»'


async def welcomeNewMembers(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    # Бота могут добавить и в другие чаты — приветствуем только в клубном.
    if _TELEGRAM_CHAT_ID and str(update.effective_chat.id) != _TELEGRAM_CHAT_ID:
        return
    members = update.message.new_chat_members or []
    # Добавили только ботов — здороваться не с кем.
    if members and all(u.is_bot for u in members):
        return
    newcomers = [u for u in members if not u.is_bot]
    await update.message.reply_text(await welcomeText(newcomers), parse_mode=ParseMode.HTML)


async def welcomeText(newcomers: list) -> str:
    names = ', '.join(u.mention_html() for u in newcomers)
    greeting = '👋 Добро пожаловать в элитный книжный клуб 📚'
    lines = [f'Привет, {names}! {greeting}' if names else greeting]

    links = [f'📜 <a href="{_RULES_URL}">Правила клуба</a>']
    if _FRONTEND_URL:
        links.append(
            f'🌐 <a href="{html.escape(_FRONTEND_URL)}">Наш сайт</a> — '
            'чувствительные данные спрятаны за авторизацией, входи через Telegram 🔐'
        )
    lines.append('\n'.join(links))

    status_line = await _club_status_line()
    if status_line:
        lines.append(status_line)

    lines.append('Файлы для чтения, ссылки на аудиокниги смотри в последних закрепах 📌')
    lines.append('А чтобы узнать, что я умею, пиши /help 🪨')
    return '\n\n'.join(lines)
