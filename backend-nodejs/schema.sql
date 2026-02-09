-- DeployFlow MySQL Schema
-- Run this on your MySQL server to create the required tables

-- Create database (optional - use your existing database)
CREATE DATABASE IF NOT EXISTS deployflow;
USE deployflow;

-- Repositories table
CREATE TABLE IF NOT EXISTS repositories (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    provider ENUM('github', 'gitlab', 'bitbucket') NOT NULL,
    url VARCHAR(500) NOT NULL,
    auth_type ENUM('pat', 'ssh', 'oauth') NOT NULL,
    auth_token VARCHAR(500),
    auth_username VARCHAR(255),
    default_branch VARCHAR(100) DEFAULT 'main',
    is_local BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Deployment configurations table
CREATE TABLE IF NOT EXISTS deployment_configs (
    id VARCHAR(36) PRIMARY KEY,
    repo_id VARCHAR(36) NOT NULL,
    deploy_type ENUM('ftp', 'cpanel') NOT NULL,
    project_type ENUM('react', 'angular', 'vue', 'nextjs', 'nodejs', 'python', 'static') DEFAULT 'static',
    host VARCHAR(255),
    username VARCHAR(255),
    password VARCHAR(500),
    remote_path VARCHAR(500) DEFAULT '/',
    use_tls BOOLEAN DEFAULT FALSE,
    api_token VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (repo_id) REFERENCES repositories(id) ON DELETE CASCADE
);

-- Operations/history table
CREATE TABLE IF NOT EXISTS operations (
    id VARCHAR(36) PRIMARY KEY,
    repo_id VARCHAR(36) NOT NULL,
    operation_type ENUM('create_branch', 'push', 'merge', 'deploy', 'preview') NOT NULL,
    branch_name VARCHAR(255),
    status ENUM('pending', 'success', 'failed') DEFAULT 'pending',
    message TEXT,
    file_count INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (repo_id) REFERENCES repositories(id) ON DELETE CASCADE
);

-- Indexes for better performance
CREATE INDEX idx_operations_repo ON operations(repo_id);
CREATE INDEX idx_operations_created ON operations(created_at DESC);
CREATE INDEX idx_deployment_configs_repo ON deployment_configs(repo_id);
