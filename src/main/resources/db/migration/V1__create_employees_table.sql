-- Migration: create employees table
-- Generated to match frontend UI metadata

CREATE TABLE IF NOT EXISTS employees (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  first_name VARCHAR(900) NOT NULL,
  last_name VARCHAR(150) NOT NULL,
  email VARCHAR(254) NOT NULL UNIQUE,
  position VARCHAR(200),
  salary DECIMAL(12,2),
  hired_date DATE
);
