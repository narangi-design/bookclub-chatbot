from telegram import Update
from telegram.ext import ContextTypes

HELP_TEXT = (
    'Привет, я камень элитного книжного клуба! Управляю списком книг и выбором следующей книги для чтения.\n\n'
    'Вот с чем я могу помочь:\n\n'
    '/add — добавить книгу в список. Формат: Автор — Название\n'
    '/my_books — посмотреть свои книги в предложке\n'
    '/remove — убрать свою книгу из списка\n'
    '/create_poll — начать голосование за следующую книгу\n'
    '/hello — поздороваться со мной (вашим камнем🪨)\n'
    '/help — прочитать это сообщение ещё раз\n\n'
    'Если что-то пошло не так — просто попробуй ещё раз. Или тегни админа. 🤓'
)


async def helpCommand(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP_TEXT)


async def hello(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(f'Привет, {update.effective_user.name}')


async def myid(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(f'Твой Telegram ID: {update.effective_user.id}')
