"""Database models for Render.

All tables use the `render_` prefix to namespace within Cairn's shared PostgreSQL.
PostgreSQL only — SQLite fallback removed (Cairn PG on nbne1 is the sole target).
"""
import json
import os
from pathlib import Path

import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://cairn:cairn_nbne_2026@192.168.1.228:5432/claw")

P = "%s"  # SQL placeholder (PostgreSQL only)


def get_placeholder():
    return P


_connection_pool = None


def _get_pool():
    global _connection_pool
    if _connection_pool is None:
        _connection_pool = pool.SimpleConnectionPool(minconn=2, maxconn=10, dsn=DATABASE_URL)
    return _connection_pool


def get_db():
    conn = _get_pool().getconn()
    conn.autocommit = True
    return conn


def release_db(conn):
    _get_pool().putconn(conn)


def dict_cursor(conn):
    return conn.cursor(cursor_factory=RealDictCursor)


def _alter_add(cur, table: str, column: str, col_type: str) -> None:
    """Add a column if it doesn't exist; swallow duplicate-column errors only."""
    try:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
    except Exception as exc:
        msg = str(exc).lower()
        if "duplicate column" in msg or "already exists" in msg:
            pass
        else:
            raise


def init_db():
    """Create or migrate all render_* database tables."""
    conn = get_db()
    cur = conn.cursor()

    # ── render_blanks ────────────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS render_blanks (
            id SERIAL PRIMARY KEY,
            slug TEXT UNIQUE NOT NULL,
            display TEXT NOT NULL,
            width_mm REAL NOT NULL,
            height_mm REAL NOT NULL,
            is_circular INTEGER DEFAULT 0,
            amazon_code TEXT,
            sign_x REAL NOT NULL,
            sign_y REAL NOT NULL,
            sign_w REAL NOT NULL,
            sign_h REAL NOT NULL,
            peel_x REAL,
            peel_y REAL,
            peel_w REAL,
            peel_h REAL,
            has_portrait INTEGER DEFAULT 0,
            active INTEGER DEFAULT 1,
            sort_order INTEGER DEFAULT 0
        )
    """)

    # ── render_products ──────────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS render_products (
            id SERIAL PRIMARY KEY,
            m_number TEXT UNIQUE NOT NULL,
            description TEXT,
            size TEXT,
            color TEXT,
            layout_mode TEXT DEFAULT 'A',
            icon_files TEXT,
            text_line_1 TEXT,
            text_line_2 TEXT,
            text_line_3 TEXT,
            orientation TEXT DEFAULT 'landscape',
            font TEXT DEFAULT 'arial_heavy',
            material TEXT DEFAULT '1mm_aluminium',
            mounting_type TEXT DEFAULT 'self_adhesive',
            ean TEXT,
            qa_status TEXT DEFAULT 'pending',
            qa_comment TEXT,
            icon_scale REAL DEFAULT 1.0,
            text_scale REAL DEFAULT 1.0,
            icon_offset_x REAL DEFAULT 0.0,
            icon_offset_y REAL DEFAULT 0.0,
            ai_theme TEXT,
            ai_use_cases TEXT,
            ai_content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    for col, typ in [("ai_theme", "TEXT"), ("ai_use_cases", "TEXT"), ("ai_content", "TEXT")]:
        _alter_add(cur, "render_products", col, typ)

    # ── render_product_content ───────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS render_product_content (
            id SERIAL PRIMARY KEY,
            product_id INTEGER REFERENCES render_products(id),
            title TEXT,
            description TEXT,
            bullet_points TEXT,
            search_terms TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── render_product_images ────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS render_product_images (
            id SERIAL PRIMARY KEY,
            product_id INTEGER REFERENCES render_products(id),
            image_type TEXT,
            url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── render_batches ───────────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS render_batches (
            id SERIAL PRIMARY KEY,
            name TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP
        )
    """)

    # ── render_users ─────────────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS render_users (
            id SERIAL PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── render_sales_imports ─────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS render_sales_imports (
            id          SERIAL PRIMARY KEY,
            filename    TEXT,
            report_start TEXT,
            report_end  TEXT,
            row_count   INTEGER DEFAULT 0,
            imported_by TEXT,
            imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── render_sales_data ────────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS render_sales_data (
            id          SERIAL PRIMARY KEY,
            import_id   INTEGER,
            asin        TEXT,
            parent_asin TEXT,
            sku         TEXT,
            title       TEXT,
            sessions    REAL DEFAULT 0,
            units       REAL DEFAULT 0,
            revenue     REAL DEFAULT 0,
            cvr         REAL DEFAULT 0,
            buy_box_pct REAL DEFAULT 0,
            report_start TEXT,
            report_end  TEXT
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_render_sales_sku  ON render_sales_data(sku)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_render_sales_asin ON render_sales_data(asin)")

    # ── render_publish_log ───────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS render_publish_log (
            id              SERIAL PRIMARY KEY,
            m_number        TEXT NOT NULL,
            channel         TEXT NOT NULL,
            status          TEXT NOT NULL DEFAULT 'pending',
            external_id     TEXT,
            error_message   TEXT,
            published_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_render_publish_m ON render_publish_log(m_number)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_render_publish_channel ON render_publish_log(channel)")

    # ── render_catalogue_listing ─────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS render_catalogue_listing (
            id                  SERIAL PRIMARY KEY,
            internal_ref        VARCHAR(100) UNIQUE NOT NULL,
            product_type        VARCHAR(100) NOT NULL,
            brand_name          VARCHAR(100) NOT NULL DEFAULT 'NorthByNorthEast',
            title_base          TEXT NOT NULL,
            description         TEXT,
            bullet_point_1      TEXT,
            bullet_point_2      TEXT,
            bullet_point_3      TEXT,
            bullet_point_4      TEXT,
            bullet_point_5      TEXT,
            generic_keywords    TEXT,
            recommended_browse_nodes VARCHAR(50),
            variation_theme     VARCHAR(50) DEFAULT 'Size & Colour',
            batteries_required  BOOLEAN DEFAULT FALSE,
            dangerous_goods     VARCHAR(50) DEFAULT 'Not Applicable',
            country_of_origin   VARCHAR(50) DEFAULT 'Great Britain',
            created_at          TIMESTAMPTZ DEFAULT NOW(),
            updated_at          TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # ── render_catalogue_variant ─────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS render_catalogue_variant (
            id                  SERIAL PRIMARY KEY,
            listing_id          INTEGER REFERENCES render_catalogue_listing(id),
            sku                 VARCHAR(50) UNIQUE NOT NULL,
            ean                 VARCHAR(13) UNIQUE,
            title_full          TEXT NOT NULL,
            colour_name         VARCHAR(50),
            colour_map          VARCHAR(50),
            size_name           VARCHAR(20),
            size_map            VARCHAR(20),
            length_cm           NUMERIC(6,1),
            width_cm            NUMERIC(6,1),
            list_price          NUMERIC(8,2),
            style_name          VARCHAR(100),
            image_urls          JSONB DEFAULT '[]',
            amazon_asin         VARCHAR(20),
            amazon_published_at TIMESTAMPTZ,
            amazon_status       VARCHAR(20) DEFAULT 'unpublished',
            etsy_listing_id     VARCHAR(30),
            etsy_published_at   TIMESTAMPTZ,
            ebay_listing_id     VARCHAR(30),
            ebay_published_at   TIMESTAMPTZ,
            fulfillment_channel VARCHAR(30) DEFAULT 'AMAZON_UK_RAFN',
            quantity            INTEGER DEFAULT 5,
            shipping_group      TEXT DEFAULT 'RM Tracked 48 Free, 24 -- £2.99, SD -- £7.99',
            condition_type      VARCHAR(20) DEFAULT 'New',
            created_at          TIMESTAMPTZ DEFAULT NOW(),
            updated_at          TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_rcat_variant_listing ON render_catalogue_variant(listing_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_rcat_variant_status  ON render_catalogue_variant(amazon_status)")

    # ── render_ean_pool ──────────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS render_ean_pool (
            id          SERIAL PRIMARY KEY,
            ean         VARCHAR(13) UNIQUE NOT NULL,
            assigned_to VARCHAR(50),
            assigned_at TIMESTAMPTZ,
            created_at  TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    # Deferred FK so EANs can be seeded before variants exist
    cur.execute("""
        DO $$
        BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'fk_ean_pool_variant'
          ) THEN
            ALTER TABLE render_ean_pool
              ADD CONSTRAINT fk_ean_pool_variant
              FOREIGN KEY (assigned_to)
              REFERENCES render_catalogue_variant(sku)
              DEFERRABLE INITIALLY DEFERRED;
          END IF;
        END$$
    """)

    # ── render_spapi_log ─────────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS render_spapi_log (
            id              SERIAL PRIMARY KEY,
            sku             VARCHAR(50),
            operation       VARCHAR(50),
            request_payload JSONB,
            response_status INTEGER,
            response_body   JSONB,
            error_code      VARCHAR(100),
            created_at      TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_rspapi_log_sku ON render_spapi_log(sku)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_rspapi_log_op  ON render_spapi_log(operation)")

    release_db(conn)

    # Seed blanks and users
    _seed_blanks()
    _seed_users()


def _seed_blanks():
    """Populate render_blanks from BLANK_SEEDS if it has no rows."""
    from config import BLANK_SEEDS

    conn = get_db()
    try:
        cur = dict_cursor(conn)
        cur.execute("SELECT COUNT(*) as n FROM render_blanks")
        row = dict(cur.fetchone())
        if row["n"] > 0:
            return

        cur2 = conn.cursor()
        for i, (slug, b) in enumerate(BLANK_SEEDS.items()):
            peel = b.get("peel_bounds")
            cur2.execute("""
                INSERT INTO render_blanks
                    (slug, display, width_mm, height_mm, is_circular, amazon_code,
                     sign_x, sign_y, sign_w, sign_h,
                     peel_x, peel_y, peel_w, peel_h,
                     has_portrait, active, sort_order)
                VALUES
                    (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                slug, b["display"], b["width_mm"], b["height_mm"],
                1 if b["is_circular"] else 0, b["amazon_code"],
                b["sign_bounds"][0], b["sign_bounds"][1],
                b["sign_bounds"][2], b["sign_bounds"][3],
                peel[0] if peel else None, peel[1] if peel else None,
                peel[2] if peel else None, peel[3] if peel else None,
                1 if b["has_portrait"] else 0, 1, i,
            ))
    finally:
        release_db(conn)


def _seed_users():
    """Populate render_users with the default NBNE team if empty."""
    from werkzeug.security import generate_password_hash
    from config import DEFAULT_USERS

    conn = get_db()
    try:
        cur = dict_cursor(conn)
        cur.execute("SELECT COUNT(*) as n FROM render_users")
        if dict(cur.fetchone())["n"] > 0:
            return
        cur2 = conn.cursor()
        for email, name in DEFAULT_USERS.items():
            from config import DEFAULT_PASSWORD
            cur2.execute(
                "INSERT INTO render_users (email, name, password_hash) VALUES (%s,%s,%s)",
                (email, name, generate_password_hash(DEFAULT_PASSWORD)),
            )
    finally:
        release_db(conn)


# ── User model ────────────────────────────────────────────────────────────────

class User:
    @staticmethod
    def authenticate(email: str, password: str):
        """Return user dict if credentials valid, else None."""
        from werkzeug.security import check_password_hash
        conn = get_db()
        try:
            cur = dict_cursor(conn)
            cur.execute("SELECT * FROM render_users WHERE email = %s AND active = 1", (email.lower().strip(),))
            row = cur.fetchone()
            if row:
                u = dict(row)
                if check_password_hash(u["password_hash"], password):
                    return u
            return None
        finally:
            release_db(conn)

    @staticmethod
    def get(email: str):
        conn = get_db()
        try:
            cur = dict_cursor(conn)
            cur.execute("SELECT * FROM render_users WHERE email = %s", (email.lower().strip(),))
            row = cur.fetchone()
            return dict(row) if row else None
        finally:
            release_db(conn)

    @staticmethod
    def all():
        conn = get_db()
        try:
            cur = dict_cursor(conn)
            cur.execute("SELECT id, email, name, active, created_at FROM render_users ORDER BY name")
            return [dict(r) for r in cur.fetchall()]
        finally:
            release_db(conn)

    @staticmethod
    def set_password(email: str, password: str):
        from werkzeug.security import generate_password_hash
        conn = get_db()
        try:
            cur = conn.cursor()
            cur.execute(
                "UPDATE render_users SET password_hash = %s WHERE email = %s",
                (generate_password_hash(password), email.lower().strip()),
            )
            _commit(conn)
        finally:
            release_db(conn)

    @staticmethod
    def create(email: str, name: str, password: str):
        from werkzeug.security import generate_password_hash
        conn = get_db()
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO render_users (email, name, password_hash) VALUES (%s,%s,%s)",
                (email.lower().strip(), name, generate_password_hash(password)),
            )
            _commit(conn)
        finally:
            release_db(conn)


# ── Blank model ───────────────────────────────────────────────────────────────

class Blank:
    """Sign blank (substrate size/shape) model."""

    @staticmethod
    def all(active_only: bool = False):
        conn = get_db()
        try:
            cur = dict_cursor(conn)
            if active_only:
                cur.execute("SELECT * FROM render_blanks WHERE active=1 ORDER BY sort_order, slug")
            else:
                cur.execute("SELECT * FROM render_blanks ORDER BY sort_order, slug")
            return [dict(r) for r in cur.fetchall()]
        finally:
            release_db(conn)

    @staticmethod
    def get(slug: str):
        conn = get_db()
        try:
            cur = dict_cursor(conn)
            cur.execute("SELECT * FROM render_blanks WHERE slug = %s", (slug,))
            row = cur.fetchone()
            return dict(row) if row else None
        finally:
            release_db(conn)

    @staticmethod
    def create(data: dict):
        conn = get_db()
        try:
            cur = conn.cursor()
            peel = data.get("peel_bounds")
            cur.execute("""
                INSERT INTO render_blanks
                    (slug, display, width_mm, height_mm, is_circular, amazon_code,
                     sign_x, sign_y, sign_w, sign_h,
                     peel_x, peel_y, peel_w, peel_h,
                     has_portrait, active, sort_order)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                data["slug"], data["display"], data["width_mm"], data["height_mm"],
                1 if data.get("is_circular") else 0, data.get("amazon_code"),
                data["sign_x"], data["sign_y"], data["sign_w"], data["sign_h"],
                data.get("peel_x"), data.get("peel_y"),
                data.get("peel_w"), data.get("peel_h"),
                1 if data.get("has_portrait") else 0,
                1 if data.get("active", True) else 0,
                data.get("sort_order", 0),
            ))
            _commit(conn)
        finally:
            release_db(conn)

    @staticmethod
    def update(slug: str, data: dict):
        conn = get_db()
        try:
            cur = conn.cursor()
            fields, values = [], []
            allowed = {
                "display", "width_mm", "height_mm", "is_circular", "amazon_code",
                "sign_x", "sign_y", "sign_w", "sign_h",
                "peel_x", "peel_y", "peel_w", "peel_h",
                "has_portrait", "active", "sort_order",
            }
            for k, v in data.items():
                if k in allowed:
                    fields.append(f"{k} = %s")
                    values.append(v)
            if not fields:
                return
            values.append(slug)
            cur.execute(
                f"UPDATE render_blanks SET {', '.join(fields)} WHERE slug = %s",
                tuple(values),
            )
            _commit(conn)
        finally:
            release_db(conn)

    @staticmethod
    def as_image_generator_dict() -> dict:
        """
        Return blanks in the format image_generator.py expects:
            { slug: (width_mm, height_mm, is_circular) }
        """
        return {
            b["slug"]: (b["width_mm"], b["height_mm"], bool(b["is_circular"]))
            for b in Blank.all(active_only=True)
        }

    @staticmethod
    def sign_bounds_dict() -> dict:
        """{ slug: (sign_x, sign_y, sign_w, sign_h) } for active blanks."""
        return {
            b["slug"]: (b["sign_x"], b["sign_y"], b["sign_w"], b["sign_h"])
            for b in Blank.all(active_only=True)
        }

    @staticmethod
    def peel_bounds_dict() -> dict:
        """{ slug: (peel_x, peel_y, peel_w, peel_h) } for blanks that have peel overrides."""
        result = {}
        for b in Blank.all(active_only=True):
            if b["peel_x"] is not None:
                result[b["slug"]] = (b["peel_x"], b["peel_y"], b["peel_w"], b["peel_h"])
        return result


# ── Product model ─────────────────────────────────────────────────────────────

class Product:
    """Product model."""

    @staticmethod
    def _ensure_ean_string(d):
        if d and d.get("ean"):
            d["ean"] = str(d["ean"])
        return d

    @staticmethod
    def all():
        conn = get_db()
        try:
            cur = dict_cursor(conn)
            cur.execute("SELECT * FROM render_products ORDER BY m_number")
            return [Product._ensure_ean_string(dict(r)) for r in cur.fetchall()]
        finally:
            release_db(conn)

    @staticmethod
    def get(m_number):
        conn = get_db()
        try:
            cur = dict_cursor(conn)
            cur.execute(f"SELECT * FROM render_products WHERE m_number ={P}", (m_number,))
            row = cur.fetchone()
            return Product._ensure_ean_string(dict(row)) if row else None
        finally:
            release_db(conn)

    @staticmethod
    def approved():
        conn = get_db()
        try:
            cur = dict_cursor(conn)
            cur.execute("SELECT * FROM render_products WHERE qa_status = 'approved' ORDER BY m_number")
            return [Product._ensure_ean_string(dict(r)) for r in cur.fetchall()]
        finally:
            release_db(conn)

    @staticmethod
    def create(data):
        conn = get_db()
        try:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO render_products (m_number, description, size, color, layout_mode,
                    icon_files, text_line_1, text_line_2, text_line_3, orientation,
                    font, material, mounting_type, ean, qa_status,
                    icon_scale, text_scale, icon_offset_x, icon_offset_y)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                data.get("m_number"), data.get("description"), data.get("size"),
                data.get("color"), data.get("layout_mode", "A"), data.get("icon_files"),
                data.get("text_line_1"), data.get("text_line_2"), data.get("text_line_3"),
                data.get("orientation", "landscape"), data.get("font", "arial_heavy"),
                data.get("material", "1mm_aluminium"), data.get("mounting_type", "self_adhesive"),
                data.get("ean"), data.get("qa_status", "pending"),
                data.get("icon_scale", 1.0), data.get("text_scale", 1.0),
                data.get("icon_offset_x", 0.0), data.get("icon_offset_y", 0.0),
            ))
            _commit(conn)
        finally:
            release_db(conn)

    @staticmethod
    def update(m_number, data):
        conn = get_db()
        try:
            cur = conn.cursor()
            fields, values = [], []
            for k, v in data.items():
                # Allow explicit None to clear a field by using a sentinel check
                fields.append(f"{k} = %s")
                values.append(v)
            if not fields:
                return
            fields.append("updated_at = CURRENT_TIMESTAMP")
            values.append(m_number)
            cur.execute(
                f"UPDATE render_products SET {', '.join(fields)} WHERE m_number = %s",
                tuple(values),
            )
            _commit(conn)
        finally:
            release_db(conn)

    @staticmethod
    def delete(m_number):
        conn = get_db()
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM render_products WHERE m_number = %s", (m_number,))
            _commit(conn)
        finally:
            release_db(conn)

    @staticmethod
    def clear_all():
        conn = get_db()
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM render_products")
            _commit(conn)
        finally:
            release_db(conn)


