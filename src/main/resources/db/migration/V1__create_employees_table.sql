-- Flyway migration: create employees table
CREATE TABLE IF NOT EXISTS employees (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  first_name VARCHAR(800) NOT NULL,
  last_name VARCHAR(150) NOT NULL,
  project_name VARCHAR(500),
  email VARCHAR(255) NOT NULL,
  position VARCHAR(200),
  salary DECIMAL(15,2),
  hired_date DATE
);
