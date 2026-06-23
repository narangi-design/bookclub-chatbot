# bookclub-chatbot

Telegram bot for a book club. Handles nominations, voting, cover images, and discussion recordings. Runs as a Vercel Serverless Function via webhook.

Part of the [Book Club](https://github.com/stars/narangi-design/lists/book-club) project — all bot data is stored and served through [Book Club API](https://github.com/narangi-design/bookclub-api), and the same data is visualised in the [Web Dashboard](https://github.com/narangi-design/bookclub-frontend).

> All bot messages and club content are in Russian.

---

## Stack

- **python-telegram-bot 22.7** — command and callback handlers
- **FastAPI** + **Mangum** — Vercel adapter
- **httpx** — requests to bookclub-api and cover image downloading

---

## Commands

| Command | Description |
|---|---|
| `/add Author — Title` | Nominate a book |
| `/remove Title` | Remove your nomination |
| `/my_books` | List your current nominations |
| `/create_poll` | Start a vote (weighted sample of 12 books) |
| `/results` | Save poll results — reply to a closed poll |
| `/second_round` | Start a runoff vote when the first round is tied — reply to the tied poll |
| `/cover` | Add a cover image to a book that doesn't have one |
| `/discussion` | Attach a discussion recording to a book — reply to the video message |

---

## Getting started

**Prerequisites:** Python 3.11+

```bash
pip install -r requirements.txt
```

Required `.env`:
```
BOT_TOKEN=
API_URL=https://your-api.vercel.app
BOT_SECRET=
```

In production the bot receives updates via webhook (Vercel URL). For local testing, use ngrok or a similar tunnel and register the URL with Telegram's `setWebhook`.

### Tests

```bash
.\venv\Scripts\pytest tests/ -v
```

---

## Technical decisions

### Stateless cover callbacks
Cover callback data encodes `source:book_id:ref_id`. The actual image URL is reconstructed client-side from these parts. This avoids storing URLs in the message or in server state.

### Discussion URL from message text
The discussion URL is stored in the bot message text itself (as the last line). The callback handler reads it back from there. No session state needed.

### Shared poll formatting
Both stage-1 and stage-2 polls use a single `_poll_options` helper that formats book entries. `member_display_name` and `author_name` are included when present and omitted when not — so the same function works for both the full candidate list and the shorter runoff list.

### Voting through save_poll_results
Both `/results` and `/second_round` go through the same `save_poll_results` API call. The call is idempotent: if votes are already stored it skips insertion and re-evaluates the result. This avoids duplicating the winner/tie logic in two places.

---

## Future improvements

- Automated weekly rubric posts via Vercel Cron (reading tips, anniversaries, etc.)
- Extract discussion recording duration from the video message metadata
---

## File structure

```
api/index.py        # FastAPI app, handler registration
handlers/
  books.py          # /add, /remove, /my_books, /cover, /discussion
  polls.py          # /create_poll, /results, /second_round
  common.py         # /help, /hello, /myid
api_client.py       # HTTP client for bookclub-api
mock_db.py          # Mock data for /create_poll_test
tests/              # pytest tests for handlers
```