class SalesImport:
    @staticmethod
    def create(filename, report_start, report_end, row_count, imported_by):
        conn = get_db()
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO render_sales_imports (filename, report_start, report_end, row_count, imported_by)"
                " VALUES (%s,%s,%s,%s,%s)",
                (filename, report_start, report_end, row_count, imported_by),
            )
            cur.execute("SELECT lastval()")
            return cur.fetchone()[0]
        finally:
            release_db(conn)

    @staticmethod
    def list_all():
        conn = get_db()
        try:
            cur = dict_cursor(conn)
            cur.execute("SELECT * FROM render_sales_imports ORDER BY imported_at DESC")
            return [dict(r) for r in cur.fetchall()]
        finally:
            release_db(conn)

    @staticmethod
    def import_exists(report_start, report_end):
        """Check if a report for this exact date range was already imported."""
        conn = get_db()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT id FROM render_sales_imports WHERE report_start=%s AND report_end=%s",
                (report_start, report_end),
            )
            return cur.fetchone() is not None
        finally:
            release_db(conn)


class SalesData:
    @staticmethod
    def bulk_insert(rows: list[dict]):
        """Insert a batch of sales rows. Each dict must have keys matching the table."""
        if not rows:
            return
        conn = get_db()
        try:
            cur = conn.cursor()
            for r in rows:
                cur.execute(
                    "INSERT INTO render_sales_data"
                    " (import_id,asin,parent_asin,sku,title,sessions,units,revenue,cvr,buy_box_pct,report_start,report_end)"
                    " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        r["import_id"], r["asin"], r["parent_asin"], r["sku"], r["title"],
                        r["sessions"], r["units"], r["revenue"], r["cvr"], r["buy_box_pct"],
                        r["report_start"], r["report_end"],
                    ),
                )
            _commit(conn)
        finally:
            release_db(conn)

    @staticmethod
    def top_performers(limit=50, min_units=1):
        """Return top products by revenue across all imports, deduplicated by SKU."""
        conn = get_db()
        try:
            cur = dict_cursor(conn)
            cur.execute(f"""
                SELECT
                    sku, parent_asin, title,
                    SUM(units)   AS total_units,
                    SUM(revenue) AS total_revenue,
                    SUM(sessions) AS total_sessions,
                    CASE WHEN SUM(sessions) > 0
                         THEN ROUND(CAST(SUM(units)*100.0/SUM(sessions) AS NUMERIC), 1)
                         ELSE 0 END AS blended_cvr,
                    COUNT(DISTINCT import_id) AS import_count
                FROM render_sales_data
                WHERE units >= {min_units}
                GROUP BY sku, parent_asin, title
                ORDER BY total_revenue DESC
                LIMIT {limit}
            """)
            return [dict(r) for r in cur.fetchall()]
        finally:
            release_db(conn)

    @staticmethod
    def category_summary():
        """Group top performers by inferred category."""
        conn = get_db()
        try:
            cur = dict_cursor(conn)
            cur.execute("""
                SELECT sku, title, SUM(units) AS units, SUM(revenue) AS revenue,
                       CASE WHEN SUM(sessions)>0
                            THEN ROUND(CAST(SUM(units)*100.0/SUM(sessions) AS NUMERIC),1) ELSE 0 END AS cvr
                FROM render_sales_data
                GROUP BY sku, title
                ORDER BY revenue DESC
            """)
            rows = [dict(r) for r in cur.fetchall()]
            return rows
        finally:
            release_db(conn)

    @staticmethod
    def for_sku(sku: str):
        conn = get_db()
        try:
            cur = dict_cursor(conn)
            cur.execute(
                "SELECT * FROM render_sales_data WHERE sku=%s ORDER BY report_end DESC", (sku,)
            )
            return [dict(r) for r in cur.fetchall()]
        finally:
            release_db(conn)

