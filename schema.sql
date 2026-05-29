-- PostgreSQL Schema
--  Run this once to set up the database.
-- Target database: facreview
-- Supabase usage notes:
--  · Supabase already provisions a PostgreSQL database for your project.
--  · To run this schema in Supabase: open your Supabase project → SQL Editor → New query,
--    paste the contents of this file and execute it. Do NOT run `createdb` in Supabase.
--  · This file assumes the `public` search_path; we'll set it explicitly below.

SET search_path = public;

-- If you want to run locally instead, create a database named `proflore` and
-- run: psql -d proflore -f schema.sql

-- --- VERDICT TYPE ------------------------------------------------------------
DO $$ BEGIN
    CREATE TYPE verdict_type AS ENUM ('w', 'l');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- --- FACULTY -----------------------------------------------------------------
-- Based on data/vit_chennai_fac.csv

CREATE TABLE IF NOT EXISTS faculty (
    id                INTEGER       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    employee_id       VARCHAR(20)   NOT NULL UNIQUE,        -- e.g. "54506"
    name              VARCHAR(120)  NOT NULL,               -- e.g. "Dr. Jayaraman G"
    designation       VARCHAR(150)  DEFAULT NULL,           -- e.g. "Professor and Dean"
    email             VARCHAR(150)  DEFAULT NULL,
    research_area     TEXT          DEFAULT NULL,
    profile_url       VARCHAR(500)  DEFAULT NULL,           -- VIT profile page
    image_url         VARCHAR(500)  DEFAULT NULL,           -- Main image url
    all_image_urls    TEXT          DEFAULT NULL,           -- Comma separated image urls
    school_page       VARCHAR(500)  DEFAULT NULL,
    faculty_page      VARCHAR(500)  DEFAULT NULL,
    campus            VARCHAR(60)   DEFAULT NULL,           -- e.g. "Chennai"
    
    created_at        TIMESTAMPTZ   DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_faculty_campus      ON faculty (campus);
CREATE INDEX IF NOT EXISTS idx_faculty_employee_id ON faculty (employee_id);


-- --- COURSES -----------------------------------------------------------------
-- Based on data/courses.csv

CREATE TABLE IF NOT EXISTS courses (
    course_id         VARCHAR(20)   PRIMARY KEY,            -- e.g. "BCHY101L"
    course_name       VARCHAR(150)  NOT NULL,               -- e.g. "Engineering Chemistry"
    course_type       VARCHAR(20)   DEFAULT NULL,           -- e.g. "theory", "lab"
    credits           NUMERIC(3,1)  DEFAULT NULL            -- e.g. 3.0
);

CREATE INDEX IF NOT EXISTS idx_courses_name ON courses (course_name);


-- --- FACULTY COURSES ---------------------------------------------------------

CREATE TABLE IF NOT EXISTS faculty_courses (
    id          INTEGER       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    faculty_id  INTEGER       NOT NULL REFERENCES faculty(id) ON DELETE CASCADE,
    course_id   VARCHAR(20)   NOT NULL REFERENCES courses(course_id) ON DELETE CASCADE,
    semester    VARCHAR(20)   DEFAULT NULL, -- e.g. "ODD2024", "EVEN2025"
    UNIQUE (faculty_id, course_id)
);

CREATE INDEX IF NOT EXISTS idx_fc_course  ON faculty_courses (course_id);
CREATE INDEX IF NOT EXISTS idx_fc_faculty ON faculty_courses (faculty_id, course_id);


-- --- REVIEWS -----------------------------------------------------------------
-- Based on main.js payload and METRIC_DEFS

CREATE TABLE IF NOT EXISTS reviews (
    id            BIGINT        GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    faculty_id    INTEGER       NOT NULL REFERENCES faculty(id) ON DELETE CASCADE,
    
    -- Metric scores (1-5)
    score_lecture SMALLINT      NOT NULL CHECK (score_lecture BETWEEN 1 AND 5),
    score_da      SMALLINT      NOT NULL CHECK (score_da      BETWEEN 1 AND 5),
    score_assign  SMALLINT      NOT NULL CHECK (score_assign  BETWEEN 1 AND 5),
    score_vibe    SMALLINT      NOT NULL CHECK (score_vibe    BETWEEN 1 AND 5),

    -- Binary verdict ('w' or 'l')
    verdict       verdict_type  NOT NULL,

    -- Lore chips as JSONB — e.g. '["Surprise quizzes","Chill with DA"]'
    lore_chips    JSONB         DEFAULT NULL,

    -- Course the review is for (e.g. "TOC101" or "BCSE301P")
    course_code   VARCHAR(20)   DEFAULT NULL,

    -- Anti-spam
    browser_fp    VARCHAR(32)   NOT NULL,     -- FNV hash from frontend
    ip_address    VARCHAR(45)   DEFAULT NULL, -- IPv4 or IPv6
    user_agent    VARCHAR(500)  DEFAULT NULL,

    submitted_at  TIMESTAMPTZ   DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reviews_course_code ON reviews (faculty_id, course_code);

CREATE INDEX IF NOT EXISTS idx_reviews_faculty_id ON reviews (faculty_id);
CREATE INDEX IF NOT EXISTS idx_reviews_browser_fp ON reviews (browser_fp);
CREATE INDEX IF NOT EXISTS idx_reviews_lore       ON reviews USING GIN (lore_chips);


-- --- REVIEW AGGREGATES -------------------------------------------------------

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
    top_lore      JSONB         DEFAULT NULL,   -- top 5 chips
    last_reviewed TIMESTAMPTZ   DEFAULT NOW()
);


-- --- DATABASE TRIGGERS & FUNCTIONS -------------------------------------------

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
