"""Database models for Render."""
import json
import os
from pathlib import Path

DATABASE_URL = os.getenv("DATABASE_URL", "")

P = "%s" if DATABASE_URL.startswith("postgres") else "?"  # SQL placeholder


def get_placeholder():
    return P


if DATABASE_URL.startswith("postgres"):
    import psycopg2
    from psycopg2 import pool
    from psycopg2.extras import RealDictCursor

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

else:
    import sqlite3

    DB_PATH = Path(__file__).parent / "render.db"

    def get_db():
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        return conn

    def release_db(conn):
        conn.close()

    def dict_cursor(conn):
        return conn.cursor()


def _commit(conn):
    """Commit only for SQLite; PostgreSQL runs with autocommit."""
    if not DATABASE_URL.startswith("postgres"):
        conn.commit()


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
    """Create or migrate all database tables."""
    conn = get_db()
    cur = conn.cursor()

    is_postgres = DATABASE_URL.startswith("postgres")
    id_type = "SERIAL PRIMARY KEY" if is_postgres else "INTEGER PRIMARY KEY AUTOINCREMENT"

    # ── blanks ───────────────────────────────────────────────────────────────
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS blanks (
            id {id_type},
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

    # ── products ─────────────────────────────────────────────────────────────
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS products (
            id {id_type},
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
    # Backfill columns added after initial release
    for col, typ in [("ai_theme", "TEXT"), ("ai_use_cases", "TEXT"), ("ai_content", "TEXT")]:
        _alter_add(cur, "products", col, typ)

    # ── product_content ───────────────────────────────────────────────────────
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS product_content (
            id {id_type},
            product_id INTEGER REFERENCES products(id),
            title TEXT,
            description TEXT,
            bullet_points TEXT,
            search_terms TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── product_images ────────────────────────────────────────────────────────
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS product_images (
            id {id_type},
            product_id INTEGER REFERENCES products(id),
            image_type TEXT,
            url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── batches ───────────────────────────────────────────────────────────────
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS batches (
            id {id_type},
            name TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP
        )
    """)

    _commit(conn)
    release_db(conn)

    # Seed blanks from config if the table is empty
    _seed_blanks()


def _seed_blanks():
    """Populate the blanks table from BLANK_SEEDS if it has no rows."""
    from config import BLANK_SEEDS

    conn = get_db()
    try:
        cur = dict_cursor(conn)
        cur.execute("SELECT COUNT(*) as n FROM blanks")
        row = dict(cur.fetchone())
        if row["n"] > 0:
            return

        cur2 = conn.cursor()
        for i, (slug, b) in enumerate(BLANK_SEEDS.items()):
            peel = b.get("peel_bounds")
            cur2.execute(f"""
                INSERT INTO blanks
                    (slug, display, width_mm, height_mm, is_circular, amazon_code,
                     sign_x, sign_y, sign_w, sign_h,
                     peel_x, peel_y, peel_w, peel_h,
                     has_portrait, active, sort_order)
                VALUES
                    ({P},{P},{P},{P},{P},{P},{P},{P},{P},{P},{P},{P},{P},{P},{P},{P},{P})
            """, (
                slug, b["display"], b["width_mm"], b["height_mm"],
                1 if b["is_circular"] else 0, b["amazon_code"],
                b["sign_bounds"][0], b["sign_bounds"][1],
                b["sign_bounds"][2], b["sign_bounds"][3],
                peel[0] if peel else None, peel[1] if peel else None,
                peel[2] if peel else None, peel[3] if peel else None,
                1 if b["has_portrait"] else 0, 1, i,
            ))
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
                cur.execute("SELECT * FROM blanks WHERE active=1 ORDER BY sort_order, slug")
            else:
                cur.execute("SELECT * FROM blanks ORDER BY sort_order, slug")
            return [dict(r) for r in cur.fetchall()]
        finally:
            release_db(conn)

    @staticmethod
    def get(slug: str):
        conn = get_db()
        try:
            cur = dict_cursor(conn)
            cur.execute(f"SELECT * FROM blanks WHERE slug = {P}", (slug,))
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
            cur.execute(f"""
                INSERT INTO blanks
                    (slug, display, width_mm, height_mm, is_circular, amazon_code,
                     sign_x, sign_y, sign_w, sign_h,
                     peel_x, peel_y, peel_w, peel_h,
                     has_portrait, active, sort_order)
                VALUES ({P},{P},{P},{P},{P},{P},{P},{P},{P},{P},{P},{P},{P},{P},{P},{P},{P})
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
                    fields.append(f"{k} = {P}")
                    values.append(v)
            if not fields:
                return
            values.append(slug)
            cur.execute(
                f"UPDATE blanks SET {', '.join(fields)} WHERE slug = {P}",
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
            cur.execute("SELECT * FROM products ORDER BY m_number")
            return [Product._ensure_ean_string(dict(r)) for r in cur.fetchall()]
        finally:
            release_db(conn)

    @staticmethod
    def get(m_number):
        conn = get_db()
        try:
            cur = dict_cursor(conn)
            cur.execute(f"SELECT * FROM products WHERE m_number = {P}", (m_number,))
            row = cur.fetchone()
            return Product._ensure_ean_string(dict(row)) if row else None
        finally:
            release_db(conn)

    @staticmethod
    def approved():
        conn = get_db()
        try:
            cur = dict_cursor(conn)
            cur.execute("SELECT * FROM products WHERE qa_status = 'approved' ORDER BY m_number")
            return [Product._ensure_ean_string(dict(r)) for r in cur.fetchall()]
        finally:
            release_db(conn)

    @staticmethod
    def create(data):
        conn = get_db()
        try:
            cur = conn.cursor()
            cur.execute(f"""
                INSERT INTO products (m_number, description, size, color, layout_mode,
                    icon_files, text_line_1, text_line_2, text_line_3, orientation,
                    font, material, mounting_type, ean, qa_status,
                    icon_scale, text_scale, icon_offset_x, icon_offset_y)
                VALUES ({P},{P},{P},{P},{P},{P},{P},{P},{P},{P},{P},{P},{P},{P},{P},{P},{P},{P},{P})
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
                fields.append(f"{k} = {P}")
                values.append(v)
            if not fields:
                return
            fields.append("updated_at = CURRENT_TIMESTAMP")
            values.append(m_number)
            cur.execute(
                f"UPDATE products SET {', '.join(fields)} WHERE m_number = {P}",
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
            cur.execute(f"DELETE FROM products WHERE m_number = {P}", (m_number,))
            _commit(conn)
        finally:
            release_db(conn)

    @staticmethod
    def clear_all():
        conn = get_db()
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM products")
            _commit(conn)
        finally:
            release_db(conn)


if __name__ == "__main__":
    init_db()
    print("Database initialized.")
