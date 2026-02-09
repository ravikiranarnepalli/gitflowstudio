from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
import aiomysql
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone
import git
import shutil
import tempfile
from ftplib import FTP, FTP_TLS
import subprocess
import json

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Create the main app
app = FastAPI()
api_router = APIRouter(prefix="/api")

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# MySQL connection pool
pool = None

async def get_pool():
    global pool
    if pool is None:
        try:
            pool = await aiomysql.create_pool(
                host=os.environ.get('MYSQL_HOST', 'localhost'),
                port=int(os.environ.get('MYSQL_PORT', 3306)),
                user=os.environ.get('MYSQL_USER', 'root'),
                password=os.environ.get('MYSQL_PASSWORD', ''),
                db=os.environ.get('MYSQL_DATABASE', 'deployflow'),
                autocommit=True,
                minsize=1,
                maxsize=10
            )
            logger.info("✅ MySQL connected successfully")
        except Exception as e:
            logger.error(f"❌ MySQL connection failed: {e}")
            logger.warning("⚠️  Running without database - configure MYSQL_* in .env")
    return pool

# ============= Models =============

class RepositoryCreate(BaseModel):
    name: str
    provider: str
    url: str
    auth_type: str
    auth_data: Dict[str, Any]
    default_branch: str = "main"
    is_local: bool = False

class BranchCreateRequest(BaseModel):
    branch_name: str
    base_branch: Optional[str] = None

class PushRequest(BaseModel):
    branch_name: str
    commit_message: Optional[str] = "Auto commit"

class MergeRequest(BaseModel):
    source_branch: str
    target_branch: str = "main"

class DeploymentConfigCreate(BaseModel):
    repo_id: str
    deploy_type: str
    project_type: str = "static"
    config: Dict[str, Any]

class DeployRequest(BaseModel):
    branch_name: Optional[str] = None

class TestConnectionRequest(BaseModel):
    provider: str
    url: str
    auth_type: str
    auth_data: Dict[str, Any]

class TestFTPRequest(BaseModel):
    host: str
    username: str
    password: str
    use_tls: bool = False

# ============= Helper Functions =============

def get_auth_url(url: str, provider: str, auth_type: str, auth_data: dict) -> str:
    if auth_type == 'pat':
        token = auth_data.get('token')
        if not token:
            raise ValueError("Access token is required")
        if 'github.com' in url:
            return url.replace('https://', f'https://{token}@')
        elif 'gitlab.com' in url:
            return url.replace('https://', f'https://oauth2:{token}@')
        elif 'bitbucket.org' in url:
            username = auth_data.get('username', 'x-token-auth')
            return url.replace('https://', f'https://{username}:{token}@')
        return url.replace('https://', f'https://{token}@')
    return url

def build_project(repo_path: str, project_type: str) -> str:
    logger.info(f"Building {project_type} project at {repo_path}")
    
    if project_type in ['react', 'vue', 'nextjs']:
        package_json = os.path.join(repo_path, 'package.json')
        if not os.path.exists(package_json):
            raise ValueError("No package.json found.")
        
        try:
            logger.info("Installing dependencies...")
            subprocess.run(['npm', 'install', '--legacy-peer-deps'], cwd=repo_path, capture_output=True, timeout=300)
            
            logger.info("Running build...")
            result = subprocess.run(['npm', 'run', 'build'], cwd=repo_path, capture_output=True, text=True, timeout=600)
            
            if result.returncode != 0:
                raise ValueError(f"Build failed: {result.stderr[:300]}")
            
            for dir_name in ['build', 'dist']:
                dir_path = os.path.join(repo_path, dir_name)
                if os.path.exists(dir_path):
                    return dir_path
            raise ValueError("Build output directory not found")
        except subprocess.TimeoutExpired:
            raise ValueError("Build timed out")
    
    elif project_type == 'angular':
        package_json = os.path.join(repo_path, 'package.json')
        if not os.path.exists(package_json):
            raise ValueError("No package.json found.")
        
        try:
            logger.info("Installing Angular dependencies...")
            subprocess.run(['npm', 'install', '--legacy-peer-deps'], cwd=repo_path, capture_output=True, timeout=300)
            
            logger.info("Running Angular build...")
            result = subprocess.run(['npx', 'ng', 'build', '--configuration=production'], cwd=repo_path, capture_output=True, text=True, timeout=600)
            
            if result.returncode != 0:
                result = subprocess.run(['npm', 'run', 'build'], cwd=repo_path, capture_output=True, text=True, timeout=600)
                if result.returncode != 0:
                    raise ValueError(f"Angular build failed: {result.stderr[:300]}")
            
            dist_dir = os.path.join(repo_path, 'dist')
            if os.path.exists(dist_dir):
                subdirs = [d for d in os.listdir(dist_dir) if os.path.isdir(os.path.join(dist_dir, d))]
                if subdirs:
                    return os.path.join(dist_dir, subdirs[0])
                return dist_dir
            raise ValueError("dist directory not found")
        except subprocess.TimeoutExpired:
            raise ValueError("Build timed out")
    
    return repo_path

