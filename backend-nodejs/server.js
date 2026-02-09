const express = require('express');
const cors = require('cors');
const mysql = require('mysql2/promise');
const { v4: uuidv4 } = require('uuid');
const simpleGit = require('simple-git');
const ftp = require('basic-ftp');
const path = require('path');
const fs = require('fs').promises;
const { execSync } = require('child_process');
const os = require('os');
require('dotenv').config();

const app = express();
const PORT = process.env.PORT || 8001;

// Middleware
app.use(cors({
  origin: process.env.CORS_ORIGINS || '*',
  credentials: true
}));
app.use(express.json());

// MySQL Connection Pool
let pool = null;

async function getPool() {
  if (!pool) {
    try {
      pool = mysql.createPool({
        host: process.env.MYSQL_HOST || 'localhost',
        port: parseInt(process.env.MYSQL_PORT) || 3306,
        user: process.env.MYSQL_USER || 'root',
        password: process.env.MYSQL_PASSWORD || '',
        database: process.env.MYSQL_DATABASE || 'deployflow',
        waitForConnections: true,
        connectionLimit: 10,
        queueLimit: 0
      });
      
      // Test connection
      const conn = await pool.getConnection();
      console.log('✅ MySQL connected successfully');
      conn.release();
    } catch (error) {
      console.error('❌ MySQL connection failed:', error.message);
      console.log('⚠️  Running without database - configure MYSQL_* in .env');
      pool = null;
    }
  }
  return pool;
}

// ============= Helper Functions =============

function getAuthUrl(url, provider, authType, authToken, authUsername) {
  if (authType === 'pat' && authToken) {
    if (url.includes('github.com')) {
      return url.replace('https://', `https://${authToken}@`);
    } else if (url.includes('gitlab.com')) {
      return url.replace('https://', `https://oauth2:${authToken}@`);
    } else if (url.includes('bitbucket.org')) {
      const username = authUsername || 'x-token-auth';
      return url.replace('https://', `https://${username}:${authToken}@`);
    }
    return url.replace('https://', `https://${authToken}@`);
  }
  return url;
}

async function buildProject(repoPath, projectType) {
  console.log(`Building ${projectType} project at ${repoPath}`);
  
  const packageJsonPath = path.join(repoPath, 'package.json');
  
  if (['react', 'vue', 'nextjs'].includes(projectType)) {
    try {
      await fs.access(packageJsonPath);
    } catch {
      throw new Error('No package.json found. Cannot build frontend project.');
    }
    
    try {
      console.log('Installing dependencies...');
      execSync('npm install --legacy-peer-deps', { cwd: repoPath, timeout: 300000, stdio: 'pipe' });
      
      console.log('Running build...');
      execSync('npm run build', { cwd: repoPath, timeout: 600000, stdio: 'pipe' });
      
      const buildDir = path.join(repoPath, 'build');
      const distDir = path.join(repoPath, 'dist');
      
      try {
        await fs.access(buildDir);
        return buildDir;
      } catch {
        try {
          await fs.access(distDir);
          return distDir;
        } catch {
          throw new Error("Build completed but output directory not found (expected 'build' or 'dist')");
        }
      }
    } catch (error) {
      if (error.message.includes('TIMEOUT')) {
        throw new Error('Build process timed out.');
      }
      throw new Error(`Build failed: ${error.message}`);
    }
  }
  
  if (projectType === 'angular') {
    try {
      await fs.access(packageJsonPath);
    } catch {
      throw new Error('No package.json found. Cannot build Angular project.');
    }
    
    try {
      console.log('Installing Angular dependencies...');
      execSync('npm install --legacy-peer-deps', { cwd: repoPath, timeout: 300000, stdio: 'pipe' });
      
      console.log('Running Angular build...');
      try {
        execSync('npx ng build --configuration=production', { cwd: repoPath, timeout: 600000, stdio: 'pipe' });
      } catch {
        execSync('npm run build', { cwd: repoPath, timeout: 600000, stdio: 'pipe' });
      }
      
      const distDir = path.join(repoPath, 'dist');
      try {
        await fs.access(distDir);
        const subdirs = await fs.readdir(distDir);
        for (const subdir of subdirs) {
          const subPath = path.join(distDir, subdir);
          const stat = await fs.stat(subPath);
          if (stat.isDirectory()) {
            return subPath;
          }
        }
        return distDir;
      } catch {
        throw new Error('Build completed but dist directory not found');
      }
    } catch (error) {
      throw new Error(`Angular build failed: ${error.message}`);
    }
  }
  
  return repoPath;
}

