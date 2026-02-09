# Smart Deployment Guide

## How It Works

SourceCtrl automatically builds and deploys your projects based on the project type you select.

## Deployment Flow

```
1. Clone Repository → 2. Checkout Branch → 3. Build Project → 4. Filter Files → 5. Upload to Server
```

## Project Types & Build Process

### React (build → deploy build/)
- **Build Command**: `npm install` → `npm run build`
- **Deploy**: Only files from `build/` folder
- **Excludes**: `node_modules`, `src`, `public`, `tests`, `.env`, `package.json`
- **Build Time**: 2-5 minutes (depending on project size)

### Angular (build → deploy dist/)
- **Build Command**: `npm install` → `npx ng build --configuration=production`
- **Fallback**: `npm run build` if ng command fails
- **Deploy**: Only files from `dist/[project-name]` folder
- **Excludes**: `node_modules`, `src`, `tests`, `.env`, `angular.json`
- **Build Time**: 3-7 minutes (Angular builds are slower)

### Vue.js (build → deploy dist/)
- **Build Command**: `npm install` → `npm run build`
- **Deploy**: Only files from `dist/` folder
- **Excludes**: `node_modules`, `src`, `public`, `tests`, `.env`
- **Build Time**: 2-4 minutes

### Next.js (build → deploy .next/)
- **Build Command**: `npm install` → `npm run build`
- **Deploy**: Only files from `.next/` folder
- **Excludes**: `node_modules`, `pages`, `components`, `.env`
- **Build Time**: 3-6 minutes

### Node.js (exclude node_modules)
- **Build Command**: `npm install --production` (if build script exists)
- **Deploy**: Source code files
- **Excludes**: `node_modules`, `tests`, `.env`, `README.md`
- **No Build**: Deploys source directly unless build script exists

### Python (exclude venv)
- **Build Command**: None
- **Deploy**: Source code files
- **Excludes**: `venv`, `__pycache__`, `*.pyc`, `tests`, `.env`
- **No Build**: Deploys source directly

### Static HTML/CSS/JS
- **Build Command**: None
- **Deploy**: All files as-is
- **Excludes**: `.git`, `node_modules`, `.env`
- **No Build**: Deploys everything directly

## Common Build Errors & Solutions

### Error: "Build failed: npm not found"
**Cause**: Node.js/npm not installed on deployment server
**Solution**: This error means the server needs Node.js. Contact your hosting provider or install Node.js on the deployment server.

### Error: "Dependency installation failed"
**Cause**: npm install failed (package conflicts, network issues)
**Solution**: 
1. Check your `package.json` for invalid dependencies
2. Ensure your Git repository has a valid `package.json`
3. Try building locally first: `npm install && npm run build`

### Error: "Build process timed out"
**Cause**: Build took longer than 10 minutes
**Solution**:
1. Your project might be too large
2. Check for infinite loops in build scripts
3. Consider optimizing your build process
4. For very large projects, consider building locally and deploying the build folder directly

### Error: "Build completed but output directory not found"
**Cause**: Build succeeded but created output in unexpected location
**Solution**:
1. For React: Ensure build creates `build/` or `dist/` folder
2. For Angular: Check `angular.json` output path configuration
3. For Vue: Check `vue.config.js` output directory
4. Verify build script in `package.json` creates the expected output

### Error: "Angular build failed: ng not found"
**Fixed**: We now use `npx ng build` which works without global Angular CLI

### Error: "No package.json found"
**Cause**: Repository doesn't contain package.json file
**Solution**:
1. Ensure you selected the correct repository
2. Check if package.json exists in your Git repository
3. If deploying a subdirectory, ensure the root has package.json

## Build Process Details

### What Happens During Build:

1. **Clone Repository** (10-30 seconds)
   - Downloads your code from Git
   - Checks out the specified branch

2. **Install Dependencies** (1-3 minutes)
   - Runs `npm install --legacy-peer-deps`
   - Downloads all required packages
   - May show peer dependency warnings (normal)

3. **Run Build** (2-7 minutes)
   - Executes your build script
   - Compiles/transpiles code
   - Optimizes for production
   - Creates build output folder

4. **Filter Files** (5-10 seconds)
   - Identifies only necessary files
   - Excludes development files
   - Prepares deployment package

5. **Upload to Server** (30 seconds - 3 minutes)
   - Creates directory structure on FTP
   - Uploads files one by one
   - Shows progress: "Deployed X/Y files"

### Total Time Estimates:
- **React**: 4-8 minutes
- **Angular**: 6-12 minutes
- **Vue**: 4-7 minutes
- **Node.js**: 2-4 minutes (if build exists)
- **Static**: 1-2 minutes (no build)

## Deployment Tips

### Before Deploying:
1. ✓ Test build locally: `npm install && npm run build`
2. ✓ Ensure build creates output folder (build/ or dist/)
3. ✓ Check FTP credentials with "Test Connection"
4. ✓ Select correct project type
5. ✓ Have valid Git credentials configured

### After Deployment:
1. Check Operations page for deployment status
2. Look for "Deployed X/Y files successfully" message
3. If failures, check which files failed to upload
4. Verify website works by visiting your domain

### Optimization:
- **React**: Use `.env.production` for production settings
- **Angular**: Ensure `--configuration=production` builds
- **Vue**: Check `vue.config.js` production settings
- **All**: Use environment variables, don't commit `.env` files

## Troubleshooting Workflow

```
1. Check Operations page → See error message
2. If "Build failed" → Check if project builds locally
3. If "Authentication failed" → Test Git credentials
4. If "FTP failed" → Test FTP connection
5. If "Timed out" → Project too large or stuck
6. Still failing? → Check backend logs for details
```

## FTP Upload Details

### Directory Structure:
The deployment maintains your project structure:
```
Remote Server:
/path/
  ├── index.html
  ├── assets/
  │   ├── css/
  │   └── js/
  └── images/
```

### What Gets Uploaded:
- ✓ HTML files
- ✓ CSS files
- ✓ JavaScript files
- ✓ Images, fonts, assets
- ✓ Configuration files (except .env)
- ✗ node_modules (never uploaded)
- ✗ Source files (src/, pages/, etc.)
- ✗ Test files
- ✗ Development configs

## Need Help?

1. **Check Operations page** for detailed error messages
2. **Review backend logs** at `/var/log/supervisor/backend.err.log`
3. **Test locally** by running build commands manually
4. **Verify credentials** using test connection features
5. **Check Git repository** has correct structure and files

## Advanced: Custom Build Commands

If your project uses custom build commands not supported by default:

1. **Workaround**: Change project type to "Node.js" or "Static"
2. **Build locally**, commit the build folder
3. **Deploy** the pre-built files directly
4. **Or** modify your package.json to have a standard "build" script

Example package.json:
```json
{
  "scripts": {
    "build": "your-custom-build-command"
  }
}
```
