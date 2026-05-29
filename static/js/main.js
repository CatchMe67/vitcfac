/* ─── main.js ─────────────────────────────────────────────────────────────
   Detects the current page and runs the right init function.
────────────────────────────────────────────────────────────────────────── */

// Apply saved theme immediately to prevent flashing before DOM loads
(() => {
  const savedTheme = localStorage.getItem("theme") || (window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark");
  applyTheme(savedTheme);
})();

function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  if (document.body) {
    document.body.classList.toggle("dark", theme === "dark");
    document.body.classList.toggle("light", theme === "light");
  }
}

const PAGE = (() => {
  const f = window.location.pathname.split("/").pop().replace(".html", "");
  return f || "index";
})();

document.addEventListener("DOMContentLoaded", () => {
  // Theme Toggle Event Delegation
  document.addEventListener("click", (e) => {
    const toggleBtn = e.target.closest("#theme-toggle");
      if (toggleBtn) {
        const currentTheme = document.documentElement.getAttribute("data-theme") || "dark";
        const newTheme = currentTheme === "light" ? "dark" : "light";
        applyTheme(newTheme);
        localStorage.setItem("theme", newTheme);
      
        // Update theme color meta tag dynamically
        const metaTheme = document.querySelector('meta[name="theme-color"]');
        if (metaTheme) {
          metaTheme.setAttribute("content", newTheme === "light" ? "#F9FAFB" : "#0C0C0B");
        }
      }
  });

  const pages = { index: initIndex, profile: initProfile, review: initReview, leaderboard: initLeaderboard, admin: initAdmin };
  if (pages[PAGE]) pages[PAGE]();
  injectFooter();

  // Global shortcut (Ctrl + Shift + A) to open admin dashboard
  document.addEventListener("keydown", (e) => {
    if (e.ctrlKey && e.shiftKey && (e.key === "A" || e.key === "a")) {
      e.preventDefault();
      window.location.href = "admin.html";
    }
  });
});

function injectFooter() {
  const pageContainer = document.querySelector(".page");
  if (!pageContainer) return;
  const footer = document.createElement("footer");
  footer.className = "footer";
  footer.innerHTML = `
    <div class="footer-left">
      <div class="footer-text">
        We are an independent student platform. Not affiliated with VIT. Reviews reflect personal student opinions only.
      </div>
    </div>
    <div class="footer-right">
      <div class="footer-links">
        <a class="footer-link" href="terms.html">Terms of Use</a>
        <a class="footer-link" href="privacy.html">Privacy Policy</a>
        <a class="footer-link" href="about.html">About</a>
        <a id="footer-contact" class="footer-link footer-contact-link" href="mailto:vit.fac@proton.me">Contact</a>
      </div>
    </div>
  `;
  pageContainer.appendChild(footer);

  // Brief preview: show only footer on first visit for ~900ms to surface contact
  try {
    const previewKey = 'seen_footer_preview_v2';
    const firstVisit = !localStorage.getItem(previewKey);
    if (firstVisit) {
      pageContainer.classList.add('hide-content');
      setTimeout(() => {
        pageContainer.classList.remove('hide-content');
        localStorage.setItem(previewKey, '1');
        const contact = document.getElementById('footer-contact');
        if (contact) {
          contact.classList.add('pulse-once');
          setTimeout(() => contact.classList.remove('pulse-once'), 2200);
        }
      }, 900);
    } else {
      // gentle persistent highlight for returning visitors
      setTimeout(() => {
        const contact = document.getElementById('footer-contact');
        if (contact) contact.classList.add('pulse');
      }, 400);
    }
  } catch (e) { /* ignore storage errors */ }
}

/* ═══════════════════════════════════════════════════════════════════════
   INDEX PAGE
═══════════════════════════════════════════════════════════════════════ */
function initIndex() {
  const ns = el("nav-slot");
  if (ns) ns.innerHTML = NAV_HTML("index");
  const lbBanner = el("lb-banner");
  if (lbBanner) lbBanner.style.display = "none";
  renderPromoBanner();
  loadProfList(1);

  el("search").addEventListener("input", debounce(() => loadProfList(1), 200));

  // Re-render when crossing the mobile breakpoint so the home page can use
  // the leaderboard-style list only on phones.
  const mobileQuery = window.matchMedia("(max-width: 767.98px)");
  let lastMobileMode = mobileQuery.matches;
  const syncHomeListMode = () => {
    if (PAGE !== "index") return;
    const nowMobile = mobileQuery.matches;
    if (nowMobile !== lastMobileMode) {
      lastMobileMode = nowMobile;
      loadProfList(_homePage);
    }
  };

  if (mobileQuery.addEventListener) {
    mobileQuery.addEventListener("change", syncHomeListMode);
  } else if (mobileQuery.addListener) {
    mobileQuery.addListener(syncHomeListMode);
  }
}

function renderPromoBanner() {
  const slot = el("promo-banner-slot");
  if (!slot) return;

  const key = "promo_banner_hidden_v1";
  const hidden = localStorage.getItem(key) === "1";
  if (hidden) {
    slot.innerHTML = "";
    slot.style.display = "none";
    return;
  }

  slot.style.display = "block";
  slot.innerHTML = `
    <div class="promo-banner" role="region" aria-label="Promotional banner">
      <button class="promo-banner-close" type="button" aria-label="Dismiss banner" onclick="dismissPromoBanner()">
        <svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true" focusable="false">
          <path d="M6 6l12 12M18 6 6 18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
        </svg>
      </button>
      <div class="promo-banner-copy">
        <strong>Don't let your friends get cooked this sem. 💀💀</strong>
        <span>Drop the link in your class groups.</span>
      </div>
      <button class="promo-share-btn" type="button" onclick="shareHomepage()" aria-label="Share VITC Faculty Review">
        Share
      </button>
    </div>`;
}

window.shareHomepage = async function() {
  const title = "VITC Faculty Review";
  const text = "Check out the W/L stats for profs before FFCS slot allocation.";
  const url = "https://vitcfac.vercel.app/";

  try {
    if (navigator.share) {
      await navigator.share({ title, text, url });
      return;
    }

    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(url);
      showToast("Link copied to clipboard.");
      return;
    }

    const fallback = window.prompt("Copy this link", url);
    if (fallback !== null) showToast("Copy the link to share.", "error");
  } catch (err) {
    if (err?.name === "AbortError" || err?.name === "NotAllowedError") return;
    try {
      await navigator.clipboard?.writeText?.(url);
      showToast("Link copied to clipboard.");
    } catch (_) {
      showToast("Sharing is unavailable right now.", "error");
    }
  }
};

