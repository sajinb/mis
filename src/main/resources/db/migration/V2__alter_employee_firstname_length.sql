-- Migration: increase employees.first_name length to 900
-- Adjust the statement below according to your RDBMS.

-- For PostgreSQL:
ALTER TABLE employees ALTER COLUMN first_name TYPE varchar(900);

-- For MySQL (uncomment if using MySQL):
-- ALTER TABLE employees MODIFY COLUMN first_name VARCHAR(900) NOT NULL;

-- If you use Flyway, place this file under src/main/resources/db/migration and ensure the version (V2) is appropriate.
