from datetime import date
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
    msg = await context.bot.send_poll(
        chat_id=update.effective_chat.id,
        question=f'Выбираем следующую книгу, {update.effective_chat.title}!',
        options=options,
        is_anonymous=False,
        allows_multiple_answers=True,
        open_period=86400,
    )
    return msg, candidates


async def createPollTest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    candidates = mock_db.get_poll_candidates(n=4)
    await _send_poll(update, context, candidates)


async def createPoll(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    candidates = api_client.get_poll_candidates(n=12)
    result = await _send_poll(update, context, candidates)
    if result is None:
        return
    msg, candidates = result
    try:
        api_client.create_poll(
            stage=1,
            date=date.today().isoformat(),
            telegram_poll_id=msg.poll.id,
            book_ids=[c['id'] for c in candidates],
        )
    except Exception:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text='⚠️ Опрос создан, но не удалось сохранить его в базу. Запиши ID опроса вручную.',
        )


async def pollResults(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    reply = update.message.reply_to_message
    if not reply or not reply.poll:
        await update.message.reply_text('Реплайни на сообщение с опросом.')
        return

    poll = reply.poll
    options = [
        {'option_index': i, 'votes_count': opt.voter_count}
        for i, opt in enumerate(poll.options)
    ]

    try:
        result = api_client.save_poll_results(
            telegram_poll_id=poll.id,
            total_voters=poll.total_voter_count,
            options=options,
        )
        winner = result.get('winner')
        total = result.get('total_voters', poll.total_voter_count)
        if winner:
            username = f'@{winner["added_by_username"]}' if winner['added_by_username'] else 'Участник'
            await update.message.reply_text(
                f'Что мы читаем дальше:\n'
                f'«{winner["title"]}», {winner["author"]}\n\n'
                f'{username}, за твою книгу проголосовали {winner["votes"]} человек!\n'
                f'Всего в голосовании приняли участие {total} человек.'
            )
        else:
            await update.message.reply_text('Результаты сохранены!')
    except Exception:
        await update.message.reply_text('Не удалось сохранить результаты. Может, попробовать ещё раз? Или позовите админа!')
