#!/usr/bin/env bash
# Redeploy swmatters.com: pull the latest code from GitHub, install requirements,
# restart the backend, and check that it came back up.
#
# Install once:  cp /var/www/swmatters/deploy/redeploy_swmatters.sh ~/redeploy_swmatters.sh && chmod +x ~/redeploy_swmatters.sh
# Run:           ~/redeploy_swmatters.sh
#
# Run it as the user that owns /var/www/swmatters (not root). It uses sudo only for systemctl.
set -euo pipefail

APP_DIR="${APP_DIR:-/var/www/swmatters}"
BRANCH="${BRANCH:-master}"
SERVICE="${SERVICE:-swmatters}"
VENV="$APP_DIR/venv"

say() { printf '\n\033[1;33m==> %s\033[0m\n' "$*"; }
fail() { printf '\n\033[1;31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }

[ -d "$APP_DIR/.git" ] || fail "$APP_DIR is not a git checkout"
cd "$APP_DIR"

say "Pulling $BRANCH from GitHub"
before=$(git rev-parse HEAD)
git fetch --quiet origin "$BRANCH"
git checkout --quiet "$BRANCH"
git merge --ff-only "origin/$BRANCH" \
  || fail "local changes on the server block the update; run 'git status' in $APP_DIR"
after=$(git rev-parse HEAD)
if [ "$before" = "$after" ]; then
  echo "Already up to date ($(git log -1 --format='%h %s'))"
else
  git log --format='  %h %s' "$before..$after"
fi

say "Installing requirements"
[ -x "$VENV/bin/python" ] || python3 -m venv "$VENV"
"$VENV/bin/pip" install --quiet --upgrade pip
"$VENV/bin/pip" install --quiet -r requirements.txt

# Files the backend (www-data) must be able to write/read
mkdir -p data
sudo chown -R www-data:www-data data
[ -f .env ] || fail ".env is missing in $APP_DIR (copy .env.example and fill it in)"

say "Restarting $SERVICE"
if ! cmp -s deploy/swmatters.service "/etc/systemd/system/$SERVICE.service"; then
  echo "Note: deploy/swmatters.service differs from the installed unit; installing the new one"
  sudo cp deploy/swmatters.service "/etc/systemd/system/$SERVICE.service"
  sudo systemctl daemon-reload
fi
sudo systemctl restart "$SERVICE"

say "Checking"
for _ in $(seq 1 15); do
  code=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/ || true)
  [ "$code" = "200" ] && break
  sleep 1
done
if [ "${code:-}" != "200" ]; then
  sudo journalctl -u "$SERVICE" -n 30 --no-pager
  fail "$SERVICE is not responding (last HTTP code: ${code:-none}); logs above"
fi
echo "$SERVICE is up (HTTP 200)"

if ! sudo cmp -s deploy/nginx.conf /etc/nginx/sites-available/swmatters 2>/dev/null; then
  echo
  echo "Note: deploy/nginx.conf differs from /etc/nginx/sites-available/swmatters."
  echo "      That's expected after certbot edits it; merge any real changes by hand, then:"
  echo "      sudo nginx -t && sudo systemctl reload nginx"
fi

say "Done: $(git log -1 --format='%h %s')"
