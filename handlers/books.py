from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from mock_db import author_name_exists, get_book_by_title

TITLE, AUTHOR = range(2)

cancel_button = InlineKeyboardMarkup([[InlineKeyboardButton("Отмена", callback_data="cancel")]])


async def addBook(update: Update, _: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text('Название книги?', reply_markup=cancel_button)
    return TITLE


async def addBook_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['title'] = update.message.text
    await update.message.reply_text(f'Книга "{update.message.text}", а кто автор? Формат: Имя Фамилия', reply_markup=cancel_button)
    return AUTHOR


async def addBook_author(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    title = context.user_data['title']
    author = update.message.text

    if author_name_exists(author):
        await update.message.reply_text(f'В списке пополнение: "{title}", {author}')
    else:
        await update.message.reply_text(
            f'Автор "{author}" не найден в базе, но книгу "{title}" добавил(а). '
            f'Попроси администратора уточнить автора.'
        )
    return ConversationHandler.END


async def cancel(update: Update, _: ContextTypes.DEFAULT_TYPE) -> int:
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text('Добавление книги отменено.')
    else:
        await update.message.reply_text('Добавление книги отменено.')
    return ConversationHandler.END


async def removeBook(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    title = update.message.text.strip() if update.message.text else ''
    book = get_book_by_title(title)
    if book:
        await update.message.reply_text(f'Книга "{title}" удалена из списка.')
    else:
        await update.message.reply_text(f'Книга "{title}" не найдена в списке.')
