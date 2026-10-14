# Fine Thread Weddings

A wedding coordinator site where an AI assistant (Needle) drafts plans and a human coordinator (Amir) reviews and approves them. Built for every tradition. Islamic and Christian templates first.

**Rule:** Needle never moves money or signs anything. Anything involving money, contracts or sending to vendors waits in the approval queue for Amir.

## Run locally

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
flask --app app run --debug
```

Open http://127.0.0.1:5000. Data lives in `instance/ftw.db` (SQLite for now; PostgreSQL when deployed).

## Layout
- `app/` Flask app (intake form, approval queue)
- `docs/copy-deck.md` page copy, FAQ and items still to confirm
- `design/` logo SVGs and the Structured-style homepage boards (`.dc.html`)

## Not legal advice
We point couples to GOV.UK for marriage law.
