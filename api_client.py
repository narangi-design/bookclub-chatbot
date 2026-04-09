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
