"""Bulk-fill missing faculty images for VIT Chennai.

Strategy:
1. Load faculty rows with no image_url from Supabase.
2. Prefer the existing profile_url, then try VIT-Chennai-specific search results.
3. Scrape the profile page for og:image / twitter:image / first useful image.
4. Download the image, upload it to Supabase Storage, and upsert faculty.image_url.
5. Write any unresolved faculty to a CSV so they can be checked manually.

Usage:
    python fill_missing_faculty_images.py
    python fill_missing_faculty_images.py --limit 20 --dry-run

Environment:
    SUPABASE_URL
    SUPABASE_KEY
    SUPABASE_BUCKET (optional, default: VITC fac images)

Notes:
- This script only uses stdlib + supabase + python-dotenv.
- It is intentionally conservative: it tries multiple sources and skips records
  that it cannot confidently resolve.
"""

from __future__ import annotations

import argparse
import csv
import html
import mimetypes
import os
import re
import sys
import time
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Iterable, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus, urljoin, urlparse
from urllib.request import Request, urlopen

from dotenv import load_dotenv
from supabase import Client, create_client


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
DEFAULT_BUCKET = "VITC fac images"
DEFAULT_SEARCH_SUFFIX = "chennai"
DEFAULT_OUT_CSV = "missing_faculty_image_unresolved.csv"
DEFAULT_UPLOAD_PREFIX = "faculty-images"


@dataclass
class FacultyRow:
    id: int
    employee_id: str
    name: str
    designation: str
    profile_url: str
    campus: str


class MetaImageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.meta_images: list[str] = []
        self.link_images: list[str] = []
        self.img_sources: list[str] = []
        self.canonical_url: Optional[str] = None

    def handle_starttag(self, tag: str, attrs):
        attr = {k.lower(): v for k, v in attrs if k}
        if tag.lower() == "meta":
            prop = (attr.get("property") or attr.get("name") or "").lower()
            content = (attr.get("content") or "").strip()
            if prop in {"og:image", "og:image:secure_url", "twitter:image", "twitter:image:src"} and content:
                self.meta_images.append(content)
        elif tag.lower() == "link":
            rel = (attr.get("rel") or "").lower()
            href = (attr.get("href") or "").strip()
            if rel == "canonical" and href:
                self.canonical_url = href
            if rel in {"image_src", "preload"} and href:
                self.link_images.append(href)
        elif tag.lower() == "img":
            src = (attr.get("src") or "").strip()
            srcset = (attr.get("srcset") or "").strip()
            if src:
                self.img_sources.append(src)
            elif srcset:
                first = srcset.split(",")[0].split()[0].strip()
                if first:
                    self.img_sources.append(first)


def log(msg: str) -> None:
    print(msg, flush=True)


def make_supabase() -> Client:
    load_dotenv()
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise SystemExit("SUPABASE_URL and SUPABASE_KEY must be set in .env")
    return create_client(url, key)


def fetch_text(url: str, timeout: int = 15) -> str:
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"})
    with urlopen(req, timeout=timeout) as resp:
        data = resp.read()
        charset = resp.headers.get_content_charset() or "utf-8"
    return data.decode(charset, errors="replace")


def fetch_bytes(url: str, timeout: int = 20) -> tuple[bytes, str]:
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "image/*,*/*;q=0.8"})
    with urlopen(req, timeout=timeout) as resp:
        data = resp.read()
        content_type = resp.headers.get_content_type() or "application/octet-stream"
    return data, content_type


def normalize_url(base_url: str, maybe_url: str) -> str:
    if not maybe_url:
        return ""
    maybe_url = html.unescape(maybe_url.strip())
    return urljoin(base_url, maybe_url)


