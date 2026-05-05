from telegram import Update
from telegram.ext import ContextTypes


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text='Привет, я ваш камень! Я помогаю со списком книг и выбором книги для чтения.'
    )


async def hello(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(f'Привет, {update.effective_user.name}')


async def myid(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(f'Твой Telegram ID: {update.effective_user.id}')
