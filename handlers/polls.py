from datetime import date
from telegram import Update
from telegram.ext import ContextTypes

import mock_db
import api_client


async def _send_poll(update: Update, context: ContextTypes.DEFAULT_TYPE, question: str, options: list[str], allows_multiple_answers: bool = True):
    msg = await context.bot.send_poll(
        chat_id=update.effective_chat.id,
        question=question,
        options=options,
        is_anonymous=False,
        allows_multiple_answers=allows_multiple_answers,
        open_period=86400,
    )
    return msg


def _stage1_options(candidates: list) -> list[str]:
    return [
        f'«{c["title"]}», {c["author_name"]} — {c["member_display_name"]}'
        for c in candidates
    ]


async def createPollTest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    candidates = mock_db.get_poll_candidates(n=4)
    if not candidates:
        await update.message.reply_text('Нет книг для голосования.')
        return
    chat_title = update.effective_chat.title or 'клуб'
    await _send_poll(update, context, f'Выбираем следующую книгу, {chat_title}!', _stage1_options(candidates))


async def createPoll(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    candidates = api_client.get_poll_candidates(n=12)
    if not candidates:
        await update.message.reply_text('Нет книг для голосования. Сначала кто-нибудь должен предложить книги командой /add.')
        return
    chat_title = update.effective_chat.title or 'клуб'
    msg = await _send_poll(update, context, f'Выбираем следующую книгу, {chat_title}!', _stage1_options(candidates))
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


async def secondRound(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    reply = update.message.reply_to_message
    if not reply or not reply.poll:
        await update.message.reply_text('Реплайни на сообщение с опросом первого тура.')
        return

    poll = reply.poll
    options = [{'option_index': i, 'votes_count': opt.voter_count} for i, opt in enumerate(poll.options)]

    try:
        result = api_client.save_poll_results(
            telegram_poll_id=poll.id,
            total_voters=poll.total_voter_count,
            options=options,
        )
    except Exception:
        await update.message.reply_text('Не нашёл опрос в базе. Убедись, что опрос был создан через бота.')
        return

    tied_books = result.get('tied_books')
    if not tied_books:
        await update.message.reply_text('Но нам не нужен второй тур, книгу уже выбрали. 🤔')
        return

    books = tied_books
    parent_poll_id = result.get('poll_id')

    options = [
        f'«{b["title"]}», {b["author"]}' if b.get('author') else f'«{b["title"]}»'
        for b in books
    ]
    msg = await _send_poll(
        update, context,
        'Клуб, у нас второй тур голосования, выбираем один вариант.',
        options,
        allows_multiple_answers=False,
    )
    try:
        api_client.create_poll(
            stage=2,
            date=date.today().isoformat(),
            telegram_poll_id=msg.poll.id,
            book_ids=[b['id'] for b in books],
            parent_poll_id=parent_poll_id,
        )
    except Exception:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text='⚠️ Второй тур создан, но не удалось сохранить его в базу. Запиши ID опроса вручную.',
        )


async def pollResults(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
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
        tied_books = result.get('tied_books')
        total = result.get('total_voters', poll.total_voter_count)
        if winner:
            username = f'@{winner["added_by_username"]}' if winner['added_by_username'] else 'Участник'
            await update.message.reply_text(
                f'Что мы читаем дальше:\n'
                f'«{winner["title"]}», {winner["author"]}\n\n'
                f'{username}, за твою книгу проголосовали {winner["votes"]} человек!\n'
                f'Всего в голосовании приняли участие {total} человек.'
            )
        elif tied_books:
            titles = ', '.join(f'«{b["title"]}»' for b in tied_books)
            await update.message.reply_text(f'Ничья: {titles}. Нужен второй тур — запускай /second_round.')
        else:
            await update.message.reply_text('Результаты сохранены!')
    except Exception:
        await update.message.reply_text('Не удалось сохранить результаты. Может, попробовать ещё раз? Или позови админа!')