def guess_slug_from_name(name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", name.lower()).strip("-")
    cleaned = re.sub(r"\b(dr|prof|mr|ms|mrs)\b-?", "", cleaned).strip("-")
    return cleaned


def search_duckduckgo(query: str, max_results: int = 5) -> list[str]:
    search_url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
    try:
        html_text = fetch_text(search_url, timeout=20)
    except Exception:
        return []

    results: list[str] = []
    # DuckDuckGo HTML result links commonly appear as /l/?uddg=<encoded-url>
    for match in re.finditer(r'href="(?P<href>(?:/l/\?uddg=|https?://)[^"]+)"', html_text, re.I):
        href = html.unescape(match.group("href"))
        if href.startswith("/l/?uddg="):
            from urllib.parse import unquote

            href = unquote(href.split("uddg=", 1)[1])
        if href.startswith("http") and href not in results:
            results.append(href)
        if len(results) >= max_results:
            break
    return results


def extract_image_url_from_html(page_url: str, html_text: str) -> Optional[str]:
    parser = MetaImageParser()
    try:
        parser.feed(html_text)
    except Exception:
        pass

    candidates: list[str] = []
    candidates.extend(parser.meta_images)
    candidates.extend(parser.link_images)
    candidates.extend(parser.img_sources)

    # Prefer VIT-hosted images and uploads directories.
    preferred_markers = ("wp-content/uploads", "/storage/v1/object/public/", ".jpg", ".jpeg", ".png", ".webp")
    scored: list[tuple[int, str]] = []
    for c in candidates:
        c = normalize_url(page_url, c)
        if not c:
            continue
        score = 0
        lower = c.lower()
        if any(m in lower for m in preferred_markers):
            score += 10
        if "vit" in lower:
            score += 3
        if any(x in lower for x in ("profile", "faculty", "member")):
            score += 2
        if any(x in lower for x in ("logo", "icon", "sprite", "avatar")):
            score -= 4
        scored.append((score, c))

    if scored:
        scored.sort(key=lambda t: t[0], reverse=True)
        return scored[0][1]

    return None


def resolve_profile_page(row: FacultyRow) -> Optional[str]:
    candidates: list[str] = []
    if row.profile_url:
        candidates.append(row.profile_url)

    slug = guess_slug_from_name(row.name)
    if slug:
        candidates.extend(
            [
                f"https://chennai.vit.ac.in/member/{slug}/",
                f"https://chennai.vit.ac.in/member/{slug}",
            ]
        )

    query = f'site:chennai.vit.ac.in/member/ "{row.name}" "{DEFAULT_SEARCH_SUFFIX}"'
    candidates.extend(search_duckduckgo(query, max_results=5))

    # de-duplicate while preserving order
    seen = set()
    ordered = []
    for url in candidates:
        if url and url not in seen:
            ordered.append(url)
            seen.add(url)

    for url in ordered:
        try:
            page = fetch_text(url, timeout=20)
        except (HTTPError, URLError, TimeoutError, ValueError):
            continue
        if not page:
            continue
        image_url = extract_image_url_from_html(url, page)
        if image_url:
            return image_url
    return None


def ensure_table_rows(supabase: Client) -> list[dict]:
    rows: list[dict] = []
    batch_size = 1000
    offset = 0
    while True:
        res = (
            supabase.table("faculty")
            .select("id, employee_id, name, designation, profile_url, campus, image_url")
            .is_("image_url", None)
            .eq("campus", "Chennai")
            .range(offset, offset + batch_size - 1)
            .execute()
        )
        batch = res.data or []
        rows.extend(batch)
        if len(batch) < batch_size:
            break
        offset += batch_size
    return rows


def ext_from_url_or_type(source_url: str, content_type: str) -> str:
    path = urlparse(source_url).path
    _, ext = os.path.splitext(path)
    ext = ext.lower()
    if ext in {".jpg", ".jpeg", ".png", ".webp"}:
        return ext
    guessed = mimetypes.guess_extension(content_type.split(";")[0].strip()) or ".jpg"
    if guessed == ".jpe":
        guessed = ".jpg"
    return guessed


def upload_and_upsert(
    supabase: Client,
    bucket_name: str,
    faculty: FacultyRow,
    image_url: str,
    dry_run: bool = False,
) -> Optional[str]:
    try:
        image_bytes, content_type = fetch_bytes(image_url)
    except Exception as exc:
        log(f"  [download-failed] {faculty.name}: {exc}")
        return None

    ext = ext_from_url_or_type(image_url, content_type)
    file_name = f"{faculty.employee_id}{ext}"
    public_url = f"{os.getenv('SUPABASE_URL').rstrip('/')}/storage/v1/object/public/{bucket_name}/{file_name}"

    if dry_run:
        log(f"  [dry-run] would upload {file_name} and set image_url for {faculty.name}")
        return public_url

    try:
        supabase.storage.from_(bucket_name).upload(
            file_name,
            image_bytes,
            file_options={"content-type": content_type, "x-upsert": "true"},
        )
    except Exception as exc:
        log(f"  [upload-failed] {faculty.name}: {exc}")
        return None

    try:
        supabase.table("faculty").update({"image_url": public_url}).eq("employee_id", faculty.employee_id).execute()
    except Exception as exc:
        log(f"  [db-update-failed] {faculty.name}: {exc}")
        return None

    return public_url


def main() -> int:
    parser = argparse.ArgumentParser(description="Fill missing faculty images from VIT Chennai profile pages.")
    parser.add_argument("--limit", type=int, default=0, help="Process only the first N unresolved faculty rows.")
    parser.add_argument("--dry-run", action="store_true", help="Resolve and print actions without uploading or updating the DB.")
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV, help="CSV file for unresolved rows.")
    parser.add_argument("--bucket", default=os.getenv("SUPABASE_BUCKET", DEFAULT_BUCKET), help="Supabase storage bucket.")
    parser.add_argument("--sleep", type=float, default=0.5, help="Seconds to sleep between records.")
    args = parser.parse_args()

    supabase = make_supabase()

    rows = ensure_table_rows(supabase)
    if args.limit and args.limit > 0:
        rows = rows[: args.limit]

    if not rows:
        log("No missing Chennai faculty images found.")
        return 0

    unresolved: list[dict] = []
    resolved_count = 0

    log(f"Processing {len(rows)} faculty rows...")
    for idx, row in enumerate(rows, start=1):
        faculty = FacultyRow(
            id=int(row.get("id") or 0),
            employee_id=str(row.get("employee_id") or "").strip(),
            name=str(row.get("name") or "").strip(),
            designation=str(row.get("designation") or "").strip(),
            profile_url=str(row.get("profile_url") or "").strip(),
            campus=str(row.get("campus") or "").strip(),
        )

        if not faculty.employee_id or not faculty.name:
            unresolved.append({**row, "reason": "missing employee_id or name"})
            continue

        log(f"[{idx}/{len(rows)}] {faculty.name}")
        image_url = resolve_profile_page(faculty)
        if not image_url:
            log("  [unresolved] could not find a profile image")
            unresolved.append({**row, "reason": "could not resolve profile image"})
            time.sleep(args.sleep)
            continue

        log(f"  found: {image_url}")
        public_url = upload_and_upsert(supabase, args.bucket, faculty, image_url, dry_run=args.dry_run)
        if public_url:
            resolved_count += 1
            log(f"  saved: {public_url}")
        else:
            unresolved.append({**row, "reason": "download/upload/db update failed"})

        time.sleep(args.sleep)

    if unresolved:
        with open(args.out_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["id", "employee_id", "name", "designation", "profile_url", "campus", "image_url", "reason"],
            )
            writer.writeheader()
            for row in unresolved:
                writer.writerow({
                    "id": row.get("id", ""),
                    "employee_id": row.get("employee_id", ""),
                    "name": row.get("name", ""),
                    "designation": row.get("designation", ""),
                    "profile_url": row.get("profile_url", ""),
                    "campus": row.get("campus", ""),
                    "image_url": row.get("image_url", ""),
                    "reason": row.get("reason", ""),
                })
        log(f"Unresolved rows written to {args.out_csv}")

    log("")
    log(f"Resolved:   {resolved_count}")
    log(f"Unresolved: {len(unresolved)}")
    log("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
