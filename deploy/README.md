# Deploying swmatters.com (systemd + nginx)

Assumes Ubuntu/Debian with `git`, `python3-venv`, `nginx`, `curl` and `certbot` (`python3-certbot-nginx`) installed.

Layout: the GitHub repo is cloned to `/var/www/swmatters`. nginx serves only `index.html` from it
(see `nginx.conf`), so `.env`, the Python code, `data/` and `.git` are never reachable from the web.
The checkout is owned by your own (sudo) user, so `git pull` works without root; the backend runs as
`www-data`, which only needs to read the code and `.env` and write `data/`.

## 1. First-time setup
```sh
sudo mkdir -p /var/www/swmatters && sudo chown "$USER":"$USER" /var/www/swmatters
git clone https://github.com/Software-Matters/website.git /var/www/swmatters   # files land directly in /var/www/swmatters
cd /var/www/swmatters
# (If /var/www/swmatters already exists and isn't empty, instead run inside it:
#    git init && git remote add origin https://github.com/Software-Matters/website.git && git pull origin master )

cp .env.example .env && nano .env              # fill in real values
sudo chown "$USER":www-data .env && chmod 640 .env

python3 -m venv venv
venv/bin/pip install -r requirements.txt
mkdir -p data && sudo chown www-data:www-data data

cp deploy/redeploy_swmatters.sh ~/redeploy_swmatters.sh && chmod +x ~/redeploy_swmatters.sh
```
If the GitHub repo is private, the VPS needs read access first: add a
[deploy key](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/managing-deploy-keys)
and clone with `git@github.com:Software-Matters/website.git` instead.

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

nginx (`www-data`) must be able to traverse `/var/www/swmatters` and read `index.html`. The default
`git clone` permissions (755 dirs / 644 files) allow this.

## 4. Test
```sh
curl -i -X POST https://swmatters.com/api/contact \
  -F name="Test" -F email="you@example.com" -F message="Test from curl"
curl -I https://swmatters.com/.env        # must be 404
```
Expect `{"ok": true}`, an email at `MAIL_TO`, and a ClickUp task. Then submit the real form in a browser and confirm the "Message sent" panel.

## Updating the site
Push to GitHub, then on the VPS run:
```sh
~/redeploy_swmatters.sh
```
It pulls `master`, installs `requirements.txt` into the venv, reinstalls the systemd unit if
`deploy/swmatters.service` changed, restarts `swmatters`, and checks the app answers on port 8000
(printing the last 30 log lines if it doesn't). `index.html` changes are live as soon as they're pulled.
It does not touch nginx (certbot edits that file); it only warns if `deploy/nginx.conf` changed.
After editing `.env` only: `sudo systemctl restart swmatters`.

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
- Repeat memory lives in `/var/www/swmatters/data/submissions.db` (SQLite, table `seen`, created automatically; must be writable by `www-data`). Delete a row to "un-remember" a sender.
