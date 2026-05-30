"""
Flask Backend (PostgreSQL via Supabase)
===================================================
Install:
    pip install -r requirements.txt

Run:
    python app.py
"""

import os
import time
import base64
from functools import wraps
from datetime import datetime
from collections import Counter
from html import escape

import urllib.request
import rjsmin
import rcssmin
from flask import Flask, request, jsonify, g, send_from_directory, Response
from flask_cors import CORS
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

app = Flask(__name__, template_folder='templates', static_folder='static')
CORS(app, origins=os.getenv("ALLOWED_ORIGINS", "*"))

url: str = os.getenv("SUPABASE_URL")
key: str = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(url, key)

# ─── IP RATE LIMITER ──────────────────────────────────────────────────────
_rate_store: dict[str, list] = {}
RATE_LIMIT  = int(os.getenv("RATE_LIMIT",  "5"))
RATE_WINDOW = int(os.getenv("RATE_WINDOW", "3600"))

def rate_limited(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        ip  = get_ip()
        now = time.time()
        hits = [t for t in _rate_store.get(ip, []) if now - t < RATE_WINDOW]
        if len(hits) >= RATE_LIMIT:
            return jsonify({"error": "Too many submissions. Try later."}), 429
        hits.append(now)
        _rate_store[ip] = hits
        return fn(*args, **kwargs)
    return wrapper

def get_ip():
    return (
        request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        or request.remote_addr or "unknown"
    )

# ─── REAL-TIME TRAFFIC TRACKER ──────────────────────────────────────────
_active_traffic = []

@app.before_request
def track_traffic():
    path = request.path
    # Ignore static asset files
    if any(path.endswith(ext) for ext in [".js", ".css", ".png", ".jpg", ".jpeg", ".ico", ".svg", ".gif", ".webp"]):
        return
    # Ignore administrative routes to prevent self-polling contamination
    if path.startswith("/api/admin") or "admin" in path:
        return
        
    ip = get_ip()
    ua = request.headers.get("User-Agent", "unknown")
    
    global _active_traffic
    _active_traffic.append({
        "timestamp": time.time(),
        "ip": ip,
        "path": path,
        "ua": ua
    })
    
    # Prune data older than 24 hours to keep memory ultra-low
    now = time.time()
    _active_traffic = [h for h in _active_traffic if now - h["timestamp"] < 86400]


# ─── HELPERS ──────────────────────────────────────────────────────────────
def err(msg, code=400):
    return jsonify({"error": msg}), code

@app.route("/api/ping")
def ping():
    return jsonify({"status": "ok", "ts": datetime.utcnow().isoformat()})

@app.route("/")
def home():
    return send_from_directory("templates", "index.html")

def encode_id(emp_id):
    if not emp_id: return None
    s = str(emp_id) + "V"
    return base64.urlsafe_b64encode(s.encode()).decode().rstrip('=')

def decode_id(enc):
    if not enc: return None
    try:
        s = base64.urlsafe_b64decode(enc + "===").decode()
        if s.endswith("V"): return s[:-1]
    except Exception:
        pass
    return enc

def format_prof(row):
    stats = row.get("faculty_stats")
    if isinstance(stats, list) and len(stats) > 0:
        stats = stats[0]
    elif not stats:
        stats = {
            "w_pct": 0, "total_reviews": 0,
            "avg_lecture": 0, "avg_da": 0, "avg_assign": 0, "avg_vibe": 0,
            "top_lore": {"green": [], "red": []}
        }
    
    # Calculate avatar text
    name = row.get("name", "?")
    parts = name.split()
    avatar = parts[0][0] + parts[-1][0] if len(parts) > 1 else name[:2]

    # Extract school/department abbreviation
    school_page = row.get("school_page") or ""
    school = "OTHER"
    if "cse" in school_page.lower() or "computer" in school_page.lower():
        school = "CSE"
    elif "ece" in school_page.lower() or "electronics" in school_page.lower():
        school = "ECE"
    elif "mech" in school_page.lower() or "mechanical" in school_page.lower():
        school = "MECH"
    elif "ssl" in school_page.lower() or "science" in school_page.lower():
        school = "SSL"
    elif "sbst" in school_page.lower() or "bio" in school_page.lower():
        school = "SBST"

    # Extract lore & courses from top_lore JSONB safely
    lore_data = stats.get("top_lore") or {}
    if not isinstance(lore_data, dict):
        lore_data = {"green": [], "red": []}
        
    def _normalize_counter_map(value):
        if isinstance(value, dict):
            items = value.items()
        elif isinstance(value, list):
            items = value
        else:
            items = []

        out = []
        for item in items:
            if isinstance(item, tuple) and len(item) == 2:
                text, count = item
            elif isinstance(item, list) and len(item) == 2:
                text, count = item[0], item[1]
            else:
                text, count = item, 1
            try:
                count = int(count)
            except Exception:
                count = 1
            if text:
                out.append({"text": str(text), "count": max(count, 1)})
        return out

    clean_lore = {
        "green": _normalize_counter_map(lore_data.get("green") or []),
        "red": _normalize_counter_map(lore_data.get("red") or [])
    }
    courses_list = lore_data.get("courses") or []

    return {
        "id": encode_id(row.get("employee_id")), # Obfuscated ID
        "name": name,
        "designation": row.get("designation"),
        "dept": school, 
        "courses": courses_list,
        "wPct": stats.get("w_pct") or 0,
        "reviews": stats.get("total_reviews") or 0,
        "wCount": stats.get("w_count") or 0,
        "lCount": stats.get("l_count") or 0,
        "metrics": {
            "lecture": float(stats.get("avg_lecture") or 0),
            "da": float(stats.get("avg_da") or 0),
            "assign": float(stats.get("avg_assign") or 0),
            "vibe": float(stats.get("avg_vibe") or 0)
        },
        "lore": clean_lore,
        "image_url": f"/api/profs/{encode_id(row.get('employee_id'))}/image" if row.get("image_url") else None,
        "avatar": avatar.upper()
    }


def make_placeholder_avatar(name: str = "?"):
    """Return a tiny inline SVG avatar so broken image fetches never surface as 404s.

    This keeps the browser console clean even when the upstream image URL is
    missing, blocked, or temporarily unavailable.
    """
    name = (name or "?").strip()
    parts = [p for p in name.split() if p]
    initials = ""
    if len(parts) >= 2:
        initials = (parts[0][0] + parts[-1][0]).upper()
    elif parts:
        initials = parts[0][:2].upper()
    else:
        initials = "?"

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 256 256" role="img" aria-label="Professor avatar placeholder">
      <rect width="256" height="256" rx="128" fill="#F5F5F3"/>
      <rect x="8" y="8" width="240" height="240" rx="120" fill="#E9E7E1"/>
      <text x="50%" y="54%" text-anchor="middle" dominant-baseline="middle"
            font-family="Arial, Helvetica, sans-serif" font-size="84" font-weight="700" fill="#233042">{initials}</text>
    </svg>'''
    return Response(svg, mimetype="image/svg+xml", headers={"Cache-Control": "no-store"})


def get_prof_for_share(prof_id):
    """Return a formatted professor payload for share pages and OG tags."""
    real_id = decode_id(prof_id)
    if not real_id:
        return None

    res = supabase.table("faculty").select("*, faculty_stats(*)").eq("employee_id", str(real_id)).execute()
    if not res.data:
        return None
    return format_prof(res.data[0])


def wrap_svg_text(text, max_chars=26, max_lines=2):
    """Wrap text into SVG tspans without relying on external image libraries."""
    words = (text or "").split()
    if not words:
        return ""

    lines = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if len(candidate) <= max_chars or len(lines) >= max_lines - 1:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)

    if len(lines) > max_lines:
        lines = lines[:max_lines]

    if len(lines) == max_lines and len(lines[-1]) > max_chars:
        lines[-1] = lines[-1][: max_chars - 1].rstrip() + "…"

    tspans = []
    for i, line in enumerate(lines):
        dy = 0 if i == 0 else 68
        tspans.append(f'<tspan x="80" dy="{dy}">{escape(line)}</tspan>')
    return "".join(tspans)


def build_profile_og_svg(prof):
    """Build a premium, lightweight OG image for professor profile shares."""
    name = escape(prof.get("name") or "VITC Faculty Review")
    dept = escape(prof.get("dept") or "Faculty")
    courses = prof.get("courses") or []
    course_text = escape(", ".join(courses[:4]) if courses else "Open the page for full stats")
    reviews = int(prof.get("reviews") or 0)
    w_count = int(prof.get("wCount") or 0)
    l_count = int(prof.get("lCount") or 0)
    w_pct = int(prof.get("wPct") or 0)
    verdict = "W" if w_pct >= 60 else "L"
    image_note = "Premium faculty preview"

    if reviews > 0:
        score_line = f"{verdict} rating · {w_pct}% win rate"
        review_line = f"{reviews} review{'s' if reviews != 1 else ''} · W {w_count} / L {l_count}"
    else:
        score_line = "No ratings yet"
        review_line = "Be the first to drop the lore"

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630" role="img" aria-label="{name} - VITC Faculty Review">
      <defs>
        <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stop-color="#0B1220"/>
          <stop offset="55%" stop-color="#141B2D"/>
          <stop offset="100%" stop-color="#241637"/>
        </linearGradient>
        <radialGradient id="glow" cx="50%" cy="35%" r="65%">
          <stop offset="0%" stop-color="#7C5CFF" stop-opacity="0.36"/>
          <stop offset="70%" stop-color="#7C5CFF" stop-opacity="0"/>
        </radialGradient>
      </defs>
      <rect width="1200" height="630" fill="url(#bg)"/>
      <rect width="1200" height="630" fill="url(#glow)"/>
      <circle cx="1030" cy="120" r="170" fill="#60A5FA" opacity="0.14"/>
      <circle cx="1080" cy="525" r="210" fill="#A855F7" opacity="0.12"/>

      <rect x="60" y="54" width="180" height="44" rx="22" fill="#FFFFFF" fill-opacity="0.08" stroke="#FFFFFF" stroke-opacity="0.14"/>
      <text x="150" y="82" text-anchor="middle" font-family="Inter, Arial, sans-serif" font-size="18" font-weight="700" fill="#E5E7EB" letter-spacing="2">VITC FACULTY REVIEW</text>

      <text x="80" y="220" font-family="Inter, Arial, sans-serif" font-size="76" font-weight="800" fill="#FFFFFF">{wrap_svg_text(prof.get('name') or 'VITC Faculty Review')}</text>

      <text x="82" y="356" font-family="Inter, Arial, sans-serif" font-size="30" font-weight="600" fill="#C7D2FE">{dept}</text>
      <text x="82" y="402" font-family="Inter, Arial, sans-serif" font-size="24" font-weight="500" fill="#CBD5E1">{escape(score_line)}</text>
      <text x="82" y="446" font-family="Inter, Arial, sans-serif" font-size="22" font-weight="500" fill="#94A3B8">{escape(review_line)}</text>

      <rect x="80" y="500" width="1040" height="2" rx="1" fill="#FFFFFF" fill-opacity="0.12"/>
      <text x="82" y="548" font-family="Inter, Arial, sans-serif" font-size="22" font-weight="600" fill="#E5E7EB">{course_text}</text>
      <text x="1118" y="548" text-anchor="end" font-family="Inter, Arial, sans-serif" font-size="18" font-weight="500" fill="#94A3B8">{image_note}</text>
    </svg>'''
    return Response(svg, mimetype="image/svg+xml", headers={"Cache-Control": "public, max-age=86400"})


def build_profile_html(prof_id=None):
    """Inject social metadata into the profile page without changing the client app."""
    template_path = os.path.join(app.root_path, "templates", "profile.html")
    try:
        with open(template_path, "r", encoding="utf-8") as f:
            html = f.read()
    except Exception:
        return send_from_directory("templates", "profile.html")

    prof = get_prof_for_share(prof_id) if prof_id else None
    base_url = request.url_root.rstrip("/")
    share_path = f"/prof/{prof_id}" if prof_id else "/profile.html"
    og_title = f"{prof['name']} - VITC Faculty Review" if prof else "VITC Faculty Review"
    og_desc = (
        f"Check out the W/L stats, verdict vibe, and review lore for {prof['name']} before FFCS."
        if prof else
        "Check out faculty W/L stats, verdict vibe, and review lore before FFCS."
    )
    og_image = f"{base_url}/api/og/profs/{prof_id}.svg" if prof_id else f"{base_url}/api/og/default.svg"

    meta_block = f"""
  <link rel="canonical" href="{base_url}{share_path}">
  <meta property="og:site_name" content="VITC Faculty Review">
  <meta property="og:title" content="{escape(og_title)}">
  <meta property="og:description" content="{escape(og_desc)}">
  <meta property="og:url" content="{base_url}{share_path}">
  <meta property="og:type" content="website">
  <meta property="og:image" content="{og_image}">
  <meta property="og:image:type" content="image/svg+xml">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{escape(og_title)}">
  <meta name="twitter:description" content="{escape(og_desc)}">
  <meta name="twitter:image" content="{og_image}">
"""

    html = html.replace(
        '<meta name="robots" content="noindex, nofollow">',
        '<meta name="robots" content="noindex, nofollow">\n' + meta_block,
        1
    )

    if prof_id:
        title = f"{escape(prof['name'])} - VITC Faculty Review" if prof else "Professor Profile - VITC Faculty Review"
        html = html.replace("<title>Professor Profile</title>", f"<title>{title}</title>", 1)

    return Response(html, mimetype="text/html")

# ══════════════════════════════════════════════════════════════════════════
#  ROUTES
# ══════════════════════════════════════════════════════════════════════════

@app.route("/api/profs")
def get_profs():
    """Get professors filtered by department and search query."""
    dept   = request.args.get("dept", "").strip().upper()
    q      = request.args.get("q", "").strip().lower()
    
    # Load all courses for lookup if there is a query
    course_map = {}
    if q:
        global _cached_courses
        if _cached_courses is None:
            get_courses()
        if _cached_courses:
            for c in _cached_courses:
                course_map[c["id"].lower()] = c["name"].lower()
                
    # Fetch all with stats
    res = supabase.table("faculty").select("*, faculty_stats(*)").execute()
    profs = []
    
    for row in res.data:
        prof = format_prof(row)
        
        # Filter by department
        if dept and dept != "ALL":
            # Match part of the department string
            if not prof["dept"] or dept not in prof["dept"].upper():
                continue
                
        # Filter by search query
        if q:
            name_match = prof["name"] and q in prof["name"].lower()
            desig_match = prof["designation"] and q in prof["designation"].lower()
            dept_match = prof["dept"] and q in prof["dept"].lower()
            
            # Check for course code or course name matches
            course_match = False
            if prof.get("courses"):
                for c_code in prof["courses"]:
                    c_code_lower = c_code.lower()
                    if q in c_code_lower:
                        course_match = True
                        break
                    c_name_full = course_map.get(c_code_lower)
                    if c_name_full and q in c_name_full:
                        course_match = True
                        break
            
            if not (name_match or desig_match or dept_match or course_match):
                continue
                
        profs.append(prof)
    


    profs.sort(key=lambda x: (
        -(1 if (x.get("reviews") or 0) > 0 else 0),
        -(x.get("reviews") or 0),
        -(x.get("wPct") or 0),
        x.get("name") or ""
    ))
    return jsonify(profs)


_cached_courses = None

@app.route("/api/courses")
def get_courses():
    """Get list of all courses from Supabase courses table (super fast in-memory caching)."""
    global _cached_courses
    if _cached_courses is not None:
        return jsonify(_cached_courses)
        
    courses = []
    try:
        res = supabase.table("courses").select("course_id, course_name").execute()
        if res.data:
            for row in res.data:
                c_id = row.get("course_id", "").strip()
                c_name = row.get("course_name", "").strip()
                if c_id and c_name:
                    courses.append({
                        "id": c_id,
                        "name": c_name
                    })
    except Exception as e:
        print(f"Error reading courses from Supabase: {str(e)}")
        
    # Fallback to local CSV if Supabase is unavailable or empty
    if not courses:
        csv_path = os.path.join("data", "courses.csv")
        if os.path.exists(csv_path):
            try:
                import csv
                with open(csv_path, newline='', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        c_id = row.get("course_id", "").strip()
                        c_name = row.get("course_name", "").strip()
                        if c_id and c_name:
                            courses.append({
                                "id": c_id,
                                "name": c_name
                            })
            except Exception as e:
                print(f"Error reading courses CSV: {str(e)}")
                
    # Sort courses alphabetically by course code
    courses.sort(key=lambda x: x["id"])
    _cached_courses = courses
    return jsonify(courses)


@app.route("/api/profs/<prof_id>")
def get_prof(prof_id):
    """Get a specific professor with all details."""
    real_id = decode_id(prof_id)
    res = supabase.table("faculty").select("*, faculty_stats(*)").eq("employee_id", str(real_id)).execute()
    if not res.data:
        return err("Professor not found.", 404)
    return jsonify(format_prof(res.data[0]))


@app.route("/api/profs/<prof_id>/image")
def get_prof_image(prof_id):
    """Proxy the professor image to hide the bare employee ID in the URL."""
    real_id = decode_id(prof_id)
    res = supabase.table("faculty").select("name, image_url").eq("employee_id", str(real_id)).execute()
    if not res.data:
        return make_placeholder_avatar("?")

    row = res.data[0] or {}
    image_url = row.get("image_url")
    name = row.get("name") or "?"
    if not image_url:
        return make_placeholder_avatar(name)
    
    url = image_url.replace(" ", "%20")
    try:
        req = urllib.request.urlopen(url, timeout=8)
        return Response(req.read(), mimetype=req.info().get_content_type())
    except Exception:
        return make_placeholder_avatar(name)


@app.route("/api/profs/<prof_id>/stats-by-course")
def get_prof_stats_by_course(prof_id):
    """Get per-course aggregated stats for a specific professor."""
    real_id = decode_id(prof_id)
    res = supabase.table("faculty").select("id").eq("employee_id", str(real_id)).execute()
    if not res.data:
        return err("Professor not found.", 404)
    internal_id = res.data[0]["id"]

    reviews = supabase.table("reviews").select("*").eq("faculty_id", internal_id).execute().data

    good_words = ["pass", "prep", "deadline", "marks", "redo", "chill", "friendly", "easy"]

    def compute_stats(review_list):
        total = len(review_list)
        if total == 0:
            return None
        w_count = sum(1 for r in review_list if r["verdict"] == "w")
        w_pct   = int((w_count / total) * 100)

        avg_lecture = sum(r["score_lecture"] for r in review_list) / total
        avg_da      = sum(r["score_da"]      for r in review_list) / total
        avg_assign  = sum(r["score_assign"]  for r in review_list) / total
        avg_vibe    = sum(r["score_vibe"]    for r in review_list) / total

        green_chips, red_chips = [], []
        for r in review_list:
            for chip in (r.get("lore_chips") or []):
                if chip.startswith("Course: "):
                    continue
                is_green = any(word in chip.lower() for word in good_words)
                (green_chips if is_green else red_chips).append(chip)

        top_green = [k for k, _ in Counter(green_chips).most_common(3)]
        top_red   = [k for k, _ in Counter(red_chips).most_common(3)]

        return {
            "wPct":    w_pct,
            "reviews": total,
            "metrics": {
                "lecture": round(avg_lecture, 2),
                "da":      round(avg_da,      2),
                "assign":  round(avg_assign,  2),
                "vibe":    round(avg_vibe,     2),
            },
            "lore": {"green": top_green, "red": top_red},
        }

    if not reviews:
        return jsonify({"global": None, "courses": []})

    global_stats = compute_stats(reviews)

    # Group by course_code (only reviews that have one)
    course_groups: dict[str, list] = {}
    for r in reviews:
        cc = r.get("course_code")
        if cc:
            course_groups.setdefault(cc, []).append(r)

    # Fetch human-readable course names in one query
    course_names: dict[str, str] = {}
    if course_groups:
        try:
            codes = list(course_groups.keys())
            cr = supabase.table("courses").select("course_id, course_name").in_("course_id", codes).execute()
            if cr.data:
                for c in cr.data:
                    course_names[c["course_id"]] = c["course_name"]
        except Exception as e:
            print(f"Error fetching course names: {e}")

    courses = []
    for code, rev_list in sorted(course_groups.items(), key=lambda x: -len(x[1])):
        stats = compute_stats(rev_list)
        if stats:
            courses.append({
                "code":  code,
                "name":  course_names.get(code, code),
                **stats,
            })

    return jsonify({"global": global_stats, "courses": courses})


@app.route("/profile.html")
def profile_page():
    """Serve the profile page with server-rendered social metadata."""
    return build_profile_html(request.args.get("id"))


@app.route("/prof/<prof_id>")
def prof_share_page(prof_id):
    """Pretty share URL for professor profiles."""
    return build_profile_html(prof_id)


@app.route("/api/og/profs/<prof_id>.svg")
def prof_og_image(prof_id):
    """Generate a lightweight OG image for professor shares."""
    prof = get_prof_for_share(prof_id)
    if not prof:
        return build_profile_og_svg({
            "name": "VITC Faculty Review",
            "dept": "Faculty",
            "courses": [],
            "reviews": 0,
            "wCount": 0,
            "lCount": 0,
            "wPct": 0,
        })
    return build_profile_og_svg(prof)


@app.route("/api/og/default.svg")
def default_og_image():
    """Generic OG image for the site."""
    return build_profile_og_svg({
        "name": "VITC Faculty Review",
        "dept": "Faculty Reviews",
        "courses": [],
        "reviews": 0,
        "wCount": 0,
        "lCount": 0,
        "wPct": 0,
    })


@app.route("/api/profs/<prof_id>/review", methods=["POST"])
@rate_limited
def submit_review(prof_id):
    """Submit a review for a professor."""
    real_id = decode_id(prof_id)
    # Find the internal integer ID
    res = supabase.table("faculty").select("id").eq("employee_id", str(real_id)).execute()
    if not res.data:
        return err("Professor not found.", 404)
    internal_id = res.data[0]["id"]
    
    body = request.get_json(silent=True) or {}
    
    # Honeypot
    if body.get("website"):
        return jsonify({"success": True})
    
    # Validate metrics
    metrics = body.get("metrics", {})
    required = ["lecture", "da", "assign", "vibe"]
    for key in required:
        val = metrics.get(key)
        if not isinstance(val, (int, float)) or not (1 <= int(val) <= 5):
            return err(f"Invalid metric value for '{key}'. Must be 1-5.")

    # Validate verdict
    verdict = body.get("verdict", "")
    if verdict not in ("w", "l"):
        return err("Verdict must be 'w' or 'l'.")

    # Validate lore chips
    lore = body.get("lore", [])
    if not isinstance(lore, list) or len(lore) > 3:
        return err("Max 3 lore chips.")
    
    course_val = body.get("course", "").strip()
    if len(course_val) > 100:
        course_val = course_val[:100]
        
    complete_lore = list(lore)
    if course_val:
        complete_lore.insert(0, f"Course: {course_val}")

    # Anti-duplicate: allow one review per browser_fp + faculty_id + course_code
    fp = body.get("fp") or body.get("browser_fp") or "unknown"
    try:
        if course_val:
            dup_q = supabase.table("reviews").select("id").eq("faculty_id", internal_id).eq("browser_fp", fp).eq("course_code", course_val).execute()
        else:
            # Match NULL course_code entries
            dup_q = supabase.table("reviews").select("id").eq("faculty_id", internal_id).eq("browser_fp", fp).is_("course_code", None).execute()

        if dup_q.data and len(dup_q.data) > 0:
            return err("You have already submitted for this professor and subject.", 409)

        supabase.table("reviews").insert({
            "faculty_id":    internal_id,
            "score_lecture": metrics["lecture"],
            "score_da":      metrics["da"],
            "score_assign":  metrics["assign"],
            "score_vibe":    metrics["vibe"],
            "verdict":       verdict,
            "lore_chips":    complete_lore,
            "browser_fp":    fp,
            "ip_address":    get_ip(),
            "course_code":   course_val if course_val else None
        }).execute()

        # Recalculate stats
        update_faculty_stats(internal_id)

        return jsonify({"success": True}), 201
    except Exception as e:
        return err(f"Error submitting review: {str(e)}"), 500



def update_faculty_stats(faculty_id):
    """Recalculate stats for a specific professor based on all their reviews."""
    reviews = supabase.table("reviews").select("*").eq("faculty_id", faculty_id).execute().data
    if not reviews:
        return
        
    total = len(reviews)
    w_count = sum(1 for r in reviews if r["verdict"] == "w")
    l_count = total - w_count
    w_pct = int((w_count / total) * 100) if total > 0 else 0
    
    avg_lecture = sum(r["score_lecture"] for r in reviews) / total
    avg_da = sum(r["score_da"] for r in reviews) / total
    avg_assign = sum(r["score_assign"] for r in reviews) / total
    avg_vibe = sum(r["score_vibe"] for r in reviews) / total
    
    green_chips = []
    red_chips = []
    courses = []
    
    # Simple logic for categorizing green vs red lore
    good_words = ["pass", "prep", "deadline", "marks", "redo", "chill", "friendly", "easy"]
    
    for r in reviews:
        # Check course_code if it exists in the database reviews table
        cc = r.get("course_code")
        if cc:
            courses.append(cc)
            
        for chip in (r.get("lore_chips") or []):
            if chip.startswith("Course: "):
                c_val = chip.replace("Course: ", "").strip()
                if c_val:
                    courses.append(c_val)
                continue  # Skip adding course tags to general positive/consideration lore chips!
                
            is_green = any(word in chip.lower() for word in good_words)
            if is_green:
                green_chips.append(chip)
            else:
                red_chips.append(chip)
                
    green_counts = Counter(green_chips)
    red_counts = Counter(red_chips)
    
    # Extract top unique courses taught, sorted by frequency
    unique_courses = [k for k, v in Counter(courses).most_common(5)]

    def _counter_to_objects(counter_obj):
        return [{"text": text, "count": count} for text, count in counter_obj.most_common()]
    
    stats = {
        "faculty_id": faculty_id,
        "total_reviews": total,
        "w_count": w_count,
        "l_count": l_count,
        "w_pct": w_pct,
        "avg_lecture": round(avg_lecture, 2),
        "avg_da": round(avg_da, 2),
        "avg_assign": round(avg_assign, 2),
        "avg_vibe": round(avg_vibe, 2),
        "top_lore": {
            "green": _counter_to_objects(green_counts),
            "red": _counter_to_objects(red_counts),
            "courses": unique_courses
        }
    }
    
    supabase.table("faculty_stats").upsert(stats).execute()


@app.route("/api/leaderboard")
def get_leaderboard():
    """Get leaderboard sorted by W%."""
    try:
        res = supabase.table("faculty").select("*, faculty_stats(*)").execute()
        profs = [format_prof(r) for r in (res.data or [])]
        profs.sort(key=lambda x: (-x.get("wPct", 0), -x.get("reviews", 0)))
        return jsonify(profs)
    except Exception as e:
        print(f"Error in /api/leaderboard: {e}")
        return jsonify([])


@app.route("/api/admin/stats")
def get_admin_stats():
    admin_key = request.headers.get("X-Admin-Key") or request.args.get("key")
    if admin_key != os.getenv("ADMIN_SECRET", "kaju#11"):
        return jsonify({"error": "Unauthorized"}), 401
        
    try:
        profs_res = supabase.table("faculty").select("id").execute().data
        reviews_res = supabase.table("reviews").select("ip_address, browser_fp").execute().data
        
        total_profs = len(profs_res) if profs_res else 0
        total_reviews = len(reviews_res) if reviews_res else 0
        unique_ips = len(set(r["ip_address"] for r in reviews_res if r.get("ip_address"))) if reviews_res else 0
        unique_fps = len(set(r["browser_fp"] for r in reviews_res if r.get("browser_fp"))) if reviews_res else 0
        
        latest_reviews_res = supabase.table("reviews").select("*, faculty(*)").order("submitted_at", desc=True).limit(30).execute().data
        reviews_data = []
        if latest_reviews_res:
            for r in latest_reviews_res:
                fac = r.get("faculty") or {}
                reviews_data.append({
                    "id": r["id"],
                    "prof_name": fac.get("name") or "Unknown",
                    "prof_id": encode_id(fac.get("employee_id")) if fac.get("employee_id") else None,
                    "lecture": r["score_lecture"],
                    "da": r["score_da"],
                    "assign": r["score_assign"],
                    "vibe": r["score_vibe"],
                    "verdict": r["verdict"],
                    "lore": r.get("lore_chips") or [],
                    "ip": r.get("ip_address") or "unknown",
                    "fp": r.get("browser_fp") or "unknown",
                    "submitted_at": r["submitted_at"]
                })
                
        top_reviewed_res = supabase.table("faculty_stats").select("*, faculty(*)").order("total_reviews", desc=True).limit(10).execute().data
        top_profs = []
        if top_reviewed_res:
            for item in top_reviewed_res:
                fac = item.get("faculty") or {}
                if not fac:
                    continue
                top_profs.append({
                    "name": fac.get("name") or "Unknown",
                    "id": encode_id(fac.get("employee_id")) if fac.get("employee_id") else None,
                    "reviews": item["total_reviews"],
                    "w_pct": item["w_pct"]
                })
                
        now = time.time()
        # Active visitors in the last 5 minutes
        active_5m = [h for h in _active_traffic if now - h["timestamp"] < 300]
        active_visitors = len(set(h["ip"] for h in active_5m))
        
        # Total tracked pageviews in the last 24 hours
        views_24h = len(_active_traffic)

        return jsonify({
            "total_profs": total_profs,
            "total_reviews": total_reviews,
            "unique_ips": unique_ips,
            "unique_fps": unique_fps,
            "latest_reviews": reviews_data,
            "top_profs": top_profs,
            "active_visitors": active_visitors,
            "views_24h": views_24h
        })
    except Exception as e:
        return err(f"Admin API error: {str(e)}", 500)


_asset_cache = {}

@app.route("/<path:path>")
def serve_static(path):
    # Check if the requested file is in static folder
    static_file_path = os.path.join("static", path)
    if os.path.exists(static_file_path) and os.path.isfile(static_file_path):
        # We only dynamically minify .js and .css files
        if path.endswith(".js") or path.endswith(".css"):
            try:
                mtime = os.path.getmtime(static_file_path)
                cached = _asset_cache.get(static_file_path)
                
                # If cached and file hasn't changed, serve the cached version
                if cached and cached["mtime"] == mtime:
                    content = cached["content"]
                else:
                    # File changed or not cached, compile it!
                    with open(static_file_path, "r", encoding="utf-8") as f:
                        raw_content = f.read()
                    
                    if path.endswith(".js"):
                        minified = rjsmin.jsmin(raw_content)
                    else:
                        minified = rcssmin.cssmin(raw_content)
                    
                    _asset_cache[static_file_path] = {
                        "mtime": mtime,
                        "content": minified
                    }
                    content = minified
                
                mimetype = "application/javascript" if path.endswith(".js") else "text/css"
                return Response(content, mimetype=mimetype)
            except Exception:
                # Fallback to serving raw file on any error
                return send_from_directory("static", path)
        else:
            return send_from_directory("static", path)
            
    # Map static file requests from root to the templates folder (HTML pages, etc.)
    if os.path.exists(os.path.join("templates", path)):
        return send_from_directory("templates", path)
        
    return err("Not found", 404)


if __name__ == "__main__":
    app.run(
        host  = "0.0.0.0",
        port  = int(os.getenv("PORT", "5000")),
        debug = os.getenv("FLASK_DEBUG", "false").lower() == "true",
    )
