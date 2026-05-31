"""Download missing faculty images listed in a CSV-like file.

Reads `missing_fac_final.txt` (or any CSV file) with header containing `employee_id` and `image_url`.
Saves each image as `<employee_id><ext>` into `data/missing_fac/`.
Writes failures to `download_failures.csv`.

Usage:
    python download_missing_fac_images.py --input missing_fac_final.txt
    python download_missing_fac_images.py --input missing_fac_final.txt --out data/missing_fac --dry-run --limit 50
"""

from __future__ import annotations

import argparse
import csv
import mimetypes
import os
import ssl
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
DEFAULT_OUT_DIR = os.path.join("data", "missing_fac")
DEFAULT_FAIL_CSV = "download_failures.csv"


# Try to build a certifi-backed SSL context. If certifi isn't installed we'll
# fall back to the system default context. The CLI exposes `--insecure` to
# explicitly disable verification when necessary (not recommended).
try:
    import certifi  # type: ignore
    DEFAULT_SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except Exception:
    DEFAULT_SSL_CONTEXT = ssl.create_default_context()


def sanitize_employee_id(emp_id: str) -> str:
    return emp_id.strip()


def guess_ext_from_url(url: str) -> str:
    path = urlparse(url).path
    base, ext = os.path.splitext(path)
    ext = ext.lower()
    if ext in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        return ext
    return ""


def ext_from_content_type(content_type: str) -> str:
    if not content_type:
        return ".jpg"
    ct = content_type.split(";")[0].strip()
    ext = mimetypes.guess_extension(ct) or ".jpg"
    if ext == ".jpe":
        ext = ".jpg"
    return ext


def fetch_image_bytes(url: str, timeout: int = 20, context: ssl.SSLContext | None = None) -> tuple[bytes, str]:
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "image/*,*/*;q=0.8"})
    # urlopen accepts a context parameter for SSL verification control
    if context is not None:
        with urlopen(req, timeout=timeout, context=context) as resp:
            data = resp.read()
            content_type = resp.headers.get_content_type() or "application/octet-stream"
    else:
        with urlopen(req, timeout=timeout) as resp:
            data = resp.read()
            content_type = resp.headers.get_content_type() or "application/octet-stream"
    return data, content_type


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def process_rows(input_path: str, out_dir: str, dry_run: bool = False, limit: int = 0, sleep: float = 0.2, ssl_context: ssl.SSLContext | None = None) -> int:
    ensure_dir(out_dir)
    failures = []
    processed = 0

    with open(input_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, start=1):
            if limit and processed >= limit:
                break

            emp = sanitize_employee_id(row.get("employee_id", "") or row.get("employee id", ""))
            img_url = (row.get("image_url") or row.get("image url") or "").strip()
            if not emp or not img_url:
                failures.append({**row, "reason": "missing employee_id or image_url"})
                continue

            print(f"[{i}] {emp} -> {img_url}")

            ext = guess_ext_from_url(img_url)
            try:
                # Determine extension by URL if available, otherwise fetch bytes
                if not ext:
                    data, content_type = fetch_image_bytes(img_url, context=ssl_context)
                    ext = ext_from_content_type(content_type)
                else:
                    if dry_run:
                        print("  dry-run: would download (skipping actual fetch)")
                        processed += 1
                        continue
                    data, content_type = fetch_image_bytes(img_url, context=ssl_context)
                    if not ext:
                        ext = ext_from_content_type(content_type)

                file_name = f"{emp}{ext}"
                out_path = os.path.join(out_dir, file_name)

                if dry_run:
                    print(f"  dry-run: would save to {out_path}")
                    processed += 1
                    continue

                # write file
                with open(out_path, "wb") as wf:
                    wf.write(data)

                print(f"  saved: {out_path}")
                processed += 1

            except (HTTPError, URLError) as err:
                print(f"  failed to fetch: {err}")
                failures.append({**row, "reason": f"fetch error: {err}"})
            except Exception as err:
                print(f"  unexpected error: {err}")
                failures.append({**row, "reason": f"error: {err}"})

            time.sleep(sleep)

    # write failures
    if failures:
        with open(DEFAULT_FAIL_CSV, "w", newline="", encoding="utf-8") as ff:
            keys = list(failures[0].keys())
            writer = csv.DictWriter(ff, fieldnames=keys)
            writer.writeheader()
            writer.writerows(failures)
        print(f"Wrote failures to {DEFAULT_FAIL_CSV}")

    print(f"Done. Processed: {processed}, Failures: {len(failures)}")
    return processed


def main() -> int:
    parser = argparse.ArgumentParser(description="Download missing faculty images from CSV")
    parser.add_argument("--input", "-i", default="missing_fac_final.txt", help="Input CSV file path")
    parser.add_argument("--out", "-o", default=DEFAULT_OUT_DIR, help="Output directory")
    parser.add_argument("--dry-run", action="store_true", help="Do not download or write files; print actions only")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of rows to process")
    parser.add_argument("--sleep", type=float, default=0.2, help="Seconds to sleep between downloads")
    parser.add_argument("--insecure", action="store_true", help="Disable SSL certificate verification (insecure)")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Input file not found: {args.input}")
        return 2

    # Decide SSL context
    if args.insecure:
        print("WARNING: running with SSL verification disabled (--insecure). This is insecure.")
        ssl_context = ssl._create_unverified_context()
    else:
        ssl_context = DEFAULT_SSL_CONTEXT

    process_rows(args.input, args.out, dry_run=args.dry_run, limit=args.limit, sleep=args.sleep, ssl_context=ssl_context)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
