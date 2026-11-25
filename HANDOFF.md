# Software Matters website — handoff: wire up the contact form

## Context
- Site: a single static page, `index.html` (self-contained HTML/CSS/JS, no build step).
- Company: Software Matters (swmatters.com), software administration & support.
- Hosting plan: the owner's own **VPS**, serving `swmatters.com`.
- Email sending: **SMTP** (the owner supplies host, port, username and password).
- Version history is in this folder's git repo (`git log --oneline`).

## Goal
When someone submits the contact form:
1. **Email** the submission to `contact@swmatters.com`.
2. **Create a task in ClickUp** (the owner's task manager) with the submission details.
3. Return success, so the page shows its built-in "Message sent" confirmation.

## The form as it is now (in `index.html`)
- Element: `<form class="ct-form" id="contactForm" action="" method="POST" data-endpoint="">`
- Fields (`name` attributes):
  - `name`: required
  - `company`: optional
  - `email`: required
  - `phone`: optional
  - `message`: required
  - `website`: honeypot (hidden). If it's filled in, it's a bot, so drop the submission silently.
  - `source`: hidden, value `swmatters.com contact form`
- Front-end JS (search for `// Contact form:`):
  - If `data-endpoint` is empty → shows the confirmation without sending (preview mode).
  - If it's set → `fetch(endpoint, {method:'POST', body:FormData, headers:{Accept:'application/json'}})`.
    - A 2xx response shows the "Message sent" panel.
    - Anything else shows the error "Please email contact@swmatters.com directly."
- **To connect it:** set `data-endpoint` (and `action`) to the handler URL, e.g. `/api/contact`.

## Suggested implementation (Claude Code may choose otherwise)
The owner works in Python, Flask and Docker, so prefer that stack.

- **A small Flask app** that does two things:
  - Serves `index.html` as a static file, or let the web server serve it (see below).
  - Handles `POST /api/contact`:
    1. Read the form fields.
    2. If the honeypot is filled, return 200 without doing anything.
    3. Validate the required fields and the email format. Cap the length of each field.
    4. **Send the email over SMTP** (Python `smtplib` with STARTTLS or SSL).
       - To `MAIL_TO`, from `MAIL_FROM`.
       - Set Reply-To to the submitter's email.
       - Subject: `Website inquiry: {name} ({company})`.
    5. **Create the ClickUp task** via `POST https://api.clickup.com/api/v2/list/{CLICKUP_LIST_ID}/task`:
       - Header: `Authorization: {CLICKUP_TOKEN}`
       - Task name: `Website inquiry: {name} ({company})`
       - Description: all fields plus a timestamp.
    6. Return `{"ok": true}` with status 200 if at least the email went out.
       - Log the ClickUp error, but don't fail the visitor over it.
       - If the email fails, return a 5xx status, so the page shows its fallback message.
- **Basic rate limiting** on `/api/contact`, e.g. a few requests per minute per IP, through Flask-Limiter or the web server.
- **Configuration in a `.env` file** that is not committed. Read it with `python-dotenv` or Docker `env_file`:
  - `SMTP_HOST`
  - `SMTP_PORT`
  - `SMTP_USER`
  - `SMTP_PASS`
  - `SMTP_TLS` (starttls or ssl)
  - `MAIL_TO` = `contact@swmatters.com`
  - `MAIL_FROM`
  - `CLICKUP_TOKEN`
  - `CLICKUP_LIST_ID`
- In `index.html`, set the form's `data-endpoint` and `action` to `/api/contact`.

## Deploy on the VPS
1. Package the app with Docker:
   - A `Dockerfile` that runs the Flask app with **gunicorn**.
   - A `docker-compose.yml` that loads `env_file: .env`.
2. Put a reverse proxy in front: **Caddy** (automatic HTTPS) or Nginx with Certbot.
   - Serve `index.html` as static files.
   - Proxy `/api/*` to gunicorn.
3. DNS: point the `A` record for `swmatters.com` and `www` at the VPS IP. Redirect `www` to the bare domain.
4. Test with a real submission. Check that the email and the ClickUp task both arrive, and that the confirmation panel shows.
5. Also check email deliverability:
   - SPF and DKIM must be set for whichever domain or provider sends the SMTP mail.
   - Otherwise these messages may land in spam.

### Alternative with no code
Point `data-endpoint` at a Make or Zapier webhook. The scenario then sends the email and creates the ClickUp task. The webhook must return 2xx.

## Don't change
The design, copy, fonts, animations and layout are approved. Only touch the form `data-endpoint`/`action` and add the backend.
