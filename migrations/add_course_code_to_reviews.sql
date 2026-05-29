-- ─── MIGRATION: Add course_code column to reviews ────────────────────────────
-- Run this once in your Supabase SQL Editor.
-- Go to: Supabase Dashboard → SQL Editor → New Query → Paste → Run

-- 1. Add the column (safe to run even if reviews table already has data)
ALTER TABLE reviews
  ADD COLUMN IF NOT EXISTS course_code VARCHAR(20) DEFAULT NULL;

-- 2. Add an index so per-course queries are fast
CREATE INDEX IF NOT EXISTS idx_reviews_course_code
  ON reviews (faculty_id, course_code);

-- 3. Backfill: pull course codes out of lore_chips for existing reviews.
--    The app stored them as "Course: <code>" at index 0 of the lore_chips array.
UPDATE reviews
SET    course_code = REPLACE(lore_chips->>0, 'Course: ', '')
WHERE  course_code IS NULL
  AND  lore_chips IS NOT NULL
  AND  lore_chips->>0 LIKE 'Course: %';

-- Done! Verify:
-- SELECT id, faculty_id, course_code, lore_chips FROM reviews LIMIT 20;
