import os
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from handlers.books import addBook, removeBook
from handlers.polls import createPoll, createPollTest

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

load_dotenv()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text='Привет, я ваш камень! Я помогаю со списком книг и выбором книги для чтения.'
    )

async def hello(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(f'Привет, {update.effective_user.name}')

async def myid(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(f'Твой Telegram ID: {update.effective_user.id}')


if __name__ == '__main__':
    app = ApplicationBuilder().token(os.getenv('BOT_TOKEN')).build()

    app.add_handler(CommandHandler('myid', myid))
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('hello', hello))
    app.add_handler(CommandHandler('add', addBook))
#    app.add_handler(CommandHandler('remove', removeBook))
    app.add_handler(CommandHandler('create_poll', createPoll))
#    app.add_handler(CommandHandler('create_poll_test', createPollTest))

    app.run_polling()
