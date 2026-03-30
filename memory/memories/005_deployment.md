# Deployment — own Ubuntu server with Docker + nginx
Tags: deployment docker nginx ubuntu ssl certbot gunicorn server
Date: 2026-03-30

## Setup

- **Server**: 178.104.1.152 (in-house Ubuntu, Cloudflare DNS)
- **Domain**: render.nbnesigns.co.uk (Cloudflare proxied → server)
- **App port**: 8025 (internal), nginx proxies 443 → 127.0.0.1:8025
- **Docker project name**: `render` (important — use `-p render` flag)

## Directory layout on server

```
/opt/nbne/render/
  app/                    ← git repo (github.com/NBNEORIGIN/render)
    docker-compose.yml
    ...
  docker-compose.override.yml   ← bind mounts /opt/nbne/render/images to /images
  .env                    ← secrets (not in git)
  images/                 ← generated product images (served by nginx)
```

## Standard rebuild command

```bash
ssh root@178.104.1.152
cd /opt/nbne/render/app && git pull
docker compose -p render \
  -f docker-compose.yml \
  -f /opt/nbne/render/docker-compose.override.yml \
  --env-file /opt/nbne/render/.env \
  up -d --build
```

## Why the `-p render` flag matters

Docker Compose names containers `{project}_{service}_1`.
The project name defaults to the directory name — which is `app` here.
Using `-p render` keeps containers named `render-app-1`, `render-db-1`
consistent with how the stack was initially deployed.
Without it, compose creates duplicate `app-*` containers and loses the existing volumes.

## Services

- **db**: postgres:16-alpine, pgdata volume, healthcheck on `pg_isready`
- **app**: built from Dockerfile, depends on db healthy, port 127.0.0.1:8025:5000

## SSL

Let's Encrypt via certbot. The nginx config has a `.well-known/acme-challenge/` passthrough.
Certbot renews automatically via cron/systemd timer.

## nginx quirk

nginx 1.24 on Ubuntu does not support `http2 on;` as a standalone directive.
Must use `listen 443 ssl http2;` combined on one line.
The `http2 on;` directive was introduced in nginx 1.25.1.

## Environment file

`.env` at `/opt/nbne/render/.env` (not inside the `app/` git repo).
Contains: DB_PASSWORD, SECRET_KEY, ANTHROPIC_API_KEY, OPENAI_API_KEY,
eBay credentials, SMTP credentials, PUBLIC_BASE_URL.

## Initial deploy

`deploy.sh` in repo root handles first-time server setup:
clones repo, generates .env (prompts for secrets), runs certbot, configures nginx, starts stack.
