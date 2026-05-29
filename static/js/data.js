/* ─── data.js ─────────────────────────────────────────────────────────────
   Replace API stub calls with real fetch() to your Flask endpoints.
   All mock data lives here during development.
────────────────────────────────────────────────────────────────────────── */

const DEPARTMENTS = ["ALL", "CSE", "ECE", "MECH", "SSL", "SBST", "OTHER"];

const METRIC_DEFS = [
  { key: "lecture", label: "Lecture Value",      low: "Just reads the PPT",      high: "Actually explains things" },
  { key: "da",      label: "DA & Quiz Leniency", low: "Fights for every mark",   high: "Basically free marks"     },
  { key: "assign",  label: "Assignment Hassle",  low: "Nitpicky & strict",       high: "Super flexible"           },
  { key: "vibe",    label: "Vibe Check",         low: "Massive ego / scary",     high: "Super approachable"       },
];

const LORE_GREEN = [
  "Actually wants you to pass",
  "Goated for FAT prep",
  "Chill with DA deadlines",
  "Basically free DA marks",
  "Lets you redo assignments",
  "Chill / Can Slack Off"
];
const LORE_RED = [
  "Gatekeeps internal marks",
  "Strict 100% attendance vibe",
  "Surprise quizzes",
  "Goes off syllabus",
  "Mass fails assignments",
  "Biased Grader",
  "High Class Average"
];

/* ─── ANTI-SPAM: Browser Fingerprint ─────────────────────────────────────
   FNV-1a 32-bit hash of stable browser signals. Not foolproof but blocks
   99% of casual double-voting. IP rate-limiting handles the rest on backend.
────────────────────────────────────────────────────────────────────────── */
function getFingerprint() {
  const raw = [
    navigator.userAgent || "",
    navigator.language || "",
    String(screen.width) + "x" + String(screen.height),
    String(screen.colorDepth),
    String(new Date().getTimezoneOffset()),
    String(navigator.hardwareConcurrency || 0),
    String(navigator.maxTouchPoints || 0),
  ].join("::");

  let h = 0x811c9dc5;
  for (let i = 0; i < raw.length; i++) {
    h ^= raw.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return (h >>> 0).toString(36);
}

function hasReviewed(profId, course = null) {
  try {
    const fp = getFingerprint();
    const data = JSON.parse(localStorage.getItem("plore_v") || "{}");
    const entries = data[fp] || [];
    
    profId = String(profId).trim();
    
    // course === null -> check ANY review for this prof (used when caller didn't pass a course)
    if (course === null) {
      const result = entries.some(e => e.startsWith(`${profId}::`));
      console.log(`[hasReviewed] checking ANY for profId=${profId}, found=${result}, entries=${JSON.stringify(entries)}`);
      return result;
    }
    
    // Normalize course to empty string if null, undefined, or not provided
    if (course === undefined) course = null; // Already handled above
    course = String(course || "").trim();
    
    // Check specifically for this exact course (empty string = global/no-course reviews)
    const key = `${profId}::${course}`;
    const result = entries.includes(key);
    console.log(`[hasReviewed] checking key="${key}", found=${result}, allEntries=${JSON.stringify(entries)}`);
    return result;
  } catch (e) {
    console.error("hasReviewed error:", e);
    return false;
  }
}

function markReviewed(profId, course = "") {
  try {
    const fp = getFingerprint();
    const data = JSON.parse(localStorage.getItem("plore_v") || "{}");
    if (!data[fp]) data[fp] = [];
    
    profId = String(profId).trim();
    // Normalize course: empty string, null, or undefined all mean "global" review
    course = String(course || "").trim();
    
    const key = `${profId}::${course}`;
    if (!data[fp].includes(key)) {
      data[fp].push(key);
      console.log(`[markReviewed] stored key="${key}", allEntries=${JSON.stringify(data[fp])}`);
    } else {
      console.log(`[markReviewed] key="${key}" already exists`);
    }
    localStorage.setItem("plore_v", JSON.stringify(data));
  } catch (e) {
    console.error("markReviewed error:", e);
  }
}

const API = {
  async getProfs(dept, query) {
    const params = new URLSearchParams();
    if (dept && dept !== "ALL") params.set("dept", dept);
    if (query) params.set("q", query);
    return await fetch(`/api/profs?${params}`).then(r => r.json());
  },

  async getProf(id) {
    return await fetch(`/api/profs/${id}`).then(r => r.json());
  },

  async getProfStatsByCourse(profId) {
    return await fetch(`/api/profs/${profId}/stats-by-course`).then(r => r.json());
  },

  async submitReview(profId, payload) {
    return await fetch(`/api/profs/${profId}/review`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }).then(r => r.json());
  },

  async getLeaderboard() {
    return await fetch('/api/leaderboard').then(r => r.json());
  },

  async getCourses() {
    return await fetch('/api/courses').then(r => r.json());
  },

  async getAdminStats(key) {
    return await fetch(`/api/admin/stats?key=${encodeURIComponent(key)}`).then(async r => {
      if (r.status === 401) throw new Error("Unauthorized");
      if (!r.ok) throw new Error("Server error");
      return await r.json();
    });
  }
};

