"""
Recovery script — rebuild render_products from image evidence.

Run on Hetzner: docker exec render-app-1 python /app/recover_products.py
"""
import os
import sys
from models import get_db, release_db

BLANKS_ORDER = [
    ("dracula",    "9.5 x 9.5 cm"),
    ("saville",    "11 x 9.5 cm"),
    ("dick",       "14 x 9 cm"),
    ("barzan",     "19 x 14 cm"),
    ("baby_jesus", "29 x 19 cm"),
]
COLORS = ["silver", "gold", "white"]


def next_ean(cur) -> str:
    cur.execute(
        "DELETE FROM render_ean_pool WHERE ean = "
        "(SELECT ean FROM render_ean_pool WHERE assigned_to IS NULL ORDER BY ean LIMIT 1) "
        "RETURNING ean"
    )
    row = cur.fetchone()
    if not row:
        raise RuntimeError("EAN pool exhausted")
    return row[0]


def make_batch(cur, start_m: int, description: str, icon_files: str = "",
               text_line_1: str = "", text_line_2: str = "", text_line_3: str = "",
               layout_mode: str = "A", font: str = "arial_heavy",
               icon_scale: float = 1.0, text_scale: float = 1.0,
               icon_offset_x: float = 0.0, icon_offset_y: float = 0.0,
               dry_run: bool = False) -> list[int]:
    """Insert 15 products (5 blanks × 3 colors) starting at start_m."""
    inserted = []
    m = start_m
    for blank_slug, _ in BLANKS_ORDER:
        for color in COLORS:
            ean = next_ean(cur)
            if not dry_run:
                cur.execute(
                    """
                    INSERT INTO render_products
                        (m_number, description, size, color, layout_mode, icon_files,
                         text_line_1, text_line_2, text_line_3,
                         orientation, font, material, mounting_type, ean,
                         qa_status, icon_scale, text_scale,
                         icon_offset_x, icon_offset_y)
                    VALUES
                        (%s, %s, %s, %s, %s, %s,
                         %s, %s, %s,
                         'landscape', %s, '1mm_aluminium', 'self_adhesive', %s,
                         'approved', %s, %s, %s, %s)
                    ON CONFLICT (m_number) DO NOTHING
                    """,
                    (f"M{m}", description, blank_slug, color, layout_mode, icon_files,
                     text_line_1, text_line_2, text_line_3,
                     font, ean, icon_scale, text_scale, icon_offset_x, icon_offset_y)
                )
            print(f"  M{m}  {blank_slug:12s}  {color:8s}  EAN={ean}")
            inserted.append(m)
            m += 1
    return inserted


def restore_reception(cur, dry_run=False):
    """Restore exact Reception data from the April 8 backup."""
    rows = [
        # (m_number, blank_slug, color, ean, icon_scale)
        (4005, "dracula",    "silver", "5056338677273", 1.25),
        (4006, "dracula",    "gold",   "5056338677280", 1.25),
        (4007, "dracula",    "white",  "5056338677297", 1.25),
        (4008, "saville",    "silver", "5056338677303", 1.20),
        (4009, "saville",    "gold",   "5056338677310", 1.20),
        (4010, "saville",    "white",  "5056338677327", 1.20),
        (4011, "dick",       "silver", "5056338677334", 1.50),
        (4012, "dick",       "gold",   "5056338677341", 1.50),
        (4013, "dick",       "white",  "5056338677358", 1.50),
        (4014, "barzan",     "silver", "5056338677365", 1.35),
        (4015, "barzan",     "gold",   "5056338677372", 1.35),
        (4016, "barzan",     "white",  "5056338677389", 1.35),
        (4017, "baby_jesus", "silver", "5056338677396", 1.50),
        (4018, "baby_jesus", "gold",   "5056338677402", 1.50),
        (4019, "baby_jesus", "white",  "5056338677419", 1.50),
    ]
    # Remove these specific EANs from the pool (they are permanently consumed)
    for m_num, blank_slug, color, ean, icon_scale in rows:
        if not dry_run:
            cur.execute("DELETE FROM render_ean_pool WHERE ean = %s", (ean,))
            cur.execute(
                """
                INSERT INTO render_products
                    (m_number, description, size, color, layout_mode, icon_files,
                     orientation, font, material, mounting_type, ean,
                     qa_status, icon_scale, text_scale, icon_offset_x, icon_offset_y)
                VALUES
                    (%s, 'Reception', %s, %s, 'A', 'icon_template_100mm.svg',
                     'landscape', 'arial_heavy', '1mm_aluminium', 'self_adhesive', %s,
                     'approved', %s, 1.0, 0.0, 0.0)
                ON CONFLICT (m_number) DO NOTHING
                """,
                (f"M{m_num}", blank_slug, color, ean, icon_scale)
            )
        print(f"  M{m_num}  {blank_slug:12s}  {color:8s}  EAN={ean}  (backup)")


def main():
    dry_run = "--dry-run" in sys.argv
    if dry_run:
        print("DRY RUN — no changes will be committed")

    conn = get_db()
    conn.autocommit = False
    cur = conn.cursor()

    try:
        # Check current state
        cur.execute("SELECT count(*) FROM render_products")
        existing = cur.fetchone()[0]
        print(f"Current render_products count: {existing}")
        if existing > 0 and "--force" not in sys.argv:
            print("Products already exist. Use --force to overwrite. Aborting.")
            return

        print("\n=== Restoring Reception (M4005-M4019) from backup ===")
        restore_reception(cur, dry_run)

        print("\n=== Please Do Not Waste Water (M2960-M2974) ===")
        make_batch(cur, 2960, "Please Do Not Waste Water",
                   icon_files="", text_line_1="PLEASE DO NOT", text_line_2="WASTE WATER",
                   icon_scale=1.0, dry_run=dry_run)

        print("\n=== Please Wait Here (M2975-M2989) ===")
        make_batch(cur, 2975, "Please Wait Here",
                   icon_files="", text_line_1="PLEASE", text_line_2="WAIT HERE",
                   icon_scale=1.0, dry_run=dry_run)

        print("\n=== Please Wait To Be Served (M2990-M3004) ===")
        make_batch(cur, 2990, "Please Wait To Be Served",
                   icon_files="", text_line_1="PLEASE WAIT", text_line_2="TO BE", text_line_3="SERVED",
                   icon_scale=1.0, dry_run=dry_run)

        print("\n=== Please Do Not Knock (M4020-M4034) ===")
        make_batch(cur, 4020, "Please Do Not Knock",
                   icon_files="", text_line_1="PLEASE DO NOT", text_line_2="KNOCK",
                   icon_scale=1.0, dry_run=dry_run)

        print("\n=== Please Use Other Door (M4050-M4064) ===")
        make_batch(cur, 4050, "Please Use Other Door",
                   icon_files="", text_line_1="PLEASE USE", text_line_2="OTHER DOOR",
                   icon_scale=1.0, dry_run=dry_run)

        print("\n=== No Public Toilets (M4080-M4094) ===")
        make_batch(cur, 4080, "No Public Toilets",
                   icon_files="", text_line_1="NO PUBLIC", text_line_2="TOILETS",
                   icon_scale=1.0, dry_run=dry_run)

        if not dry_run:
            conn.commit()
            cur.execute("SELECT count(*) FROM render_products")
            print(f"\nDone. render_products now has {cur.fetchone()[0]} rows.")
        else:
            conn.rollback()
            print("\nDry run complete — no changes made.")

    except Exception as e:
        conn.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        release_db(conn)


if __name__ == "__main__":
    main()
