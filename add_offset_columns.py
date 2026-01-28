import sqlite3

conn = sqlite3.connect('signmaker.db')
cur = conn.cursor()

# Check existing columns
cur.execute("PRAGMA table_info(products)")
columns = [row[1] for row in cur.fetchall()]
print(f"Existing columns: {columns}")

# Add columns if they don't exist
if 'icon_offset_x' not in columns:
    cur.execute('ALTER TABLE products ADD COLUMN icon_offset_x REAL DEFAULT 0.0')
    print("Added icon_offset_x column")
else:
    print("icon_offset_x already exists")

if 'icon_offset_y' not in columns:
    cur.execute('ALTER TABLE products ADD COLUMN icon_offset_y REAL DEFAULT 0.0')
    print("Added icon_offset_y column")
else:
    print("icon_offset_y already exists")

conn.commit()
conn.close()
print("Done")
