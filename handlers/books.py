import re
import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import ContextTypes

import api_client


def _fetch_bytes(url: str) -> bytes | None:
    try:
        r = httpx.get(url, timeout=10, follow_redirects=True)
        return r.content if r.status_code == 200 else None
    except Exception:
        return None

COVER_GOOGLE = 'cover_g'
COVER_LITRES = 'cover_l'
COVER_SKIP = 'cover_skip'


def _url_from_callback(source: str, ref_id: str) -> str | None:
    if source == COVER_GOOGLE:
        return f'http://books.google.com/books/content?id={ref_id}&printsec=frontcover&img=1&zoom=0&source=gbs_api'
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
        result = api_client.add_book(
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
        await _send_cover_options(update, book_id)
    except Exception:
        await update.message.reply_text('Не удалось добавить книгу. Попробуй ещё раз.')


def _book_label(book: dict) -> str:
    author = f', {book["author"]}' if book.get('author') else ''
    return f'«{book["title"]}»{author}'


async def removeBook(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = ' '.join(context.args).strip() if context.args else ''

    if not query:
        await update.message.reply_text(
            'Напиши /remove и название книги, тогда я смогу убрать книгу из очереди.'
        )
        return

    try:
        matches = api_client.search_books_to_remove(query)
    except Exception:
        await update.message.reply_text('Не удалось найти книгу. Попробуй ещё раз.')
        return

    if not matches:
        try:
            my_books = api_client.get_member_books(update.effective_user.id, update.effective_user.username)
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
        books = api_client.get_member_books(update.effective_user.id, update.effective_user.username)
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


async def _send_cover_options(update: Update, book_id: int) -> None:
    try:
        found = api_client.get_book_covers(book_id)
    except Exception:
        return
    if not found:
        return

    skip_btn = InlineKeyboardButton('❌', callback_data=f'{COVER_SKIP}:{book_id}')

    photos = [(_fetch_bytes(c['url']), c) for c in found]
    photos = [(img, c) for img, c in photos if img]
    if not photos:
        return

    try:
        if len(photos) == 1:
            img, c = photos[0]
            buttons = InlineKeyboardMarkup([[
                InlineKeyboardButton('Берём', callback_data=f'{c["source"]}:{book_id}:{c["ref_id"]}'),
                skip_btn,
            ]])
            await update.message.reply_photo(photo=img, reply_markup=buttons)
        else:
            media = [InputMediaPhoto(media=img, caption=str(i + 1)) for i, (img, _) in enumerate(photos)]
            await update.message.reply_media_group(media=media)
            number_btns = [
                InlineKeyboardButton(str(i + 1), callback_data=f'{c["source"]}:{book_id}:{c["ref_id"]}')
                for i, (_, c) in enumerate(photos)
            ]
            buttons = InlineKeyboardMarkup([number_btns + [skip_btn]])
            await update.message.reply_text('Выбери обложку:', reply_markup=buttons)
    except Exception:
        return


async def coverCallback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    parts = query.data.split(':', 2)
    source = parts[0]

    if source == COVER_SKIP:
        await query.edit_message_text('Без обложки, окей.')
        return

    _, book_id_str, ref_id = parts
    cover_url = _url_from_callback(source, ref_id)
    if not cover_url:
        await query.edit_message_text('Не удалось определить обложку.')
        return

    try:
        api_client.save_cover_url(int(book_id_str), cover_url)
        await query.edit_message_text('Обложка сохранена.')
    except Exception:
        await query.edit_message_text('Не удалось сохранить обложку. Попробуй ещё раз.')


async def removeBookCallback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    data = query.data  # 'remove:{book_id}' or 'remove:cancel'
    _, payload = data.split(':', 1)

    if payload == 'cancel':
        await query.edit_message_text('Отменено.')
        return

    try:
        found = api_client.remove_book(book_id=int(payload))
        if found:
            await query.edit_message_text('Книга удалена из списка.')
        else:
            await query.edit_message_text('Книга не найдена — возможно, уже удалена.')
    except Exception:
        await query.edit_message_text('Не удалось удалить книгу. Попробуй ещё раз.')
