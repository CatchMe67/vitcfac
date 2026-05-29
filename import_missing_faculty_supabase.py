import csv
import os
import sys
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

url: str = os.getenv("SUPABASE_URL")
key: str = os.getenv("SUPABASE_KEY")

if not url or not key:
    print("Error: SUPABASE_URL and SUPABASE_KEY must be set in .env")
    sys.exit(1)

supabase: Client = create_client(url, key)

def main():
    csv_path = r"C:\Users\aditya\Desktop\Project\facReviewWEBSITE\missingFaculty_ready.csv"
    
    if not os.path.exists(csv_path):
        print(f"File not found: {csv_path}")
        sys.exit(1)

    inserted = 0
    errors = 0

    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, start=2):
            emp_id = row.get("employee_id", "").strip()
            if not emp_id:
                continue

            try:
                # Upsert to supabase with valid columns
                data = {
                    "employee_id": emp_id,
                    "name": row.get("name", "").strip(),
                    "designation": row.get("designation", "").strip() or None,
                    "profile_url": row.get("profile_url", "").strip() or None,
                    "campus": row.get("campus", "").strip() or None,
                    "image_url": row.get("faculty_image_url", "").strip() or None
                }
                
                # Check for on_conflict parameter. Supabase python sometimes uses on_conflict
                res = supabase.table("faculty").upsert(data, on_conflict="employee_id").execute()
                inserted += 1
            except Exception as e:
                print(f"  [error] Row {i} (emp_id={emp_id}): {e}")
                errors += 1

    print(f"\nDone.")
    print(f"  Upserted : {inserted}")
    print(f"  Errors   : {errors}")

if __name__ == "__main__":
    main()
