import os
from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes

import api_client

_FRONTEND_URL = os.getenv('FRONTEND_URL', '').rstrip('/')

_ERROR_TEXT = 'Не удалось получить данные опроса. Попробуй ещё раз или позови админа.'
_CATEGORY_LABELS = {'favorite': 'Книга года', 'least_favorite': 'Антикнига года'}


def _survey_link() -> str:
    return f'{_FRONTEND_URL}/survey' if _FRONTEND_URL else '/survey'


def _results_link() -> str:
    return f'{_FRONTEND_URL}/survey/results' if _FRONTEND_URL else '/survey/results'


def _format_date(iso: str) -> str:
    return datetime.fromisoformat(iso).strftime('%d.%m.%Y')


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


async def surveyClose(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        meta = await api_client.get_survey_meta()
        award_events = await api_client.get_award_events()
    except Exception:
        await update.message.reply_text(_ERROR_TEXT)
        return

    # award_events only gets a row for this year once close_survey.py has
    # actually run — meta['is_closed'] alone just means the deadline passed,
    # which isn't enough to tell "no tie happened" apart from "nobody's
    # closed the survey yet".
    results_ready = any(e['year'] == meta['year'] for e in award_events)
    if not results_ready:
        await update.message.reply_text('Итоги ещё не посчитаны — сначала нужно запустить close_survey.py на бэкенде.')
        return

    try:
        tiebreaks = await api_client.get_survey_tiebreaks()
    except Exception:
        await update.message.reply_text(_ERROR_TEXT)
        return

    unresolved = [tb for tb in tiebreaks if not tb['resolved']]
    if unresolved:
        lines = ['⚖️ Ничья! Нужен второй тур:']
        for tb in unresolved:
            label = _CATEGORY_LABELS.get(tb['category'], tb['category'])
            lines.append(f'— «{label}» — голосуем до {_format_date(tb["deadline"])}')
        lines.append('')
        lines.append(_survey_link())
        await update.message.reply_text('\n'.join(lines))
        return

    await update.message.reply_text(f'🎉 Итоги премии «Книга года {meta["year"]}» подведены!\n\n{_results_link()}')
