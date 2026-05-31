"""Upload images from data/missing_fac to Supabase and update faculty.image_url.

Reads `missing_fac_final.txt` (CSV with header: id,employee_id,name,image_url).
For each row, looks for a local file in `data/missing_fac/` matching `employee_id` with common extensions.
Uploads file to Supabase storage bucket (default: `VITC fac images`) as `<employee_id><ext>` and updates
`public.faculty.image_url` to the public storage URL:

  {SUPABASE_URL}/storage/v1/object/public/{bucket}/{file_name}

Usage:
    python upload_and_update_images.py --input missing_fac_final.txt
    python upload_and_update_images.py --input missing_fac_final.txt --dry-run --limit 20

Environment variables required in .env:
    SUPABASE_URL
    SUPABASE_KEY
    SUPABASE_BUCKET (optional, default: "VITC fac images")

Outputs:
- Prints per-row status
- Writes `upload_failures.csv` for any failures
"""

from __future__ import annotations

import csv
import os
import mimetypes
import argparse
import time
from urllib.parse import quote
from dotenv import load_dotenv
from supabase import create_client, Client

COMMON_EXTS = [".jpg", ".jpeg", ".png", ".webp", ".gif"]
LOCAL_DIR = os.path.join("data", "missing_fac")
FAIL_CSV = "upload_failures.csv"


def find_local_image(employee_id: str, local_dir: str = LOCAL_DIR) -> tuple[str, str] | tuple[None, None]:
    """Return (path, ext) if found, else (None, None)."""
    if not employee_id:
        return None, None
    # exact match with any ext
    for ext in COMMON_EXTS:
        p = os.path.join(local_dir, f"{employee_id}{ext}")
        if os.path.exists(p):
            return p, ext
    # try any file starting with employee_id
    if os.path.exists(local_dir):
        for fn in os.listdir(local_dir):
            if fn.startswith(employee_id + "."):
                return os.path.join(local_dir, fn), os.path.splitext(fn)[1].lower()
    return None, None


def public_url(supabase_url: str, bucket: str, file_name: str) -> str:
    # bucket must be URL-encoded (spaces -> %20)
    enc_bucket = quote(bucket, safe="")
    return f"{supabase_url.rstrip('/')}/storage/v1/object/public/{enc_bucket}/{file_name}"


def upload_file_to_bucket(supabase: Client, bucket: str, file_name: str, file_bytes: bytes, content_type: str) -> bool:
    try:
        # x-upsert true to overwrite if exists
        supabase.storage.from_(bucket).upload(
            file_name,
            file_bytes,
            file_options={"content-type": content_type, "x-upsert": "true"}
        )
        return True
    except Exception as e:
        print(f"  [upload error] {e}")
        return False


def update_db_image_url(supabase: Client, faculty_id: int, new_url: str) -> bool:
    try:
        res = supabase.table("faculty").update({"image_url": new_url}).eq("id", faculty_id).execute()
        # res may contain error info depending on supabase client
        return True
    except Exception as e:
        print(f"  [db update error] {e}")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Upload images to Supabase and update faculty.image_url")
    parser.add_argument("--input", "-i", default="missing_fac_final.txt", help="CSV input file")
    parser.add_argument("--bucket", default=os.getenv("SUPABASE_BUCKET", "VITC fac images"), help="Supabase storage bucket name")
    parser.add_argument("--local-dir", default=LOCAL_DIR, help="Local dir containing images")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=0, help="Limit rows processed")
    parser.add_argument("--sleep", type=float, default=0.25, help="Seconds between uploads")
    args = parser.parse_args()

    load_dotenv()
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    if not supabase_url or not supabase_key:
        print("SUPABASE_URL and SUPABASE_KEY must be set in environment (.env)")
        return 2

    supabase = create_client(supabase_url, supabase_key)

    if not os.path.exists(args.input):
        print(f"Input CSV not found: {args.input}")
        return 2

    failures = []
    processed = 0

    with open(args.input, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, start=1):
            if args.limit and processed >= args.limit:
                break

            fid = row.get("id")
            emp = (row.get("employee_id") or "").strip()
            if not fid or not emp:
                failures.append({**row, "reason": "missing id or employee_id"})
                continue

            print(f"[{i}] id={fid} emp={emp}")

            local_path, ext = find_local_image(emp, args.local_dir)
            if not local_path:
                print("  local file not found; skipping")
                failures.append({**row, "reason": "local file not found"})
                continue

            # read bytes
            with open(local_path, "rb") as rf:
                file_bytes = rf.read()

            content_type = mimetypes.guess_type(local_path)[0] or "application/octet-stream"
            file_name = f"{emp}{ext}"
            dest_url = public_url(supabase_url, args.bucket, file_name)

            if args.dry_run:
                print(f"  dry-run: would upload {local_path} -> {file_name} and set image_url -> {dest_url}")
                processed += 1
                continue

            ok = upload_file_to_bucket(supabase, args.bucket, file_name, file_bytes, content_type)
            if not ok:
                failures.append({**row, "reason": "upload failed"})
                continue

            ok2 = update_db_image_url(supabase, int(fid), dest_url)
            if not ok2:
                failures.append({**row, "reason": "db update failed"})
                continue

            print(f"  uploaded and updated -> {dest_url}")
            processed += 1
            time.sleep(args.sleep)

    if failures:
        keys = list(failures[0].keys())
        with open(FAIL_CSV, "w", newline="", encoding="utf-8") as ff:
            writer = csv.DictWriter(ff, fieldnames=keys)
            writer.writeheader()
            writer.writerows(failures)
        print(f"Wrote failures to {FAIL_CSV}")

    print(f"Done. Processed: {processed}, Failures: {len(failures)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
