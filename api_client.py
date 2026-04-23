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


def add_book(title: str, author_name: str, telegram_id: int) -> dict:
    response = httpx.post(
        f'{_BOT_URL}/books',
        json={'title': title, 'author_name': author_name, 'telegram_id': telegram_id},
        headers=_HEADERS,
    )
    response.raise_for_status()
    return response.json()


def remove_book(title: str) -> bool:
    response = httpx.delete(
        f'{_BOT_URL}/books',
        params={'title': title},
        headers=_HEADERS,
    )
    response.raise_for_status()
    return response.json().get('found', False)
