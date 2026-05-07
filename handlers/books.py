import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import api_client

HELP_TEXT = (
    'Пиши /add, пробел и что-то из этого:\n'
    '🔸Имя Фамилия — Название книги\n'
    '🔸Имя Фамилия, .., Имя Фамилия (и т.д.) — Название книги\n'
    '🔸Имя и Имя Фамилия — Название книги\n'
    '🔸Имя, Имя, ... и Имя Фамилия — Название книги\n\n'
    'P.S. Тирешки, минусы, дефисы — можно. 🤓'
)

# Разделитель: em-dash, en-dash или дефис с пробелами
_SEPARATOR = re.compile(r'^(.+?)(?:\s*[—–]\s*|\s+-\s+)(.+)$')


async def addBook(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = ' '.join(context.args).strip() if context.args else ''
    match = _SEPARATOR.match(text)

    if not match:
        await update.message.reply_text(HELP_TEXT)
        return

    author_name = match.group(1).strip()
    title = match.group(2).strip()
    tg_user = update.effective_user

    try:
        result = api_client.add_book(
            title=title,
            author_name=author_name,
            telegram_id=tg_user.id,
            telegram_username=tg_user.username,
            telegram_fullname=tg_user.full_name,
        )
        if result.get('exists'):
            await update.message.reply_text(
                f'Похоже, книга «{result["existing_title"]}» уже есть в списке.'
            )
            return
        name = tg_user.first_name or tg_user.username or 'друг'
        await update.message.reply_text(
            f'Книга теперь в списке, {name}!\n'
            f'Название: «{title}»\n'
            f'Автор: {author_name}\n\n'
            f'Удачи на голосовании. 😈'
        )
    except Exception:
        await update.message.reply_text('Не удалось добавить книгу. Попробуй ещё раз.')


def _book_label(book: dict) -> str:
    author = f', {book["author"]}' if book.get('author') else ''
    return f'«{book["title"]}»{author}'


async def removeBook(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = ' '.join(context.args).strip() if context.args else ''

    if not query:
        await update.message.reply_text('Укажи название: /remove Название книги')
        return

    try:
        matches = api_client.search_books_to_remove(query)
    except Exception:
        await update.message.reply_text('Не удалось найти книгу. Попробуй ещё раз.')
        return

    if not matches:
        await update.message.reply_text('Не нашёл ничего похожего в списке.')
        return

    buttons = [
        [InlineKeyboardButton(_book_label(b), callback_data=f'remove:{b["id"]}')]
        for b in matches
    ]
    buttons.append([InlineKeyboardButton('❌ Отмена', callback_data='remove:cancel')])

    text = 'Выбери книгу:' if len(matches) > 1 else 'Нашёл книгу:'
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))


async def removeBookCallback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    data = query.data  # 'remove:{book_id}' or 'remove:cancel'
    _, payload = data.split(':', 1)

    if payload == 'cancel':
        await query.edit_message_text('Отменено.')
        return

    try:
        found = api_client.remove_book(book_id=int(payload))
        if found:
            await query.edit_message_text('Книга удалена из списка.')
        else:
            await query.edit_message_text('Книга не найдена — возможно, уже удалена.')
    except Exception:
        await query.edit_message_text('Не удалось удалить книгу. Попробуй ещё раз.')