def get_files_to_deploy(deploy_dir: str, project_type: str):
    exclude_patterns = {
        'react': ['.git', 'node_modules', 'src', 'public', 'tests', '.env', 'package.json', 'README.md'],
        'angular': ['.git', 'node_modules', 'src', 'tests', '.env', 'package.json', 'angular.json', 'README.md'],
        'vue': ['.git', 'node_modules', 'src', 'public', 'tests', '.env', 'package.json', 'README.md'],
        'nextjs': ['.git', 'node_modules', 'pages', 'components', '.env', 'package.json', 'README.md'],
        'nodejs': ['.git', 'node_modules', 'tests', '.env', 'README.md'],
        'python': ['.git', 'venv', '__pycache__', 'tests', '.env', 'README.md'],
        'static': ['.git', 'node_modules', '.env', 'README.md']
    }
    
    excludes = exclude_patterns.get(project_type, ['.git', 'node_modules', '.env'])
    files = []
    
    for root, dirs, filenames in os.walk(deploy_dir):
        dirs[:] = [d for d in dirs if d not in excludes and not d.startswith('.')]
        
        for filename in filenames:
            if filename in excludes or filename.startswith('.'):
                continue
            
            local_path = os.path.join(root, filename)
            relative_path = os.path.relpath(local_path, deploy_dir)
            file_size = os.path.getsize(local_path)
            files.append({
                'local_path': local_path,
                'relative_path': relative_path.replace(os.sep, '/'),
                'size': file_size
            })
    
    return files

def format_size(bytes_size):
    if bytes_size < 1024:
        return f"{bytes_size} B"
    elif bytes_size < 1024 * 1024:
        return f"{bytes_size / 1024:.1f} KB"
    return f"{bytes_size / (1024 * 1024):.2f} MB"

# ============= Repository Endpoints =============

@api_router.get("/repos")
async def get_repositories():
    try:
        pool = await get_pool()
        if not pool:
            return []
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute("SELECT * FROM repositories ORDER BY created_at DESC")
                rows = await cur.fetchall()
                return [{
                    'id': r['id'],
                    'name': r['name'],
                    'provider': r['provider'],
                    'url': r['url'],
                    'auth_type': r['auth_type'],
                    'auth_data': {'token': r['auth_token'] or '', 'username': r['auth_username'] or ''},
                    'default_branch': r['default_branch'],
                    'is_local': bool(r['is_local']),
                    'created_at': r['created_at'].isoformat() if r['created_at'] else None
                } for r in rows]
    except Exception as e:
        logger.error(f"Error fetching repos: {e}")
        return []

