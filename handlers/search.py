import html
from datetime import date

from telegram import Update, LinkPreviewOptions
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import api_client

# Telegram caps a message at 4096 chars; ~3 lines per book keeps 15 well under it.
MAX_RESULTS = 15

_MONTHS_PREP = [
    'январе', 'феврале', 'марте', 'апреле', 'мае', 'июне',
    'июле', 'августе', 'сентябре', 'октябре', 'ноябре', 'декабре',
]

SEARCH_HELP = (
    'Напиши /search и что ищешь — название или автора.\n'
    'Например: /search паланик'
)


def _added_by(book: dict) -> str | None:
    # Без @ — иначе каждый результат поиска пингует того, кто добавил книгу
    return book.get('added_by_fullname') or book.get('added_by_username')


def _status_line(book: dict) -> str:
    status = book['status']
    if status == 'read':
        line = '✅ прочитали'
        if book.get('elected_at'):
            d = date.fromisoformat(book['elected_at'][:10])
            line += f' в {_MONTHS_PREP[d.month - 1]} {d.year}'
        if book.get('discussion_url'):
            line += f' · <a href="{html.escape(book["discussion_url"])}">запись заседания</a>'
        return line
    if status == 'removed':
        return '🚫 убрали из списка'
    return '📚 в очереди'


def format_book(book: dict) -> str:
    title = f'«{html.escape(book["title"])}»'
    if book.get('author_name'):
        title += f', {html.escape(book["author_name"])}'

    lines = [title, _status_line(book)]

    added = []
    if name := _added_by(book):
        added.append(html.escape(name))
    if book.get('added_at'):
        added.append(date.fromisoformat(book['added_at'][:10]).strftime('%d.%m.%Y'))
    if added:
        lines.append(f'Инициатива: {", ".join(added)}')

    return '\n'.join(lines)


def format_results(books: list[dict]) -> str:
    intro = 'Вот что я нашёл по запросу:'
    shown = books[:MAX_RESULTS]
    text = intro + '\n\n' + '\n\n'.join(format_book(b) for b in shown)
    if len(books) > MAX_RESULTS:
        text += f'\n\n…и ещё {len(books) - MAX_RESULTS}. Попробуй уточнить запрос.'
    return text


async def searchBooks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = ' '.join(context.args).strip() if context.args else ''
    if not query:
        await update.message.reply_text(SEARCH_HELP)
        return

    try:
        books = await api_client.lookup_books(query)
    except Exception:
        await update.message.reply_text('Не удалось поискать. Попробуй ещё раз.')
        return

    if not books:
        await update.message.reply_text(
            'Ничего не нашёл 🤔\n'
            'Может, пока и нечего искать? Добавить можно через /add.'
        )
        return

    await update.message.reply_text(
        format_results(books),
        parse_mode=ParseMode.HTML,
        link_preview_options=LinkPreviewOptions(is_disabled=True),
    )
