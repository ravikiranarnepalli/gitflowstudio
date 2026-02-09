# Error Handling & Test Connection Guide

## Overview

SourceCtrl now includes comprehensive error handling and test connection features to help you validate credentials before saving configurations.

## Test Connection Features

### 1. Git Repository Test Connection

**Location**: Repositories → Add Repository → Test Connection button

**What it tests**:
- Repository accessibility
- Authentication credentials (PAT, SSH keys)
- Repository existence and permissions
- Network connectivity to Git provider

**How to use**:
1. Fill in repository details (URL, Provider, Authentication)
2. Click "Test Connection" button
3. Wait for validation (usually 3-10 seconds)
4. Review the result message

**Common Error Messages**:

| Error Message | Cause | Solution |
|--------------|-------|----------|
| "Authentication failed" | Invalid access token or credentials | Regenerate your PAT/token and try again |
| "Repository not found" | Wrong URL or no access permissions | Verify the repository URL and your access rights |
| "Could not connect to Git server" | Network/DNS issue | Check the repository URL for typos |
| "Successfully connected!" | ✓ All good | Proceed to add the repository |

### 2. FTP Connection Test

**Location**: Deployment → Add Deployment → Test FTP Connection button

**What it tests**:
- FTP server connectivity
- Username and password authentication
- TLS/SSL connection (if enabled)
- Server responsiveness

**How to use**:
1. Fill in FTP credentials (Host, Username, Password)
2. Click "Test FTP Connection" button
3. Wait for validation (usually 2-5 seconds)
4. Review the result message

**Common Error Messages**:

| Error Message | Cause | Solution |
|--------------|-------|----------|
| "Authentication failed" | Wrong username or password | Verify your FTP credentials |
| "Connection timed out" | Wrong host or firewall blocking | Check the FTP host address |
| "Successfully connected!" | ✓ All good | Proceed to save the configuration |

## Enhanced Error Handling

### Git Operations Error Messages

#### Create Branch Errors
- **"Authentication failed. Please check your credentials"**
  - Your access token may have expired
  - Regenerate a new token from your Git provider
  
- **"Branch already exists"**
  - The branch name you chose is already in use
  - Choose a different branch name

#### Push Errors
- **"Branch does not exist. Please create it first"**
  - You're trying to push to a non-existent branch
  - Create the branch first or check the branch name

- **"Push failed. Please check your credentials"**
  - Authentication issue during push
  - Verify your access token has write permissions

#### Merge Errors
- **"Target branch does not exist"**
  - The branch you're merging into doesn't exist
  - Verify the target branch name (usually 'main' or 'master')

- **"Merge conflict detected. Please resolve conflicts manually"**
  - Your branches have conflicting changes
  - Use Git client to resolve conflicts manually

- **"Source branch not found or cannot be merged"**
  - The source branch doesn't exist
  - Verify the source branch name

### Deployment Errors
- **"Deployment config not found for this repository"**
  - No deployment configuration set up
  - Go to Deployment page and add a configuration first

- **"Deployment failed. Please check your configuration"**
  - FTP credentials or cPanel settings are incorrect
  - Use Test Connection before saving

## Best Practices

### Before Adding a Repository
1. ✓ **Always test the connection first**
2. ✓ Ensure your access token has required permissions:
   - GitHub: `repo`, `workflow`
   - GitLab: `api`, `write_repository`
   - Bitbucket: Repository Read, Write
3. ✓ Verify the repository URL format
4. ✓ Check that the default branch name is correct

### Before Configuring Deployment
1. ✓ **Always test FTP connection first**
2. ✓ Verify FTP credentials with your hosting provider
3. ✓ Confirm the remote path is correct
4. ✓ Enable TLS/SSL if your server supports it

### During Git Operations
1. ✓ Create descriptive branch names
2. ✓ Verify branch exists before pushing
3. ✓ Check for conflicts before merging
4. ✓ Monitor the Operations page for real-time status

## Troubleshooting Tips

### Git Authentication Issues
**Problem**: Test connection fails with authentication error

**Solutions**:
1. Regenerate your Personal Access Token
2. Ensure token hasn't expired
3. Verify token has correct scopes/permissions
4. For GitHub: Use `https://github.com/user/repo.git` format
5. For GitLab: Use `https://gitlab.com/user/repo.git` format

### FTP Connection Issues
**Problem**: FTP test fails with timeout

**Solutions**:
1. Verify FTP host address (usually `ftp.yourdomain.com`)
2. Check if your IP needs to be whitelisted
3. Try with and without TLS/SSL
4. Contact your hosting provider for correct FTP details

### Operation Failures
**Problem**: Git operations succeed in test but fail during actual execution

**Solutions**:
1. Check Operations page for detailed error messages
2. Verify network connectivity
3. Ensure you have latest repository state
4. Try the operation again (temporary network issues)

## Error Message Reference

### Success Messages
- ✓ "Successfully connected to repository! Authentication verified."
- ✓ "Branch [name] created successfully"
- ✓ "Pushed to [branch] successfully"
- ✓ "Merged [source] into [target] successfully"
- ✓ "Deployed successfully to [ftp/cpanel]"

### Warning Messages
- ⚠ "No changes to commit"
- ⚠ "Branch already up to date"

### Error Messages
- ✗ "Authentication failed"
- ✗ "Repository not found"
- ✗ "Branch does not exist"
- ✗ "Merge conflict detected"
- ✗ "Deployment failed"

## Getting Help

If you encounter an error not listed here:
1. Check the **Operations** page for full error details
2. Verify your credentials and network connection
3. Review the browser console for additional information
4. Check the backend logs at `/var/log/supervisor/backend.err.log`

## Quick Reference

### Test Before Save
| Feature | Test Button Location |
|---------|---------------------|
| Repository | Add Repository dialog |
| FTP Deployment | Add Deployment dialog (FTP only) |

### Required Permissions
| Provider | Token Scopes |
|----------|-------------|
| GitHub | `repo`, `workflow` |
| GitLab | `api`, `write_repository` |
| Bitbucket | Repository Read, Write |

### Common Branch Names
- `main` (modern default)
- `master` (legacy default)
- `develop` (development branch)
- `feature/*` (feature branches)
- `fix/*` (bug fix branches)
