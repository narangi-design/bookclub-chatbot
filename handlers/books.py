import asyncio
import logging
import re
import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import ContextTypes

import api_client

logger = logging.getLogger(__name__)

# Telegram caps sendMediaGroup at 10 items — cover_search.py can return more
# candidates than that, so the list needs trimming before it gets there.
MAX_MEDIA_GROUP_SIZE = 10


async def _fetch_bytes(url: str) -> bytes | None:
    try:
        r = await asyncio.to_thread(httpx.get, url, timeout=10, follow_redirects=True)
        if r.status_code == 200:
            return r.content
        logger.warning('Cover fetch %s returned status %s', url, r.status_code)
        return None
    except Exception:
        logger.warning('Cover fetch %s failed', url, exc_info=True)
        return None

COVER_GOOGLE = 'cover_g'
COVER_LITRES = 'cover_l'
COVER_SKIP = 'cover_skip'
COVER_UPLOAD_CANCEL = 'cover_upload_cancel'
REMOVE = 'remove'


def _url_from_callback(source: str, ref_id: str) -> str | None:
    if source == COVER_GOOGLE:
        return f'https://books.google.com/books/content?id={ref_id}&printsec=frontcover&img=1&zoom=0&source=gbs_api'
    if source == COVER_LITRES:
        return f'https://www.litres.ru/pub/c/cover/{ref_id}.jpg'
    return None

HELP_TEXT = (
    'Пиши /add, пробел и что-то из этого:\n'
    '🔸Имя Фамилия — Название книги\n'
    '🔸Имя Фамилия, .., Имя Фамилия (и т.д.) — Название книги\n'
    '🔸Имя и Имя Фамилия — Название книги\n'
    '🔸Имя, Имя, ... и Имя Фамилия — Название книги\n\n'
    'P.S. Тирешки, минусы, дефисы — можно. 🤓'
)

# Разделитель: em-dash, en-dash или дефис с пробелами
_SEPARATOR = re.compile(r'^(.+?)(?:\s*[—–]\s*|\s+-\s+)(.+)$')


async def addBook(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = ' '.join(context.args).strip() if context.args else ''
    match = _SEPARATOR.match(text)

    if not match:
        await update.message.reply_text(HELP_TEXT)
        return

    author_name = match.group(1).strip()
    title = match.group(2).strip()
    tg_user = update.effective_user

    try:
        result = await api_client.add_book(
            title=title,
            author_name=author_name,
            telegram_id=tg_user.id,
            telegram_username=tg_user.username,
            telegram_fullname=tg_user.full_name,
        )
        if result.get('exists'):
            await update.message.reply_text(
                f'Похоже, книга «{result["existing_title"]}» уже есть в списке.'
            )
            return
        name = tg_user.first_name or tg_user.username or 'друг'
        book_id = result['book_id']
        await update.message.reply_text(
            f'Книга теперь в списке, {name}!\n'
            f'Название: «{title}»\n'
            f'Автор: {author_name}\n\n'
            f'Удачи на голосовании. 😈'
        )
        # coverCallback reads this to name the book in its reply — without it,
        # it falls back to "#<id>" (pickCoverCallback sets the same key for
        # the /cover flow; addBook needs its own since it calls
        # _send_cover_options directly, skipping that handler).
        context.user_data['cover_book_title'] = f'«{title}»'
        await _send_cover_options(update.message, book_id)
    except Exception:
        await update.message.reply_text('Не удалось добавить книгу. Попробуй ещё раз.')


def _book_label(book: dict) -> str:
    author = f', {book["author_name"]}' if book.get('author_name') else ''
    return f'«{book["title"]}»{author}'


def _label_from_keyboard(query, callback_data: str) -> str | None:
    if not query.message.reply_markup:
        return None
    for row in query.message.reply_markup.inline_keyboard:
        for button in row:
            if button.callback_data == callback_data:
                return button.text
    return None


def _title_from_label(label: str) -> str:
    m = re.search(r'(«.+?»)', label)
    return m.group(1) if m else label


async def removeBook(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = ' '.join(context.args).strip() if context.args else ''

    if not query:
        await update.message.reply_text(
            'Напиши /remove и название книги, тогда я смогу убрать книгу из очереди.'
        )
        return

    try:
        matches = await api_client.search_books_to_remove(query)
    except Exception:
        await update.message.reply_text('Не удалось найти книгу. Попробуй ещё раз.')
        return

    if not matches:
        try:
            my_books = await api_client.get_member_books(update.effective_user.id, update.effective_user.username)
        except Exception:
            my_books = []

        if my_books:
            book_list = '\n'.join(_book_label(b) for b in my_books)
            text = (
                'Кажется, в списке нет такой книги.\n'
                'На всякий случай вот список книг, предложенных тобой:\n'
                f'{book_list}'
            )
        else:
            text = 'Кажется, в списке нет такой книги.'
        await update.message.reply_text(text)
        return

    buttons = [
        [InlineKeyboardButton(_book_label(b), callback_data=f'remove:{b["id"]}')]
        for b in matches
    ]
    buttons.append([InlineKeyboardButton('❌ Отмена', callback_data='remove:cancel')])

    text = 'Выбери книгу:' if len(matches) > 1 else 'Нашёл книгу:'
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))


