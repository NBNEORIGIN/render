"""Fix EANs stored in scientific notation."""
from models import get_db, release_db

conn = get_db()
cur = conn.cursor()
cur.execute("UPDATE render_products SET ean = '' WHERE ean LIKE '%E+%'")
print(f"Cleared {cur.rowcount} scientific notation EANs")
release_db(conn)
