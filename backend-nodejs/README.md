# DeployFlow - Node.js Backend

A complete Node.js backend for the DeployFlow source control and deployment management application.

## Tech Stack
- **Express.js** - Web framework
- **mysql2** - MySQL database driver (with promises)
- **simple-git** - Git operations
- **basic-ftp** - FTP deployments
- **uuid** - Unique ID generation

## Setup

### 1. Install Dependencies
```bash
cd /app/backend-nodejs
yarn install
```

### 2. Configure MySQL Database

First, run the schema on your MySQL server:
```sql
-- Copy contents from schema.sql and run on your MySQL server
```

Then update `.env` with your credentials:
```env
MYSQL_HOST=your-mysql-host.com
MYSQL_PORT=3306
MYSQL_USER=your_username
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=deployflow
PORT=8001
CORS_ORIGINS=*
```

### 3. Run the Server

**Development (with auto-reload):**
```bash
yarn dev
```

**Production:**
```bash
yarn start
```

## API Endpoints

### Health Check
- `GET /api/health` - Server health check

### Repositories
- `GET /api/repos` - List all repositories
- `POST /api/repos` - Create a repository
- `GET /api/repos/:repoId` - Get single repository
- `DELETE /api/repos/:repoId` - Delete repository

### Git Operations
- `POST /api/repos/:repoId/create-branch` - Create new branch
- `POST /api/repos/:repoId/push` - Push changes
- `POST /api/repos/:repoId/merge` - Merge branches
- `GET /api/operations` - List all operations

### Deployment
- `GET /api/deployment-configs` - List deployment configs
- `POST /api/deployment-configs` - Create deployment config
- `PUT /api/deployment-configs/:configId` - Update deployment config
- `DELETE /api/deployment-configs/:configId` - Delete deployment config
- `POST /api/repos/:repoId/preview-deploy` - Preview files before deployment
- `POST /api/repos/:repoId/deploy` - Execute deployment

### Connection Testing
- `POST /api/test-git-connection` - Test Git repository connection
- `POST /api/test-ftp-connection` - Test FTP server connection

## Features

### Smart Deployments
Automatically builds projects before deployment:
- **React/Vue/Next.js**: `npm install && npm run build` → deploys `build/` or `dist/`
- **Angular**: `npm install && npx ng build` → deploys `dist/project-name/`
- **Node.js**: Deploys source code (excludes node_modules)
- **Python**: Deploys source code (excludes venv)
- **Static**: Deploys as-is

### Deployment Preview
Preview all files that will be uploaded before deploying:
- Total file count and size
- Directory structure
- Individual file list with sizes

## File Structure
```
/app/backend-nodejs/
├── server.js        # Main Express server with all routes
├── package.json     # Dependencies
├── schema.sql       # MySQL database schema
├── .env             # Configuration (create from template)
└── README.md        # This file
```
