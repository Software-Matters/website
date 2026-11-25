"""Software Matters site backend: handles the contact form.

POST /api/contact  -> qualifies the submission (OpenAI), then:
                        lead         -> email + ClickUp task
                        solicitation -> email only, first time; similar repeats are dropped
                        spam         -> email only, first time; similar repeats are dropped
GET  /             -> serves index.html (for local dev; nginx serves it in production).
"""
import logging
import os
import re
import smtplib
import ssl
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import formatdate, make_msgid, parseaddr

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory
from werkzeug.middleware.proxy_fix import ProxyFix

from qualify import SeenMemory, classify

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

app = Flask(__name__, static_folder=None)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024  # whole request body cap

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("swmatters")

seen_memory = SeenMemory(os.environ.get("DB_PATH") or os.path.join(BASE_DIR, "data", "submissions.db"))

# Per-field length caps
LIMITS = {
    "name": 200,
    "company": 200,
    "email": 254,
    "phone": 50,
    "message": 5000,
    "source": 100,
}
REQUIRED = ("name", "email", "message")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def env(key, default=None):
    return os.environ.get(key, default)


def one_line(s):
    """Collapse whitespace/newlines so values are safe in headers and task names."""
    return re.sub(r"\s+", " ", s).strip()


def subject_for(data):
    name = one_line(data["name"])
    company = one_line(data["company"])
    return f"Website inquiry: {name} ({company})" if company else f"Website inquiry: {name}"


def body_for(data, timestamp, category, reason):
    return (
        f"Classification: {category} ({reason})\n\n"
        f"Name:    {data['name']}\n"
        f"Company: {data['company'] or '-'}\n"
        f"Email:   {data['email']}\n"
        f"Phone:   {data['phone'] or '-'}\n"
        f"Source:  {data['source'] or '-'}\n"
        f"Time:    {timestamp}\n"
        f"IP:      {request.remote_addr or '-'}\n"
        f"\nMessage:\n{data['message']}\n"
    )


def send_email(data, subject, body):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = env("MAIL_FROM")
    msg["To"] = env("MAIL_TO", "contact@swmatters.com")
    msg["Reply-To"] = data["email"]
    msg["Date"] = formatdate(localtime=True)
    from_addr = parseaddr(env("MAIL_FROM", ""))[1]
    msg["Message-ID"] = make_msgid(domain=from_addr.split("@")[-1] if "@" in from_addr else None)
    msg.set_content(body)

    host = env("SMTP_HOST")
    port = int(env("SMTP_PORT", "587"))
    user, password = env("SMTP_USER"), env("SMTP_PASS")
    mode = env("SMTP_TLS", "starttls").lower()
    ctx = ssl.create_default_context()

    if mode == "ssl":
        server = smtplib.SMTP_SSL(host, port, context=ctx, timeout=20)
    else:
        server = smtplib.SMTP(host, port, timeout=20)
    with server:
        if mode == "starttls":
            server.starttls(context=ctx)
        if user:
            server.login(user, password)
        server.send_message(msg)


def create_clickup_task(subject, body):
    token, list_id = env("CLICKUP_TOKEN"), env("CLICKUP_LIST_ID")
    if not token or not list_id:
        log.warning("ClickUp not configured; skipping task creation")
        return
    r = requests.post(
        f"https://api.clickup.com/api/v2/list/{list_id}/task",
        headers={"Authorization": token, "Content-Type": "application/json"},
        json={"name": subject, "description": body},
        timeout=15,
    )
    r.raise_for_status()
    log.info("ClickUp task created: %s", r.json().get("id"))


@app.post("/api/contact")
def contact():
    form = request.form

    # Honeypot: pretend success, do nothing.
    if form.get("website", "").strip():
        log.info("Honeypot triggered from %s; dropped", request.remote_addr)
        return jsonify(ok=True)

    data = {k: form.get(k, "").strip() for k in LIMITS}

    errors = [f"{k} is required" for k in REQUIRED if not data[k]]
    errors += [f"{k} is too long" for k, cap in LIMITS.items() if len(data[k]) > cap]
    if data["email"] and not EMAIL_RE.match(data["email"]):
        errors.append("email is invalid")
    if errors:
        return jsonify(ok=False, errors=errors), 400

    # Repeat of spam/solicitation we've already emailed: drop silently
    # (checked before classifying, so repeats cost nothing).
    repeat = seen_memory.match(data)
    if repeat:
        log.info("Repeat %s from %s dropped", repeat, request.remote_addr)
        return jsonify(ok=True)

    category, reason = classify(data)
    log.info("Classified as %s: %s", category, reason)

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    subject = subject_for(data)
    if category != "lead":
        subject = f"[{category.capitalize()}] {subject}"
    body = body_for(data, timestamp, category, reason)

    try:
        send_email(data, subject, body)
    except Exception:
        log.exception("Email send failed")
        return jsonify(ok=False, error="email failed"), 502

    if category in ("spam", "solicitation"):
        seen_memory.remember(data, category)  # only after the email went out, so a failed send can retry
    else:
        try:
            create_clickup_task(subject, body)
        except Exception:
            log.exception("ClickUp task creation failed (email was sent)")

    return jsonify(ok=True)


# Local dev convenience; in production nginx serves index.html directly.
@app.get("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=True)
