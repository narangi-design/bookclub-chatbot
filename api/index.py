import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from fastapi import FastAPI, Request, Response
from mangum import Mangum
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from dotenv import load_dotenv

load_dotenv()

from handlers.common import helpCommand, hello, myid
from handlers.books import (
    addBook, removeBook, removeBookCallback, myBooks,
    addCover, pickCoverCallback, coverCallback,
    addDiscussion, pickDiscussionCallback,
    uploadCoverPhoto, cancelCoverUploadCallback,
    REMOVE, PICK_COVER, PICK_DISCUSSION, COVER_GOOGLE, COVER_LITRES, COVER_SKIP, COVER_UPLOAD_CANCEL,
)
from handlers.polls import createPoll, createPollTest, pollResults, secondRound


def _build_app() -> Application:
    tg_app = Application.builder().token(os.getenv('BOT_TOKEN', '')).build()
    tg_app.add_handler(CommandHandler('help', helpCommand))
    tg_app.add_handler(CommandHandler('hello', hello))
    tg_app.add_handler(CommandHandler('myid', myid))
    tg_app.add_handler(CommandHandler('add', addBook))
    tg_app.add_handler(CommandHandler('remove', removeBook))
    tg_app.add_handler(CallbackQueryHandler(removeBookCallback, pattern=f'^{REMOVE}:'))
    tg_app.add_handler(CommandHandler('discussion', addDiscussion))
    tg_app.add_handler(CallbackQueryHandler(pickDiscussionCallback, pattern=f'^{PICK_DISCUSSION}:'))
    tg_app.add_handler(CommandHandler('cover', addCover))
    tg_app.add_handler(CallbackQueryHandler(pickCoverCallback, pattern=f'^{PICK_COVER}:'))
    tg_app.add_handler(CallbackQueryHandler(cancelCoverUploadCallback, pattern=f'^{COVER_UPLOAD_CANCEL}$'))
    tg_app.add_handler(CallbackQueryHandler(coverCallback, pattern=f'^({COVER_GOOGLE}|{COVER_LITRES}|{COVER_SKIP})'))
    tg_app.add_handler(MessageHandler(filters.PHOTO & filters.REPLY, uploadCoverPhoto))
    tg_app.add_handler(CommandHandler('my_books', myBooks))
    tg_app.add_handler(CommandHandler('create_poll', createPoll))
    tg_app.add_handler(CommandHandler('create_poll_test', createPollTest))
    tg_app.add_handler(CommandHandler('results', pollResults))
    tg_app.add_handler(CommandHandler('second_round', secondRound))
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
