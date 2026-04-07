#!/bin/bash
# deploy.sh — Deploy Render app on NBNE Ubuntu server
# Run as root or with sudo
# Usage: ./deploy.sh

set -e

DOMAIN="render.nbnesigns.co.uk"
INSTANCE_DIR="/opt/nbne/render"
REPO_DIR="$INSTANCE_DIR/app"
IMAGES_DIR="$INSTANCE_DIR/images"
NGINX_CONF="/etc/nginx/sites-available/${DOMAIN}.conf"

echo "=== Render deployment: $DOMAIN ==="

# ── 1. Instance directory ────────────────────────────────────────────────────
mkdir -p "$INSTANCE_DIR" "$IMAGES_DIR"

# ── 2. Clone or pull repo ────────────────────────────────────────────────────
if [ ! -d "$REPO_DIR/.git" ]; then
    git clone https://github.com/NBNEORIGIN/render.git "$REPO_DIR"
else
    cd "$REPO_DIR" && git pull
fi

# ── 3. Write .env if it doesn't exist ───────────────────────────────────────
cd "$INSTANCE_DIR"
if [ ! -f .env ]; then
    DB_PASSWORD=$(openssl rand -hex 16)
    SECRET_KEY=$(openssl rand -hex 32)
    APP_TOKEN=$(openssl rand -hex 24)

    cat > .env <<ENVEOF
DB_PASSWORD=${DB_PASSWORD}
SECRET_KEY=${SECRET_KEY}
APP_TOKEN=${APP_TOKEN}
PUBLIC_BASE_URL=https://${DOMAIN}

# Fill these in before starting:
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
EBAY_CLIENT_ID=
EBAY_CLIENT_SECRET=
EBAY_RU_NAME=
EBAY_ENVIRONMENT=PRODUCTION
EBAY_MERCHANT_LOCATION_KEY=default
ENVEOF

    echo ""
    echo "  .env written to $INSTANCE_DIR/.env"
    echo "  APP_TOKEN: $APP_TOKEN  ← save this, you'll need it to log in"
    echo ""
    echo "  Fill in ANTHROPIC_API_KEY, OPENAI_API_KEY, and eBay credentials"
    echo "  in $INSTANCE_DIR/.env before proceeding."
    echo ""
    read -p "  Press Enter when .env is complete..."
fi

# ── 4. SSL certificate ───────────────────────────────────────────────────────
if [ ! -d "/etc/letsencrypt/live/${DOMAIN}" ]; then
    echo "--- Obtaining SSL certificate..."

    # Temporary HTTP-only nginx block for certbot challenge
    cat > /etc/nginx/sites-available/${DOMAIN}-temp.conf <<NGINXEOF
server {
    listen 80;
    server_name ${DOMAIN};
    location /.well-known/acme-challenge/ { root /var/www/certbot; }
}
NGINXEOF
    ln -sf /etc/nginx/sites-available/${DOMAIN}-temp.conf /etc/nginx/sites-enabled/
    mkdir -p /var/www/certbot
    nginx -t && systemctl reload nginx

    certbot certonly --webroot -w /var/www/certbot -d "$DOMAIN" --non-interactive --agree-tos -m toby@nbnesigns.com

    rm /etc/nginx/sites-enabled/${DOMAIN}-temp.conf
    rm /etc/nginx/sites-available/${DOMAIN}-temp.conf
fi

# ── 5. Nginx config ──────────────────────────────────────────────────────────
echo "--- Configuring nginx..."
# Patch images path in nginx config to use our host bind mount path
sed "s|/opt/nbne/render/images/|${IMAGES_DIR}/|g" \
    "$REPO_DIR/docker/nginx/${DOMAIN}.conf" > "$NGINX_CONF"

ln -sf "$NGINX_CONF" /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx

# ── 6. Docker volume → bind mount: update docker-compose for host path ───────
# We use a named volume in docker-compose.yml but need nginx to read the same
# files. The simplest approach: override images volume to a bind mount.
COMPOSE_OVERRIDE="$INSTANCE_DIR/docker-compose.override.yml"
cat > "$COMPOSE_OVERRIDE" <<OVERRIDEEOF
services:
  app:
    volumes:
      - ${IMAGES_DIR}:/images
volumes:
  images:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: ${IMAGES_DIR}
OVERRIDEEOF

# ── 7. Start stack ───────────────────────────────────────────────────────────
echo "--- Starting Docker stack..."
cd "$REPO_DIR"
docker compose \
    --env-file "$INSTANCE_DIR/.env" \
    -f docker-compose.yml \
    -f "$COMPOSE_OVERRIDE" \
    -p render \
    up -d --build

echo ""
echo "=== Done ==="
echo "  App:    https://${DOMAIN}"
echo "  Images: ${IMAGES_DIR}"
echo "  Logs:   docker compose -p render logs -f app"
echo "  Redeploy: cd $REPO_DIR && git pull && docker compose --env-file $INSTANCE_DIR/.env -f docker-compose.yml -f $COMPOSE_OVERRIDE -p render up -d --build"
