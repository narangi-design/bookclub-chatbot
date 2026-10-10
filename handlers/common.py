from telegram import Update
from telegram.ext import ContextTypes

HELP_TEXT = (
    'Привет, я камень элитного книжного клуба! Управляю списком книг и выбором следующей книги для чтения.\n\n'
    'Вот с чем я могу помочь:\n\n'
    '/add — добавить книгу в список. Формат: Имя Фамилия — Название книги\n'
    '/remove — убрать свою книгу из списка\n'
    '/my_books — посмотреть свои книги в предложке\n'
    '/create_poll — начать голосование за следующую книгу\n'
    '/second_round — начать второй тур голосования при ничьей\n'
    '/results — подвести итоги голосования\n'
    '/discussion — ответом на сообщение с записью — привязать запись к книге\n'
    '/cover — посмотреть, есть ли книжки без обложки, добавить обложку, если надо\n'
    '/search — найти книгу по названию или автору\n'
    '/recommend — ответом на сообщение — сохранить его в рекомендации на сайте\n'
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