@api_router.post("/repos")
async def create_repository(repo: RepositoryCreate):
    try:
        pool = await get_pool()
        if not pool:
            raise HTTPException(status_code=500, detail="Database not connected")
        
        repo_id = str(uuid.uuid4())
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "INSERT INTO repositories (id, name, provider, url, auth_type, auth_token, auth_username, default_branch, is_local) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (repo_id, repo.name, repo.provider, repo.url, repo.auth_type, repo.auth_data.get('token', ''), repo.auth_data.get('username', ''), repo.default_branch, repo.is_local)
                )
        
        return {
            'id': repo_id,
            'name': repo.name,
            'provider': repo.provider,
            'url': repo.url,
            'auth_type': repo.auth_type,
            'auth_data': repo.auth_data,
            'default_branch': repo.default_branch,
            'is_local': repo.is_local,
            'created_at': datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Error creating repo: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/repos/{repo_id}")
async def get_repository(repo_id: str):
    try:
        pool = await get_pool()
        if not pool:
            raise HTTPException(status_code=500, detail="Database not connected")
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute("SELECT * FROM repositories WHERE id = %s", (repo_id,))
                r = await cur.fetchone()
                if not r:
                    raise HTTPException(status_code=404, detail="Repository not found")
                return {
                    'id': r['id'],
                    'name': r['name'],
                    'provider': r['provider'],
                    'url': r['url'],
                    'auth_type': r['auth_type'],
                    'auth_data': {'token': r['auth_token'] or '', 'username': r['auth_username'] or ''},
                    'default_branch': r['default_branch'],
                    'is_local': bool(r['is_local']),
                    'created_at': r['created_at'].isoformat() if r['created_at'] else None
                }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching repo: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.delete("/repos/{repo_id}")
async def delete_repository(repo_id: str):
    try:
        pool = await get_pool()
        if not pool:
            raise HTTPException(status_code=500, detail="Database not connected")
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("DELETE FROM repositories WHERE id = %s", (repo_id,))
                if cur.rowcount == 0:
                    raise HTTPException(status_code=404, detail="Repository not found")
        return {"message": "Repository deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting repo: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============= Operations Endpoints =============

@api_router.get("/operations")
async def get_operations(repo_id: Optional[str] = None):
    try:
        pool = await get_pool()
        if not pool:
            return []
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                if repo_id:
                    await cur.execute("SELECT * FROM operations WHERE repo_id = %s ORDER BY created_at DESC LIMIT 100", (repo_id,))
                else:
                    await cur.execute("SELECT * FROM operations ORDER BY created_at DESC LIMIT 100")
                rows = await cur.fetchall()
                return [{
                    'id': r['id'],
                    'repo_id': r['repo_id'],
                    'operation_type': r['operation_type'],
                    'branch_name': r['branch_name'],
                    'status': r['status'],
                    'message': r['message'],
                    'created_at': r['created_at'].isoformat() if r['created_at'] else None
                } for r in rows]
    except Exception as e:
        logger.error(f"Error fetching operations: {e}")
        return []

async def create_operation(repo_id: str, op_type: str, branch_name: str, status: str, message: str) -> str:
    op_id = str(uuid.uuid4())
    try:
        pool = await get_pool()
        if pool:
            async with pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "INSERT INTO operations (id, repo_id, operation_type, branch_name, status, message) VALUES (%s, %s, %s, %s, %s, %s)",
                        (op_id, repo_id, op_type, branch_name, status, message)
                    )
    except Exception as e:
        logger.error(f"Error creating operation: {e}")
    return op_id

async def update_operation(op_id: str, status: str, message: str):
    try:
        pool = await get_pool()
        if pool:
            async with pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("UPDATE operations SET status = %s, message = %s WHERE id = %s", (status, message, op_id))
    except Exception as e:
        logger.error(f"Error updating operation: {e}")

# ============= Git Operations =============

async def get_repo_data(repo_id: str):
    pool = await get_pool()
    if not pool:
        raise HTTPException(status_code=500, detail="Database not connected")
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT * FROM repositories WHERE id = %s", (repo_id,))
            repo = await cur.fetchone()
            if not repo:
                raise HTTPException(status_code=404, detail="Repository not found")
            return repo

@api_router.post("/repos/{repo_id}/create-branch")
async def create_branch(repo_id: str, request: BranchCreateRequest):
    repo = await get_repo_data(repo_id)
    op_id = await create_operation(repo_id, 'create_branch', request.branch_name, 'pending', f'Creating branch {request.branch_name}')
    
    try:
        temp_dir = tempfile.mkdtemp()
        auth_url = get_auth_url(repo['url'], repo['provider'], repo['auth_type'], {'token': repo['auth_token'], 'username': repo['auth_username']})
        
        git_repo = git.Repo.clone_from(auth_url, temp_dir, depth=1)
        base_branch = request.base_branch or repo['default_branch'] or 'main'
        
        new_branch = git_repo.create_head(request.branch_name)
        new_branch.checkout()
        git_repo.remote('origin').push(request.branch_name, set_upstream=True)
        
        shutil.rmtree(temp_dir, ignore_errors=True)
        await update_operation(op_id, 'success', f'Branch {request.branch_name} created successfully')
        
        return {"success": True, "message": f"Branch {request.branch_name} created successfully", "operation_id": op_id}
    except Exception as e:
        await update_operation(op_id, 'failed', str(e))
        raise HTTPException(status_code=400, detail=str(e))

@api_router.post("/repos/{repo_id}/push")
async def push_to_branch(repo_id: str, request: PushRequest):
    repo = await get_repo_data(repo_id)
    op_id = await create_operation(repo_id, 'push', request.branch_name, 'pending', f'Pushing to {request.branch_name}')
    
    try:
        temp_dir = tempfile.mkdtemp()
        auth_url = get_auth_url(repo['url'], repo['provider'], repo['auth_type'], {'token': repo['auth_token'], 'username': repo['auth_username']})
        
        git_repo = git.Repo.clone_from(auth_url, temp_dir)
        git_repo.git.checkout(request.branch_name)
        git_repo.git.add(A=True)
        
        if git_repo.is_dirty() or git_repo.untracked_files:
            git_repo.index.commit(request.commit_message)
        
        git_repo.remote('origin').push(request.branch_name)
        
        shutil.rmtree(temp_dir, ignore_errors=True)
        await update_operation(op_id, 'success', f'Pushed to {request.branch_name} successfully')
        
        return {"success": True, "message": f"Pushed to {request.branch_name} successfully", "operation_id": op_id}
    except Exception as e:
        await update_operation(op_id, 'failed', str(e))
        raise HTTPException(status_code=400, detail=str(e))

@api_router.post("/repos/{repo_id}/merge")
async def merge_branches(repo_id: str, request: MergeRequest):
    repo = await get_repo_data(repo_id)
    op_id = await create_operation(repo_id, 'merge', f'{request.source_branch} -> {request.target_branch}', 'pending', f'Merging {request.source_branch} into {request.target_branch}')
    
    try:
        temp_dir = tempfile.mkdtemp()
        auth_url = get_auth_url(repo['url'], repo['provider'], repo['auth_type'], {'token': repo['auth_token'], 'username': repo['auth_username']})
        
        git_repo = git.Repo.clone_from(auth_url, temp_dir)
        git_repo.git.checkout(request.target_branch)
        git_repo.git.merge(request.source_branch)
        git_repo.remote('origin').push(request.target_branch)
        
        shutil.rmtree(temp_dir, ignore_errors=True)
        await update_operation(op_id, 'success', f'Merged {request.source_branch} into {request.target_branch} successfully')
        
        return {"success": True, "message": f"Merged {request.source_branch} into {request.target_branch} successfully", "operation_id": op_id}
    except Exception as e:
        await update_operation(op_id, 'failed', str(e))
        raise HTTPException(status_code=400, detail=str(e))

# ============= Deployment Config Endpoints =============

@api_router.get("/deployment-configs")
async def get_deployment_configs(repo_id: Optional[str] = None):
    try:
        pool = await get_pool()
        if not pool:
            return []
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                if repo_id:
                    await cur.execute("SELECT * FROM deployment_configs WHERE repo_id = %s ORDER BY created_at DESC", (repo_id,))
                else:
                    await cur.execute("SELECT * FROM deployment_configs ORDER BY created_at DESC")
                rows = await cur.fetchall()
                return [{
                    'id': r['id'],
                    'repo_id': r['repo_id'],
                    'deploy_type': r['deploy_type'],
                    'project_type': r['project_type'],
                    'config': {
                        'host': r['host'],
                        'username': r['username'],
                        'password': r['password'],
                        'path': r['remote_path'],
                        'use_tls': bool(r['use_tls']),
                        'api_token': r['api_token']
                    },
                    'created_at': r['created_at'].isoformat() if r['created_at'] else None
                } for r in rows]
    except Exception as e:
        logger.error(f"Error fetching deployment configs: {e}")
        return []

@api_router.post("/deployment-configs")
async def create_deployment_config(config: DeploymentConfigCreate):
    try:
        pool = await get_pool()
        if not pool:
            raise HTTPException(status_code=500, detail="Database not connected")
        
        config_id = str(uuid.uuid4())
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "INSERT INTO deployment_configs (id, repo_id, deploy_type, project_type, host, username, password, remote_path, use_tls, api_token) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (config_id, config.repo_id, config.deploy_type, config.project_type, config.config.get('host'), config.config.get('username'), config.config.get('password'), config.config.get('path', '/'), config.config.get('use_tls', False), config.config.get('api_token', ''))
                )
        
        return {
            'id': config_id,
            'repo_id': config.repo_id,
            'deploy_type': config.deploy_type,
            'project_type': config.project_type,
            'config': config.config,
            'created_at': datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Error creating deployment config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.put("/deployment-configs/{config_id}")
async def update_deployment_config(config_id: str, config: DeploymentConfigCreate):
    try:
        pool = await get_pool()
        if not pool:
            raise HTTPException(status_code=500, detail="Database not connected")
        
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "UPDATE deployment_configs SET repo_id = %s, deploy_type = %s, project_type = %s, host = %s, username = %s, password = %s, remote_path = %s, use_tls = %s, api_token = %s WHERE id = %s",
                    (config.repo_id, config.deploy_type, config.project_type, config.config.get('host'), config.config.get('username'), config.config.get('password'), config.config.get('path', '/'), config.config.get('use_tls', False), config.config.get('api_token', ''), config_id)
                )
                if cur.rowcount == 0:
                    raise HTTPException(status_code=404, detail="Deployment config not found")
        
        return {
            'id': config_id,
            'repo_id': config.repo_id,
            'deploy_type': config.deploy_type,
            'project_type': config.project_type,
            'config': config.config
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating deployment config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.delete("/deployment-configs/{config_id}")
async def delete_deployment_config(config_id: str):
    try:
        pool = await get_pool()
        if not pool:
            raise HTTPException(status_code=500, detail="Database not connected")
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("DELETE FROM deployment_configs WHERE id = %s", (config_id,))
                if cur.rowcount == 0:
                    raise HTTPException(status_code=404, detail="Deployment config not found")
        return {"message": "Deployment config deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting deployment config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============= Deployment Preview (NEW) =============

@api_router.post("/repos/{repo_id}/preview-deploy")
async def preview_deployment(repo_id: str):
    """Preview files that will be deployed before actual deployment"""
    repo = await get_repo_data(repo_id)
    
    pool = await get_pool()
    if not pool:
        raise HTTPException(status_code=500, detail="Database not connected")
    
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT * FROM deployment_configs WHERE repo_id = %s", (repo_id,))
            deploy_config = await cur.fetchone()
            if not deploy_config:
                raise HTTPException(status_code=404, detail="Deployment config not found for this repository")
    
    try:
        temp_dir = tempfile.mkdtemp()
        auth_url = get_auth_url(repo['url'], repo['provider'], repo['auth_type'], {'token': repo['auth_token'], 'username': repo['auth_username']})
        
        logger.info("Cloning repository for preview...")
        git.Repo.clone_from(auth_url, temp_dir, depth=1)
        
        project_type = deploy_config['project_type'] or 'static'
        deploy_dir = temp_dir
        
        # Build project if needed
        if project_type in ['react', 'angular', 'vue', 'nextjs']:
            logger.info(f"Building {project_type} project...")
            deploy_dir = build_project(temp_dir, project_type)
        
        # Get files to deploy
        files = get_files_to_deploy(deploy_dir, project_type)
        
        # Calculate totals
        total_size = sum(f['size'] for f in files)
        directories = sorted(set(os.path.dirname(f['relative_path']) for f in files if os.path.dirname(f['relative_path'])))
        
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)
        
        return {
            "success": True,
            "preview": {
                "total_files": len(files),
                "total_size": format_size(total_size),
                "total_size_bytes": total_size,
                "project_type": project_type,
                "deploy_type": deploy_config['deploy_type'],
                "target_host": deploy_config['host'],
                "target_path": deploy_config['remote_path'],
                "directories": directories,
                "files": sorted([{
                    "path": f['relative_path'],
                    "size": format_size(f['size']),
                    "size_bytes": f['size']
                } for f in files], key=lambda x: x['path'])
            }
        }
    except Exception as e:
        logger.error(f"Preview error: {e}")
        raise HTTPException(status_code=400, detail=f"Preview failed: {str(e)}")

# ============= Deploy =============

@api_router.post("/repos/{repo_id}/deploy")
async def deploy_repository(repo_id: str, request: DeployRequest):
    repo = await get_repo_data(repo_id)
    
    pool = await get_pool()
    if not pool:
        raise HTTPException(status_code=500, detail="Database not connected")
    
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT * FROM deployment_configs WHERE repo_id = %s", (repo_id,))
            deploy_config = await cur.fetchone()
            if not deploy_config:
                raise HTTPException(status_code=404, detail="Deployment config not found")
    
    op_id = await create_operation(repo_id, 'deploy', request.branch_name, 'pending', f'Deploying to {deploy_config["deploy_type"]}')
    
    try:
        temp_dir = tempfile.mkdtemp()
        auth_url = get_auth_url(repo['url'], repo['provider'], repo['auth_type'], {'token': repo['auth_token'], 'username': repo['auth_username']})
        
        logger.info("Cloning repository...")
        git_repo = git.Repo.clone_from(auth_url, temp_dir, depth=1)
        
        if request.branch_name:
            git_repo.git.checkout(request.branch_name)
        
        project_type = deploy_config['project_type'] or 'static'
        deploy_dir = temp_dir
        
        # Build project if needed
        if project_type in ['react', 'angular', 'vue', 'nextjs']:
            logger.info(f"Building {project_type} project...")
            deploy_dir = build_project(temp_dir, project_type)
        
        # Get files
        files = get_files_to_deploy(deploy_dir, project_type)
        if not files:
            raise ValueError("No files found to deploy")
        
        # FTP Deployment
        if deploy_config['deploy_type'] == 'ftp':
            if deploy_config['use_tls']:
                ftp = FTP_TLS(deploy_config['host'], timeout=30)
            else:
                ftp = FTP(deploy_config['host'], timeout=30)
            
            ftp.login(deploy_config['username'], deploy_config['password'])
            
            remote_path = deploy_config['remote_path'] or '/'
            try:
                ftp.cwd(remote_path)
            except:
                ftp.mkd(remote_path)
                ftp.cwd(remote_path)
            
            uploaded_count = 0
            failed_files = []
            created_dirs = set()
            
            for file_info in files:
                try:
                    relative_path = file_info['relative_path']
                    local_path = file_info['local_path']
                    remote_dir = os.path.dirname(relative_path)
                    
                    # Create directory structure
                    if remote_dir and remote_dir != '.':
                        dirs = remote_dir.split('/')
                        ftp.cwd(remote_path)
                        current = remote_path.rstrip('/')
                        
                        for d in dirs:
                            if d:
                                current = f"{current}/{d}"
                                if current not in created_dirs:
                                    try:
                                        ftp.cwd(d)
                                    except:
                                        ftp.mkd(d)
                                        ftp.cwd(d)
                                    created_dirs.add(current)
                    else:
                        ftp.cwd(remote_path)
                    
                    # Upload file
                    with open(local_path, 'rb') as f:
                        ftp.storbinary(f'STOR {os.path.basename(relative_path)}', f)
                    uploaded_count += 1
                    
                except Exception as file_error:
                    failed_files.append(relative_path)
                    logger.warning(f"Failed to upload {relative_path}: {file_error}")
            
            ftp.quit()
            
            message = f"Deployed {uploaded_count}/{len(files)} files successfully"
            if failed_files:
                message += f" ({len(failed_files)} files failed)"
            
            await update_operation(op_id, 'success', message)
            shutil.rmtree(temp_dir, ignore_errors=True)
            
            return {
                "success": True,
                "message": message,
                "operation_id": op_id,
                "details": {
                    "uploaded": uploaded_count,
                    "total": len(files),
                    "failed": len(failed_files),
                    "project_type": project_type
                }
            }
        
        elif deploy_config['deploy_type'] == 'cpanel':
            message = f"cPanel deployment initiated for {deploy_config['host']} (Full cPanel integration coming soon)"
            await update_operation(op_id, 'success', message)
            shutil.rmtree(temp_dir, ignore_errors=True)
            return {"success": True, "message": message, "operation_id": op_id}
        
        else:
            raise ValueError(f"Unknown deployment type: {deploy_config['deploy_type']}")
    
    except Exception as e:
        await update_operation(op_id, 'failed', str(e))
        raise HTTPException(status_code=400, detail=str(e))

# ============= Test Connections =============

@api_router.post("/test-git-connection")
async def test_git_connection(request: TestConnectionRequest):
    try:
        temp_dir = tempfile.mkdtemp()
        auth_url = get_auth_url(request.url, request.provider, request.auth_type, request.auth_data)
        
        git.Repo.clone_from(auth_url, temp_dir, depth=1)
        shutil.rmtree(temp_dir, ignore_errors=True)
        
        return {"success": True, "message": "Successfully connected to repository! Authentication verified."}
    except Exception as e:
        error_msg = str(e).lower()
        if 'authentication' in error_msg or 'could not read' in error_msg:
            message = "Authentication failed. Please verify your access token or credentials."
        elif 'not found' in error_msg:
            message = "Repository not found. Check the URL and your access permissions."
        elif 'resolve host' in error_msg:
            message = "Could not connect to Git server. Please verify the repository URL."
        else:
            message = f"Connection test failed: {str(e)}"
        return {"success": False, "message": message}

@api_router.post("/test-ftp-connection")
async def test_ftp_connection(request: TestFTPRequest):
    try:
        if request.use_tls:
            ftp = FTP_TLS(request.host, timeout=10)
        else:
            ftp = FTP(request.host, timeout=10)
        
        ftp.login(request.username, request.password)
        welcome = ftp.getwelcome()
        ftp.quit()
        
        return {"success": True, "message": f"Successfully connected to FTP server! {welcome}"}
    except Exception as e:
        error_msg = str(e)
        if '530' in error_msg or 'authentication' in error_msg.lower():
            message = "Authentication failed. Please verify your username and password."
        elif 'timed out' in error_msg.lower():
            message = "Connection timed out. Please verify the host address."
        else:
            message = f"FTP connection test failed: {error_msg}"
        return {"success": False, "message": message}

# ============= Health Check =============

@api_router.get("/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}

# Include router and middleware
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown():
    global pool
    if pool:
        pool.close()
        await pool.wait_closed()