window.dismissPromoBanner = function() {
  try {
    localStorage.setItem("promo_banner_hidden_v1", "1");
  } catch (e) {}
  const slot = el("promo-banner-slot");
  if (slot) {
    slot.innerHTML = "";
    slot.style.display = "none";
  }
};

function renderLbBanner() {
  return `
    <a class="lb-banner" href="leaderboard.html">
      <div>
        <div class="lb-eyebrow">Live Rankings</div>
        <div class="lb-title">W/L Leaderboard</div>
      </div>
      <div class="lb-banner-right">${ARROW_RIGHT_SVG}</div>
    </a>`;
}

let _homePage = 1;
const ITEMS_PER_PAGE = 15;

function isHomeMobileMode() {
  return PAGE === "index" && window.matchMedia("(max-width: 767.98px)").matches;
}


async function loadProfList(page = 1) {
  _homePage = page;
  const q    = document.getElementById("search").value.trim();
  const list = el("prof-list");
  const countEl = el("list-count");
  const pagEl = el("pagination-slot");
  const mobileMode = isHomeMobileMode();

  if (mobileMode) {
    list.className = "lb-list home-mobile-list";
  } else {
    list.className = "prof-list";
  }

  list.innerHTML = mobileMode ? renderHomeMobileSkeletons(ITEMS_PER_PAGE) : renderSkeletons(ITEMS_PER_PAGE);
  if (pagEl) pagEl.innerHTML = "";

  const profs = await API.getProfs("ALL", q);

  countEl.textContent = `${profs.length} professor${profs.length !== 1 ? "s" : ""}`;

  if (profs.length === 0) {
    const q = document.getElementById("search").value.trim();
    list.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
            <path d="M8 11h6M11 8v6" opacity="0.4"/>
          </svg>
        </div>
        <div class="empty-title">No professors found</div>
        <div class="empty-sub">Try a different name or department.</div>
      </div>`;
    if (pagEl) pagEl.innerHTML = "";
    const rtSlot = el("request-teacher-slot");
    if (rtSlot) rtSlot.innerHTML = renderRequestTeacherBanner(q);
    return;
  }

  const start = (page - 1) * ITEMS_PER_PAGE;
  const end = start + ITEMS_PER_PAGE;
  const paginatedProfs = profs.slice(start, end);

  list.innerHTML = mobileMode
    ? paginatedProfs.map((p, idx) => renderHomeMobileProfItem(p, start + idx + 1)).join("")
    : paginatedProfs.map(renderProfCard).join("");

  if (pagEl) {
    pagEl.innerHTML = renderPagination(profs.length, _homePage, ITEMS_PER_PAGE, "changeHomePage");
  }

  // Always show the request-teacher banner at the bottom of every page
  const rtSlot = el("request-teacher-slot");
  if (rtSlot) rtSlot.innerHTML = renderRequestTeacherBanner();
}

window.changeHomePage = function(page) {
  loadProfList(page);
  el("list-header").scrollIntoView({ behavior: "smooth", block: "start" });
};

function renderProfCard(p) {
  const vi = verdictInfo(p);
  return `
    <a class="prof-card" href="profile.html?id=${p.id}">
      <div class="prof-avatar">${p.image_url ? `<img src="${p.image_url}" alt="${p.name}" style="width:100%;height:100%;object-fit:cover;" onerror="this.outerHTML='${p.avatar}'">` : p.avatar}</div>
      <div class="prof-info">
        <div class="prof-name">${p.name}</div>
        <div class="prof-meta">${p.dept}${p.courses && p.courses.length > 0 ? renderCourseBadges(p.courses) : ""}</div>
      </div>
      <div class="prof-right">
        ${vi.hasReviews ? `<span class="w-badge ${vi.cls}">${vi.label}</span>` : `<span class="w-badge" style="border-color: var(--border2); color: var(--muted);">No ratings</span>`}
        <span class="prof-pct" title="${vi.title}">${vi.hasReviews ? `${vi.dominant.toUpperCase()} ${vi.pct}%` : "—%"}</span>
        <span class="prof-count">${p.reviews} ratings</span>
      </div>
    </a>`;
}

function renderCourseBadges(courses) {
  if (!courses || courses.length === 0) return "";
  const show = courses.slice(0,2);
  const more = Math.max(0, courses.length - show.length);
  const encoded = encodeURIComponent(courses.join("|"));
  let out = "<span class=\"course-badges\">";
  show.forEach(c => { out += `<span class=\"course-badge\">${c}</span>`; });
  if (more > 0) {
    out += `<button class=\"course-badge course-more\" type=\"button\" onclick=\"showAllSubjects('${encoded}')\">+${more} more</button>`;
  }
  out += "</span>";
  return out;
}

window.showAllSubjects = function(encoded) {
  try {
    const raw = decodeURIComponent(encoded || "");
    const list = raw ? raw.split("|") : [];
    const content = list.length ? list.map(c => `<div class=\"subject-list-item\">${c}</div>`).join("") : "No subjects";
    // create modal
    const existing = document.getElementById("subject-modal");
    if (existing) existing.remove();
    const modal = document.createElement("div");
    modal.id = "subject-modal";
    modal.className = "subject-modal";
    modal.innerHTML = `
      <div class=\"subject-modal-backdrop\" onclick=\"document.getElementById('subject-modal')?.remove()\"></div>
      <div class=\"subject-modal-panel\">
        <div class=\"subject-modal-header\">All subjects</div>
        <div class=\"subject-modal-body\">${content}</div>
        <button class=\"subject-modal-close\" onclick=\"document.getElementById('subject-modal')?.remove()\">Close</button>
      </div>`;
    document.body.appendChild(modal);
  } catch (e) { alert((decodeURIComponent(encoded||"")).replace(/\|/g, ', ')); }
}

function verdictInfo(p) {
  const reviews = p.reviews || 0;
  // Prefer explicit counts from API if available
  let wCount = (typeof p.wCount === 'number') ? p.wCount : Math.round(((p.wPct || 0) / 100) * reviews);
  let lCount = (typeof p.lCount === 'number') ? p.lCount : Math.max(0, reviews - wCount);
  if (reviews === 0) return { hasReviews: false, dominant: 'w', pct: 0, label: '', cls: '', title: '' };
  const dominant = (wCount >= lCount) ? 'w' : 'l';
  const pct = Math.round(((dominant === 'w' ? wCount : lCount) / reviews) * 100);
  const cls = dominant === 'w' ? 'w' : 'l';
  const label = dominant === 'w' ? 'W Prof' : 'L Prof';
  const title = dominant === 'w' ? 'Percent of positive (W) ratings' : 'Percent of negative (L) ratings';
  return { hasReviews: true, dominant, pct, label, cls, title };
}

function renderHomeMobileProfItem(p, rank) {
  const isW = p.wPct >= 60;
  const hasReviews = p.reviews > 0;
    const vi = verdictInfo(p);
    const rankCls = rank === 1 ? "gold" : rank === 2 ? "silver" : rank === 3 ? "bronze" : "other";
    return `
      <a class="lb-item" href="profile.html?id=${p.id}">
        <div class="lb-rank ${rankCls}">#${rank}</div>
        <div class="lb-avatar">${p.image_url ? `<img src="${p.image_url}" alt="${p.name}" style="width:100%;height:100%;object-fit:cover;" onerror="this.outerHTML='${p.avatar}'">` : p.avatar}</div>
        <div class="lb-info">
          <div class="lb-name">${p.name}</div>
          <div class="lb-dept">${p.dept}${p.courses && p.courses.length > 0 ? `, ${p.courses.slice(0,2).join(", ")}${p.courses.length > 2 ? "..." : ""}` : ""}</div>
        </div>
        <div class="lb-score ${vi.hasReviews ? vi.cls : 'l'}" title="${vi.title}">${vi.hasReviews ? `${vi.dominant.toUpperCase()} ${vi.pct}%` : "—%"}</div>
      </a>`;
}

function renderSkeletons(n) {
  return Array.from({length: n}, () => `
    <div class="prof-card" style="pointer-events:none">
      <div class="prof-avatar skeleton" style="width:42px;height:42px"></div>
      <div class="prof-info">
        <div class="skeleton" style="height:13px;width:140px;border-radius:3px;margin-bottom:6px"></div>
        <div class="skeleton" style="height:11px;width:90px;border-radius:3px"></div>
      </div>
      <div class="prof-right">
        <div class="skeleton" style="height:20px;width:52px;border-radius:3px;margin-bottom:4px"></div>
        <div class="skeleton" style="height:18px;width:40px;border-radius:3px"></div>
      </div>
    </div>`
  ).join("");
}

function renderHomeMobileSkeletons(n) {
  return Array.from({length: n}, (_, i) => `
    <div class="lb-item" style="pointer-events:none">
      <div class="skeleton" style="width:24px;height:16px;border-radius:3px;flex-shrink:0"></div>
      <div class="skeleton" style="width:38px;height:38px;border-radius:50%;flex-shrink:0"></div>
      <div class="lb-info" style="min-width:0;flex:1">
        <div class="skeleton" style="height:13px;width:150px;border-radius:3px;margin-bottom:6px"></div>
        <div class="skeleton" style="height:11px;width:110px;border-radius:3px"></div>
      </div>
      <div class="skeleton" style="width:48px;height:16px;border-radius:3px;flex-shrink:0"></div>
    </div>
  `).join("");
}

/* ═══════════════════════════════════════════════════════════════════════
   PROFILE PAGE
═══════════════════════════════════════════════════════════════════════ */

// Module-level state for the subject toggle
let _profData       = null;
let _courseStats    = null;
let _activeCourse   = "global"; // "global" | course code string

async function initProfile() {
  const id   = getParam("id");
  const slot = el("content-slot");

  el("nav-slot").innerHTML = NAV_HTML("profile");

  if (!id) { slot.innerHTML = errorBlock("No professor selected."); return; }

  // Fetch both in parallel — stats-by-course is non-critical, so swallow errors
  const [p, courseStats] = await Promise.all([
    API.getProf(id),
    API.getProfStatsByCourse(id).catch(() => ({ global: null, courses: [] }))
  ]);

  if (!p) { slot.innerHTML = errorBlock("Professor not found."); return; }

  if (id !== p.id) {
    const newUrl = new URL(window.location);
    newUrl.searchParams.set("id", p.id);
    window.history.replaceState(null, "", newUrl);
  }

  document.title = p.name;

  // Store for tab switching
  _profData     = p;
  _courseStats  = courseStats;
  _activeCourse = "global";

  const reviewed = hasReviewed(p.id, "");

  // ── Static shell (avatar, name, dept tags — never changes per tab) ──────
  slot.innerHTML = `
    ${BACK_BTN("index.html", "All Professors")}

    <div class="profile-hero page-fade">
      <div class="profile-top">
        <div class="profile-avatar">${p.image_url
          ? `<img src="${p.image_url}" alt="${p.name}" style="width:100%;height:100%;object-fit:cover;" onerror="this.outerHTML='${p.avatar}'">`
          : p.avatar}</div>
        <div>
          <div class="profile-name-row">
              <div class="profile-name">${p.name}</div>
            </div>
          <div class="profile-dept-tag">${p.dept}${p.courses.length ? `, ${p.courses.join(", ")}` : ""}</div>
        </div>
      </div>
      <!-- Dynamic: W% badge + review count -->
      <div id="profile-verdict-row"></div>
    </div>

    <!-- Subject Toggle Bar (always visible) -->
    <div id="subject-toggle-wrap"></div>

    <!-- Dynamic: stat cards -->
    <div id="profile-stat-row"></div>

    <!-- Dynamic: metric bars -->
    <div id="profile-metrics"></div>

    <!-- Dynamic: lore drops -->
    <div id="profile-lore"></div>

    <!-- Dynamic: review CTA or already-reviewed -->
    <div id="profile-cta"></div>
  `;

  renderSubjectToggle(courseStats);
  renderProfileDynamic("global", p, courseStats);
  renderProfileCTA(p, reviewed, "global");
  initBars();
}

window.shareProfessor = async function(profName, profId) {
  if (!profId) return;

  const shareUrl = new URL(`/prof/${encodeURIComponent(profId)}`, window.location.origin).toString();
  const shareText = `${profName} — VITC Faculty Review`;

  try {
    if (navigator.share) {
      await navigator.share({
        title: shareText,
        text: `Check out ${profName}'s W/L stats on VITC Faculty Review.`,
        url: shareUrl
      });
      return;
    }

    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(`${shareText} ${shareUrl}`);
      showToast("Link copied to clipboard.");
      return;
    }

    throw new Error("Clipboard unavailable");
  } catch (err) {
    if (err?.name === "AbortError" || err?.name === "NotAllowedError") return;
    try {
      const fallback = `${shareText} ${shareUrl}`;
      window.prompt("Copy this link", fallback);
    } catch (_) {
      showToast("Sharing is unavailable right now.", "error");
    }
  }
};