async function getFilesToDeploy(deployDir, projectType) {
  const excludePatterns = {
    react: ['.git', 'node_modules', 'src', 'public', 'tests', 'test', '.env', 'package.json', 'README.md'],
    angular: ['.git', 'node_modules', 'src', 'tests', '.env', 'package.json', 'angular.json', 'README.md'],
    vue: ['.git', 'node_modules', 'src', 'public', 'tests', '.env', 'package.json', 'README.md'],
    nextjs: ['.git', 'node_modules', 'pages', 'components', '.env', 'package.json', 'README.md'],
    nodejs: ['.git', 'node_modules', 'tests', '.env', 'README.md', '.gitignore'],
    python: ['.git', 'venv', '__pycache__', 'tests', '.env', 'README.md', '.gitignore'],
    static: ['.git', 'node_modules', '.env', 'README.md', '.gitignore']
  };
  
  const excludes = excludePatterns[projectType] || ['.git', 'node_modules', '.env'];
  const files = [];
  
  async function walkDir(dir, baseDir) {
    let entries;
    try {
      entries = await fs.readdir(dir, { withFileTypes: true });
    } catch {
      return;
    }
    
    for (const entry of entries) {
      if (excludes.includes(entry.name) || entry.name.startsWith('.')) continue;
      
      const fullPath = path.join(dir, entry.name);
      const relativePath = path.relative(baseDir, fullPath);
      
      if (entry.isDirectory()) {
        await walkDir(fullPath, baseDir);
      } else {
        try {
          const stat = await fs.stat(fullPath);
          files.push({
            localPath: fullPath,
            relativePath: relativePath.replace(/\\/g, '/'),
            size: stat.size
          });
        } catch {}
      }
    }
  }
  
  await walkDir(deployDir, deployDir);
  return files;
}

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

// ============= Database Helpers =============

async function createOperation(repoId, opType, branchName, status, message) {
  const id = uuidv4();
  try {
    const pool = await getPool();
    if (pool) {
      await pool.execute(
        'INSERT INTO operations (id, repo_id, operation_type, branch_name, status, message) VALUES (?, ?, ?, ?, ?, ?)',
        [id, repoId, opType, branchName, status, message]
      );
    }
  } catch (error) {
    console.error('Error creating operation:', error.message);
  }
  return id;
}

async function updateOperation(id, status, message) {
  try {
    const pool = await getPool();
    if (pool) {
      await pool.execute('UPDATE operations SET status = ?, message = ? WHERE id = ?', [status, message, id]);
    }
  } catch (error) {
    console.error('Error updating operation:', error.message);
  }
}

// ============= API Routes =============

