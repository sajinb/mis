-- Migration: change first_name column length from 150 to 100 to match UI metadata
-- MySQL/MariaDB:
ALTER TABLE employees MODIFY first_name VARCHAR(100) NOT NULL;

-- PostgreSQL (alternative, uncomment if using PostgreSQL):
-- ALTER TABLE employees ALTER COLUMN first_name TYPE VARCHAR(100);
-- If first_name is defined as NOT NULL already, the above is sufficient. Otherwise, to ensure NOT NULL:
-- ALTER TABLE employees ALTER COLUMN first_name SET NOT NULL;
