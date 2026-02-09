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

## Architecture
```
/app/
├── backend/
│   ├── server.py         # FastAPI - all routes and business logic
│   ├── requirements.txt
│   └── .env
├── frontend/
│   ├── src/
│   │   ├── components/   # Shadcn/UI components
│   │   └── pages/        # Dashboard, Repositories, Operations, Deployment
│   └── package.json
└── memory/PRD.md
```

## Tech Stack
- **Backend**: FastAPI, Motor (async MongoDB), GitPython, Paramiko (SSH), ftplib
- **Frontend**: React, Tailwind CSS, Shadcn/UI, Lucide Icons, Sonner (toasts)
- **Database**: MongoDB

## Implemented Features (✅ Complete)

### Repository Management
- Add repositories (GitHub, GitLab, Bitbucket)
- Authentication: Personal Access Token (PAT), SSH, OAuth
- Test connection before saving
- Delete repositories

### Git Operations
- **Create Branch**: Create new branch from any base branch
- **Push**: Stage, commit, and push changes to remote
- **Merge**: Merge source branch into target branch with conflict detection

### Deployment Configuration
- CRUD for deployment configs (FTP/cPanel)
- Project type selection: React, Angular, Vue, Next.js, Node.js, Python, Static
- FTP connection testing
- Edit and delete configurations

### Smart Deployments (✅ Fixed Feb 9, 2026)
- Automatic project build before deployment:
  - React/Vue: `npm install && npm run build` → deploy `build/` or `dist/`
  - Angular: `npm install && npx ng build` → deploy `dist/project-name/`
  - Node.js: Optional build, exclude node_modules
  - Python: Deploy source, exclude venv
  - Static: Deploy as-is
- **FTP nested directory creation** - Fixed bug where subdirectories weren't being created

### Operations Tracking
- Full history of all Git and deployment operations
- Status tracking: pending, success, failed
- Detailed error messages

## Bug Fixes Log

### Feb 9, 2026 - FTP Directory Creation Bug
**Issue**: Angular deployments were failing to upload files in nested directories (e.g., `browser/media/`, `browser/contact-us/`)
**Root Cause**: The `ensure_remote_dir` function wasn't properly creating nested FTP directories
**Fix**: Rewrote the directory creation logic to:
1. Track already-created directories to avoid redundant operations
2. Properly navigate from base path when creating subdirectories
3. Stay in target directory after creation for immediate file upload
**Result**: 92/92 files now upload successfully (was 77/92)

## Backlog / Future Tasks

### P1 - High Priority
- [ ] cPanel API integration (currently placeholder)
- [ ] SSH key authentication for Git operations

### P2 - Medium Priority
- [ ] Deployment rollback functionality
- [ ] Duplicate deployment configuration
- [ ] Connection history log
- [ ] Refactor server.py into modules (routes/, models/, services/)

### P3 - Low Priority
- [ ] Webhook support for automatic deployments
- [ ] Multi-environment deployments (dev, staging, prod)
- [ ] Deployment scheduling

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
- `POST /api/repos/{repo_id}/deploy` - Trigger deployment

### Testing
- `POST /api/test-git-connection` - Test Git credentials
- `POST /api/test-ftp-connection` - Test FTP credentials

## Database Schema

### repositories
```json
{
  "id": "uuid",
  "name": "string",
  "provider": "github|gitlab|bitbucket",
  "url": "string",
  "auth_type": "pat|ssh|oauth",
  "auth_data": { "token": "string", "username": "string" },
  "default_branch": "string",
  "is_local": "boolean",
  "created_at": "datetime"
}
```

### deployment_configs
```json
{
  "id": "uuid",
  "repo_id": "string",
  "deploy_type": "ftp|cpanel",
  "project_type": "react|angular|vue|nextjs|nodejs|python|static",
  "config": {
    "host": "string",
    "username": "string",
    "password": "string",
    "path": "string",
    "use_tls": "boolean"
  },
  "created_at": "datetime"
}
```

### operations
```json
{
  "id": "uuid",
  "repo_id": "string",
  "operation_type": "create_branch|push|merge|deploy",
  "branch_name": "string",
  "status": "pending|success|failed",
  "message": "string",
  "created_at": "datetime"
}
```
