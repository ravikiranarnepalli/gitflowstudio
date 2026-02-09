# DeployFlow - Source Control & Deployment Manager

## Original Problem Statement
Build a source control application with:
- Create branch, push, merge functionality
- Deploy to FTP/cPanel servers
- Support for GitHub, GitLab, Bitbucket
- Modern dashboard with "code aesthetic"

## Architecture

### Currently Active: Python Backend (with MongoDB)
```
/app/backend/
├── server.py         # FastAPI + MongoDB (ACTIVE)
├── requirements.txt
└── .env
```

### Alternative: Node.js Backend (with MySQL) - READY TO USE
```
/app/backend-nodejs/
├── server.js         # Express + MySQL
├── schema.sql        # MySQL schema to run on your server
├── package.json
├── .env              # MySQL config (needs your credentials)
└── README.md
```

## How to Switch to Node.js + MySQL Backend

1. **Run the SQL schema** on your MySQL server:
   ```bash
   cat /app/backend-nodejs/schema.sql
   # Copy and run on your MySQL server
   ```

2. **Update MySQL credentials** in `/app/backend-nodejs/.env`:
   ```env
   MYSQL_HOST=your-host.com
   MYSQL_PORT=3306
   MYSQL_USER=your_user
   MYSQL_PASSWORD=your_password
   MYSQL_DATABASE=deployflow
   ```

3. **Update supervisor** to run Node.js (requires manual config change)

## Implemented Features

### Repository Management
- Add repositories (GitHub, GitLab, Bitbucket)
- PAT/SSH/OAuth authentication
- Test connection before saving

### Git Operations
- Create Branch
- Push
- Merge

### Deployment
- FTP deployment with TLS support
- Smart builds: React, Angular, Vue, Next.js, Node.js, Python, Static
- **NEW: Deployment Preview** - See all files before deploying

### Operations Tracking
- Full history with status indicators

## Tech Stack

| Component | Python Backend | Node.js Backend |
|-----------|---------------|-----------------|
| Framework | FastAPI | Express.js |
| Database | MongoDB | MySQL |
| Git | GitPython | simple-git |
| FTP | ftplib | basic-ftp |

## API Endpoints

- `GET /api/repos` - List repositories
- `POST /api/repos` - Create repository
- `DELETE /api/repos/:id` - Delete repository
- `POST /api/repos/:id/create-branch` - Create branch
- `POST /api/repos/:id/push` - Push changes
- `POST /api/repos/:id/merge` - Merge branches
- `GET /api/deployment-configs` - List configs
- `POST /api/deployment-configs` - Create config
- `PUT /api/deployment-configs/:id` - Update config
- `POST /api/repos/:id/preview-deploy` - **Preview files**
- `POST /api/repos/:id/deploy` - Deploy

## Changelog

### Feb 9, 2026
- Added **Deployment Preview** feature
- Created separate **Node.js + MySQL backend** at `/app/backend-nodejs/`
- Fixed FTP nested directory creation bug
- Python backend continues using MongoDB (working)

## Backlog

- [ ] Full cPanel API integration
- [ ] SSH key authentication
- [ ] Deployment rollback
- [ ] Multi-environment deployments