/* ─── URL HELPERS ────────────────────────────────────────────────────────*/
function getParam(key) {
  const params = new URLSearchParams(window.location.search);
  const value = params.get(key);
  if (value !== null) return value;

  if (key === "id") {
    const match = window.location.pathname.match(/^\/prof\/([^/]+)\/?$/i);
    if (match) return decodeURIComponent(match[1]);
  }

  return null;
}
function go(path, params = {}) {
  const qs  = Object.entries(params).map(([k,v]) => `${k}=${encodeURIComponent(v)}`).join("&");
  window.location.href = qs ? `${path}?${qs}` : path;
}

/* ─── DOM HELPERS ────────────────────────────────────────────────────────*/
function el(id) { return document.getElementById(id); }
function qs(sel, root = document) { return root.querySelector(sel); }
function qsa(sel, root = document) { return [...root.querySelectorAll(sel)]; }

function showToast(msg, type = "success") {
  let t = document.querySelector(".toast");
  if (!t) { t = document.createElement("div"); t.className = "toast"; document.body.appendChild(t); }
  t.textContent = msg;
  t.className   = "toast" + (type === "error" ? " error" : "");
  requestAnimationFrame(() => {
    requestAnimationFrame(() => t.classList.add("show"));
  });
  clearTimeout(t._timer);
  t._timer = setTimeout(() => t.classList.remove("show"), 2800);
}

function barColor(v) {
  if (v >= 4.0) return "green";
  if (v >= 2.6) return "amber";
  return "red";
}

function renderBar(val, max = 5) {
  const pct = Math.round((val / max) * 100);
  return `<div class="bar-track"><div class="bar-fill ${barColor(val)}" style="width:${pct}%"></div></div>`;
}

function initBars() {
  qsa(".bar-fill").forEach(b => {
    const w = b.style.width;
    b.style.width = "0%";
    requestAnimationFrame(() => { requestAnimationFrame(() => { b.style.width = w; }); });
  });
}

/* ─── SVG LOGO MARK ──────────────────────────────────────────────────────*/
const LOGO_SVG = `
<svg class="nav-logo-mark" viewBox="0 0 28 28" fill="none" xmlns="http://www.w3.org/2000/svg">
  <rect width="28" height="28" rx="5" fill="#1C1C1A"/>
  <rect x="5" y="5" width="8" height="8" rx="1.5" fill="#3D9E6A"/>
  <rect x="15" y="5" width="8" height="8" rx="1.5" fill="#252523"/>
  <rect x="5" y="15" width="8" height="8" rx="1.5" fill="#252523"/>
  <rect x="15" y="15" width="8" height="8" rx="1.5" fill="#C04040"/>
</svg>`;

const NAV_HTML = (activePage) => `
  <nav class="nav">
    <a class="nav-brand" href="index.html">
      <div class="nav-name" style="font-size: 16px; font-weight: 800; letter-spacing: 0.03em;">VITC Faculty</div>
    </a>
    <div class="nav-actions">
      <a class="nav-link ${activePage === 'leaderboard' ? 'active' : ''}" href="leaderboard.html">Rankings</a>
      <button id="theme-toggle" class="theme-toggle-btn" title="Toggle Theme" aria-label="Toggle Theme">
        <svg class="sun-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/>
        </svg>
        <svg class="moon-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
        </svg>
      </button>
    </div>
  </nav>
`;

const BACK_BTN = (href, label = "Back") => `
<a class="back-btn" href="${href}">
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <path d="M19 12H5M12 5l-7 7 7 7"/>
  </svg>
  ${label}
</a>`;

const ARROW_RIGHT_SVG = `
<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
  <path d="M5 12h14M12 5l7 7-7 7"/>
</svg>`;
