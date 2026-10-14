import os, sqlite3
from flask import Flask, g, render_template, request, redirect, url_for

SCHEMA = """
CREATE TABLE IF NOT EXISTS enquiries (
  id INTEGER PRIMARY KEY, created TEXT DEFAULT CURRENT_TIMESTAMP,
  names TEXT, email TEXT, wedding_date TEXT, guests INTEGER,
  tradition TEXT, budget TEXT, notes TEXT);
CREATE TABLE IF NOT EXISTS approvals (
  id INTEGER PRIMARY KEY, created TEXT DEFAULT CURRENT_TIMESTAMP,
  enquiry_id INTEGER, kind TEXT, summary TEXT, draft TEXT,
  status TEXT DEFAULT 'pending');
"""

def create_app():
    app = Flask(__name__, instance_relative_config=True)
    os.makedirs(app.instance_path, exist_ok=True)
    app.config["DB"] = os.path.join(app.instance_path, "ftw.db")

    def db():
        if "db" not in g:
            g.db = sqlite3.connect(app.config["DB"]); g.db.row_factory = sqlite3.Row
            g.db.executescript(SCHEMA)
        return g.db

    @app.teardown_appcontext
    def close(_):
        d = g.pop("db", None)
        if d: d.close()

    @app.get("/")
    def home():
        return render_template("home.html")

    @app.route("/enquire", methods=["GET", "POST"])
    def enquire():
        if request.method == "POST":
            f = request.form
            cur = db().execute(
                "INSERT INTO enquiries(names,email,wedding_date,guests,tradition,budget,notes) VALUES(?,?,?,?,?,?,?)",
                (f.get("names"), f.get("email"), f.get("wedding_date"), f.get("guests") or None,
                 f.get("tradition"), f.get("budget"), f.get("notes")))
            # Needle's first draft goes to the queue; nothing is sent to the couple until Amir approves.
            db().execute("INSERT INTO approvals(enquiry_id,kind,summary,draft) VALUES(?,?,?,?)",
                (cur.lastrowid, "welcome_email", f"Welcome email to {f.get('names')}",
                 "Draft pending: Needle will write this once the Claude API is connected."))
            db().commit()
            return redirect(url_for("thanks"))
        return render_template("enquire.html")

    @app.get("/thanks")
    def thanks():
        return render_template("thanks.html")

    @app.get("/admin/queue")
    def queue():
        rows = db().execute("SELECT * FROM approvals ORDER BY id DESC").fetchall()
        return render_template("queue.html", rows=rows)

    @app.post("/admin/queue/<int:i>/<action>")
    def decide(i, action):
        if action in ("approved", "rejected"):
            db().execute("UPDATE approvals SET status=? WHERE id=?", (action, i)); db().commit()
        return redirect(url_for("queue"))

    return app
