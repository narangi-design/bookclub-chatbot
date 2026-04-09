from telegram import Update
from telegram.ext import ContextTypes

import mock_db
import api_client


async def _send_poll(update: Update, context: ContextTypes.DEFAULT_TYPE, candidates: list) -> None:
    if not candidates:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text='Нет книг для голосования. Сначала добавьте книги командой /add.'
        )
        return

    options = [
        f'«{c["title"]}», {c["author_name"]} — {c["member_display_name"]}'
        for c in candidates
    ]
    await context.bot.send_poll(
        chat_id=update.effective_chat.id,
        question=f'Выбираем следующую книгу, {update.effective_chat.title}!',
        options=options,
        is_anonymous=False,
        allows_multiple_answers=True,
        open_period=86400,
    )


async def createPollTest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    candidates = mock_db.get_poll_candidates(n=4)
    await _send_poll(update, context, candidates)


async def createPoll(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    candidates = api_client.get_poll_candidates(n=12)
    await _send_poll(update, context, candidates)
