-- ─────────────────────────────────────────────────────────────────────────
--  PostgreSQL Schema
--  Run this once to set up the database.
--
--  Commands:
--    createdb facreview
--    psql -d facreview -f schema.sql
--
--  Key differences from MySQL version:
--    · AUTO_INCREMENT     → GENERATED ALWAYS AS IDENTITY
--    · TINYINT            → SMALLINT
--    · ENUM               → custom TYPE
--    · ENGINE=InnoDB      → removed (Postgres default)
--    · DELIMITER $$       → $$ dollar-quoting in CREATE FUNCTION
--    · INDEX inside CREATE TABLE → separate CREATE INDEX statements
--    · ON UPDATE CURRENT_TIMESTAMP → handled inside trigger function
--    · JSON               → JSONB  (binary JSON, faster indexing & querying)
--    · GROUP_CONCAT       → STRING_AGG  (used in app.py queries)
-- ─────────────────────────────────────────────────────────────────────────

-- ─── VERDICT TYPE ─────────────────────────────────────────────────────────
DO $$ BEGIN
    CREATE TYPE verdict_type AS ENUM ('w', 'l');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;


-- ─── FACULTY ──────────────────────────────────────────────────────────────
-- Sourced from VIT's official faculty data (CSV import).
-- Sensitive HR fields (date_of_joining, faculty_type) stored but NEVER
-- exposed via any public API route — students only see the safe subset.

