#!/bin/bash
# Deploy Render to nbne1 (192.168.1.228)
# Run this ON nbne1 as toby or root.
set -euo pipefail

APP_DIR="/opt/nbne/render/app"
ENV_FILE="/opt/nbne/render/.env"
IMAGES_DIR="/data/render/images"

echo "=== Render deployment to nbne1 ==="

# 1. Create directories
sudo mkdir -p "$APP_DIR" "$IMAGES_DIR"
sudo chown -R toby:toby /opt/nbne/render "$IMAGES_DIR"

# 2. Clone or pull repo
if [ -d "$APP_DIR/.git" ]; then
    echo "Pulling latest..."
    cd "$APP_DIR"
    git pull origin main
else
    echo "Cloning repo..."
    git clone https://github.com/NBNEORIGIN/render.git "$APP_DIR"
    cd "$APP_DIR"
fi

# 3. Create .env if it doesn't exist
if [ ! -f "$ENV_FILE" ]; then
    echo "Creating .env — EDIT THIS with real values!"
    cat > "$ENV_FILE" <<'ENVEOF'
# Database — Cairn PG on localhost (same host)
DATABASE_URL=postgresql://cairn:cairn_nbne_2026@192.168.1.228:5432/claw

# Flask
SECRET_KEY=CHANGE_ME_RANDOM_HEX

# AI APIs
ANTHROPIC_API_KEY=sk-ant-CHANGE_ME
OPENAI_API_KEY=sk-proj-CHANGE_ME

# eBay
EBAY_CLIENT_ID=CHANGE_ME
EBAY_CLIENT_SECRET=CHANGE_ME
EBAY_RU_NAME=CHANGE_ME
EBAY_ENVIRONMENT=PRODUCTION
EBAY_MERCHANT_LOCATION_KEY=default

# Public URL
PUBLIC_BASE_URL=https://render.nbnesigns.co.uk
IMAGES_DIR=/images

# SMTP
SMTP_HOST=smtp.ionos.co.uk
SMTP_PORT=587
SMTP_USER=toby@nbnesigns.com
SMTP_PASSWORD=CHANGE_ME

# Etsy
ETSY_API_KEY=mcalbkdw9sd4xzwhnqv6a30p
ETSY_SHARED_SECRET=57sk14cuxp
ETSY_SHOP_ID=11706740
ETSY_REDIRECT_URI=https://render.nbnesigns.co.uk/etsy/oauth/callback

# Phloe
PHLOE_API_URL=https://app.nbnesigns.co.uk
PHLOE_TENANT_SLUG=mind-department
PHLOE_USERNAME=toby@nbnesigns.com
PHLOE_PASSWORD=CHANGE_ME
ENVEOF
    echo ">>> EDIT $ENV_FILE before starting! <<<"
    exit 1
fi

# 4. Build and start
echo "Building Docker image..."
cd "$APP_DIR"
docker compose -p render --env-file "$ENV_FILE" up -d --build

echo ""
echo "=== Deployment complete ==="
echo "App: http://localhost:8003"
echo "Images: $IMAGES_DIR"
echo ""
echo "Next steps:"
echo "  1. Set up Cloudflare Tunnel: cloudflared tunnel route dns render render.nbnesigns.co.uk"
echo "  2. Rsync images from Hetzner: rsync -avz root@178.104.1.152:/opt/nbne/render/images/ $IMAGES_DIR/"
echo "  3. Migrate DB data (see migrate-data.sh)"
echo "  4. Test: curl http://localhost:8003/health"
