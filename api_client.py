import os
import httpx
from dotenv import load_dotenv

load_dotenv()

_API_URL = os.getenv('API_URL', 'http://localhost:8000')
_BOT_URL = f'{_API_URL}/api/bot'
_HEADERS = {'x-bot-secret': os.getenv('BOT_SECRET', '')}


def get_poll_candidates(n: int = 4) -> list:
    response = httpx.get(
        f'{_BOT_URL}/poll-candidates',
        params={'n': n},
        headers=_HEADERS,
    )
    response.raise_for_status()
    return response.json()


def add_book(title: str, author_name: str, telegram_id: int,
             telegram_username: str | None = None, telegram_fullname: str | None = None) -> dict:
    response = httpx.post(
        f'{_BOT_URL}/books',
        json={
            'title': title,
            'author_name': author_name,
            'telegram_id': telegram_id,
            'telegram_username': telegram_username,
            'telegram_fullname': telegram_fullname,
        },
        headers=_HEADERS,
    )
    response.raise_for_status()
    return response.json()  # {'ok': True} или {'exists': True, 'existing_title': '...'}


def create_poll(stage: int, date: str, telegram_poll_id: str, book_ids: list[int]) -> dict:
    response = httpx.post(
        f'{_BOT_URL}/polls',
        json={
            'stage': stage,
            'date': date,
            'telegram_poll_id': telegram_poll_id,
            'book_ids': book_ids,
        },
        headers=_HEADERS,
    )
    response.raise_for_status()
    return response.json()


def save_poll_results(telegram_poll_id: str, total_voters: int, options: list[dict]) -> dict:
    response = httpx.post(
        f'{_BOT_URL}/polls/results',
        json={
            'telegram_poll_id': telegram_poll_id,
            'total_voters': total_voters,
            'options': options,
        },
        headers=_HEADERS,
    )
    response.raise_for_status()
    return response.json()


def get_member_books(telegram_id: int) -> list[dict]:
    response = httpx.get(
        f'{_BOT_URL}/members/{telegram_id}/books',
        headers=_HEADERS,
    )
    response.raise_for_status()
    return response.json()


def search_books_to_remove(q: str) -> list[dict]:
    response = httpx.get(
        f'{_BOT_URL}/books/search',
        params={'q': q},
        headers=_HEADERS,
    )
    response.raise_for_status()
    return response.json()


def remove_book(book_id: int) -> bool:
    response = httpx.delete(
        f'{_BOT_URL}/books/{book_id}',
        headers=_HEADERS,
    )
    response.raise_for_status()
    return response.json().get('found', False)
