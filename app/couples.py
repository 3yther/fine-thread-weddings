"""Couple accounts: invite-only. Amir creates a one-time invite link; the couple sets a password and sees their plan."""
import hashlib, secrets, time, functools
from werkzeug.security import generate_password_hash, check_password_hash
from flask import render_template, request, redirect, url_for, session, abort

INVITE_DAYS = 7

def _h(t): return hashlib.sha256(t.encode()).hexdigest()

def register_couples(app, db, admin_required, fails):

    def couple_required(fn):
        @functools.wraps(fn)
        def wrapper(*a, **kw):
            if not session.get("couple"):
                return redirect(url_for("couple_login"))
            return fn(*a, **kw)
        return wrapper

    def throttle(key):
        n, until = fails.get(key, (0, 0))
        return n, time.time() < until

    # ---- admin side ----
    @app.get("/admin/enquiries")
    @admin_required
    def enquiries():
        rows = db().execute("""SELECT e.*, c.id AS couple_id FROM enquiries e
                               LEFT JOIN couples c ON c.enquiry_id = e.id ORDER BY e.id DESC""").fetchall()
        link = session.pop("new_invite", None)
        return render_template("enquiries.html", rows=rows, link=link)

    @app.post("/admin/enquiries/<int:i>/invite")
    @admin_required
    def invite(i):
        e = db().execute("SELECT * FROM enquiries WHERE id=?", (i,)).fetchone()
        if not e: abort(404)
        if db().execute("SELECT 1 FROM couples WHERE enquiry_id=? AND pw_hash IS NOT NULL", (i,)).fetchone():
            return redirect(url_for("enquiries"))
        token = secrets.token_urlsafe(32)
        db().execute("DELETE FROM couples WHERE enquiry_id=? AND pw_hash IS NULL", (i,))
        db().execute("INSERT INTO couples(enquiry_id,email,invite_hash,invite_expires) VALUES(?,?,?,?)",
                     (i, e["email"].strip().lower(), _h(token), time.time() + INVITE_DAYS * 86400))
        db().commit()
        session["new_invite"] = {"names": e["names"], "url": request.host_url.rstrip("/") + url_for("join", token=token)}
        return redirect(url_for("enquiries"))

    @app.post("/admin/enquiries/<int:i>/tasks")
    @admin_required
    def add_task(i):
        title = (request.form.get("title") or "").strip()[:200]
        if title:
            db().execute("INSERT INTO tasks(enquiry_id,title,due) VALUES(?,?,?)", (i, title, request.form.get("due") or None))
            db().commit()
        return redirect(url_for("enquiry_tasks", i=i))

    @app.get("/admin/enquiries/<int:i>/tasks")
    @admin_required
    def enquiry_tasks(i):
        e = db().execute("SELECT * FROM enquiries WHERE id=?", (i,)).fetchone()
        if not e: abort(404)
        t = db().execute("SELECT * FROM tasks WHERE enquiry_id=? ORDER BY done, due IS NULL, due, id", (i,)).fetchall()
        return render_template("admin_tasks.html", e=e, tasks=t)

    # ---- couple side ----
    @app.route("/join/<token>", methods=["GET", "POST"])
    def join(token):
        row = db().execute("SELECT * FROM couples WHERE invite_hash=? AND pw_hash IS NULL", (_h(token),)).fetchone()
        if not row or row["invite_expires"] < time.time():
            return render_template("join.html", bad=True), 404
        err = None
        if request.method == "POST":
            pw = request.form.get("password", "")
            if len(pw) < 12: err = "Use at least 12 characters."
            elif pw != request.form.get("again", ""): err = "The two passwords did not match."
            else:
                db().execute("UPDATE couples SET pw_hash=?, invite_hash=NULL, invite_expires=NULL WHERE id=?",
                             (generate_password_hash(pw), row["id"]))
                db().commit()
                session.clear(); session["couple"] = row["id"]; session.permanent = True
                return redirect(url_for("plan"))
        return render_template("join.html", err=err)

    @app.route("/login", methods=["GET", "POST"])
    def couple_login():
        err = None; key = "c:" + (request.remote_addr or "")
        if request.method == "POST":
            n, locked = throttle(key)
            if locked:
                err = "Too many attempts. Wait a few minutes."
            else:
                c = db().execute("SELECT * FROM couples WHERE email=? AND pw_hash IS NOT NULL",
                                 ((request.form.get("email") or "").strip().lower(),)).fetchone()
                # always run a hash check so timing does not reveal whether the email exists
                ok = check_password_hash(c["pw_hash"] if c else generate_password_hash("x"), request.form.get("password", ""))
                if c and ok:
                    fails.pop(key, None); session.clear(); session["couple"] = c["id"]; session.permanent = True
                    return redirect(url_for("plan"))
                n += 1; fails[key] = (n, time.time() + 300 if n >= 5 else 0)
                err = "That email and password do not match."
        return render_template("couple_login.html", err=err)

    @app.get("/plan")
    @couple_required
    def plan():
        c = db().execute("SELECT * FROM couples WHERE id=?", (session["couple"],)).fetchone()
        if not c: session.clear(); return redirect(url_for("couple_login"))
        e = db().execute("SELECT * FROM enquiries WHERE id=?", (c["enquiry_id"],)).fetchone()
        t = db().execute("SELECT * FROM tasks WHERE enquiry_id=? ORDER BY done, due IS NULL, due, id", (c["enquiry_id"],)).fetchall()
        return render_template("plan.html", e=e, tasks=t)

    @app.post("/plan/tasks/<int:i>/toggle")
    @couple_required
    def toggle_task(i):
        c = db().execute("SELECT enquiry_id FROM couples WHERE id=?", (session["couple"],)).fetchone()
        # a couple can only change their own tasks
        db().execute("UPDATE tasks SET done = 1 - done WHERE id=? AND enquiry_id=?", (i, c["enquiry_id"]))
        db().commit()
        return redirect(url_for("plan"))

    @app.post("/plan/logout")
    def couple_logout():
        session.clear(); return redirect(url_for("home"))
