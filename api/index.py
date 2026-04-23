import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from fastapi import FastAPI, Request, Response
from mangum import Mangum
from telegram import Update
from telegram.ext import Application, CommandHandler
from dotenv import load_dotenv

load_dotenv()

from bot import start, hello, myid
from handlers.books import addBook, removeBook
from handlers.polls import createPoll, createPollTest


def _build_app() -> Application:
    tg_app = Application.builder().token(os.getenv('BOT_TOKEN', '')).build()
    tg_app.add_handler(CommandHandler('start', start))
    tg_app.add_handler(CommandHandler('hello', hello))
    tg_app.add_handler(CommandHandler('myid', myid))
    tg_app.add_handler(CommandHandler('add', addBook))
    tg_app.add_handler(CommandHandler('remove', removeBook))
    tg_app.add_handler(CommandHandler('create_poll', createPoll))
    tg_app.add_handler(CommandHandler('create_poll_test', createPollTest))
    return tg_app

_tg_app = _build_app()

app = FastAPI()


@app.post('/')
async def webhook(request: Request) -> Response:
    if not _tg_app.running:
        await _tg_app.initialize()
    data = await request.json()
    update = Update.de_json(data, _tg_app.bot)
    await _tg_app.process_update(update)
    return Response(status_code=200)


handler = Mangum(app)
