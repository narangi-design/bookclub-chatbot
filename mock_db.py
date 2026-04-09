# Временная реализация на основе fixtures.
# Когда бэкенд будет готов — каждая функция заменяется на вызов api_client.
from tests.fixtures import (
    authors as _authors,
    members as _members,
    books as _books,
    get_author_by_id,
    get_books_by_status,
    get_book_by_title,
    author_name_exists,
)

import copy
from datetime import datetime

# Рабочие копии, чтобы тесты не портили друг друга при добавлении/удалении
_books_store = copy.deepcopy(_books)


def get_all_books() -> list:
    return _books_store


def get_to_read_books() -> list:
    return [b for b in _books_store if b["status"] == "to_read"]


def add_book(title: str, author_name: str, member_telegram_id: int) -> dict:
    from tests.fixtures import members, get_member_by_telegram_id
    member = get_member_by_telegram_id(member_telegram_id)
    author = next((a for a in _authors if a["name"].lower() == author_name.lower()), None)

    book = {
        "id": max((b["id"] for b in _books_store), default=0) + 1,
        "title": title,
        "author_id": author["id"] if author else None,
        "country": None,
        "added_by_member_id": member["id"] if member else None,
        "added_at": datetime.now().strftime("%Y-%m-%d"),
        "status": "to_read",
        "elected_poll_id": None,
        "elected_at": None,
        "annotation": None,
        "discussion_url": None,
    }
    _books_store.append(book)
    return book


def get_poll_candidates(n: int = 4) -> list:
    import random
    to_read = [b for b in _books_store if b["status"] == "to_read"]
    sample = random.sample(to_read, min(n, len(to_read)))

    result = []
    for book in sample:
        author = next((a for a in _authors if a["id"] == book["author_id"]), None)
        member = next((m for m in _members if m["id"] == book["added_by_member_id"]), None)

        if member:
            display_name = member["telegram_fullname"] or member["telegram_username"]
        else:
            display_name = "неизвестно"

        result.append({
            "id": book["id"],
            "title": book["title"],
            "author_name": author["name"] if author else "неизвестный автор",
            "member_display_name": display_name,
        })
    return result


def remove_book(title: str) -> bool:
    for book in _books_store:
        if book["title"].lower() == title.lower() and book["status"] != "removed":
            book["status"] = "removed"
            return True
    return False
