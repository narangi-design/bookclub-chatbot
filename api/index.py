import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from mangum import Mangum
from telegram import Update
from telegram.ext import Application, CommandHandler
from dotenv import load_dotenv

load_dotenv()

from bot import start, hello, myid
from handlers.books import removeBook
from handlers.polls import createPoll, createPollTest

_tg_app: Application | None = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    global _tg_app
    _tg_app = Application.builder().token(os.getenv('BOT_TOKEN', '')).build()
    _tg_app.add_handler(CommandHandler('start', start))
    _tg_app.add_handler(CommandHandler('hello', hello))
    _tg_app.add_handler(CommandHandler('myid', myid))
    _tg_app.add_handler(CommandHandler('remove', removeBook))
    _tg_app.add_handler(CommandHandler('create_poll', createPoll))
    _tg_app.add_handler(CommandHandler('create_poll_test', createPollTest))
    await _tg_app.initialize()
    yield
    await _tg_app.shutdown()


app = FastAPI(lifespan=lifespan)


@app.post('/')
async def webhook(request: Request) -> Response:
    data = await request.json()
    update = Update.de_json(data, _tg_app.bot)
    await _tg_app.process_update(update)
    return Response(status_code=200)


handler = Mangum(app)