CREATE TABLE IF NOT EXISTS faculty (
    id                INTEGER       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    employee_id       VARCHAR(20)   NOT NULL UNIQUE,       -- e.g. "51074"
    name              VARCHAR(120)  NOT NULL,               -- e.g. "Dr A Felix"
    designation       VARCHAR(100)  DEFAULT NULL,           -- "Associate Professor"
    school_centre     VARCHAR(150)  DEFAULT NULL,           -- "School of Advanced Sciences"
    campus            VARCHAR(60)   DEFAULT NULL,           -- "Chennai"
    faculty_image_url VARCHAR(500)  DEFAULT NULL,           -- original CDN url
    profile_url       VARCHAR(500)  DEFAULT NULL,           -- VIT profile page

    -- Hidden from students — HR use only
    date_of_joining   DATE          DEFAULT NULL,
    faculty_type      VARCHAR(60)   DEFAULT NULL,           -- "Regular" / "Visiting"

    created_at        TIMESTAMPTZ   DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_faculty_campus      ON faculty (campus);
CREATE INDEX IF NOT EXISTS idx_faculty_school      ON faculty (school_centre);
CREATE INDEX IF NOT EXISTS idx_faculty_employee_id ON faculty (employee_id);


-- ─── FACULTY COURSES ─────────────────────────────────────────────────────
-- Maps course codes to faculty. One faculty can teach many courses.
-- Populate from your college's course registration data / VTOP.

CREATE TABLE IF NOT EXISTS faculty_courses (
    id          INTEGER       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    faculty_id  INTEGER       NOT NULL REFERENCES faculty(id) ON DELETE CASCADE,
    course_code VARCHAR(20)   NOT NULL,     -- e.g. "CS2001"
    course_name VARCHAR(150)  NOT NULL,     -- e.g. "Data Structures"
    semester    VARCHAR(20)   DEFAULT NULL, -- e.g. "ODD2024", "EVEN2025"

    UNIQUE (faculty_id, course_code)
);

CREATE INDEX IF NOT EXISTS idx_course_code    ON faculty_courses (course_code);
CREATE INDEX IF NOT EXISTS idx_faculty_course ON faculty_courses (faculty_id, course_code);


-- ─── REVIEWS ──────────────────────────────────────────────────────────────
-- One row per submission. No user accounts — identity tracked via
-- browser fingerprint only (anti-spam, not authentication).

CREATE TABLE IF NOT EXISTS reviews (
    id            BIGINT        GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    faculty_id    INTEGER       NOT NULL REFERENCES faculty(id) ON DELETE CASCADE,

    -- Metric scores (1-5)
    score_lecture SMALLINT      NOT NULL CHECK (score_lecture BETWEEN 1 AND 5),
    score_da      SMALLINT      NOT NULL CHECK (score_da      BETWEEN 1 AND 5),
    score_assign  SMALLINT      NOT NULL CHECK (score_assign  BETWEEN 1 AND 5),
    score_vibe    SMALLINT      NOT NULL CHECK (score_vibe    BETWEEN 1 AND 5),

    -- Binary verdict
    verdict       verdict_type  NOT NULL,

    -- Lore chips as JSONB — e.g. '["Surprise quizzes","Chill with DA"]'
    -- JSONB is faster than JSON for reads and supports GIN indexing
    lore_chips    JSONB         DEFAULT NULL,

    -- Anti-spam
    browser_fp    VARCHAR(32)   NOT NULL,     -- FNV hash from frontend
    ip_address    VARCHAR(45)   DEFAULT NULL, -- IPv4 or IPv6, for rate-limiting
    user_agent    VARCHAR(500)  DEFAULT NULL,

    submitted_at  TIMESTAMPTZ   DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reviews_faculty_id ON reviews (faculty_id);
CREATE INDEX IF NOT EXISTS idx_reviews_browser_fp ON reviews (browser_fp);
CREATE INDEX IF NOT EXISTS idx_reviews_ip         ON reviews (ip_address);
CREATE INDEX IF NOT EXISTS idx_reviews_submitted  ON reviews (submitted_at);
-- GIN index lets you query lore_chips JSONB array elements efficiently
CREATE INDEX IF NOT EXISTS idx_reviews_lore       ON reviews USING GIN (lore_chips);


-- ─── REVIEW AGGREGATES (denormalised for fast reads) ─────────────────────
-- Recalculated by a trigger on every INSERT into reviews.
-- Avoids expensive AVG() queries on every page load.

CREATE TABLE IF NOT EXISTS faculty_stats (
    faculty_id    INTEGER       PRIMARY KEY REFERENCES faculty(id) ON DELETE CASCADE,
    total_reviews INTEGER       DEFAULT 0,
    w_count       INTEGER       DEFAULT 0,
    l_count       INTEGER       DEFAULT 0,
    w_pct         SMALLINT      DEFAULT 0,      -- 0-100
    avg_lecture   NUMERIC(3,2)  DEFAULT 0.00,
    avg_da        NUMERIC(3,2)  DEFAULT 0.00,
    avg_assign    NUMERIC(3,2)  DEFAULT 0.00,
    avg_vibe      NUMERIC(3,2)  DEFAULT 0.00,
    top_lore      JSONB         DEFAULT NULL,   -- top 5 chips by frequency
    last_reviewed TIMESTAMPTZ   DEFAULT NOW()
);


-- ─── PROFESSOR SUGGESTIONS ────────────────────────────────────────────────
-- Students submit names that aren't in the DB yet.
-- Review these in your admin panel and add to faculty table.

CREATE TABLE IF NOT EXISTS prof_suggestions (
    id           INTEGER       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name         VARCHAR(120)  NOT NULL,
    ip_address   VARCHAR(45)   DEFAULT NULL,
    user_agent   VARCHAR(500)  DEFAULT NULL,
    reviewed     BOOLEAN       DEFAULT FALSE, -- FALSE = pending, TRUE = done
    submitted_at TIMESTAMPTZ   DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_suggestions_reviewed ON prof_suggestions (reviewed);


-- ─── FUNCTION: upsert aggregated stats for one faculty member ─────────────
-- Called by both triggers. Single place to change recalc logic.

CREATE OR REPLACE FUNCTION upsert_faculty_stats(fid INTEGER)
RETURNS VOID AS $$
DECLARE
    v_total   INTEGER;
    v_w       INTEGER;
    v_l       INTEGER;
    v_w_pct   SMALLINT;
    v_lecture NUMERIC(3,2);
    v_da      NUMERIC(3,2);
    v_assign  NUMERIC(3,2);
    v_vibe    NUMERIC(3,2);
BEGIN
    SELECT
        COUNT(*)                                          ,
        COUNT(*) FILTER (WHERE verdict = 'w')            ,
        COUNT(*) FILTER (WHERE verdict = 'l')            ,
        ROUND(AVG(score_lecture)::NUMERIC, 2)            ,
        ROUND(AVG(score_da)::NUMERIC,      2)            ,
        ROUND(AVG(score_assign)::NUMERIC,  2)            ,
        ROUND(AVG(score_vibe)::NUMERIC,    2)
    INTO v_total, v_w, v_l, v_lecture, v_da, v_assign, v_vibe
    FROM reviews
    WHERE faculty_id = fid;

    v_w_pct := CASE
        WHEN v_total > 0 THEN ROUND(v_w * 100.0 / v_total)
        ELSE 0
    END;

    INSERT INTO faculty_stats
        (faculty_id, total_reviews, w_count, l_count, w_pct,
         avg_lecture, avg_da, avg_assign, avg_vibe, last_reviewed)
    VALUES
        (fid,
         COALESCE(v_total,   0),
         COALESCE(v_w,       0),
         COALESCE(v_l,       0),
         COALESCE(v_w_pct,   0),
         COALESCE(v_lecture, 0),
         COALESCE(v_da,      0),
         COALESCE(v_assign,  0),
         COALESCE(v_vibe,    0),
         NOW())
    ON CONFLICT (faculty_id) DO UPDATE SET
        total_reviews = EXCLUDED.total_reviews,
        w_count       = EXCLUDED.w_count,
        l_count       = EXCLUDED.l_count,
        w_pct         = EXCLUDED.w_pct,
        avg_lecture   = EXCLUDED.avg_lecture,
        avg_da        = EXCLUDED.avg_da,
        avg_assign    = EXCLUDED.avg_assign,
        avg_vibe      = EXCLUDED.avg_vibe,
        last_reviewed = EXCLUDED.last_reviewed;
END;
$$ LANGUAGE plpgsql;


-- ─── TRIGGER: init stats row when a faculty member is inserted ────────────

CREATE OR REPLACE FUNCTION trigger_init_faculty_stats()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO faculty_stats (faculty_id)
    VALUES (NEW.id)
    ON CONFLICT DO NOTHING;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS after_faculty_insert ON faculty;
CREATE TRIGGER after_faculty_insert
    AFTER INSERT ON faculty
    FOR EACH ROW
    EXECUTE FUNCTION trigger_init_faculty_stats();


-- ─── TRIGGER: recalculate stats after every new review ───────────────────

CREATE OR REPLACE FUNCTION trigger_update_faculty_stats()
RETURNS TRIGGER AS $$
BEGIN
    PERFORM upsert_faculty_stats(NEW.faculty_id);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS after_review_insert ON reviews;
CREATE TRIGGER after_review_insert
    AFTER INSERT ON reviews
    FOR EACH ROW
    EXECUTE FUNCTION trigger_update_faculty_stats();


-- ─── IMPORT HELPER ────────────────────────────────────────────────────────
-- After running this schema, import your CSV with:
--
--   psql -d proflore -c "
--   \COPY faculty
--     (employee_id, name, designation, school_centre,
--      date_of_joining, faculty_type, profile_url, campus, faculty_image_url)
--   FROM '/path/to/faculty.csv'
--   CSV HEADER;"
--
-- Note: Postgres \COPY expects dates as YYYY-MM-DD by default.
-- If your CSV has DD-MM-YYYY dates, use import_faculty.py instead —
-- it handles the conversion automatically.
