"""Database models for SignMaker."""
import os
from datetime import datetime
from pathlib import Path

# Use SQLite for local dev, PostgreSQL for production
DATABASE_URL = os.environ.get("DATABASE_URL", "")

if DATABASE_URL.startswith("postgres"):
    # PostgreSQL (Render) with connection pooling
    import psycopg2
    from psycopg2 import pool
    from psycopg2.extras import RealDictCursor
    
    # Create connection pool (min 2, max 10 connections)
    _connection_pool = None
    
    def _get_pool():
        global _connection_pool
        if _connection_pool is None:
            _connection_pool = pool.SimpleConnectionPool(
                minconn=2,
                maxconn=10,
                dsn=DATABASE_URL
            )
        return _connection_pool
    
    def get_db():
        pool = _get_pool()
        conn = pool.getconn()
        conn.autocommit = True
        return conn
    
    def release_db(conn):
        """Release connection back to pool."""
        pool = _get_pool()
        pool.putconn(conn)
    
    def dict_cursor(conn):
        return conn.cursor(cursor_factory=RealDictCursor)
else:
    # SQLite (local development)
    import sqlite3
    
    DB_PATH = Path(__file__).parent / "signmaker.db"
    
    def get_db():
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        return conn
    
    def release_db(conn):
        """Close connection (no pooling for SQLite)."""
        conn.close()
    
    def dict_cursor(conn):
        return conn.cursor()


def init_db():
    """Initialize database tables."""
    conn = get_db()
    cur = conn.cursor()
    
    # Use SERIAL for PostgreSQL, INTEGER PRIMARY KEY for SQLite
    is_postgres = DATABASE_URL.startswith("postgres")
    id_type = "SERIAL PRIMARY KEY" if is_postgres else "INTEGER PRIMARY KEY AUTOINCREMENT"
    
    # Products table
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
    
    # Add AI columns if they don't exist (for existing databases)
    try:
        cur.execute("ALTER TABLE products ADD COLUMN ai_theme TEXT")
    except:
        pass
    try:
        cur.execute("ALTER TABLE products ADD COLUMN ai_use_cases TEXT")
    except:
        pass
    try:
        cur.execute("ALTER TABLE products ADD COLUMN ai_content TEXT")
    except:
        pass
    
    # Generated content table
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
    
    # Image URLs table
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS product_images (
            id {id_type},
            product_id INTEGER REFERENCES products(id),
            image_type TEXT,
            url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Batches/Jobs table (for tracking pipeline runs)
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS batches (
            id {id_type},
            name TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP
        )
    """)
    
    conn.commit()
    conn.close()


class Product:
    """Product model."""
    
    @staticmethod
    def _ensure_ean_string(product_dict):
        """Ensure EAN is always a string (not scientific notation)."""
        if product_dict and product_dict.get('ean'):
            product_dict['ean'] = str(product_dict['ean'])
        return product_dict
    
    @staticmethod
    def all():
        conn = get_db()
        try:
            cur = dict_cursor(conn)
            cur.execute("SELECT * FROM products ORDER BY m_number")
            rows = cur.fetchall()
            return [Product._ensure_ean_string(dict(row)) for row in rows]
        finally:
            release_db(conn)
    
    @staticmethod
    def get(m_number):
        conn = get_db()
        try:
            cur = dict_cursor(conn)
            cur.execute("SELECT * FROM products WHERE m_number = %s", (m_number,))
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
            rows = cur.fetchall()
            return [Product._ensure_ean_string(dict(row)) for row in rows]
        finally:
            release_db(conn)
    
    @staticmethod
    def create(data):
        conn = get_db()
        try:
            cur = conn.cursor()
            # Use %s for both PostgreSQL and SQLite (psycopg2 and sqlite3 both support it)
            cur.execute("""
                INSERT INTO products (m_number, description, size, color, layout_mode, 
                    icon_files, text_line_1, text_line_2, text_line_3, orientation,
                    font, material, mounting_type, ean, qa_status, icon_scale, text_scale,
                    icon_offset_x, icon_offset_y)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                data.get('m_number'), data.get('description'), data.get('size'),
                data.get('color'), data.get('layout_mode', 'A'), data.get('icon_files'),
                data.get('text_line_1'), data.get('text_line_2'), data.get('text_line_3'),
                data.get('orientation', 'landscape'), data.get('font', 'arial_heavy'),
                data.get('material', '1mm_aluminium'), data.get('mounting_type', 'self_adhesive'),
                data.get('ean'), data.get('qa_status', 'pending'),
                data.get('icon_scale', 1.0), data.get('text_scale', 1.0),
                data.get('icon_offset_x', 0.0), data.get('icon_offset_y', 0.0)
            ))
            if not DATABASE_URL.startswith("postgres"):
                conn.commit()  # Only needed for SQLite (PostgreSQL has autocommit)
        finally:
            release_db(conn)
    
    @staticmethod
    def update(m_number, data):
        conn = get_db()
        try:
            cur = conn.cursor()
            fields = []
            values = []
            for key, value in data.items():
                if value is not None:
                    fields.append(f"{key} = ?")
                    values.append(value)
            
            if not fields:
                # Nothing to update
                return
            
            values.append(m_number)
            sql = f"UPDATE products SET {', '.join(fields)}, updated_at = CURRENT_TIMESTAMP WHERE m_number = ?"
            cur.execute(sql, values)
            conn.commit()
        finally:
            release_db(conn)
    
    @staticmethod
    def delete(m_number):
        conn = get_db()
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM products WHERE m_number = %s", (m_number,))
            if not DATABASE_URL.startswith("postgres"):
                conn.commit()  # Only needed for SQLite (PostgreSQL has autocommit)
        finally:
            release_db(conn)
    
    @staticmethod
    def clear_all():
        """Delete all products."""
        conn = get_db()
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM products")
            conn.commit()
        finally:
            release_db(conn)


if __name__ == "__main__":
    init_db()
    print("Database initialized.")
