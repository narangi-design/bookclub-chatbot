import asyncio
import os
from datetime import datetime, timezone

from telegram import Bot, Update
from telegram.ext import ContextTypes

import api_client

_FRONTEND_URL = os.getenv('FRONTEND_URL', '').rstrip('/')
_TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')

_ERROR_TEXT = 'Не удалось получить данные опроса. Попробуй ещё раз или позови админа.'
_CATEGORY_LABELS = {'favorite': 'Книга года', 'least_favorite': 'Антикнига года'}


def _survey_link() -> str:
    return f'{_FRONTEND_URL}/survey' if _FRONTEND_URL else '/survey'


def _results_link() -> str:
    return f'{_FRONTEND_URL}/survey/results' if _FRONTEND_URL else '/survey/results'


def _format_date(iso: str) -> str:
    return datetime.fromisoformat(iso).strftime('%d.%m.%Y')


def _tiebreak_invite_text(categories: list[str], deadline_iso: str) -> str:
    lines = ['⚖️ Ничья! Нужен второй тур:']
    for category in categories:
        label = _CATEGORY_LABELS.get(category, category)
        lines.append(f'— «{label}»')
    lines.append(f'\nГолосуем до {_format_date(deadline_iso)}')
    lines.append(_survey_link())
    return '\n'.join(lines)


async def surveyStart(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        meta = await api_client.get_survey_meta()
    except Exception:
        await update.message.reply_text(_ERROR_TEXT)
        return

    text = (
        f'🏆 Стартовала премия «Книга года {meta["year"]}»!\n\n'
        f'Отмечай любимые и нелюбимые книги года, отвечай на пару вопросов и делись мыслями в открытом '
        f'обращении — ответ можно менять сколько угодно раз до {_format_date(meta["deadline"])}.\n\n'
        f'{_survey_link()}'
    )
    await update.message.reply_text(text)


async def finalizeSurvey(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """/finalize — triggers the same aggregation as running finalize_survey.py
    by hand (via POST /api/bot/survey/finalize), then announces the outcome.
    Safe to run more than once — the backend is idempotent."""
    try:
        result = await api_client.finalize_survey()
    except Exception:
        await update.message.reply_text(_ERROR_TEXT)
        return

    status = result['status']

    if status == 'pending_tiebreaks':
        try:
            tiebreaks = await api_client.get_survey_tiebreaks()
        except Exception:
            await update.message.reply_text(_ERROR_TEXT)
            return
        unresolved = [tb for tb in tiebreaks if not tb['resolved'] and tb['category'] in result['unresolved_categories']]
        if unresolved:
            await update.message.reply_text(_tiebreak_invite_text(
                [tb['category'] for tb in unresolved], unresolved[0]['deadline'],
            ))
        else:
            await update.message.reply_text('Есть незакрытый тай-брейк — дождись его дедлайна и запусти close_tiebreak.py.')
        return

    if status == 'already_closed':
        await update.message.reply_text(f'🎉 Итоги премии подведены!\n\n{_results_link()}')
        return

    # status == 'finalized' — just computed for the first time by this call.
    if result['tiebreak_categories_opened']:
        await update.message.reply_text(_tiebreak_invite_text(result['tiebreak_categories_opened'], result['tiebreak_deadline']))
        return

    await update.message.reply_text(f'🎉 Итоги премии подведены!\n\n{_results_link()}')


async def announceDeadlineWhenReached(bot: Bot) -> None:
    """Fire-and-forget background task started once at process startup:
    sleeps until SURVEY_DEADLINE, then posts to the club chat that
    submissions closed and /finalize is ready to run.

    A plain asyncio timer rather than PTB's JobQueue — this bot runs
    webhook-driven (see CLAUDE.md), never calling Application.start(), which
    is what actually starts JobQueue's scheduler; a bare asyncio.sleep needs
    nothing extra and just recomputes the remaining time on every restart.
    If the process happens to restart exactly after the deadline has already
    passed, this deliberately stays quiet instead of re-announcing — anyone
    can still run /finalize by hand regardless.
    """
    if not _TELEGRAM_CHAT_ID:
        return
    try:
        meta = await api_client.get_survey_meta()
    except Exception:
        return
    if meta['is_closed']:
        return

    deadline = datetime.fromisoformat(meta['deadline'])
    seconds = (deadline - datetime.now(timezone.utc)).total_seconds()
    if seconds <= 0:
        return

    await asyncio.sleep(seconds)
    await bot.send_message(
        chat_id=_TELEGRAM_CHAT_ID,
        text=(
            'Приём ответов на премию «Книга года» завершён!\n\n'
            'Когда будете готовы подвести итоги — отправьте /finalize.'
        ),
    )
