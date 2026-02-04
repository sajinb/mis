-- Flyway migration: create employees table to match UI metadata
CREATE TABLE IF NOT EXISTS employees (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  first_name VARCHAR(500) NOT NULL,
  last_name VARCHAR(150) NOT NULL,
  email VARCHAR(254) NOT NULL UNIQUE,
  position VARCHAR(200),
  salary DECIMAL(12,2),
  hired_date DATE
);