// Health check
app.get('/api/health', (req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

// ============= Repository Routes =============

app.get('/api/repos', async (req, res) => {
  try {
    const pool = await getPool();
    if (!pool) {
      return res.json([]);
    }
    
    const [rows] = await pool.query('SELECT * FROM repositories ORDER BY created_at DESC');
    
    const repos = rows.map(row => ({
      id: row.id,
      name: row.name,
      provider: row.provider,
      url: row.url,
      auth_type: row.auth_type,
      auth_data: { token: row.auth_token || '', username: row.auth_username || '' },
      default_branch: row.default_branch,
      is_local: Boolean(row.is_local),
      created_at: row.created_at
    }));
    
    res.json(repos);
  } catch (error) {
    console.error('Error fetching repos:', error);
    res.json([]);
  }
});

app.post('/api/repos', async (req, res) => {
  try {
    const pool = await getPool();
    if (!pool) {
      return res.status(500).json({ detail: 'Database not connected' });
    }
    
    const { name, provider, url, auth_type, auth_data, default_branch, is_local } = req.body;
    const id = uuidv4();
    
    await pool.execute(
      'INSERT INTO repositories (id, name, provider, url, auth_type, auth_token, auth_username, default_branch, is_local) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
      [id, name, provider, url, auth_type, auth_data?.token || '', auth_data?.username || '', default_branch || 'main', is_local || false]
    );
    
    res.json({
      id,
      name,
      provider,
      url,
      auth_type,
      auth_data,
      default_branch: default_branch || 'main',
      is_local: is_local || false,
      created_at: new Date().toISOString()
    });
  } catch (error) {
    console.error('Error creating repo:', error);
    res.status(500).json({ detail: 'Failed to create repository' });
  }
});

app.get('/api/repos/:repoId', async (req, res) => {
  try {
    const pool = await getPool();
    if (!pool) {
      return res.status(500).json({ detail: 'Database not connected' });
    }
    
    const [rows] = await pool.query('SELECT * FROM repositories WHERE id = ?', [req.params.repoId]);
    if (rows.length === 0) {
      return res.status(404).json({ detail: 'Repository not found' });
    }
    
    const row = rows[0];
    res.json({
      id: row.id,
      name: row.name,
      provider: row.provider,
      url: row.url,
      auth_type: row.auth_type,
      auth_data: { token: row.auth_token || '', username: row.auth_username || '' },
      default_branch: row.default_branch,
      is_local: Boolean(row.is_local),
      created_at: row.created_at
    });
  } catch (error) {
    console.error('Error fetching repo:', error);
    res.status(500).json({ detail: 'Failed to fetch repository' });
  }
});

app.delete('/api/repos/:repoId', async (req, res) => {
  try {
    const pool = await getPool();
    if (!pool) {
      return res.status(500).json({ detail: 'Database not connected' });
    }
    
    const [result] = await pool.execute('DELETE FROM repositories WHERE id = ?', [req.params.repoId]);
    if (result.affectedRows === 0) {
      return res.status(404).json({ detail: 'Repository not found' });
    }
    res.json({ message: 'Repository deleted successfully' });
  } catch (error) {
    console.error('Error deleting repo:', error);
    res.status(500).json({ detail: 'Failed to delete repository' });
  }
});

// ============= Git Operations Routes =============

app.get('/api/operations', async (req, res) => {
  try {
    const pool = await getPool();
    if (!pool) {
      return res.json([]);
    }
    
    const { repo_id } = req.query;
    let query = 'SELECT * FROM operations ORDER BY created_at DESC LIMIT 100';
    let params = [];
    
    if (repo_id) {
      query = 'SELECT * FROM operations WHERE repo_id = ? ORDER BY created_at DESC LIMIT 100';
      params = [repo_id];
    }
    
    const [rows] = await pool.query(query, params);
    res.json(rows);
  } catch (error) {
    console.error('Error fetching operations:', error);
    res.json([]);
  }
});

// Helper to get repo data
async function getRepoData(repoId) {
  const pool = await getPool();
  if (!pool) {
    throw new Error('Database not connected');
  }
  
  const [rows] = await pool.query('SELECT * FROM repositories WHERE id = ?', [repoId]);
  if (rows.length === 0) {
    throw new Error('Repository not found');
  }
  return rows[0];
}

app.post('/api/repos/:repoId/create-branch', async (req, res) => {
  const { repoId } = req.params;
  const { branch_name, base_branch } = req.body;
  
  let opId;
  try {
    const repo = await getRepoData(repoId);
    opId = await createOperation(repoId, 'create_branch', branch_name, 'pending', `Creating branch ${branch_name}`);
    
    const tmpDir = path.join(os.tmpdir(), `repo-${uuidv4()}`);
    const authUrl = getAuthUrl(repo.url, repo.provider, repo.auth_type, repo.auth_token, repo.auth_username);
    
    const git = simpleGit();
    await git.clone(authUrl, tmpDir, ['--depth', '1']);
    
    const repoGit = simpleGit(tmpDir);
    await repoGit.checkoutLocalBranch(branch_name);
    await repoGit.push('origin', branch_name, ['--set-upstream']);
    
    await updateOperation(opId, 'success', `Branch ${branch_name} created successfully`);
    
    // Cleanup
    await fs.rm(tmpDir, { recursive: true, force: true });
    
    res.json({
      success: true,
      message: `Branch ${branch_name} created successfully`,
      operation_id: opId
    });
  } catch (error) {
    if (opId) await updateOperation(opId, 'failed', error.message);
    console.error('Error creating branch:', error);
    res.status(400).json({ detail: error.message });
  }
});

app.post('/api/repos/:repoId/push', async (req, res) => {
  const { repoId } = req.params;
  const { branch_name, commit_message } = req.body;
  
  let opId;
  try {
    const repo = await getRepoData(repoId);
    opId = await createOperation(repoId, 'push', branch_name, 'pending', `Pushing to ${branch_name}`);
    
    const tmpDir = path.join(os.tmpdir(), `repo-${uuidv4()}`);
    const authUrl = getAuthUrl(repo.url, repo.provider, repo.auth_type, repo.auth_token, repo.auth_username);
    
    const git = simpleGit();
    await git.clone(authUrl, tmpDir);
    
    const repoGit = simpleGit(tmpDir);
    await repoGit.checkout(branch_name);
    await repoGit.add('.');
    
    try {
      await repoGit.commit(commit_message || 'Auto commit');
    } catch (e) {
      // No changes to commit
    }
    
    await repoGit.push('origin', branch_name);
    
    await fs.rm(tmpDir, { recursive: true, force: true });
    await updateOperation(opId, 'success', `Pushed to ${branch_name} successfully`);
    
    res.json({
      success: true,
      message: `Pushed to ${branch_name} successfully`,
      operation_id: opId
    });
  } catch (error) {
    if (opId) await updateOperation(opId, 'failed', error.message);
    console.error('Error pushing:', error);
    res.status(400).json({ detail: error.message });
  }
});

app.post('/api/repos/:repoId/merge', async (req, res) => {
  const { repoId } = req.params;
  const { source_branch, target_branch } = req.body;
  
  let opId;
  try {
    const repo = await getRepoData(repoId);
    opId = await createOperation(repoId, 'merge', `${source_branch} -> ${target_branch}`, 'pending', `Merging ${source_branch} into ${target_branch}`);
    
    const tmpDir = path.join(os.tmpdir(), `repo-${uuidv4()}`);
    const authUrl = getAuthUrl(repo.url, repo.provider, repo.auth_type, repo.auth_token, repo.auth_username);
    
    const git = simpleGit();
    await git.clone(authUrl, tmpDir);
    
    const repoGit = simpleGit(tmpDir);
    await repoGit.checkout(target_branch || 'main');
    await repoGit.merge([source_branch]);
    await repoGit.push('origin', target_branch || 'main');
    
    await fs.rm(tmpDir, { recursive: true, force: true });
    await updateOperation(opId, 'success', `Merged ${source_branch} into ${target_branch} successfully`);
    
    res.json({
      success: true,
      message: `Merged ${source_branch} into ${target_branch} successfully`,
      operation_id: opId
    });
  } catch (error) {
    if (opId) await updateOperation(opId, 'failed', error.message);
    console.error('Error merging:', error);
    res.status(400).json({ detail: error.message });
  }
});

// ============= Deployment Config Routes =============

app.get('/api/deployment-configs', async (req, res) => {
  try {
    const pool = await getPool();
    if (!pool) {
      return res.json([]);
    }
    
    const { repo_id } = req.query;
    let query = 'SELECT * FROM deployment_configs ORDER BY created_at DESC';
    let params = [];
    
    if (repo_id) {
      query = 'SELECT * FROM deployment_configs WHERE repo_id = ? ORDER BY created_at DESC';
      params = [repo_id];
    }
    
    const [rows] = await pool.query(query, params);
    
    const configs = rows.map(row => ({
      id: row.id,
      repo_id: row.repo_id,
      deploy_type: row.deploy_type,
      project_type: row.project_type,
      config: {
        host: row.host,
        username: row.username,
        password: row.password,
        path: row.remote_path,
        use_tls: Boolean(row.use_tls),
        api_token: row.api_token
      },
      created_at: row.created_at
    }));
    
    res.json(configs);
  } catch (error) {
    console.error('Error fetching deployment configs:', error);
    res.json([]);
  }
});

app.post('/api/deployment-configs', async (req, res) => {
  try {
    const pool = await getPool();
    if (!pool) {
      return res.status(500).json({ detail: 'Database not connected' });
    }
    
    const { repo_id, deploy_type, project_type, config } = req.body;
    const id = uuidv4();
    
    await pool.execute(
      'INSERT INTO deployment_configs (id, repo_id, deploy_type, project_type, host, username, password, remote_path, use_tls, api_token) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
      [id, repo_id, deploy_type, project_type || 'static', config.host, config.username, config.password, config.path || '/', config.use_tls || false, config.api_token || '']
    );
    
    res.json({
      id,
      repo_id,
      deploy_type,
      project_type: project_type || 'static',
      config,
      created_at: new Date().toISOString()
    });
  } catch (error) {
    console.error('Error creating deployment config:', error);
    res.status(500).json({ detail: 'Failed to create deployment config' });
  }
});

app.put('/api/deployment-configs/:configId', async (req, res) => {
  try {
    const pool = await getPool();
    if (!pool) {
      return res.status(500).json({ detail: 'Database not connected' });
    }
    
    const { configId } = req.params;
    const { repo_id, deploy_type, project_type, config } = req.body;
    
    const [existing] = await pool.query('SELECT * FROM deployment_configs WHERE id = ?', [configId]);
    if (existing.length === 0) {
      return res.status(404).json({ detail: 'Deployment config not found' });
    }
    
    await pool.execute(
      'UPDATE deployment_configs SET repo_id = ?, deploy_type = ?, project_type = ?, host = ?, username = ?, password = ?, remote_path = ?, use_tls = ?, api_token = ? WHERE id = ?',
      [repo_id, deploy_type, project_type || 'static', config.host, config.username, config.password, config.path || '/', config.use_tls || false, config.api_token || '', configId]
    );
    
    res.json({
      id: configId,
      repo_id,
      deploy_type,
      project_type: project_type || 'static',
      config,
      created_at: existing[0].created_at
    });
  } catch (error) {
    console.error('Error updating deployment config:', error);
    res.status(500).json({ detail: 'Failed to update deployment config' });
  }
});

app.delete('/api/deployment-configs/:configId', async (req, res) => {
  try {
    const pool = await getPool();
    if (!pool) {
      return res.status(500).json({ detail: 'Database not connected' });
    }
    
    const [result] = await pool.execute('DELETE FROM deployment_configs WHERE id = ?', [req.params.configId]);
    if (result.affectedRows === 0) {
      return res.status(404).json({ detail: 'Deployment config not found' });
    }
    res.json({ message: 'Deployment config deleted successfully' });
  } catch (error) {
    console.error('Error deleting deployment config:', error);
    res.status(500).json({ detail: 'Failed to delete deployment config' });
  }
});

// ============= Deployment Preview Route =============

app.post('/api/repos/:repoId/preview-deploy', async (req, res) => {
  const { repoId } = req.params;
  
  try {
    const repo = await getRepoData(repoId);
    
    const pool = await getPool();
    const [configs] = await pool.query('SELECT * FROM deployment_configs WHERE repo_id = ?', [repoId]);
    if (configs.length === 0) {
      return res.status(404).json({ detail: 'Deployment config not found for this repository' });
    }
    
    const deployConfig = configs[0];
    
    // Clone repository to temp directory
    const tmpDir = path.join(os.tmpdir(), `preview-${uuidv4()}`);
    const authUrl = getAuthUrl(repo.url, repo.provider, repo.auth_type, repo.auth_token, repo.auth_username);
    
    console.log('Cloning repository for preview...');
    const git = simpleGit();
    await git.clone(authUrl, tmpDir, ['--depth', '1']);
    
    // Build project if needed
    const projectType = deployConfig.project_type || 'static';
    let deployDir = tmpDir;
    
    if (['react', 'angular', 'vue', 'nextjs'].includes(projectType)) {
      console.log(`Building ${projectType} project...`);
      deployDir = await buildProject(tmpDir, projectType);
    }
    
    // Get files to deploy
    const files = await getFilesToDeploy(deployDir, projectType);
    
    // Calculate totals
    const totalSize = files.reduce((sum, f) => sum + f.size, 0);
    const directories = [...new Set(files.map(f => path.dirname(f.relativePath)).filter(d => d !== '.'))].sort();
    
    // Cleanup temp directory
    await fs.rm(tmpDir, { recursive: true, force: true });
    
    res.json({
      success: true,
      preview: {
        total_files: files.length,
        total_size: formatSize(totalSize),
        total_size_bytes: totalSize,
        project_type: projectType,
        deploy_type: deployConfig.deploy_type,
        target_host: deployConfig.host,
        target_path: deployConfig.remote_path,
        directories: directories,
        files: files.map(f => ({
          path: f.relativePath,
          size: formatSize(f.size),
          size_bytes: f.size
        })).sort((a, b) => a.path.localeCompare(b.path))
      }
    });
  } catch (error) {
    console.error('Preview error:', error);
    res.status(400).json({ detail: `Preview failed: ${error.message}` });
  }
});

// ============= Deploy Route =============

app.post('/api/repos/:repoId/deploy', async (req, res) => {
  const { repoId } = req.params;
  const { branch_name } = req.body;
  
  let opId;
  try {
    const repo = await getRepoData(repoId);
    
    const pool = await getPool();
    const [configs] = await pool.query('SELECT * FROM deployment_configs WHERE repo_id = ?', [repoId]);
    if (configs.length === 0) {
      return res.status(404).json({ detail: 'Deployment config not found for this repository' });
    }
    
    const deployConfig = configs[0];
    opId = await createOperation(repoId, 'deploy', branch_name, 'pending', `Deploying to ${deployConfig.deploy_type}`);
    
    // Clone repository
    const tmpDir = path.join(os.tmpdir(), `deploy-${uuidv4()}`);
    const authUrl = getAuthUrl(repo.url, repo.provider, repo.auth_type, repo.auth_token, repo.auth_username);
    
    console.log('Cloning repository...');
    const git = simpleGit();
    await git.clone(authUrl, tmpDir, ['--depth', '1']);
    
    if (branch_name) {
      const repoGit = simpleGit(tmpDir);
      await repoGit.checkout(branch_name);
    }
    
    // Build project
    const projectType = deployConfig.project_type || 'static';
    let deployDir = tmpDir;
    
    if (['react', 'angular', 'vue', 'nextjs'].includes(projectType)) {
      console.log(`Building ${projectType} project...`);
      deployDir = await buildProject(tmpDir, projectType);
    }
    
    // Get files
    const files = await getFilesToDeploy(deployDir, projectType);
    
    if (files.length === 0) {
      throw new Error('No files found to deploy after build');
    }
    
    // FTP Deployment
    if (deployConfig.deploy_type === 'ftp') {
      const client = new ftp.Client();
      client.ftp.verbose = false;
      
      try {
        await client.access({
          host: deployConfig.host,
          user: deployConfig.username,
          password: deployConfig.password,
          secure: Boolean(deployConfig.use_tls)
        });
        
        const remotePath = deployConfig.remote_path || '/';
        await client.ensureDir(remotePath);
        
        let uploadedCount = 0;
        const failedFiles = [];
        const createdDirs = new Set();
        
        for (const file of files) {
          try {
            const remoteDir = path.dirname(file.relativePath);
            
            if (remoteDir && remoteDir !== '.') {
              const fullRemoteDir = path.posix.join(remotePath, remoteDir);
              
              if (!createdDirs.has(fullRemoteDir)) {
                await client.ensureDir(fullRemoteDir);
                createdDirs.add(fullRemoteDir);
              }
              await client.cd(fullRemoteDir);
            } else {
              await client.cd(remotePath);
            }
            
            await client.uploadFrom(file.localPath, path.basename(file.relativePath));
            uploadedCount++;
          } catch (fileError) {
            console.warn(`Failed to upload ${file.relativePath}:`, fileError.message);
            failedFiles.push(file.relativePath);
          }
        }
        
        client.close();
        
        let message = `Deployed ${uploadedCount}/${files.length} files successfully`;
        if (failedFiles.length > 0) {
          message += ` (${failedFiles.length} files failed)`;
        }
        
        await updateOperation(opId, 'success', message);
        
        // Cleanup
        await fs.rm(tmpDir, { recursive: true, force: true });
        
        res.json({
          success: true,
          message,
          operation_id: opId,
          details: {
            uploaded: uploadedCount,
            total: files.length,
            failed: failedFiles.length,
            project_type: projectType
          }
        });
      } catch (ftpError) {
        client.close();
        throw new Error(`FTP deployment failed: ${ftpError.message}`);
      }
    } else if (deployConfig.deploy_type === 'cpanel') {
      // cPanel placeholder
      const message = `cPanel deployment initiated for ${deployConfig.host} (Full cPanel integration coming soon)`;
      await updateOperation(opId, 'success', message);
      await fs.rm(tmpDir, { recursive: true, force: true });
      
      res.json({
        success: true,
        message,
        operation_id: opId
      });
    } else {
      throw new Error(`Unknown deployment type: ${deployConfig.deploy_type}`);
    }
  } catch (error) {
    if (opId) await updateOperation(opId, 'failed', error.message);
    console.error('Error deploying:', error);
    res.status(400).json({ detail: error.message });
  }
});

// ============= Test Connection Routes =============

app.post('/api/test-git-connection', async (req, res) => {
  const { provider, url, auth_type, auth_data } = req.body;
  
  try {
    const tmpDir = path.join(os.tmpdir(), `test-${uuidv4()}`);
    const authUrl = getAuthUrl(url, provider, auth_type, auth_data?.token, auth_data?.username);
    
    const git = simpleGit();
    await git.clone(authUrl, tmpDir, ['--depth', '1']);
    
    await fs.rm(tmpDir, { recursive: true, force: true });
    
    res.json({
      success: true,
      message: 'Successfully connected to repository! Authentication verified.'
    });
  } catch (error) {
    let message = 'Connection test failed';
    const errorStr = error.message.toLowerCase();
    
    if (errorStr.includes('authentication') || errorStr.includes('could not read')) {
      message = 'Authentication failed. Please verify your access token or credentials.';
    } else if (errorStr.includes('not found')) {
      message = 'Repository not found. Check the URL and your access permissions.';
    } else if (errorStr.includes('resolve host')) {
      message = 'Could not connect to Git server. Please verify the repository URL.';
    }
    
    res.json({ success: false, message });
  }
});

app.post('/api/test-ftp-connection', async (req, res) => {
  const { host, username, password, use_tls } = req.body;
  
  const client = new ftp.Client();
  
  try {
    await client.access({
      host,
      user: username,
      password,
      secure: use_tls || false
    });
    
    client.close();
    res.json({
      success: true,
      message: 'Successfully connected to FTP server!'
    });
  } catch (error) {
    client.close();
    let message = `FTP connection test failed: ${error.message}`;
    
    if (error.message.includes('530') || error.message.toLowerCase().includes('auth')) {
      message = 'Authentication failed. Please verify your username and password.';
    } else if (error.message.includes('timeout')) {
      message = 'Connection timed out. Please verify the host address.';
    }
    
    res.json({ success: false, message });
  }
});

// Start server
app.listen(PORT, '0.0.0.0', async () => {
  console.log(`🚀 DeployFlow Node.js API running on http://0.0.0.0:${PORT}`);
  await getPool(); // Initialize database connection
});
