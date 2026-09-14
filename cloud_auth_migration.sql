-- Non-destructive cloud migration for family and admin login support.
-- Run this in Supabase SQL Editor AFTER the existing cloud data is loaded.
-- Do NOT rerun backend_pg.sql for this migration because it drops tables.

ALTER TABLE users
ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255);

ALTER TABLE users
ADD COLUMN IF NOT EXISTS search_alias VARCHAR(200);
