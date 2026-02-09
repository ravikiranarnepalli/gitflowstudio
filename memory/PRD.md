# DeployFlow - Source Control & Deployment Manager

## Original Problem Statement
Build a source control application with the following features:
- When pushing to `main` branch, first create a new branch
- Button to push code to newly created branch  
- Button to merge branch into master branch
- Button to publish/deploy code to server (cPanel or FTP)
- **Git Providers**: GitHub, Bitbucket, GitLab
- **Deployment Options**: FTP and cPanel
- **Authentication**: Token-based and username/password
- **UI/UX**: Modern dashboard with "code aesthetic"

## Current Architecture
```
/app/
├── backend/
│   ├── server.py         # FastAPI with MySQL (aiomysql)
│   ├── schema.sql        # MySQL database schema
│   ├── requirements.txt
│   └── .env              # MySQL connection config
├── frontend/
│   ├── src/
│   │   ├── components/   # Shadcn/UI components
│   │   └── pages/        # Dashboard, Repositories, Operations, Deployment
│   └── package.json
└── memory/PRD.md
```

## Tech Stack
- **Backend**: FastAPI (Python), aiomysql (async MySQL), GitPython, ftplib
- **Frontend**: React, Tailwind CSS, Shadcn/UI, Lucide Icons, Sonner (toasts)
- **Database**: MySQL (user-provided remote database)

## Setup Instructions

### 1. Run the SQL Schema on Your MySQL Server
Copy the contents of `/app/backend/schema.sql` and run it on your remote MySQL database.

### 2. Configure MySQL Connection
Update `/app/backend/.env` with your MySQL credentials:
```env
MYSQL_HOST=your-mysql-host.com
MYSQL_PORT=3306
MYSQL_USER=your_username
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=deployflow
CORS_ORIGINS=*
```

### 3. Restart Backend
After updating .env, restart the backend:
```bash
sudo supervisorctl restart backend
```

## Implemented Features

### Repository Management
- Add repositories (GitHub, GitLab, Bitbucket)
- Authentication: Personal Access Token (PAT), SSH, OAuth
- Test connection before saving
- Delete repositories

### Git Operations
- **Create Branch**: Create new branch from any base branch
- **Push**: Stage, commit, and push changes to remote
- **Merge**: Merge source branch into target branch

### Deployment Configuration
- CRUD for deployment configs (FTP/cPanel)
- Project type selection: React, Angular, Vue, Next.js, Node.js, Python, Static
- FTP connection testing
- Edit and delete configurations

### Smart Deployments
- Automatic project build before deployment
- Supports: React, Angular, Vue, Next.js, Node.js, Python, Static

### NEW: Deployment Preview
- **Preview Button**: See all files that will be deployed before clicking "Deploy"
- Shows: Total files, total size, directories to create, file list with sizes
- Target server/path information
- Option to deploy directly from preview dialog

### Operations Tracking
- Full history of all Git and deployment operations
- Status tracking: pending, success, failed

## Database Schema (MySQL)

```sql
-- repositories
CREATE TABLE repositories (
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

-- deployment_configs
CREATE TABLE deployment_configs (
    id VARCHAR(36) PRIMARY KEY,
    repo_id VARCHAR(36) NOT NULL,
    deploy_type ENUM('ftp', 'cpanel') NOT NULL,
    project_type ENUM('react','angular','vue','nextjs','nodejs','python','static') DEFAULT 'static',
    host VARCHAR(255),
    username VARCHAR(255),
    password VARCHAR(500),
    remote_path VARCHAR(500) DEFAULT '/',
    use_tls BOOLEAN DEFAULT FALSE,
    api_token VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (repo_id) REFERENCES repositories(id) ON DELETE CASCADE
);

-- operations
CREATE TABLE operations (
    id VARCHAR(36) PRIMARY KEY,
    repo_id VARCHAR(36) NOT NULL,
    operation_type ENUM('create_branch','push','merge','deploy','preview') NOT NULL,
    branch_name VARCHAR(255),
    status ENUM('pending','success','failed') DEFAULT 'pending',
    message TEXT,
    file_count INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (repo_id) REFERENCES repositories(id) ON DELETE CASCADE
);
```

## API Endpoints

### Repositories
- `GET /api/repos` - List all repositories
- `POST /api/repos` - Create repository
- `GET /api/repos/{repo_id}` - Get single repository
- `DELETE /api/repos/{repo_id}` - Delete repository

### Git Operations
- `POST /api/repos/{repo_id}/create-branch` - Create new branch
- `POST /api/repos/{repo_id}/push` - Push changes
- `POST /api/repos/{repo_id}/merge` - Merge branches

### Deployment
- `GET /api/deployment-configs` - List deployment configs
- `POST /api/deployment-configs` - Create config
- `PUT /api/deployment-configs/{config_id}` - Update config
- `DELETE /api/deployment-configs/{config_id}` - Delete config
- `POST /api/repos/{repo_id}/preview-deploy` - **NEW** Preview deployment files
- `POST /api/repos/{repo_id}/deploy` - Trigger deployment

### Testing
- `POST /api/test-git-connection` - Test Git credentials
- `POST /api/test-ftp-connection` - Test FTP credentials
- `GET /api/health` - Health check

## Backlog / Future Tasks

### P1 - High Priority
- [ ] cPanel API full integration (currently placeholder)
- [ ] SSH key authentication for Git operations

### P2 - Medium Priority  
- [ ] Deployment rollback functionality
- [ ] Duplicate deployment configuration
- [ ] Connection history log

### P3 - Low Priority
- [ ] Webhook support for automatic deployments
- [ ] Multi-environment deployments (dev, staging, prod)
- [ ] Deployment scheduling

## Changelog

### Feb 9, 2026 - Database Migration & Preview Feature
- **Changed**: Migrated from MongoDB to MySQL
- **Added**: Deployment Preview feature - see all files before deploying
- **Fixed**: FTP nested directory creation bug
- **Updated**: Backend now uses aiomysql for async MySQL connections
