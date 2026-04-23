import re
from telegram import Update
from telegram.ext import ContextTypes

import api_client

HELP_TEXT = (
    'Форматы, чтобы добавить книгу:\n'
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
    telegram_id = update.effective_user.id

    try:
        api_client.add_book(title=title, author_name=author_name, telegram_id=telegram_id)
        user = update.effective_user
        name = user.first_name or user.username or 'друг'
        await update.message.reply_text(
            f'Книга теперь в списке, {name}!\n'
            f'Название: «{title}»\n'
            f'Автор: {author_name}\n\n'
            f'Удачи на голосовании. 😈'
        )
    except Exception:
        await update.message.reply_text('Не удалось добавить книгу. Попробуй ещё раз.')


async def removeBook(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    title = ' '.join(context.args).strip() if context.args else ''

    if not title:
        await update.message.reply_text('Укажи название: /remove Название книги')
        return

    try:
        found = api_client.remove_book(title=title)
        if found:
            await update.message.reply_text(f'Книга «{title}» удалена из списка.')
        else:
            await update.message.reply_text(f'Книга «{title}» не найдена в списке.')
    except Exception:
        await update.message.reply_text('Не удалось удалить книгу. Попробуй ещё раз.')
