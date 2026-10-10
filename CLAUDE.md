# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Telegram bot for a book club: nominations, voting, cover images, discussion recordings. Deployed via Docker on a private VPS, served by uvicorn, receiving Telegram updates over webhook (not polling). All bot-facing text is in Russian — keep new user-facing strings in Russian, matching the existing tone (casual, emoji-sprinkled).

This bot is one of three related repos and only handles the Telegram layer — it has no database of its own:
- **bookclub-api** — stores and serves all data; this bot calls it via `api_client.py`
- **bookclub-frontend** — web dashboard visualizing the same data

## Commands

```bash
python3 -m pytest -p no:cacheprovider                                   # run all tests (from this dir, no venv on the VPS)
python3 -m pytest -p no:cacheprovider tests/test_books_handlers.py      # single file
python3 -m pytest -p no:cacheprovider tests/test_books_handlers.py::TestRemoveBook::test_no_args_shows_help  # single test
```

**Prod deploy** (this VPS, see the root `../CLAUDE.md`): `cd .. && docker compose build chatbot && docker compose up -d chatbot`. Telegram's webhook points at `https://bot.bookclub.narangi.design` → host nginx → this container.

Env vars (in prod they come from the root `../.env` via `docker-compose.yml`, where `API_URL` is overridden to the internal `http://api:8000`):
```
BOT_TOKEN=
API_URL=https://your-api.example.com
BOT_SECRET=
FRONTEND_URL=https://your-frontend.example.com
TELEGRAM_CHAT_ID=  # club group chat id — deadline announcement target; also limits the welcome message to that chat
```

There is no local polling mode. Running the bot outside prod would need its own public URL + `setWebhook` — and pointing the real bot's webhook elsewhere takes prod offline, so test via the unit tests instead.

## Architecture

**Request flow:** Telegram → webhook POST `/` (`api/index.py`) → single FastAPI `app` served directly by uvicorn → `Update` dispatched through a python-telegram-bot `Application` whose handlers are all registered once in `_build_app()`. The `Application` is built at module import time (not per-request) and lazily `initialize()`d on first webhook call.

**Layering:** `handlers/*.py` (Telegram-facing: parse commands/callbacks, format Russian reply text) → `api_client.py` (thin httpx wrapper over bookclub-api, `x-bot-secret` header auth, 30s timeout) → external API. Handlers never call httpx directly; all backend I/O goes through `api_client`. Each handler function wraps its `api_client` call in try/except and replies with a Russian fallback message on failure — no exceptions should escape a handler.

**Callback data conventions:** Inline keyboard `callback_data` is colon-delimited (`source:book_id:ref_id`, `remove:book_id`, `pick_cover:book_id`, `pick_disc:book_id`) and prefix constants (`REMOVE`, `PICK_COVER`, `PICK_DISCUSSION`, `COVER_*`) are defined in `handlers/books.py` and imported into `api/index.py` to build the `CallbackQueryHandler` patterns — keep new callback prefixes consistent with this and register the pattern in `_build_app()`.

**Stateless-by-design patterns** (see README's "Technical decisions" for the reasoning): cover callback data encodes just enough (`source:book_id:ref_id`) to reconstruct the image URL client-side; the discussion URL is round-tripped through the bot message text itself rather than stored server-side. The one place mutable in-memory state is used is `context.bot_data['pending_cover_<message_id>']`, tracking an outstanding cover-upload-by-photo request between the prompt and the user's photo reply (`MessageHandler(filters.PHOTO & filters.REPLY, uploadCoverPhoto)`).

**Poll flow:** `/create_poll` samples 12 `to_read` books via `api_client.get_poll_candidates`, sends a Telegram poll, then persists it via `api_client.create_poll`. `/results` and `/second_round` both read the `Poll` off `update.message.reply_to_message.poll` and go through the same `api_client.save_poll_results` call (idempotent — safe to call again if votes are already stored) to get back a winner or a tie. `/second_round` only proceeds if the backend reports `tied_books`, creating a `stage=2` poll linked via `parent_poll_id`. Poll option formatting for both stages goes through the shared `_poll_options`/`_format_book` helpers in `handlers/polls.py`.

**Survey flow (Book of the Year, `handlers/survey.py`):** entirely separate from the poll system above — `/survey_start` and `/finalize` just call public/bot-secret `bookclub-api` endpoints (`/api/survey/*`, `POST /api/bot/survey/finalize`) and announce the JSON result; no bot-side state. `/finalize` is safe to run more than once (the backend is idempotent) — its response's `status` (`finalized` | `already_closed` | `pending_tiebreaks`) drives which message goes out. The one bit of actual bot-side logic is `announceDeadlineWhenReached`, an `asyncio.sleep`-based background task started once in `api/index.py`'s FastAPI startup event — not PTB's `JobQueue`, since that needs `Application.start()`, which this webhook-driven bot never calls (only the lazy `initialize()` in the webhook handler). Recomputes the remaining time on every process restart, so a redeploy before `SURVEY_DEADLINE` just reschedules correctly; a restart *after* the deadline stays quiet rather than re-announcing (`/finalize` still works by hand regardless).

**Other handlers:** `handlers/search.py` (`/search` → `GET /api/bot/books/lookup`, all statuses), `handlers/recommendations.py` (`/recommend` as a reply → `POST /api/bot/recommendations`, snapshots the replied-to message's text + entities; shown on the site's `/recommendations` page), `handlers/welcome.py` (`NEW_CHAT_MEMBERS` → greeting built from public `/api/books`, `/api/polls`, `/api/authors`, only in `TELEGRAM_CHAT_ID`'s chat when set).

**Mock data / `create_poll_test`:** `mock_db.py` at the repo root is production code (imported by `handlers/polls.py`'s `createPollTest`) but sources its data from `tests/fixtures.py` — a temporary stand-in until `/create_poll_test` is retired in favor of the real `/create_poll`. Don't be surprised that non-test code imports from `tests/`.

## Testing conventions

- Tests mock `api_client` functions at the point they're imported into each handler module (e.g. `patch('handlers.books.api_client.search_books_to_remove', ...)`), not `api_client` itself — follow this when adding tests for a new handler.
- `Update`/`Context` objects are hand-built `MagicMock`/`AsyncMock` (see helpers at the top of each test file, or `tests/fixtures.py`'s `make_update`/`make_context`/`make_poll_update`) rather than constructed via `telegram`'s real classes.
- Async tests are marked individually with `@pytest.mark.asyncio` (no global `asyncio_mode` config).
- `tests/fixtures.py` mirrors the real backend schema (authors/members/books/polls/poll_votes) — reuse it instead of inventing ad hoc fixtures when a test needs realistic data shapes.
