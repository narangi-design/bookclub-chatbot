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



def _format_book(book: dict) -> str:
    label = f'«{book["title"]}»'
    if author := book.get("author_name"):
        label += f", {author}"
    if member := book.get("member_display_name"):
        label += f" — {member}"
    return label

def _poll_options(books: list[dict]) -> list[str]:
    return [_format_book(book) for book in books]



async def createPollTest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    candidates = mock_db.get_poll_candidates(n=4)
    if not candidates:
        await update.message.reply_text('Нет книг для голосования.')
        return
    chat_title = update.effective_chat.title or 'клуб'
    await _send_poll(update, context, f'Выбираем следующую книгу, {chat_title}!', _poll_options(candidates))


async def createPoll(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    candidates = await api_client.get_poll_candidates(n=12)
    if not candidates:
        await update.message.reply_text('Нет книг для голосования. Сначала кто-нибудь должен предложить книги командой /add.')
        return
    chat_title = update.effective_chat.title or 'клуб'
    msg = await _send_poll(update, context, f'Выбираем следующую книгу, {chat_title}!', _poll_options(candidates))
    try:
        await api_client.create_poll(
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



def _poll_vote_options(tg_poll) -> list[dict]:
    return [{'option_index': i, 'votes_count': opt.voter_count} for i, opt in enumerate(tg_poll.options)]



async def secondRound(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    reply = update.message.reply_to_message
    if not reply or not reply.poll:
        await update.message.reply_text('Реплайни на сообщение с опросом первого тура.')
        return

    poll = reply.poll
    try:
        result = await api_client.save_poll_results(
            telegram_poll_id=poll.id,
            total_voters=poll.total_voter_count,
            options=_poll_vote_options(poll),
        )
    except Exception:
        await update.message.reply_text('Не нашёл опрос в базе. Убедись, что опрос был создан через бота.')
        return

    tied_books = result.get('tied_books')
    if not tied_books:
        await update.message.reply_text('Но нам не нужен второй тур, книгу уже выбрали. 🤔')
        return

    parent_poll_id = result.get('poll_id')
    msg = await _send_poll(
        update, context,
        'Клуб, у нас второй тур голосования, выбираем один вариант.',
        _poll_options(tied_books),
        allows_multiple_answers=False,
    )
    try:
        await api_client.create_poll(
            stage=2,
            date=date.today().isoformat(),
            telegram_poll_id=msg.poll.id,
            book_ids=[b['id'] for b in tied_books],
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
    try:
        result = await api_client.save_poll_results(
            telegram_poll_id=poll.id,
            total_voters=poll.total_voter_count,
            options=_poll_vote_options(poll),
        )
        winner = result.get('winner')
        tied_books = result.get('tied_books')
        total = result.get('total_voters', poll.total_voter_count)
        if winner:
            member = (
                f'@{winner["member_username"]}' if winner.get('member_username')
                else winner.get('member_fullname') or 'Участник'
            )
            added_at = ''
            if winner.get('added_at'):
                d = winner['added_at'][:10].split('-')
                added_at = f'\nЖдёт своего часа с: {d[2]}.{d[1]}.{d[0][2:]}'
            appearances = winner.get('poll_appearances') or 0
            text = (
                f'Голосование завершено!\n\n'
                f'Выбор клуба: «{winner["book_title"]}», {winner["author_name"]}\n'
                f'В списке благодаря: {member}'
                f'{added_at}\n'
                f'Голосований пройдено: {appearances}\n'
                f'{winner["votes"]} из {total} голосов'
            )
            cover_url = winner.get('cover_url')
            if cover_url:
                await update.message.reply_photo(photo=cover_url, caption=text)
            else:
                await update.message.reply_text(text)
        elif tied_books:
            titles = ', '.join(f'«{b["title"]}»' for b in tied_books)
            await update.message.reply_text(f'Ничья: {titles}. Нужен второй тур — запускай /second_round.')
        else:
            await update.message.reply_text('Результаты сохранены!')
    except Exception:
        await update.message.reply_text('Не удалось сохранить результаты. Может, попробовать ещё раз? Или позови админа!')
