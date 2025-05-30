-- PostgreSQL initialization script for Yumi Sugoi Discord Bot
-- This script sets up the database schema and initial data

-- Create database if it doesn't exist (handled by docker-compose)
-- CREATE DATABASE IF NOT EXISTS yumi_bot;

-- Use the database
\c yumi_bot;

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Create indexes for better performance
-- Note: SQLAlchemy will create the tables, but we can add additional indexes here

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create a trigger function for automatic updated_at
CREATE OR REPLACE FUNCTION create_updated_at_trigger(table_name text)
RETURNS void AS $$
BEGIN
    EXECUTE format('CREATE TRIGGER update_%I_updated_at BEFORE UPDATE ON %I FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()', table_name, table_name);
END;
$$ language 'plpgsql';

-- Create initial admin user (will be populated by the application)
-- This is just a placeholder for future use

-- Set up proper permissions
GRANT ALL PRIVILEGES ON DATABASE yumi_bot TO yumi;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO yumi;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO yumi;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO yumi;

-- Create indexes that will be useful for the application
-- These will be created after SQLAlchemy creates the tables

-- Performance optimization settings
ALTER DATABASE yumi_bot SET log_statement = 'none';
ALTER DATABASE yumi_bot SET log_min_duration_statement = 1000;

-- Success message
\echo 'Database initialization completed successfully!'
