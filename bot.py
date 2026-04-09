import os
import logging
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, ConversationHandler, MessageHandler, CallbackQueryHandler, filters
from mock_db import author_name_exists, get_book_by_title, get_books_by_status

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

load_dotenv()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text='Привет, я ассистент книжного клуба! Я помогаю со списком книг и выбором книги для чтения.')

async def hello(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(f'Привет, {update.effective_user.name}')

TITLE, AUTHOR = range(2)

cancel_button = InlineKeyboardMarkup([[InlineKeyboardButton("Отмена", callback_data="cancel")]])

async def myid(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(f'Твой Telegram ID: {update.effective_user.id}')

async def cancel(update: Update, _: ContextTypes.DEFAULT_TYPE) -> int:
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text('Добавление книги отменено.')
    else:
        await update.message.reply_text('Добавление книги отменено.')
    return ConversationHandler.END

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

async def removeBook(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    title = update.message.text.strip() if update.message.text else ''
    book = get_book_by_title(title)
    if book:
        await update.message.reply_text(f'Книга "{title}" удалена из списка.')
    else:
        await update.message.reply_text(f'Книга "{title}" не найдена в списке.')

async def createPoll(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    books = get_books_by_status("to_read")
    if not books:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text='Нет книг для голосования. Сначала добавьте книги командой /add.'
        )
        return

    options = [b["title"] for b in books]
    await context.bot.send_poll(
        chat_id=update.effective_chat.id,
        question=f'Выбираем следующую книгу, {update.effective_chat.title}!',
        options=options,
        is_anonymous=False,
        allows_multiple_answers=False,
    )


if __name__ == '__main__':
    app = ApplicationBuilder().token(os.getenv('BOT_TOKEN')).build()

    addBook_handler = ConversationHandler(
        entry_points=[CommandHandler('add', addBook)],
        states={
            TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, addBook_title)],
            AUTHOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, addBook_author)],
        },
        fallbacks=[
            CommandHandler('cancel', cancel),
            CallbackQueryHandler(cancel, pattern="^cancel$"),
        ],
        conversation_timeout=180,
    )

    app.add_handler(CommandHandler('myid', myid))
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('hello', hello))
    app.add_handler(addBook_handler)
    app.add_handler(CommandHandler('remove', removeBook))
    app.add_handler(CommandHandler('create_poll', createPoll))

    app.run_polling()