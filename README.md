# Fine Thread Weddings

A wedding coordinator site where an AI assistant (Susan) drafts plans and a human coordinator (Amir) reviews and approves them. Built for every tradition. Islamic and Christian templates first.

**Rule:** Susan never moves money or signs anything. Anything involving money, contracts or sending to vendors waits in the approval queue for Amir.

## Run locally

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
flask --app app run --debug
```

Set the admin password once (stored as a hash in `instance/admin.json`):

```bash
flask --app app set-password
```

Open http://127.0.0.1:5000. The approval queue is at http://127.0.0.1:5000/admin/queue and needs that password. Data lives in `instance/ftw.db` (SQLite for now; PostgreSQL when deployed).

## Layout
- `app/` Flask app: responsive homepage, enquiry form, approval queue
- `docs/copy-deck.md` page copy, FAQ and items still to confirm
- `design/` logo SVGs (arch mark) and the original design boards (`.dc.html`)

## Not legal advice
We point couples to GOV.UK for marriage law.

## Susan (AI drafts)
Set `ANTHROPIC_API_KEY` to have Susan write the first reply to each enquiry with the Claude API (model via `FTW_MODEL`, default `claude-sonnet-5-5`). Without a key, or if the API fails, a fixed template draft is used. Drafts appear in the approval queue, where you can edit then approve or reject. Email sending is not connected yet.

## Security notes
- Admin pages need login; sessions last 8 hours; 5 wrong passwords locks that IP for 5 minutes (in memory, resets on restart).
- All admin POSTs carry a CSRF token.
- When hosted: set `SECRET_KEY`, `ADMIN_PASSWORD_HASH` and `FTW_HTTPS=1` as environment variables, serve over HTTPS, and add rate limiting at the proxy.
