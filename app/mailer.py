"""Plain SMTP sending (works with Gmail app passwords, Fastmail, Resend/Postmark/SES SMTP, etc.).
Configure with env vars: SMTP_HOST, SMTP_PORT (default 587), SMTP_USER, SMTP_PASSWORD, MAIL_FROM, MAIL_REPLY_TO (optional).
Nothing is sent unless Amir has approved it in the queue or clicked a send button."""
import os, smtplib, ssl
from email.message import EmailMessage
from email.utils import formataddr, parseaddr

def configured():
    return all(os.environ.get(k) for k in ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "MAIL_FROM"))

def valid_address(a):
    name, addr = parseaddr(a or "")
    return bool(addr) and "@" in addr and not any(c in a for c in "\r\n,;<>")

def send_mail(to, subject, body):
    """Returns (ok, error_message)."""
    if not configured():
        return False, "Email is not configured (set SMTP_HOST, SMTP_USER, SMTP_PASSWORD, MAIL_FROM)."
    if not valid_address(to):
        return False, "The recipient address looks invalid."
    msg = EmailMessage()
    msg["From"] = formataddr(("Fine Thread Weddings", os.environ["MAIL_FROM"]))
    msg["To"] = to
    msg["Subject"] = subject
    if os.environ.get("MAIL_REPLY_TO"): msg["Reply-To"] = os.environ["MAIL_REPLY_TO"]
    msg.set_content(body)
    try:
        host, port = os.environ["SMTP_HOST"], int(os.environ.get("SMTP_PORT", "587"))
        ctx = ssl.create_default_context()
        if port == 465:
            with smtplib.SMTP_SSL(host, port, context=ctx, timeout=20) as s:
                s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"]); s.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=20) as s:
                s.starttls(context=ctx); s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"]); s.send_message(msg)
        return True, None
    except Exception as e:  # report the kind of failure, never the credentials
        return False, f"Sending failed: {type(e).__name__}"
