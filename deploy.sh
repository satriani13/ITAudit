#!/usr/bin/env bash
# Despliegue / actualizacion de it-audit en el VPS.
# Uso:  cd /var/www/proyectos-src/it-audit && ./deploy.sh
set -euo pipefail

cd "$(dirname "$0")"

echo "==> git pull"
git pull --ff-only

echo "==> venv + dependencias"
if [ ! -d venv ]; then
  python3 -m venv venv
fi
venv/bin/pip install --quiet --upgrade pip
venv/bin/pip install --quiet -r requirements.txt

echo "==> PM2"
if pm2 describe it-audit > /dev/null 2>&1; then
  pm2 restart it-audit --update-env
else
  pm2 start ecosystem.config.cjs
  pm2 save
fi

echo "==> OK. Comprueba:  curl -s http://127.0.0.1:3020/health"
