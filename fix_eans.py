"""Fix EANs stored in scientific notation."""
import sqlite3

conn = sqlite3.connect('signmaker.db')
cur = conn.cursor()

# Clear EANs that are in scientific notation format
cur.execute("UPDATE products SET ean = '' WHERE ean LIKE '%E+%'")
print(f"Cleared {cur.rowcount} scientific notation EANs")

conn.commit()
conn.close()