class CatalogueListing:
    """Parent listing in the render_catalogue_listing table."""

    @staticmethod
    def all():
        conn = get_db()
        try:
            cur = dict_cursor(conn)
            cur.execute("""
                SELECT l.*,
                  (SELECT count(*) FROM render_catalogue_variant v WHERE v.listing_id = l.id) AS variant_count,
                  (SELECT count(*) FROM render_catalogue_variant v WHERE v.listing_id = l.id AND v.amazon_status = 'live') AS amazon_live,
                  (SELECT count(*) FROM render_catalogue_variant v WHERE v.listing_id = l.id AND v.amazon_status = 'pending') AS amazon_pending,
                  (SELECT count(*) FROM render_catalogue_variant v WHERE v.listing_id = l.id AND v.amazon_status = 'unpublished') AS amazon_unpublished
                FROM render_catalogue_listing l
                ORDER BY l.internal_ref
            """)
            return [dict(r) for r in cur.fetchall()]
        finally:
            release_db(conn)

    @staticmethod
    def get(listing_id: int):
        conn = get_db()
        try:
            cur = dict_cursor(conn)
            cur.execute("SELECT * FROM render_catalogue_listing WHERE id = %s", (listing_id,))
            row = cur.fetchone()
            return dict(row) if row else None
        finally:
            release_db(conn)

    @staticmethod
    def summary() -> dict:
        """Aggregate stats for the Cairn context endpoint."""
        conn = get_db()
        try:
            cur = dict_cursor(conn)
            cur.execute("""
                SELECT
                  (SELECT count(*) FROM render_catalogue_listing)                                      AS total_listings,
                  (SELECT count(*) FROM render_catalogue_variant)                                      AS total_variants,
                  (SELECT count(*) FROM render_catalogue_variant WHERE amazon_status = 'live')         AS amazon_live,
                  (SELECT count(*) FROM render_catalogue_variant WHERE amazon_status = 'pending')      AS amazon_pending,
                  (SELECT count(*) FROM render_catalogue_variant WHERE amazon_status = 'unpublished')  AS amazon_unpublished,
                  (SELECT count(*) FROM render_ean_pool WHERE assigned_to IS NULL)                     AS ean_pool_remaining
            """)
            return dict(cur.fetchone())
        finally:
            release_db(conn)


