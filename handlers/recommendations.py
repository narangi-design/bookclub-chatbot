import logging
import os

from telegram import Update, User, ReactionTypeEmoji
from telegram.ext import ContextTypes

import api_client

logger = logging.getLogger(__name__)

_TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')

# ✍ на исходном сообщении — метка «уже сохранено»; 👌 на команде — «сработало»
SAVED_REACTION = '✍'
DONE_REACTION = '👌'

RECOMMEND_HELP = (
    'Ответь командой /recommend на сообщение с рекомендацией — '
    'и я сохраню его в список рекомендаций на сайте.'
)


def _user_payload(user: User) -> dict:
    return {
        'telegram_id': user.id,
        'telegram_username': user.username,
        'telegram_fullname': user.full_name,
    }


async def addRecommendation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    # Только клубный чат: иначе любой мог бы наполнять список из лички или чужой группы
    if _TELEGRAM_CHAT_ID and str(update.effective_chat.id) != _TELEGRAM_CHAT_ID:
        await msg.reply_text('Рекомендации сохраняю только из чата клуба.')
        return

    target = msg.reply_to_message
    if not target:
        await msg.reply_text(RECOMMEND_HELP)
        return

    # Фото с подписью — берём подпись; сами картинки не сохраняем
    text = target.text or target.caption
    if not text:
        await msg.reply_text('В этом сообщении нет текста — сохранять нечего.')
        return

    # Автор — тот, кто отправил сообщение в чат (для пересланных — кто переслал)
    author = target.from_user
    if author is None or author.is_bot:
        await msg.reply_text('Сообщения ботов в рекомендации не сохраняю.')
        return

    entities = target.entities if target.text else target.caption_entities
    try:
        created = await api_client.add_recommendation(
            chat_id=update.effective_chat.id,
            message_id=target.message_id,
            text=text,
            entities=[e.to_dict() for e in entities],
            message_date=target.date.isoformat(),
            author=_user_payload(author),
            saved_by=_user_payload(update.effective_user),
        )
    except Exception:
        logger.warning('add_recommendation failed for message %s', target.message_id, exc_info=True)
        await msg.reply_text('Не удалось сохранить рекомендацию. Попробуй ещё раз.')
        return

    if not created:
        await msg.reply_text('Это сообщение уже в рекомендациях 👌')
        return

    # Реакции вместо ответа — меньше шума в чате. Если реакции в чате
    # ограничены — отвечаем текстом.
    try:
        await target.set_reaction(ReactionTypeEmoji(SAVED_REACTION))
        await msg.set_reaction(ReactionTypeEmoji(DONE_REACTION))
    except Exception:
        logger.info('set_reaction failed for message %s, replying instead', target.message_id, exc_info=True)
        await msg.reply_text('Сохранил в рекомендации 👌')