/* ── Subject toggle pill bar ──────────────────────────────────────────── */
function renderSubjectToggle(courseStats) {
  const wrap = el("subject-toggle-wrap");
  if (!wrap) return;

  const hasCourses = courseStats && courseStats.courses && courseStats.courses.length > 0;

  // Even with no course-specific reviews yet, render the "Global" tab alone
  // so the UI is always consistent
  const globalReviews = courseStats?.global?.reviews ?? 0;
  let tabs = `
    <button class="subject-tab active" id="stab-global"
            onclick="switchSubjectTab('global')" type="button">
      All Reviews${globalReviews > 0 ? ` <span class="stab-count">${globalReviews}</span>` : ""}
    </button>`;

  if (hasCourses) {
    courseStats.courses.forEach(c => {
      const safeCode = c.code.replace(/'/g, "\\'");
      tabs += `
        <button class="subject-tab" id="stab-${c.code}"
                onclick="switchSubjectTab('${safeCode}')" type="button"
                title="${c.name}">
          ${c.code} <span class="stab-count">${c.reviews}</span>
        </button>`;
    });
  }

  wrap.innerHTML = `
    <div class="subject-toggle-bar page-fade">
      <div class="subject-toggle-label">View ratings for</div>
      <div class="subject-tabs-scroll">${tabs}</div>
    </div>`;
}

/* ── Switch tab (called from inline onclick) ──────────────────────────── */
window.switchSubjectTab = function(code) {
  if (!_profData || !_courseStats) return;
  _activeCourse = code;

  // Highlight active tab
  document.querySelectorAll(".subject-tab").forEach(btn => btn.classList.remove("active"));
  const activeTab = el(`stab-${code}`);
  if (activeTab) activeTab.classList.add("active");

  renderProfileDynamic(code, _profData, _courseStats);
  const courseKey = code === "global" ? "" : code;
  renderProfileCTA(_profData, hasReviewed(_profData.id, courseKey), code);
  initBars();
};

/* ── Render dynamic sections for the given tab ────────────────────────── */
function renderProfileDynamic(code, p, courseStats) {
  // Resolve which stats object to use
  let stats;
  if (code === "global") {
    stats = courseStats?.global;
  } else {
    stats = courseStats?.courses?.find(c => c.code === code);
  }

  // Fallback: use the prof's own pre-computed stats (for global when no stats-by-course)
  const wPct    = stats ? stats.wPct    : p.wPct;
  const reviews = stats ? stats.reviews : p.reviews;
  const metrics = stats ? stats.metrics : p.metrics;
  const lore    = stats ? stats.lore    : p.lore;
  const hasRevs = reviews > 0;
  const isW     = wPct >= 60;

  // ── Verdict row ───────────────────────────────────────────────────────
  const verdictEl = el("profile-verdict-row");
    if (verdictEl) {
    const lPct = 100 - wPct;  // Calculate L percentage
    const displayPct = isW ? wPct : lPct;  // Show appropriate percentage
    verdictEl.innerHTML = `
      <div class="verdict-row">
        <div class="verdict-left">
          <div class="verdict-pct ${hasRevs ? (isW ? "w" : "l") : "neutral"}"
               style="transition:color 0.3s">${hasRevs ? `${displayPct}%` : "—%"}</div>
          <div class="verdict-meta">
            <div class="verdict-meta-label ${hasRevs ? (isW ? "w" : "l") : "neutral"}"
                 style="${hasRevs ? "" : "color:var(--muted);"}">
              ${hasRevs ? (isW ? "W Rating" : "L Rating") : "No ratings"}
            </div>
            <div class="verdict-meta-count">${reviews} review${reviews !== 1 ? "s" : ""}${code !== "global" ? ` for ${code}` : ""}</div>
          </div>
        </div>
        <div class="verdict-actions">
          <button class="share-btn profile-share-inline" type="button" onclick='shareProfessor(${JSON.stringify(p.name)}, ${JSON.stringify(p.id)})' aria-label="Share this professor">
            <span class="share-btn-label">Share</span>
          </button>
        </div>
      </div>`;
  }

  // ── Stat cards ────────────────────────────────────────────────────────
  const statRowEl = el("profile-stat-row");
  if (statRowEl) {
    const avgVal = hasRevs ? avgMetric(metrics).toFixed(1) : "—";
    // Resolve course name when a subject tab is active
    const courseName = code !== "global"
      ? (courseStats?.courses?.find(c => c.code === code)?.name || null)
      : null;
    const courseSubline = code !== "global"
      ? `<div class="stat-course-name">${code}${courseName ? ` · ${courseName}` : ""}</div>`
      : "";
    statRowEl.innerHTML = `
      <div class="stat-row page-fade">
        <div class="stat-card">
          <div class="stat-val">${avgVal}</div>
          <div class="stat-label">Avg Score</div>
        </div>
        <div class="stat-card">
          <div class="stat-val">${reviews}</div>
          <div class="stat-label">${code === "global" ? "Total Reviews" : "Reviews"}</div>
          ${courseSubline}
        </div>
      </div>`;
  }

  // ── Metric bars ───────────────────────────────────────────────────────
  const metricsEl = el("profile-metrics");
  if (metricsEl) {
    metricsEl.innerHTML = `
      <div class="metrics-section page-fade">
        <div class="section-label metrics-title">Breakdown${code !== "global" ? ` · ${code}` : ""}</div>
        ${METRIC_DEFS.map(m => renderMetricBar(m, hasRevs ? metrics[m.key] : 0, !hasRevs)).join("")}
      </div>`;
  }

  // ── Lore drops ────────────────────────────────────────────────────────
  const loreEl = el("profile-lore");
  if (loreEl) {
    const hasLore = lore && (lore.green.length || lore.red.length);
    loreEl.innerHTML = hasLore ? `
      <div class="lore-section page-fade">
        <div class="section-label" style="margin-bottom:12px">Lore Drops${code !== "global" ? ` · ${code}` : ""}</div>
        <div class="lore-grid">
          ${lore.green.map(t => `<span class="lore-chip">${t}</span>`).join("")}
          ${lore.red.map(t   => `<span class="lore-chip">${t}</span>`).join("")}
        </div>
      </div>` : "";
  }
}

/* ── Review CTA (updates href when active course changes) ─────────────── */
function renderProfileCTA(p, reviewed, activeCourse) {
  const ctaEl = el("profile-cta");
  if (!ctaEl) return;

  if (reviewed) {
    ctaEl.innerHTML = `
      <div class="already-reviewed page-fade">
        <div class="already-reviewed-text">
          <strong>You've already rated this professor.</strong><br>
          Your lore is on record.
        </div>
      </div>`;
    return;
  }

  // Build the review URL — pass the active course as a pre-fill hint
  const reviewUrl = activeCourse && activeCourse !== "global"
    ? `review.html?id=${p.id}&course=${encodeURIComponent(activeCourse)}`
    : `review.html?id=${p.id}`;

  const subLabel = activeCourse && activeCourse !== "global"
    ? `Rating for ${activeCourse}`
    : "Rate this professor";

  ctaEl.innerHTML = `
    <a class="review-cta page-fade" href="${reviewUrl}" id="review-cta-link">
      <div>
        <div class="review-cta-title">Drop Your Rating</div>
        <div class="review-cta-sub">${subLabel}</div>
      </div>
      <div class="cta-icon">${ARROW_RIGHT_SVG}</div>
    </a>`;
}

function renderMetricBar(m, val, isEmpty) {
  const pct  = isEmpty ? 0 : Math.round((val / 5) * 100);
  const disp = isEmpty ? "—" : val.toFixed(1) + " / 5";
  return `
    <div class="metric-row">
      <div class="metric-head">
        <span class="metric-label">${m.label}</span>
        <span class="metric-val">${disp}</span>
      </div>
      <div class="bar-track">
        <div class="bar-fill ${isEmpty ? "" : barColor(val)}" style="width:${pct}%"></div>
      </div>
      <div class="metric-scale">
        <span class="metric-scale-low">${m.low}</span>
        <span class="metric-scale-high">${m.high}</span>
      </div>
    </div>`;
}

function avgMetric(m) {
  const vals = Object.values(m);
  return vals.reduce((a,b) => a+b, 0) / vals.length;
}

function errorBlock(msg) {
  return `<div class="empty-state"><div class="empty-title">${msg}</div></div>`;
}

const CHECK_SVG = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 6 9 17l-5-5"/></svg>`;

/* ═══════════════════════════════════════════════════════════════════════
   REVIEW PAGE
═══════════════════════════════════════════════════════════════════════ */
let _rv = {
  profId:  null,
  stars:   {},   // { lecture: 3, da: 4, ... }
  lore:    [],
  verdict: null,
  hp:      ""    // honeypot
};

async function initReview() {
  const id         = getParam("id");
  const presetCourse = getParam("course"); // comes from profile page subject tab
  el("nav-slot").innerHTML = NAV_HTML("review");

  if (!id) { go("index.html"); return; }

  // Already reviewed for the preset course? Only block if a course is specified.
  if (presetCourse) {
    if (hasReviewed(id, presetCourse)) {
      go("profile.html", { id });
      return;
    }
  }

  const p = await API.getProf(id);
  if (!p)  { go("index.html"); return; }

  if (id !== p.id) {
    const newUrl = new URL(window.location);
    newUrl.searchParams.set("id", p.id);
    window.history.replaceState(null, "", newUrl);
  }

  _rv.profId = p.id;
  document.title = `Rate ${p.name}`;

  el("back-slot").innerHTML   = BACK_BTN(`profile.html?id=${p.id}`, p.name);
  el("prof-name").textContent = p.name;

  el("metrics-slot").innerHTML = METRIC_DEFS.map((m, i) => renderStarGroup(m, i)).join("");
  el("lore-green").innerHTML   = LORE_GREEN.map(t => lorePick(t, "green")).join("");
  el("lore-red").innerHTML     = LORE_RED.map(t => lorePick(t, "red")).join("");

  // Load courses for live search suggestion
  (async () => {
    try {
      window._allCourses = await API.getCourses();
    } catch (err) {
      console.error("Failed loading courses", err);
    }
  })();

  // ── Pre-fill course from URL param (e.g. ?course=BCSE101E) ────────────
  if (presetCourse) {
    const courseInput = el("course-search");
    const courseSuggest = el("course-suggestions");
    if (courseInput) {
      courseInput.value = presetCourse;
      courseInput.setAttribute("data-preset", presetCourse);
      window._selectedCourseCode = presetCourse;

      // Show a locked-course badge above the input
      const wrap = courseInput.closest("div[style*='position:relative']");
      if (wrap) {
        const badge = document.createElement("div");
        badge.className = "preset-course-badge";
        badge.innerHTML = `
          <span class="preset-course-icon">
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
              <rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>
            </svg>
          </span>
          Rating for <strong>${presetCourse}</strong>
          <button class="preset-clear" type="button" onclick="clearPresetCourse()" title="Change course">✕</button>`;
        wrap.parentNode.insertBefore(badge, wrap);
        courseInput.style.display = "none";
        if (courseSuggest) courseSuggest.style.display = "none";
      }
    }
  }

  updateProgress();
  updateSubmit();
}

/* Clear a preset course and show the input again */
window.clearPresetCourse = function() {
  const courseInput   = el("course-search");
  const badge         = document.querySelector(".preset-course-badge");
  if (badge)       badge.remove();
  if (courseInput) {
    courseInput.style.display = "";
    courseInput.value = "";
    courseInput.removeAttribute("data-preset");
    window._selectedCourseCode = undefined;
    courseInput.focus();
  }
  updateSubmit();
};


function renderStarGroup(m, idx) {
  return `
    <div class="form-group">
      <div class="form-label">${m.label}</div>
      <div class="form-hint" style="display:flex; justify-content:space-between;">
        <span>${m.low}</span>
        <span>${m.high}</span>
      </div>
      <div class="star-row" data-metric="${m.key}">
        ${[1,2,3,4,5].map(n => `
          <button class="star-btn" data-val="${n}" onclick="selectStar('${m.key}', ${n}, this)" type="button">
            ${n}
          </button>`).join("")}
      </div>
    </div>`;
}

function lorePick(text, type) {
  return `<span class="lore-pick" data-type="${type}" onclick="toggleLore(this)">${text}</span>`;
}

function selectStar(metric, val, btn) {
  _rv.stars[metric] = val;
  const row = btn.closest(".star-row");
  qsa(".star-btn", row).forEach(b => {
    b.classList.toggle("lit", parseInt(b.dataset.val, 10) <= val);
  });
  updateProgress();
  updateSubmit();
}

function toggleLore(chip) {
  const text = chip.textContent.trim();
  const type = chip.dataset.type;
  const idx  = _rv.lore.indexOf(text);

  if (idx > -1) {
    _rv.lore.splice(idx, 1);
    chip.className = "lore-pick";
  } else {
    if (_rv.lore.length >= 3) {
      showToast("Max 3 lore chips per review.", "error");
      return;
    }
    _rv.lore.push(text);
    chip.className = "lore-pick selected";
  }

  // Grey out remaining chips if maxed
  qsa(".lore-pick").forEach(c => {
    const inLore = _rv.lore.includes(c.textContent.trim());
    if (_rv.lore.length >= 3 && !inLore) {
      c.classList.add("maxed");
    } else {
      c.classList.remove("maxed");
    }
  });

  el("lore-count").textContent = `${_rv.lore.length}/3 selected`;
}

function pickVerdict(v) {
  _rv.verdict = v;
  el("vbtn-w").className = "verdict-btn" + (v === "w" ? " sel-w" : "");
  el("vbtn-l").className = "verdict-btn" + (v === "l" ? " sel-l" : "");
  updateProgress();
  updateSubmit();
}

function updateProgress() {
  let done = Object.keys(_rv.stars).length;
  if (_rv.verdict) done++;
  qsa(".progress-dot").forEach((dot, i) => {
    dot.classList.toggle("done", i < done);
  });
}

window.handleCourseInput = function(inputEl) {
  const query = inputEl.value.trim().toLowerCase();
  const box = el("course-suggestions");
  if (!box) return;
  
  if (!query) {
    box.style.display = "none";
    box.innerHTML = "";
    updateSubmit();
    return;
  }
  
  const matches = (window._allCourses || []).filter(c => {
    const isCfoc = c.id.toLowerCase().startsWith("cfoc");
    const nameMatch = c.name.toLowerCase().includes(query) || c.id.toLowerCase().includes(query);
    
    if (isCfoc) {
      // ONLY allow CFOC courses to be suggested if the user typed at least 50% of "cfoc" (i.e. at least 3 characters: "cfo", "cfoc", or specific code)
      return query.length >= 3 && nameMatch;
    }
    return nameMatch;
  });
  
  if (matches.length === 0) {
    box.style.display = "block";
    box.innerHTML = `
      <div class="suggestion-item" 
           style="padding:10px 12px; cursor:pointer; font-family:var(--font-sans); font-size:14px; color:var(--text); transition:background 0.2s; background:var(--surface2);" 
           onmouseover="this.style.background='var(--surface3)'" 
           onmouseout="this.style.background='var(--surface2)'" 
           onclick="selectCustomCourse('${inputEl.value.trim().replace(/'/g, "\\'")}')">
        Use custom course: "${inputEl.value.trim()}"
      </div>`;
    updateSubmit();
    return;
  }
  
  box.style.display = "block";
  box.innerHTML = matches.slice(0, 10).map(c => {
    // Escape single quotes in name & id to prevent string breaking
    const safeId = c.id.replace(/'/g, "\\'");
    const safeName = c.name.replace(/'/g, "\\'");
    return `
      <div class="suggestion-item" 
           style="padding:10px 12px; cursor:pointer; border-bottom:1px solid var(--border); font-family:var(--font-sans); font-size:14px; color:var(--text); transition:background 0.2s; background:var(--surface2);" 
           onmouseover="this.style.background='var(--surface3)'" 
           onmouseout="this.style.background='var(--surface2)'" 
           onclick="selectSuggestion('${safeId}', '${safeName}')">
        <strong>${c.id}</strong> - ${c.name}
      </div>`;
  }).join("");
  
  updateSubmit();
};

window.selectSuggestion = function(id, name) {
  const inputEl = el("course-search");
  const box = el("course-suggestions");
  if (inputEl) {
    inputEl.value = `${id} - ${name}`;
    window._selectedCourseCode = id;
  }
  if (box) {
    box.style.display = "none";
    box.innerHTML = "";
  }
  updateSubmit();
};

window.selectCustomCourse = function(customVal) {
  const inputEl = el("course-search");
  const box = el("course-suggestions");
  if (inputEl) {
    inputEl.value = customVal;
    window._selectedCourseCode = customVal;
  }
  if (box) {
    box.style.display = "none";
    box.innerHTML = "";
  }
  updateSubmit();
};

// Close suggestions dropdown when clicking outside
document.addEventListener("click", function(e) {
  const box = el("course-suggestions");
  const searchInput = el("course-search");
  if (box && searchInput && !box.contains(e.target) && e.target !== searchInput) {
    box.style.display = "none";
  }
});

function isReviewComplete() {
  const allMetrics = METRIC_DEFS.every(m => _rv.stars[m.key] !== undefined);
  const searchInput = el("course-search");
  let courseDone = false;
  if (searchInput) {
    courseDone = searchInput.value.trim().length > 0;
  } else {
    courseDone = true;
  }
  return allMetrics && _rv.verdict !== null && courseDone;
}

function updateSubmit() {
  const btn = el("submit-btn");
  const complete = isReviewComplete();
  btn.classList.toggle("ready", complete);
  btn.disabled = !complete;
}

async function submitReview() {
  const btn = el("submit-btn");
  if (!btn.classList.contains("ready") || btn.classList.contains("loading")) return;

  btn.classList.add("loading");
  btn.textContent = "Submitting...";

  let selectedCourse = ""; // Always default to empty string
  const searchInput = el("course-search");
  if (searchInput) {
    const val = searchInput.value.trim();
    if (window._selectedCourseCode && val.startsWith(window._selectedCourseCode)) {
      selectedCourse = window._selectedCourseCode;
    } else if (val) {
      // User typed their own custom course directly
      const parts = val.split(" - ");
      selectedCourse = (parts[0] || "").trim();
    }
    // If val is empty, selectedCourse stays as ""
  }
  // Ensure selectedCourse is always a string
  selectedCourse = String(selectedCourse || "").trim();

  try {
    const payload = {
      metrics: { ...METRIC_DEFS.reduce((acc, m) => ({ ...acc, [m.key]: _rv.stars[m.key] }), {}) },
      verdict: _rv.verdict,
      lore:    [..._rv.lore],
      course:  selectedCourse,
      fp:      getFingerprint(),
      website: el("hp").value
    };

    const result = await API.submitReview(_rv.profId, payload);

    if (result.success) {
      markReviewed(_rv.profId, selectedCourse);
      showToast("Rating submitted. Lore recorded.");
      setTimeout(() => go("profile.html", { id: _rv.profId }), 1200);
    } else {
      const msg = result.error || "Something went wrong. Try again.";
      showToast(msg, "error");
      btn.classList.remove("loading");
      btn.textContent = "Submit Rating";
      return;
    }
  } catch (e) {
    showToast("Something went wrong. Try again.", "error");
    btn.classList.remove("loading");
    btn.textContent = "Submit Rating";
  }
}

/* ═══════════════════════════════════════════════════════════════════════
   LEADERBOARD PAGE
═══════════════════════════════════════════════════════════════════════ */
let _lbMode = "w";
let _leaderboardPage = 1;

async function initLeaderboard() {
  el("nav-slot").innerHTML = NAV_HTML("leaderboard");
  _leaderboardPage = 1;
  const profs = await API.getLeaderboard();
  renderLeaderboard(profs, "w", 1);
}

function setLbTab(mode) {
  _lbMode = mode === "l" ? "l" : "w";
  _leaderboardPage = 1;
  qsa(".lb-tab").forEach(t => t.classList.remove("active", "w-tab", "l-tab"));
  const active = el(`tab-${_lbMode}`);
  if (active) active.classList.add("active", _lbMode === "w" ? "w-tab" : "l-tab");
  API.getLeaderboard().then(profs => renderLeaderboard(profs, _lbMode, 1));
}

function renderLeaderboard(sorted, mode, page = 1) {
  _leaderboardPage = page;
  const list = el("lb-list");
  const pagEl = el("pagination-slot");
  // Keep server order but filter to the selected mode (W or L)
  const all = sorted.slice();
  const display = all.filter(p => {
    const vi = verdictInfo(p);
    // Only include profs with reviews in leaderboard tabs
    if (!vi.hasReviews) return false;
    return mode === "l" ? vi.dominant === 'l' : vi.dominant === 'w';
  });

  if (display.length === 0) {
    list.innerHTML = errorBlock("No data yet.");
    if (pagEl) pagEl.innerHTML = "";
    return;
  }

  const start = (page - 1) * ITEMS_PER_PAGE;
  const end = start + ITEMS_PER_PAGE;
  const paginated = display.slice(start, end);

  list.innerHTML = paginated.map((p, i) => {
    const globalRank = mode === "l" ? sorted.length - (start + i) : (start + i) + 1;
    const rankCls    = (start + i) === 0 ? "gold" : (start + i) === 1 ? "silver" : (start + i) === 2 ? "bronze" : "other";
    const vi = verdictInfo(p);
    return `
      <a class="lb-item" href="profile.html?id=${p.id}">
        <div class="lb-rank ${rankCls}">#${globalRank}</div>
        <div class="lb-avatar">${p.image_url ? `<img src="${p.image_url}" alt="${p.name}" style="width:100%;height:100%;object-fit:cover;" onerror="this.outerHTML='${p.avatar}'">` : p.avatar}</div>
        <div class="lb-info">
          <div class="lb-name">${p.name}</div>
          <div class="lb-dept">${p.dept}, ${p.reviews} reviews</div>
        </div>
        <div class="lb-score ${vi.hasReviews ? vi.cls : 'l'}" title="${vi.title}">${vi.hasReviews ? `${vi.dominant.toUpperCase()} ${vi.pct}%` : '—%'}</div>
      </a>`;
  }).join("");

  if (pagEl) {
    pagEl.innerHTML = renderPagination(display.length, _leaderboardPage, ITEMS_PER_PAGE, "changeLeaderboardPage");
  }

  // Always show the request-teacher banner at the bottom
  const rtSlot = el("request-teacher-slot");
  if (rtSlot) rtSlot.innerHTML = renderRequestTeacherBanner();
}

window.changeLeaderboardPage = function(page) {
  API.getLeaderboard().then(profs => {
    renderLeaderboard(profs, _lbMode, page);
    el("lb-list").scrollIntoView({ behavior: "smooth", block: "start" });
  });
};

function renderPagination(totalItems, currentPage, itemsPerPage, onPageChangeName) {
  const totalPages = Math.ceil(totalItems / itemsPerPage);
  if (totalPages <= 1) return "";

  let selectOptions = "";
  for (let i = 1; i <= totalPages; i++) {
    selectOptions += `<option value="${i}" ${i === currentPage ? "selected" : ""}>Page ${i}</option>`;
  }

  let numbersHtml = "";
  const maxButtons = 5;
  
  if (totalPages <= maxButtons) {
    for (let i = 1; i <= totalPages; i++) {
      numbersHtml += `<div class="pag-num ${i === currentPage ? "active" : ""}" onclick="${onPageChangeName}(${i})">${i}</div>`;
    }
  } else {
    let startPage = Math.max(1, currentPage - 1);
    let endPage = Math.min(totalPages, currentPage + 1);

    if (currentPage <= 2) {
      endPage = 4;
    } else if (currentPage >= totalPages - 1) {
      startPage = totalPages - 3;
    }

    if (startPage > 1) {
      numbersHtml += `<div class="pag-num" onclick="${onPageChangeName}(1)">1</div>`;
      if (startPage > 2) {
        numbersHtml += `<span class="pag-dots">...</span>`;
      }
    }

    for (let i = startPage; i <= endPage; i++) {
      numbersHtml += `<div class="pag-num ${i === currentPage ? "active" : ""}" onclick="${onPageChangeName}(${i})">${i}</div>`;
    }

    if (endPage < totalPages) {
      if (endPage < totalPages - 1) {
        numbersHtml += `<span class="pag-dots">...</span>`;
      }
      numbersHtml += `<div class="pag-num" onclick="${onPageChangeName}(${totalPages})">${totalPages}</div>`;
    }
  }

  return `
    <div class="pagination-container page-fade">
      <div class="pag-row">
        <button class="pag-btn" ${currentPage === 1 ? "disabled" : ""} onclick="${onPageChangeName}(${currentPage - 1})">Prev</button>
        <div class="pag-numbers">
          ${numbersHtml}
        </div>
        <button class="pag-btn" ${currentPage === totalPages ? "disabled" : ""} onclick="${onPageChangeName}(${currentPage + 1})">Next</button>
      </div>
      <div class="pag-jump">
        <span>Jump to:</span>
        <select class="pag-select" onchange="${onPageChangeName}(parseInt(this.value))">
          ${selectOptions}
        </select>
      </div>
    </div>
  `;
}

/* ─── REQUEST TEACHER BANNER ─────────────────────────────────────────── */
function renderRequestTeacherBanner(prefill = "") {
  const safeVal = prefill ? prefill.replace(/"/g, '&quot;').replace(/'/g, '&#39;') : "";
  return `
    <div class="req-teacher-banner">
      <div class="req-teacher-inner">
        <div class="req-teacher-icon">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
            <circle cx="12" cy="8" r="4"/>
            <path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/>
          </svg>
          <span class="req-teacher-plus">+</span>
        </div>
        <div class="req-teacher-text">
          <div class="req-teacher-title">Can't find your professor?</div>
          <div class="req-teacher-sub">Enter their name and we'll add them.</div>
        </div>
      </div>
      <div class="req-teacher-form">
        <input
          id="req-teacher-name"
          class="req-teacher-input"
          type="text"
          placeholder="Professor's full name"
          value="${safeVal}"
          autocomplete="off"
          onkeydown="if(event.key==='Enter') window.submitTeacherRequest()"
        >
        <button
          class="req-teacher-btn"
          type="button"
          onclick="window.submitTeacherRequest()"
        >Request &rarr;</button>
      </div>
    </div>`;
}

window.submitTeacherRequest = function() {
  const nameEl = el("req-teacher-name");
  if (!nameEl) return;
  const name = nameEl.value.trim();
  if (!name) {
    nameEl.focus();
    nameEl.classList.add("req-shake");
    setTimeout(() => nameEl.classList.remove("req-shake"), 500);
    return;
  }
  const subject = encodeURIComponent(`[Add Professor] ${name}`);
  const body = encodeURIComponent(
    `Hi,\n\nI'd like to request the following professor to be added to the VIT Faculty Review platform:\n\nName: ${name}\nDepartment (if known): \n\nThanks!`
  );
  window.open(`mailto:vit.fac@proton.me?subject=${subject}&body=${body}`, "_blank");
};

/* ─── UTILS ───────────────────────────────────────────────────────────── */
function debounce(fn, ms) {
  let t;
  return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
}

/* ═══════════════════════════════════════════════════════════════════════
   ADMIN DASHBOARD PAGE
   ═══════════════════════════════════════════════════════════════════════ */
let adminPollInterval = null;

async function initAdmin() {
  const urlParams = new URLSearchParams(window.location.search);
  const keyParam = urlParams.get("key");
  if (keyParam) {
    localStorage.setItem("admin_secret", keyParam);
    // Remove query param from URL for visual cleanliness
    const newUrl = window.location.pathname;
    window.history.replaceState(null, "", newUrl);
  }

  const activeKey = localStorage.getItem("admin_secret");
  if (!activeKey) {
    el("admin-auth").style.display = "block";
    el("admin-dashboard").style.display = "none";
    return;
  }

  el("admin-auth").style.display = "none";
  el("admin-dashboard").style.display = "block";

  // Initial load
  await triggerAdminReload();

  // Set up 5-second polling interval
  if (adminPollInterval) clearInterval(adminPollInterval);
  adminPollInterval = setInterval(async () => {
    const key = localStorage.getItem("admin_secret");
    if (!key) {
      clearInterval(adminPollInterval);
      return;
    }
    try {
      const data = await API.getAdminStats(key);
      renderAdminDashboard(data);
    } catch (e) {
      clearInterval(adminPollInterval);
      localStorage.removeItem("admin_secret");
      window.location.reload();
    }
  }, 5000);
}

window.triggerAdminReload = async function() {
  const activeKey = localStorage.getItem("admin_secret");
  if (!activeKey) return;
  
  const refreshBtn = el("admin-refresh-btn");
  if (refreshBtn) {
    refreshBtn.disabled = true;
    refreshBtn.textContent = "🔄 Loading...";
  }

  try {
    const data = await API.getAdminStats(activeKey);
    renderAdminDashboard(data);
  } catch (err) {
    showToast("Invalid admin access key", "error");
    localStorage.removeItem("admin_secret");
    setTimeout(() => {
      window.location.reload();
    }, 1000);
  } finally {
    if (refreshBtn) {
      refreshBtn.disabled = false;
      refreshBtn.textContent = "🔄 Refresh";
    }
  }
};

window.handleAdminLogin = function() {
  const key = el("admin-password-input").value.trim();
  if (!key) {
    showToast("Please enter an access key", "error");
    return;
  }
  localStorage.setItem("admin_secret", key);
  window.location.reload();
};

window.handleAdminLogout = function() {
  localStorage.removeItem("admin_secret");
  if (adminPollInterval) clearInterval(adminPollInterval);
  window.location.reload();
};

function renderAdminDashboard(data) {
  // Update aggregate cards
  el("stat-active").textContent = data.active_visitors;
  el("stat-views").textContent = data.views_24h;
  el("stat-profs").textContent = data.total_profs;
  el("stat-reviews").textContent = data.total_reviews;
  el("stat-ips").textContent = data.unique_ips;
  el("stat-fps").textContent = data.unique_fps;

  // Render traffic time
  el("traffic-time").textContent = `UPDATED: ${new Date().toLocaleTimeString()}`;

  // Render Latest Reviews table
  const tbody = el("latest-reviews-rows");
  if (!data.latest_reviews || data.latest_reviews.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;color:var(--muted);padding:30px">No submissions logged yet.</td></tr>`;
  } else {
    tbody.innerHTML = data.latest_reviews.map(r => {
      const isW = r.verdict === "w";
      const formattedDate = new Date(r.submitted_at).toLocaleString(undefined, {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
      });
      const tagBadges = (r.lore || []).map(t => `<span class="badge-tag">${t}</span>`).join("");
      
      return `
        <tr>
          <td class="muted">${formattedDate}</td>
          <td>
            <a href="profile.html?id=${r.prof_id}" style="color:var(--text);font-weight:600;text-decoration:none;">
              ${r.prof_name}
            </a>
          </td>
          <td class="stars-cell">${r.lecture}/${r.da}/${r.assign}/${r.vibe}</td>
          <td>
            <span class="v-pill ${isW ? 'w' : 'l'}">${isW ? 'Hell Yea' : 'Hell Nah'}</span>
          </td>
          <td>
            <div class="badge-tag-list">${tagBadges || '<span class="muted">—</span>'}</div>
          </td>
          <td class="muted">${r.ip}</td>
          <td class="muted fp-cell" title="${r.fp}">${r.fp}</td>
        </tr>
      `;
    }).join("");
  }

  // Render Top Reviewed
  const rankList = el("top-reviewed-list");
  if (!data.top_profs || data.top_profs.length === 0) {
    rankList.innerHTML = `<div style="color:var(--muted);font-size:12px;text-align:center;padding:20px">No statistics computed.</div>`;
  } else {
    rankList.innerHTML = data.top_profs.map((p, idx) => {
      return `
        <div class="rank-row">
          <div class="rank-info">
            <a href="profile.html?id=${p.id}" class="rank-name" style="text-decoration:none;">
              #${idx + 1} ${p.name}
            </a>
            <span class="rank-count">${p.reviews} reviews</span>
          </div>
          <div class="rank-stat">${p.w_pct}%</div>
        </div>
      `;
    }).join("");
  }
}