class CatalogueVariant:
    """Child variant in the render_catalogue_variant table."""

    @staticmethod
    def for_listing(listing_id: int):
        conn = get_db()
        try:
            cur = dict_cursor(conn)
            cur.execute(
                "SELECT * FROM render_catalogue_variant WHERE listing_id = %s ORDER BY sku",
                (listing_id,),
            )
            return [dict(r) for r in cur.fetchall()]
        finally:
            release_db(conn)

    @staticmethod
    def unpublished():
        conn = get_db()
        try:
            cur = dict_cursor(conn)
            cur.execute(
                "SELECT sku, title_full, listing_id FROM render_catalogue_variant "
                "WHERE amazon_status = 'unpublished' ORDER BY sku"
            )
            return [dict(r) for r in cur.fetchall()]
        finally:
            release_db(conn)

    @staticmethod
    def recent_publishes(limit: int = 10):
        conn = get_db()
        try:
            cur = dict_cursor(conn)
            cur.execute(
                "SELECT sku, title_full, amazon_asin, amazon_published_at, amazon_status "
                "FROM render_catalogue_variant "
                "WHERE amazon_published_at IS NOT NULL "
                "ORDER BY amazon_published_at DESC LIMIT %s",
                (limit,),
            )
            return [dict(r) for r in cur.fetchall()]
        finally:
            release_db(conn)

    @staticmethod
    def all_for_export():
        """All variants with listing join for CSV export."""
        conn = get_db()
        try:
            cur = dict_cursor(conn)
            cur.execute("""
                SELECT
                  v.sku, v.ean, v.title_full, v.colour_name, v.size_name,
                  v.length_cm, v.width_cm, v.list_price, v.amazon_status,
                  v.amazon_asin, v.amazon_published_at, v.etsy_listing_id,
                  v.ebay_listing_id, v.image_urls
                FROM render_catalogue_variant v
                ORDER BY v.sku
            """)
            return [dict(r) for r in cur.fetchall()]
        finally:
            release_db(conn)

    @staticmethod
    def assign_ean(sku: str) -> str:
        """Atomically assign next available EAN from pool to a SKU."""
        conn = get_db()
        conn.autocommit = False
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT ean FROM render_ean_pool "
                "WHERE assigned_to IS NULL ORDER BY id LIMIT 1 FOR UPDATE SKIP LOCKED"
            )
            row = cur.fetchone()
            if not row:
                conn.rollback()
                raise ValueError("EAN pool exhausted — seed more EANs before assigning")
            ean = row[0]
            cur.execute(
                "UPDATE render_ean_pool SET assigned_to = %s, assigned_at = NOW() WHERE ean = %s",
                (sku, ean),
            )
            cur.execute(
                "UPDATE render_catalogue_variant SET ean = %s, updated_at = NOW() WHERE sku = %s",
                (ean, sku),
            )
            conn.commit()
            return ean
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.autocommit = True
            release_db(conn)


class EanPool:
    """render_ean_pool management."""

    @staticmethod
    def remaining() -> int:
        conn = get_db()
        try:
            cur = conn.cursor()
            cur.execute("SELECT count(*) FROM render_ean_pool WHERE assigned_to IS NULL")
            return cur.fetchone()[0]
        finally:
            release_db(conn)

    @staticmethod
    def seed(eans: list[str]) -> dict:
        """Insert EANs from a list; return inserted/skipped counts."""
        inserted = skipped = invalid = 0
        conn = get_db()
        try:
            cur = conn.cursor()
            for ean in eans:
                ean = ean.strip()
                if not ean.isdigit() or len(ean) != 13:
                    invalid += 1
                    continue
                try:
                    cur.execute(
                        "INSERT INTO render_ean_pool (ean) VALUES (%s) ON CONFLICT (ean) DO NOTHING",
                        (ean,),
                    )
                    if cur.rowcount:
                        inserted += 1
                    else:
                        skipped += 1
                except Exception:
                    skipped += 1
        finally:
            release_db(conn)
        return {"inserted": inserted, "skipped": skipped, "invalid": invalid}


if __name__ == "__main__":
    init_db()
    print("Database initialized.")
