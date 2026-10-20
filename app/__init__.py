import os, sqlite3, json, secrets, time, functools, getpass
import click
from .needle import draft_welcome
from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, g, render_template, request, redirect, url_for, session, abort

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
    admin_file = os.path.join(app.instance_path, "admin.json")
    key_file = os.path.join(app.instance_path, "secret_key")

    # Secret key: env var in production, otherwise generated once and kept in instance/.
    key = os.environ.get("SECRET_KEY")
    if not key:
        if not os.path.exists(key_file):
            with open(key_file, "w") as f: f.write(secrets.token_hex(32))
            os.chmod(key_file, 0o600)
        key = open(key_file).read().strip()
    app.config.update(SECRET_KEY=key, SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                      SESSION_COOKIE_SECURE=os.environ.get("FTW_HTTPS") == "1",
                      PERMANENT_SESSION_LIFETIME=60 * 60 * 8)

    def admin_hash():
        if os.environ.get("ADMIN_PASSWORD_HASH"): return os.environ["ADMIN_PASSWORD_HASH"]
        if os.path.exists(admin_file): return json.load(open(admin_file)).get("hash")
        return None

    def csrf_token():
        if "csrf" not in session: session["csrf"] = secrets.token_hex(16)
        return session["csrf"]
    app.jinja_env.globals["csrf_token"] = csrf_token

    @app.before_request
    def check_csrf():
        if request.method == "POST" and request.path.startswith("/admin"):
            if not secrets.compare_digest(request.form.get("csrf", ""), session.get("csrf", "x")):
                abort(400)

    def admin_required(fn):
        @functools.wraps(fn)
        def wrapper(*a, **kw):
            if not session.get("admin"):
                return redirect(url_for("login", next=request.path))
            return fn(*a, **kw)
        return wrapper

    @app.cli.command("set-password")
    def set_password():
        """Set the admin password (stored as a hash in instance/admin.json)."""
        pw = getpass.getpass("New admin password (12+ characters): ")
        if len(pw) < 12: raise click.ClickException("Use at least 12 characters.")
        if pw != getpass.getpass("Repeat it: "): raise click.ClickException("Passwords did not match.")
        with open(admin_file, "w") as f: json.dump({"hash": generate_password_hash(pw)}, f)
        os.chmod(admin_file, 0o600)
        click.echo("Saved.")

    fails = {}

    def db():
        if "db" not in g:
            g.db = sqlite3.connect(app.config["DB"]); g.db.row_factory = sqlite3.Row
            g.db.executescript(SCHEMA)
        return g.db

    @app.template_global()
    def img(f):
        return url_for('static', filename='img/' + f)

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
            # Needle drafts the reply; nothing reaches the couple until Amir approves it.
            e = {k: f.get(k) for k in ("names", "email", "wedding_date", "guests", "tradition", "budget", "notes")}
            text, source = draft_welcome(e)
            db().execute("INSERT INTO approvals(enquiry_id,kind,summary,draft) VALUES(?,?,?,?)",
                (cur.lastrowid, "welcome_email:" + source, f"Welcome email to {e['names']} ({e['email']})", text))
            db().commit()
            return redirect(url_for("thanks"))
        return render_template("enquire.html")

    @app.get("/thanks")
    def thanks():
        return render_template("thanks.html")

    @app.route("/admin/login", methods=["GET", "POST"])
    def login():
        h = admin_hash(); err = None
        ip = request.remote_addr; n, until = fails.get(ip, (0, 0))
        if request.method == "POST":
            if time.time() < until:
                err = "Too many attempts. Wait a few minutes."
            elif not secrets.compare_digest(request.form.get("csrf", ""), session.get("csrf", "x")):
                abort(400)
            elif h and check_password_hash(h, request.form.get("password", "")):
                fails.pop(ip, None); session.clear(); session["admin"] = True; session.permanent = True
                nxt = request.args.get("next", "")
                return redirect(nxt if nxt.startswith("/admin") else url_for("queue"))
            else:
                n += 1; fails[ip] = (n, time.time() + 300 if n >= 5 else 0)
                err = "Wrong password."
        return render_template("login.html", err=err, no_password=h is None)

    @app.post("/admin/logout")
    def logout():
        session.clear(); return redirect(url_for("home"))

    @app.get("/admin/queue")
    @admin_required
    def queue():
        rows = db().execute("SELECT * FROM approvals ORDER BY id DESC").fetchall()
        return render_template("queue.html", rows=rows)

    @app.post("/admin/queue/<int:i>/<action>")
    @admin_required
    def decide(i, action):
        if action in ("approved", "rejected"):
            draft = request.form.get("draft")
            if draft is not None:
                db().execute("UPDATE approvals SET draft=? WHERE id=? AND status='pending'", (draft, i))
            db().execute("UPDATE approvals SET status=? WHERE id=? AND status='pending'", (action, i)); db().commit()
        return redirect(url_for("queue"))

    return app