async def myBooks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        books = await api_client.get_member_books(update.effective_user.id, update.effective_user.username)
    except Exception:
        await update.message.reply_text('Не удалось получить список книг. Попробуй ещё раз.')
        return

    ps = 'P.S. Хочешь ещё что-нибудь добавить? Пиши в чат /add, там сказано как.'

    if not books:
        await update.message.reply_text(
            'Кажется, в списке клуба от тебя ничего нет.\n\n'
            'P.S. Может, добавим? Напиши в чат /add, там сказано как.'
        )
        return

    if len(books) == 1:
        await update.message.reply_text(
            f'От тебя только одна книга в предложке: {_book_label(books[0])}.\n\n{ps}'
        )
        return

    book_list = '\n'.join(_book_label(b) for b in books)
    await update.message.reply_text(
        f'Вот список книг, предложенных тобой для чтения:\n{book_list}\n\n{ps}'
    )


async def _send_cover_options(message, book_id: int) -> bool:
    try:
        found = await api_client.get_book_covers(book_id)
    except Exception:
        logger.warning('get_book_covers(%s) failed', book_id, exc_info=True)
        return False
    if not found:
        return False

    # Telegram rejects sendMediaGroup outright above MAX_MEDIA_GROUP_SIZE
    # items — trim before fetching so we're not also downloading covers
    # (each potentially 1MB+) that could never be sent anyway.
    found = found[:MAX_MEDIA_GROUP_SIZE]

    skip_btn = InlineKeyboardButton('❌', callback_data=f'{COVER_SKIP}:{book_id}')

    # Concurrent, not sequential — 10 sequential fetches at ~1-2s each
    # (litres.ru's anti-bot layer adds real per-request latency) used to
    # mean a 10-20s wait; in parallel it's bounded by the slowest one.
    fetched = await asyncio.gather(*(_fetch_bytes(c['url']) for c in found))
    photos = [(img, c) for img, c in zip(fetched, found) if img]
    if not photos:
        return False

    if len(photos) == 1:
        img, c = photos[0]
        buttons = InlineKeyboardMarkup([[
            InlineKeyboardButton('Берём', callback_data=f'{c["source"]}:{book_id}:{c["ref_id"]}'),
            skip_btn,
        ]])
        try:
            await message.reply_photo(photo=img, reply_markup=buttons)
        except Exception:
            logger.warning('reply_photo failed for book %s', book_id, exc_info=True)
            return False
    else:
        media = [InputMediaPhoto(media=img, caption=str(i + 1)) for i, (img, _) in enumerate(photos)]
        try:
            await message.reply_media_group(media=media)
        except Exception:
            # Non-fatal: the numbered buttons below still let the user pick
            # a cover by number even if the preview images failed to send —
            # but log it, this used to fail silently.
            logger.warning('reply_media_group failed for book %s (%d photos)', book_id, len(media), exc_info=True)
        number_btns = [
            InlineKeyboardButton(str(i + 1), callback_data=f'{c["source"]}:{book_id}:{c["ref_id"]}')
            for i, (_, c) in enumerate(photos)
        ]
        buttons = InlineKeyboardMarkup([number_btns + [skip_btn]])
        try:
            await message.reply_text('Выбери обложку:', reply_markup=buttons)
        except Exception:
            logger.warning('reply_text (cover picker) failed for book %s', book_id, exc_info=True)
            return False
    return True


PICK_COVER = 'pick_cover'
PICK_DISCUSSION = 'pick_disc'


