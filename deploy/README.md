# Deploying swmatters.com (systemd + nginx)

Assumes Ubuntu/Debian with `python3-venv`, `nginx` and `certbot` (`python3-certbot-nginx`) installed.

## 1. App files
```sh
sudo mkdir -p /opt/swmatters/public
sudo cp app.py qualify.py requirements.txt /opt/swmatters/
sudo cp index.html /opt/swmatters/public/      # nginx serves only public/, so .env and app.py are never exposed
sudo cp .env.example /opt/swmatters/.env && sudo nano /opt/swmatters/.env   # fill in real values
sudo python3 -m venv /opt/swmatters/venv
sudo /opt/swmatters/venv/bin/pip install -r /opt/swmatters/requirements.txt
sudo chown -R www-data:www-data /opt/swmatters
sudo chmod 600 /opt/swmatters/.env
```

## 2. systemd
```sh
sudo cp deploy/swmatters.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now swmatters
sudo systemctl status swmatters          # logs: journalctl -u swmatters -f
```

## 3. nginx + HTTPS
```sh
sudo cp deploy/nginx.conf /etc/nginx/sites-available/swmatters
sudo ln -s /etc/nginx/sites-available/swmatters /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d swmatters.com -d www.swmatters.com
```
(Point the `A` records for `swmatters.com` and `www` at the VPS IP before running certbot.)

## 4. Test
```sh
curl -i -X POST https://swmatters.com/api/contact \
  -F name="Test" -F email="you@example.com" -F message="Test from curl"
```
Expect `{"ok": true}`, an email at `MAIL_TO`, and a ClickUp task. Then submit the real form in a browser and confirm the "Message sent" panel.

## Updating the site
Copy the new `index.html` to `/opt/swmatters/public/` (no restart needed).
After changing `app.py` or `.env`: `sudo systemctl restart swmatters`.

## Notes
- `SMTP_TLS`: `starttls` (port 587), `ssl` (port 465), or `none` (plain, local testing only).
- Deliverability: `MAIL_FROM` must be on a domain whose SPF/DKIM authorize your SMTP provider, or mail may land in spam.
- ClickUp failures are logged but don't fail the visitor; email failures return 502 so the page shows its fallback message.
- Rate limit: 5 req/min per IP with a burst of 3 (`limit_req` in `nginx.conf`); excess requests get 429.
- Lead qualification: each submission is classified by OpenAI `gpt-6-luna` (`OPENAI_API_KEY` in `.env`; override with `OPENAI_MODEL`):
  - **lead**: email + ClickUp task
  - **solicitation**: email only (`[Solicitation]` subject), first time only
  - **spam**: email only (`[Spam]` subject), first time only
  - Repeat solicitations/spam (same email address, or >=85% similar text, within 180 days) are silently dropped without calling OpenAI. Leads are never deduplicated.
  - If the key is missing or the classifier fails, the submission is treated as a lead, so no real inquiry is lost.
- Repeat memory lives in `/opt/swmatters/data/submissions.db` (SQLite, table `seen`, created automatically; must be writable by `www-data`). Delete a row to "un-remember" a sender.
