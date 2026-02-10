-- Flyway migration: increase first_name length to 700 to match UI metadata
-- This migration updates the employees.first_name column length

ALTER TABLE employees
    ALTER COLUMN first_name TYPE varchar(700);

-- Add a comment explaining the change
COMMENT ON COLUMN employees.first_name IS 'Increased length to 700 to match UI metadata';
