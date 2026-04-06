#!/bin/bash
# Migrate Render data from Hetzner Docker PG to Cairn PG on nbne1.
# Run this ON nbne1 after deploy-nbne1.sh.
set -euo pipefail

HETZNER="root@178.104.1.152"
CAIRN_DB="postgresql://cairn:cairn_nbne_2026@localhost:5432/claw"
DUMP_DIR="/tmp/render-migrate"

echo "=== Render data migration: Hetzner → nbne1 ==="

mkdir -p "$DUMP_DIR"

# 1. Dump tables from Hetzner Render DB
echo "Dumping from Hetzner..."
ssh "$HETZNER" "docker exec render-db-1 pg_dump -U nbne -d render \
  --data-only --no-owner \
  -t blanks -t products -t product_content -t product_images \
  -t users -t batches -t sales_imports -t sales_data" > "$DUMP_DIR/render_data.sql"

echo "Downloaded $(wc -l < "$DUMP_DIR/render_data.sql") lines"

# 2. Rename tables in the dump to render_ prefix
echo "Renaming tables to render_ prefix..."
sed -i \
  -e 's/\bblanks\b/render_blanks/g' \
  -e 's/\bproducts\b/render_products/g' \
  -e 's/\bproduct_content\b/render_product_content/g' \
  -e 's/\bproduct_images\b/render_product_images/g' \
  -e 's/\busers\b/render_users/g' \
  -e 's/\bbatches\b/render_batches/g' \
  -e 's/\bsales_imports\b/render_sales_imports/g' \
  -e 's/\bsales_data\b/render_sales_data/g' \
  "$DUMP_DIR/render_data.sql"

# 3. Ensure render_ tables exist (init_db creates them)
echo "Creating render_ tables if needed..."
psql "$CAIRN_DB" -c "SELECT 1 FROM render_products LIMIT 1" 2>/dev/null || \
  python3 -c "import sys; sys.path.insert(0, '/opt/nbne/render/app'); from models import init_db; init_db()"

# 4. Import into Cairn DB
echo "Importing into Cairn DB..."
psql "$CAIRN_DB" < "$DUMP_DIR/render_data.sql"

# 5. Verify
echo ""
echo "=== Verification ==="
psql "$CAIRN_DB" -c "SELECT 'render_products' as tbl, count(*) FROM render_products
                      UNION ALL SELECT 'render_blanks', count(*) FROM render_blanks
                      UNION ALL SELECT 'render_users', count(*) FROM render_users
                      UNION ALL SELECT 'render_sales_data', count(*) FROM render_sales_data;"

# 6. Rsync images
echo ""
echo "Syncing images from Hetzner..."
rsync -avz "$HETZNER:/opt/nbne/render/images/" /data/render/images/
echo ""
echo "Images synced: $(find /data/render/images -name '*.jpg' | wc -l) JPEGs"

echo ""
echo "=== Migration complete ==="
echo "Cleanup: rm -rf $DUMP_DIR"
