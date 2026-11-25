# Software Matters website — handoff: wire up the contact form

## Context
- Site: a single static page, `index.html` (self-contained HTML/CSS/JS, no build step).
- Company: Software Matters (swmatters.com), software administration & support.
- Hosting plan: **Cloudflare Pages** on `swmatters.com`.
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
- **Cloudflare Pages Function** at `functions/api/contact.js` (POST only):
  1. Parse `request.formData()`.
  2. Drop the submission if the honeypot is filled.
  3. Validate the required fields and the email format.
  4. Send the email via an email API, e.g. **Resend** (verify the `swmatters.com` domain there).
     - Set Reply-To to the submitter's email.
  5. Create the ClickUp task via `POST https://api.clickup.com/api/v2/list/{LIST_ID}/task`:
     - Header: `Authorization: {CLICKUP_TOKEN}`
     - Task name: `Website inquiry: {name} ({company})`
     - Description: all fields plus a timestamp.
  6. Return JSON `{ok:true}` with status 200. On failure, return a non-2xx status.
- Store secrets as Cloudflare Pages environment variables, never in the HTML:
  - `RESEND_API_KEY`
  - `CLICKUP_TOKEN`
  - `CLICKUP_LIST_ID`
  - `MAIL_TO` = `contact@swmatters.com`
  - `MAIL_FROM` (e.g. `website@swmatters.com`)
- Optional: add Cloudflare Turnstile for extra spam protection.

### Alternative with no code
Point `data-endpoint` at a Make or Zapier webhook. The scenario then sends the email and creates the ClickUp task. The webhook must return 2xx.

## Deploy steps
1. Put `index.html` and the `functions/` folder in one repo or folder.
2. Create a Cloudflare Pages project, deploy it, then add the environment variables.
3. Add the custom domain `swmatters.com`.
4. Test with a real submission. Check that the email and the ClickUp task both arrive, and that the confirmation panel shows.

## Don't change
The design, copy, fonts, animations and layout are approved. Only touch the form `data-endpoint`/`action` and add the backend.
