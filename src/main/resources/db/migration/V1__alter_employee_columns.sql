-- Flyway migration: adjust employee column sizes to match UI
-- 1) first_name: increase length from 100 to 150
-- 2) email: set length to 254
-- 3) salary: set precision 12 scale 2

ALTER TABLE employees
    ALTER COLUMN first_name TYPE varchar(150);

-- For email: if column already exists and type supports length, alter; otherwise set to varchar(254)
ALTER TABLE employees
    ALTER COLUMN email TYPE varchar(254);

-- For salary, adjust numeric precision/scale
ALTER TABLE employees
    ALTER COLUMN salary TYPE numeric(12,2);

-- Optional: ensure position length is at least 200 (no-op if already large enough)
ALTER TABLE employees
    ALTER COLUMN position TYPE varchar(200);

-- Add a comment about migration
COMMENT ON TABLE employees IS 'Adjusted columns to align with UI constraints (first_name 150, email 254, salary numeric(12,2), position 200)';
