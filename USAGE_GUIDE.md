# SourceCtrl - Git Flow Manager

A modern Git source control management application with deployment capabilities.

## Features

### 🔄 Git Operations
- **Create Branch**: Create new branches from main/master
- **Push to Branch**: Push your changes to remote branches
- **Merge Branches**: Merge branches to main/master automatically
- **Multi-Provider Support**: GitHub, GitLab, and Bitbucket

### 🚀 Deployment
- **FTP Deployment**: Deploy to any FTP/FTPS server
- **cPanel Deployment**: Deploy to cPanel hosting
- **One-Click Deploy**: Deploy with a single click

### 🔐 Authentication
- **Personal Access Token (PAT)**: Use tokens for GitHub, GitLab, Bitbucket
- **SSH Keys**: Use SSH authentication (coming soon)
- **OAuth**: OAuth integration support (coming soon)

### 📊 Operations Tracking
- Real-time operation status
- Complete operation history
- Success/failure indicators

## Getting Started

### 1. Add a Repository

1. Navigate to **Repositories** page
2. Click **Add Repository** button
3. Fill in the details:
   - **Repository Name**: Your project name
   - **Provider**: Select GitHub, GitLab, or Bitbucket
   - **Repository URL**: Git clone URL (e.g., https://github.com/user/repo.git)
   - **Authentication Type**: Select PAT, SSH, or OAuth
   - **Access Token**: Your personal access token
   - **Default Branch**: main or master
   - **Is Local**: Check if this is the /app codebase

### 2. Create a Branch

1. Go to **Repositories** page
2. Find your repository
3. Click **Branch** button
4. Enter branch name (e.g., feature/new-feature)
5. Optionally specify base branch
6. Click **Execute**

### 3. Push Changes

1. Go to **Repositories** page
2. Find your repository
3. Click **Push** button
4. Enter branch name
5. Add commit message
6. Click **Execute**

### 4. Merge Branches

1. Go to **Repositories** page
2. Find your repository
3. Click **Merge** button (green)
4. Enter source branch (e.g., feature/new-feature)
5. Enter target branch (e.g., main)
6. Click **Execute**

### 5. Configure Deployment

1. Navigate to **Deployment** page
2. Click **Add Deployment**
3. Select your repository
4. Choose deployment type:
   
   **For FTP:**
   - FTP Host: ftp.example.com
   - Username: your-username
   - Password: your-password
   - Remote Path: /public_html
   - Use TLS: Check if needed

   **For cPanel:**
   - cPanel Host: cpanel.example.com
   - Username: your-username
   - API Token: your-api-token

4. Click **Save Configuration**

### 6. Deploy

1. Go to **Deployment** page
2. Find your deployment config
3. Click **Deploy Now**
4. Check **Operations** page for deployment status

## Getting Git Credentials

### GitHub Personal Access Token
1. Go to GitHub Settings > Developer settings > Personal access tokens
2. Click "Generate new token (classic)"
3. Select scopes: `repo`, `workflow`
4. Copy the generated token

### GitLab Personal Access Token
1. Go to GitLab Profile > Access Tokens
2. Create a new token
3. Select scopes: `api`, `write_repository`
4. Copy the token

### Bitbucket App Password
1. Go to Bitbucket Settings > App passwords
2. Create new app password
3. Select permissions: Repository Read, Write
4. Copy the password

## Operations Page

Track all your Git operations:
- **CREATE BRANCH**: Branch creation status
- **PUSH**: Push operation status
- **MERGE**: Merge operation status
- **DEPLOY**: Deployment status

Status indicators:
- 🟢 **success**: Operation completed successfully
- 🟡 **pending**: Operation in progress
- 🔴 **failed**: Operation failed (check message for details)

## Tips

1. **Test with a test repository first** before using production repos
2. **Keep your tokens secure** - they're stored in the database
3. **Check Operations page** after each action to verify success
4. **Use descriptive branch names** (e.g., feature/add-login, fix/bug-123)
5. **Always review merge operations** before executing

## Architecture

- **Backend**: FastAPI + MongoDB + GitPython
- **Frontend**: React + Tailwind CSS + Shadcn/UI
- **Design**: "The Void Terminal" - Dark cyberpunk aesthetic

## Support

For issues or questions, check the Operations log for detailed error messages.