async def addDiscussion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    reply = update.message.reply_to_message
    if not reply:
        try:
            books = await api_client.get_recently_read(n=5)
        except Exception:
            await update.message.reply_text(
                'Не удалось получить список книг без ссылки на заседание.\n'
                'Если хочешь добавить ссылку, напиши эту команду реплаем на запись дискуссии.'
            )
            return
        if not books:
            await update.message.reply_text('Все недавно прочитанные книги уже с записью заседания 🎉')
            return
        book_list = '\n'.join(f'· {_book_label(b)}' for b in books)
        await update.message.reply_text(
            f'Реплайни на сообщение с записью заседания.\n\n'
            f'Книги без записи:\n{book_list}'
        )
        return

    chat_id = update.effective_chat.id
    short_id = str(chat_id)[4:]
    discussion_url = f'https://t.me/c/{short_id}/{reply.message_id}'

    try:
        books = await api_client.get_recently_read(n=5)
    except Exception:
        await update.message.reply_text('Не удалось получить список книг. Попробуй ещё раз.')
        return

    if not books:
        await update.message.reply_text('Нет недавно прочитанных книг без записи заседания.')
        return

    buttons = [
        [InlineKeyboardButton(_book_label(b), callback_data=f'{PICK_DISCUSSION}:{b["id"]}')]
        for b in books
    ]
    buttons.append([InlineKeyboardButton('❌ Отмена', callback_data=f'{PICK_DISCUSSION}:cancel')])
    await update.message.reply_text(
        f'К какой книге привязать запись?\n{discussion_url}',
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def pickDiscussionCallback(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    payload = query.data.split(':', 1)[1]
    if payload == 'cancel':
        await query.edit_message_text('Отменено.')
        return

    lines = query.message.text.splitlines()
    discussion_url = lines[-1].strip()
    book_id = int(payload)

    book_title = _title_from_label(_label_from_keyboard(query, query.data) or f'#{book_id}')
    try:
        await api_client.save_discussion_url(book_id, discussion_url)
        await query.edit_message_text(f'Ссылка на запись заседания по книге {book_title} сохранена.')
    except Exception:
        await query.edit_message_text(f'Не удалось сохранить ссылку для книги {book_title}. Попробуй ещё раз.')


async def addCover(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        books = await api_client.get_books_without_cover()
    except Exception:
        await update.message.reply_text('Не удалось получить список книг. Попробуй ещё раз.')
        return

    if not books:
        await update.message.reply_text('У всех книг уже есть обложки.')
        return

    buttons = [
        [InlineKeyboardButton(_book_label(b), callback_data=f'{PICK_COVER}:{b["id"]}')]
        for b in books
    ]
    await update.message.reply_text('Выбери книгу для добавления обложки:', reply_markup=InlineKeyboardMarkup(buttons))


async def pickCoverCallback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    book_id = int(query.data.split(':', 1)[1])
    context.user_data['cover_book_title'] = _title_from_label(_label_from_keyboard(query, query.data) or f'#{book_id}')
    await query.edit_message_text('Ищу обложки...')
    found = await _send_cover_options(query.message, book_id)
    if not found:
        book_title = context.user_data.get('cover_book_title') or f'#{book_id}'
        sent = await query.message.reply_text(
            f'Не получилось найти обложку для книги {book_title}. 🥺\n'
            f'Может, сами закинем? Скинь картинку в ответ на это сообщение.',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton('Давай не сейчас', callback_data=COVER_UPLOAD_CANCEL)
            ]]),
        )
        context.bot_data[f'pending_cover_{sent.message_id}'] = {
            'book_id': book_id,
            'book_title': book_title,
        }


async def coverCallback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    parts = query.data.split(':', 2)
    source = parts[0]

    if source == COVER_SKIP:
        try:
            await query.edit_message_text('Без обложки, окей.')
        except Exception:
            try:
                await query.edit_message_caption('Без обложки, окей.')
            except Exception:
                await query.message.reply_text('Без обложки, окей.')
        return

    _, book_id_str, ref_id = parts
    cover_url = _url_from_callback(source, ref_id)
    if not cover_url:
        await query.edit_message_text('Не удалось определить обложку.')
        return

    async def _reply(text: str) -> None:
        try:
            await query.edit_message_text(text)
        except Exception:
            try:
                await query.edit_message_caption(text)
            except Exception:
                await query.message.reply_text(text)

    book_title = context.user_data.get('cover_book_title') or f'#{book_id_str}'
    try:
        await api_client.save_cover_url(int(book_id_str), cover_url)
        await _reply(f'{book_title} теперь с обложкой!')
    except Exception:
        await _reply(f'Не удалось сохранить обложку для книги {book_title}. Попробуй ещё раз.')


async def removeBookCallback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    data = query.data  # 'remove:{book_id}' or 'remove:cancel'
    _, payload = data.split(':', 1)

    if payload == 'cancel':
        await query.edit_message_text('Отменено.')
        return

    try:
        found = await api_client.remove_book(book_id=int(payload))
        if found:
            await query.edit_message_text('Книга удалена из списка.')
        else:
            await query.edit_message_text('Книга не найдена — возможно, уже удалена.')
    except Exception:
        await query.edit_message_text('Не удалось удалить книгу. Попробуй ещё раз.')


async def uploadCoverPhoto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    if not msg.photo or not msg.reply_to_message:
        return

    pending_key = f'pending_cover_{msg.reply_to_message.message_id}'
    pending = context.bot_data.get(pending_key)
    if not pending:
        return

    book_id: int = pending['book_id']
    book_title: str = pending['book_title']

    photo_file = await msg.photo[-1].get_file()
    image_bytes = bytes(await photo_file.download_as_bytearray())

    try:
        await api_client.save_cover_bytes(book_id, image_bytes, 'image/jpeg')
        await msg.reply_text(f'{book_title} теперь с обложкой!')
        del context.bot_data[pending_key]
    except Exception:
        await msg.reply_text(f'Не удалось сохранить обложку для книги {book_title}. Попробуй ещё раз.')


async def cancelCoverUploadCallback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    pending_key = f'pending_cover_{query.message.message_id}'
    pending = context.bot_data.pop(pending_key, {})
    book_title = pending.get('book_title', 'книга')
    await query.edit_message_text(f'Окей, {book_title} пока без обложки.')
