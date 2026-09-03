import asyncio
import os
import httpx
from dotenv import load_dotenv

load_dotenv()

_API_URL = os.getenv('API_URL', 'http://localhost:8000')
_BOT_URL = f'{_API_URL}/api/bot'
_HEADERS = {'x-bot-secret': os.getenv('BOT_SECRET', '')}
_TIMEOUT = httpx.Timeout(30.0)

# httpx's sync client is used (not httpx.AsyncClient) but every call below
# is offloaded via asyncio.to_thread — otherwise a blocking network call
# here would freeze the bot's single event loop for every other update
# (including totally unrelated commands) until it returns. See
# handlers/books.py's cover-search flow for why this bit us in practice.


async def get_poll_candidates(n: int = 4) -> list:
    response = await asyncio.to_thread(
        httpx.get,
        f'{_BOT_URL}/poll-candidates',
        params={'n': n},
        headers=_HEADERS,
        timeout=_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


async def add_book(title: str, author_name: str, telegram_id: int,
                    telegram_username: str | None = None, telegram_fullname: str | None = None) -> dict:
    response = await asyncio.to_thread(
        httpx.post,
        f'{_BOT_URL}/books',
        json={
            'title': title,
            'author_name': author_name,
            'telegram_id': telegram_id,
            'telegram_username': telegram_username,
            'telegram_fullname': telegram_fullname,
        },
        headers=_HEADERS,
        timeout=_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()  # {'ok': True} или {'exists': True, 'existing_title': '...'}


async def save_poll_results(telegram_poll_id: str, total_voters: int, options: list[dict]) -> dict:
    response = await asyncio.to_thread(
        httpx.post,
        f'{_BOT_URL}/polls/results',
        json={
            'telegram_poll_id': telegram_poll_id,
            'total_voters': total_voters,
            'options': options,
        },
        headers=_HEADERS,
        timeout=_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


async def get_member_books(telegram_id: int, telegram_username: str | None = None) -> list[dict]:
    params = {}
    if telegram_username:
        params['telegram_username'] = telegram_username
    response = await asyncio.to_thread(
        httpx.get,
        f'{_BOT_URL}/members/{telegram_id}/books',
        params=params,
        headers=_HEADERS,
        timeout=_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


async def search_books_to_remove(q: str) -> list[dict]:
    response = await asyncio.to_thread(
        httpx.get,
        f'{_BOT_URL}/books/search',
        params={'q': q},
        headers=_HEADERS,
        timeout=_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


async def create_poll(stage: int, date: str, telegram_poll_id: str, book_ids: list[int], parent_poll_id: int | None = None) -> dict:
    response = await asyncio.to_thread(
        httpx.post,
        f'{_BOT_URL}/polls',
        json={
            'stage': stage,
            'date': date,
            'telegram_poll_id': telegram_poll_id,
            'book_ids': book_ids,
            'parent_poll_id': parent_poll_id,
        },
        headers=_HEADERS,
        timeout=_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


async def get_recently_read(n: int = 5) -> list[dict]:
    response = await asyncio.to_thread(
        httpx.get, f'{_BOT_URL}/books/recently-read', params={'n': n}, headers=_HEADERS, timeout=_TIMEOUT
    )
    response.raise_for_status()
    return response.json()


async def save_discussion_url(book_id: int, discussion_url: str) -> None:
    response = await asyncio.to_thread(
        httpx.put,
        f'{_BOT_URL}/books/{book_id}/discussion_url',
        json={'discussion_url': discussion_url},
        headers=_HEADERS,
        timeout=_TIMEOUT,
    )
    response.raise_for_status()


async def get_books_without_cover() -> list[dict]:
    response = await asyncio.to_thread(
        httpx.get, f'{_BOT_URL}/books/without-cover', headers=_HEADERS, timeout=_TIMEOUT
    )
    response.raise_for_status()
    return response.json()


async def get_book_covers(book_id: int) -> list[dict]:
    response = await asyncio.to_thread(
        httpx.get,
        f'{_BOT_URL}/books/{book_id}/covers',
        headers=_HEADERS,
        timeout=_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


async def save_cover_url(book_id: int, cover_url: str) -> None:
    response = await asyncio.to_thread(
        httpx.put,
        f'{_BOT_URL}/books/{book_id}/cover_url',
        json={'cover_url': cover_url},
        headers=_HEADERS,
        timeout=_TIMEOUT,
    )
    response.raise_for_status()


async def save_cover_bytes(book_id: int, image_bytes: bytes, content_type: str = 'image/jpeg') -> None:
    response = await asyncio.to_thread(
        httpx.put,
        f'{_BOT_URL}/books/{book_id}/cover',
        content=image_bytes,
        headers={**_HEADERS, 'Content-Type': content_type},
        timeout=_TIMEOUT,
    )
    response.raise_for_status()


async def remove_book(book_id: int) -> bool:
    response = await asyncio.to_thread(
        httpx.delete,
        f'{_BOT_URL}/books/{book_id}',
        headers=_HEADERS,
        timeout=_TIMEOUT,
    )
    response.raise_for_status()
    return response.json().get('found', False)
