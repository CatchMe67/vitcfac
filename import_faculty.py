"""
import_faculty.py
────────────────
One-time script to load VIT faculty CSV into the database.

Usage:
    python import_faculty.py faculty.csv

The CSV must have this header (exactly):
    employee_id,name,designation,school_centre,date_of_joining,
    faculty_type,profile_url,campus,faculty_image_url
"""

import csv
import sys
import os
from datetime import datetime

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()


def get_db():
    return psycopg2.connect(
        host     = os.getenv("DB_HOST",     "localhost"),
        port     = int(os.getenv("DB_PORT", "3306")),
        user     = os.getenv("DB_USER",     "root"),
        password = os.getenv("DB_PASSWORD", ""),
        database = os.getenv("DB_NAME",     "proflore"),
        
        cursor_factory=psycopg2.extras.RealDictCursor,
        
    )


def parse_date(raw: str):
    """Handle DD-MM-YYYY or YYYY-MM-DD."""
    raw = raw.strip()
    if not raw:
        return None
    for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            pass
    print(f"  [warn] Could not parse date: '{raw}' — storing NULL")
    return None


def main():
    if len(sys.argv) < 2:
        print("Usage: python import_faculty.py <path/to/faculty.csv>")
        sys.exit(1)

    csv_path = sys.argv[1]
    db       = get_db()

    inserted = 0
    skipped  = 0
    errors   = 0

    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)

        # Normalise header names (strip whitespace)
        reader.fieldnames = [h.strip() for h in reader.fieldnames]

        for i, row in enumerate(reader, start=2):   # row 1 = header
            emp_id = row.get("employee_id", "").strip()
            if not emp_id:
                print(f"  [skip] Row {i}: empty employee_id")
                skipped += 1
                continue

            try:
                with db.cursor() as cur:
                    cur.execute("""
                        INSERT INTO faculty
                            (employee_id, name, designation, school_centre,
                             date_of_joining, faculty_type,
                             profile_url, campus, faculty_image_url)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                            name              = VALUES(name),
                            designation       = VALUES(designation),
                            school_centre     = VALUES(school_centre),
                            date_of_joining   = VALUES(date_of_joining),
                            faculty_type      = VALUES(faculty_type),
                            profile_url       = VALUES(profile_url),
                            campus            = VALUES(campus),
                            faculty_image_url = VALUES(faculty_image_url)
                    """, (
                        emp_id,
                        row.get("name",              "").strip(),
                        row.get("designation",       "").strip() or None,
                        row.get("school_centre",     "").strip() or None,
                        parse_date(row.get("date_of_joining", "")),
                        row.get("faculty_type",      "").strip() or None,
                        row.get("profile_url",       "").strip() or None,
                        row.get("campus",            "").strip() or None,
                        row.get("faculty_image_url", "").strip() or None,
                    ))
                inserted += 1

            except Exception as e:
                print(f"  [error] Row {i} (emp_id={emp_id}): {e}")
                errors += 1

    db.close()

    print(f"\nDone.")
    print(f"  Inserted/updated : {inserted}")
    print(f"  Skipped          : {skipped}")
    print(f"  Errors           : {errors}")


if __name__ == "__main__":
    main()
