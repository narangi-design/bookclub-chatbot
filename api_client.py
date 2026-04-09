import os
import httpx
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv('API_URL', 'http://localhost:8000')


def get_poll_candidates(n: int = 4) -> list:
    response = httpx.get(f'{BASE_URL}/api/poll-candidates', params={'n': n})
    response.raise_for_status()
    return response.json()
