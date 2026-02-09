from fastapi import FastAPI, APIRouter, HTTPException, BackgroundTasks
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone
import git
import shutil
import tempfile
import paramiko
from ftplib import FTP, FTP_TLS
import requests
import json
import subprocess

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============= Models =============

class Repository(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    provider: str  # github, gitlab, bitbucket
    url: str
    auth_type: str  # pat, ssh, oauth
    auth_data: Dict[str, Any]  # Encrypted credentials
    default_branch: str = "main"
    is_local: bool = False  # True for /app codebase
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class RepositoryCreate(BaseModel):
    name: str
    provider: str
    url: str
    auth_type: str
    auth_data: Dict[str, Any]
    default_branch: str = "main"
    is_local: bool = False

class GitOperation(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    repo_id: str
    operation_type: str  # create_branch, push, merge, deploy
    branch_name: Optional[str] = None
    status: str  # pending, success, failed
    message: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class GitOperationCreate(BaseModel):
    repo_id: str
    operation_type: str
    branch_name: Optional[str] = None
    status: str = "pending"
    message: str = ""

class DeploymentConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    repo_id: str
    deploy_type: str  # ftp, cpanel
    project_type: str = "static"  # react, angular, vue, nodejs, python, static
    config: Dict[str, Any]  # host, username, password, path, etc.
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class DeploymentConfigCreate(BaseModel):
    repo_id: str
    deploy_type: str
    project_type: str = "static"
    config: Dict[str, Any]

class BranchCreateRequest(BaseModel):
    branch_name: str
    base_branch: Optional[str] = None

class PushRequest(BaseModel):
    branch_name: str
    commit_message: Optional[str] = "Auto commit"

class MergeRequest(BaseModel):
    source_branch: str
    target_branch: str = "main"

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

def format_size(bytes_size):
    if bytes_size < 1024:
        return f"{bytes_size} B"
    elif bytes_size < 1024 * 1024:
        return f"{bytes_size / 1024:.1f} KB"
    return f"{bytes_size / (1024 * 1024):.2f} MB"

def get_auth_url(url: str, provider: str, auth_type: str, auth_data: dict) -> str:
    """Generate authenticated URL for Git operations"""
    if auth_type == 'pat':
        token = auth_data.get('token')
        if not token:
            raise ValueError("Access token is required for PAT authentication")
        
        if 'github.com' in url:
            return url.replace('https://', f'https://{token}@')
        elif 'gitlab.com' in url:
            return url.replace('https://', f'https://oauth2:{token}@')
        elif 'bitbucket.org' in url:
            username = auth_data.get('username', 'x-token-auth')
            return url.replace('https://', f'https://{username}:{token}@')
        else:
            return url.replace('https://', f'https://{token}@')
    elif auth_type == 'ssh':
        return url
    else:
        return url

def build_project(repo_path: str, project_type: str) -> str:
    """Build the project and return the deployment directory"""
    logger.info(f"Building {project_type} project at {repo_path}")
    
    if project_type in ['react', 'vue', 'nextjs']:
        build_dir = os.path.join(repo_path, 'build')
        package_json_path = os.path.join(repo_path, 'package.json')
        if not os.path.exists(package_json_path):
            raise ValueError("No package.json found. Cannot build frontend project.")
        
        try:
            logger.info("Installing dependencies...")
            install_result = subprocess.run(
                ['npm', 'install', '--legacy-peer-deps'],
                cwd=repo_path, capture_output=True, text=True, timeout=300
            )
            if install_result.returncode != 0:
                raise ValueError(f"Dependency installation failed: {install_result.stderr[:200]}")
            
            logger.info("Running build command...")
            build_result = subprocess.run(
                ['npm', 'run', 'build'],
                cwd=repo_path, capture_output=True, text=True, timeout=600
            )
            if build_result.returncode != 0:
                raise ValueError(f"Build failed: {build_result.stderr[:300]}")
            
            if os.path.exists(build_dir):
                return build_dir
            elif os.path.exists(os.path.join(repo_path, 'dist')):
                return os.path.join(repo_path, 'dist')
            else:
                raise ValueError("Build completed but output directory not found")
        except subprocess.TimeoutExpired:
            raise ValueError("Build process timed out.")
        except FileNotFoundError:
            raise ValueError("npm not found. Please ensure Node.js is installed.")
    
    elif project_type == 'angular':
        dist_dir = os.path.join(repo_path, 'dist')
        package_json_path = os.path.join(repo_path, 'package.json')
        if not os.path.exists(package_json_path):
            raise ValueError("No package.json found. Cannot build Angular project.")
        
        try:
            logger.info("Installing Angular dependencies...")
            subprocess.run(['npm', 'install', '--legacy-peer-deps'], cwd=repo_path, capture_output=True, timeout=300)
            
            logger.info("Running Angular build...")
            build_result = subprocess.run(
                ['npx', 'ng', 'build', '--configuration=production'],
                cwd=repo_path, capture_output=True, text=True, timeout=600
            )
            if build_result.returncode != 0:
                build_result = subprocess.run(['npm', 'run', 'build'], cwd=repo_path, capture_output=True, text=True, timeout=600)
                if build_result.returncode != 0:
                    raise ValueError(f"Angular build failed: {build_result.stderr[:300]}")
            
            if os.path.exists(dist_dir):
                subdirs = [d for d in os.listdir(dist_dir) if os.path.isdir(os.path.join(dist_dir, d))]
                if subdirs:
                    return os.path.join(dist_dir, subdirs[0])
                return dist_dir
            else:
                raise ValueError("Build completed but dist directory not found")
        except subprocess.TimeoutExpired:
            raise ValueError("Build process timed out.")
    
    return repo_path

def get_files_to_deploy(deploy_dir: str, project_type: str):
    """Get list of files to deploy based on project type"""
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
            should_skip = False
            for pattern in excludes:
                if pattern.startswith('*.'):
                    if filename.endswith(pattern[1:]):
                        should_skip = True
                        break
                elif filename == pattern or filename.startswith('.'):
                    should_skip = True
                    break
            
            if not should_skip:
                local_path = os.path.join(root, filename)
                relative_path = os.path.relpath(local_path, deploy_dir)
                file_size = os.path.getsize(local_path)
                files.append({
                    'local_path': local_path,
                    'relative_path': relative_path,
                    'size': file_size
                })
    
    return files

def get_git_repo(repo_data: dict):
    """Clone or open a git repository based on repo data"""
    try:
        if repo_data.get('is_local'):
            return git.Repo('/app')
        else:
            temp_dir = tempfile.mkdtemp()
            auth_type = repo_data.get('auth_type')
            url = repo_data.get('url')
            provider = repo_data.get('provider')
            auth_url = get_auth_url(url, provider, auth_type, repo_data.get('auth_data', {}))
            return git.Repo.clone_from(auth_url, temp_dir, depth=1)
    except git.exc.GitCommandError as e:
        error_msg = str(e)
        if 'authentication failed' in error_msg.lower() or 'could not read' in error_msg.lower():
            raise ValueError("Authentication failed. Please check your credentials.")
        elif 'repository not found' in error_msg.lower():
            raise ValueError("Repository not found. Please verify the URL.")
        elif 'could not resolve host' in error_msg.lower():
            raise ValueError("Could not connect to Git server.")
        else:
            raise ValueError(f"Git operation failed: {error_msg}")

# ============= Repository Endpoints =============

@api_router.get("/repos", response_model=List[Repository])
async def get_repositories():
    repos = await db.repositories.find({}, {"_id": 0}).to_list(1000)
    for repo in repos:
        if isinstance(repo.get('created_at'), str):
            repo['created_at'] = datetime.fromisoformat(repo['created_at'])
    return repos

@api_router.post("/repos", response_model=Repository)
async def create_repository(repo_input: RepositoryCreate):
    repo_dict = repo_input.model_dump()
    repo_obj = Repository(**repo_dict)
    doc = repo_obj.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.repositories.insert_one(doc)
    return repo_obj

@api_router.get("/repos/{repo_id}", response_model=Repository)
async def get_repository(repo_id: str):
    repo = await db.repositories.find_one({"id": repo_id}, {"_id": 0})
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    if isinstance(repo.get('created_at'), str):
        repo['created_at'] = datetime.fromisoformat(repo['created_at'])
    return repo

@api_router.delete("/repos/{repo_id}")
async def delete_repository(repo_id: str):
    result = await db.repositories.delete_one({"id": repo_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Repository not found")
    return {"message": "Repository deleted successfully"}

# ============= Operations Endpoints =============

@api_router.get("/operations", response_model=List[GitOperation])
async def get_operations(repo_id: Optional[str] = None):
    query = {"repo_id": repo_id} if repo_id else {}
    operations = await db.operations.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
    for op in operations:
        if isinstance(op.get('created_at'), str):
            op['created_at'] = datetime.fromisoformat(op['created_at'])
    return operations

async def update_operation_status(op_id: str, status: str, message: str):
    await db.operations.update_one({"id": op_id}, {"$set": {"status": status, "message": message}})

# ============= Git Operations =============

@api_router.post("/repos/{repo_id}/create-branch")
async def create_branch(repo_id: str, request: BranchCreateRequest):
    repo = await db.repositories.find_one({"id": repo_id}, {"_id": 0})
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    
    op_obj = GitOperation(repo_id=repo_id, operation_type="create_branch", branch_name=request.branch_name, status="pending", message=f"Creating branch {request.branch_name}")
    doc = op_obj.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.operations.insert_one(doc)
    
    try:
        git_repo = get_git_repo(repo)
        base_branch = request.base_branch or repo.get('default_branch', 'main')
        
        if base_branch in [b.name for b in git_repo.branches]:
            git_repo.git.checkout(base_branch)
        else:
            try:
                git_repo.git.checkout('master')
            except:
                git_repo.git.checkout(git_repo.head.ref.name)
        
        new_branch = git_repo.create_head(request.branch_name)
        new_branch.checkout()
        
        await update_operation_status(op_obj.id, "success", f"Branch {request.branch_name} created successfully")
        return {"success": True, "message": f"Branch {request.branch_name} created successfully", "operation_id": op_obj.id}
    except ValueError as e:
        await update_operation_status(op_obj.id, "failed", str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        await update_operation_status(op_obj.id, "failed", str(e))
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/repos/{repo_id}/push")
async def push_to_branch(repo_id: str, request: PushRequest):
    repo = await db.repositories.find_one({"id": repo_id}, {"_id": 0})
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    
    op_obj = GitOperation(repo_id=repo_id, operation_type="push", branch_name=request.branch_name, status="pending", message=f"Pushing to {request.branch_name}")
    doc = op_obj.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.operations.insert_one(doc)
    
    try:
        git_repo = get_git_repo(repo)
        git_repo.git.checkout(request.branch_name)
        git_repo.git.add(A=True)
        
        if git_repo.is_dirty() or git_repo.untracked_files:
            git_repo.index.commit(request.commit_message)
        
        origin = git_repo.remote('origin')
        origin.push(request.branch_name)
        
        await update_operation_status(op_obj.id, "success", f"Pushed to {request.branch_name} successfully")
        return {"success": True, "message": f"Pushed to {request.branch_name} successfully", "operation_id": op_obj.id}
    except Exception as e:
        await update_operation_status(op_obj.id, "failed", str(e))
        raise HTTPException(status_code=400, detail=str(e))

@api_router.post("/repos/{repo_id}/merge")
async def merge_branches(repo_id: str, request: MergeRequest):
    repo = await db.repositories.find_one({"id": repo_id}, {"_id": 0})
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    
    op_obj = GitOperation(repo_id=repo_id, operation_type="merge", branch_name=f"{request.source_branch} -> {request.target_branch}", status="pending", message=f"Merging {request.source_branch} into {request.target_branch}")
    doc = op_obj.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.operations.insert_one(doc)
    
    try:
        git_repo = get_git_repo(repo)
        git_repo.git.checkout(request.target_branch)
        git_repo.git.merge(request.source_branch)
        origin = git_repo.remote('origin')
        origin.push(request.target_branch)
        
        await update_operation_status(op_obj.id, "success", f"Merged {request.source_branch} into {request.target_branch} successfully")
        return {"success": True, "message": f"Merged successfully", "operation_id": op_obj.id}
    except Exception as e:
        await update_operation_status(op_obj.id, "failed", str(e))
        raise HTTPException(status_code=400, detail=str(e))

# ============= Deployment Config Endpoints =============

@api_router.get("/deployment-configs", response_model=List[DeploymentConfig])
async def get_deployment_configs(repo_id: Optional[str] = None):
    query = {"repo_id": repo_id} if repo_id else {}
    configs = await db.deployment_configs.find(query, {"_id": 0}).to_list(100)
    for config in configs:
        if isinstance(config.get('created_at'), str):
            config['created_at'] = datetime.fromisoformat(config['created_at'])
    return configs

@api_router.post("/deployment-configs", response_model=DeploymentConfig)
async def create_deployment_config(config_input: DeploymentConfigCreate):
    config_obj = DeploymentConfig(**config_input.model_dump())
    doc = config_obj.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.deployment_configs.insert_one(doc)
    return config_obj

@api_router.put("/deployment-configs/{config_id}", response_model=DeploymentConfig)
async def update_deployment_config(config_id: str, config_input: DeploymentConfigCreate):
    existing = await db.deployment_configs.find_one({"id": config_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Deployment config not found")
    
    config_dict = config_input.model_dump()
    config_dict['id'] = config_id
    config_dict['created_at'] = existing.get('created_at')
    config_obj = DeploymentConfig(**config_dict)
    doc = config_obj.model_dump()
    
    if isinstance(doc['created_at'], datetime):
        doc['created_at'] = doc['created_at'].isoformat()
    
    await db.deployment_configs.update_one({"id": config_id}, {"$set": doc})
    return config_obj

@api_router.delete("/deployment-configs/{config_id}")
async def delete_deployment_config(config_id: str):
    result = await db.deployment_configs.delete_one({"id": config_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Deployment config not found")
    return {"message": "Deployment config deleted successfully"}

# ============= Deployment Preview (NEW) =============

@api_router.post("/repos/{repo_id}/preview-deploy")
async def preview_deployment(repo_id: str):
    """Preview files that will be deployed"""
    repo = await db.repositories.find_one({"id": repo_id}, {"_id": 0})
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    
    deploy_config = await db.deployment_configs.find_one({"repo_id": repo_id}, {"_id": 0})
    if not deploy_config:
        raise HTTPException(status_code=404, detail="Deployment config not found")
    
    try:
        temp_dir = tempfile.mkdtemp()
        auth_url = get_auth_url(repo['url'], repo['provider'], repo['auth_type'], repo.get('auth_data', {}))
        
        logger.info("Cloning repository for preview...")
        git.Repo.clone_from(auth_url, temp_dir, depth=1)
        
        project_type = deploy_config.get('project_type', 'static')
        deploy_dir = temp_dir
        
        if project_type in ['react', 'angular', 'vue', 'nextjs']:
            logger.info(f"Building {project_type} project...")
            deploy_dir = build_project(temp_dir, project_type)
        
        files = get_files_to_deploy(deploy_dir, project_type)
        total_size = sum(f['size'] for f in files)
        directories = sorted(set(os.path.dirname(f['relative_path']) for f in files if os.path.dirname(f['relative_path'])))
        
        shutil.rmtree(temp_dir, ignore_errors=True)
        
        return {
            "success": True,
            "preview": {
                "total_files": len(files),
                "total_size": format_size(total_size),
                "total_size_bytes": total_size,
                "project_type": project_type,
                "deploy_type": deploy_config['deploy_type'],
                "target_host": deploy_config['config'].get('host'),
                "target_path": deploy_config['config'].get('path', '/'),
                "directories": directories,
                "files": sorted([{"path": f['relative_path'], "size": format_size(f['size']), "size_bytes": f['size']} for f in files], key=lambda x: x['path'])
            }
        }
    except Exception as e:
        logger.error(f"Preview error: {e}")
        raise HTTPException(status_code=400, detail=f"Preview failed: {str(e)}")

# ============= Deploy =============

@api_router.post("/repos/{repo_id}/deploy")
async def deploy_repository(repo_id: str, request: DeployRequest):
    repo = await db.repositories.find_one({"id": repo_id}, {"_id": 0})
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    
    deploy_config = await db.deployment_configs.find_one({"repo_id": repo_id}, {"_id": 0})
    if not deploy_config:
        raise HTTPException(status_code=404, detail="Deployment config not found")
    
    op_obj = GitOperation(repo_id=repo_id, operation_type="deploy", branch_name=request.branch_name, status="pending", message=f"Deploying to {deploy_config['deploy_type']}")
    doc = op_obj.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.operations.insert_one(doc)
    
    try:
        git_repo = get_git_repo(repo)
        if request.branch_name:
            git_repo.git.checkout(request.branch_name)
        
        repo_path = git_repo.working_dir
        project_type = deploy_config.get('project_type', 'static')
        
        try:
            deploy_dir = build_project(repo_path, project_type)
        except ValueError as build_error:
            await update_operation_status(op_obj.id, "failed", f"Build failed: {str(build_error)}")
            raise ValueError(f"Build failed: {str(build_error)}")
        
        files = get_files_to_deploy(deploy_dir, project_type)
        if not files:
            raise ValueError("No files found to deploy")
        
        deploy_type = deploy_config['deploy_type']
        config = deploy_config['config']
        
        if deploy_type == 'ftp':
            host = config.get('host')
            username = config.get('username')
            password = config.get('password')
            remote_path = config.get('path', '/')
            use_tls = config.get('use_tls', False)
            
            try:
                ftp = FTP_TLS(host, timeout=30) if use_tls else FTP(host, timeout=30)
                ftp.login(username, password)
                
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
                        relative_path = file_info['relative_path'].replace(os.sep, '/')
                        local_path = file_info['local_path']
                        remote_dir = os.path.dirname(relative_path)
                        
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
                
                await update_operation_status(op_obj.id, "success", message)
                
                return {
                    "success": True,
                    "message": message,
                    "operation_id": op_obj.id,
                    "details": {"uploaded": uploaded_count, "total": len(files), "failed": len(failed_files), "project_type": project_type}
                }
            except Exception as ftp_error:
                raise ValueError(f"FTP deployment failed: {str(ftp_error)}")
        
        elif deploy_type == 'cpanel':
            message = f"cPanel deployment initiated for {config.get('host')} (Full integration coming soon)"
            await update_operation_status(op_obj.id, "success", message)
            return {"success": True, "message": message, "operation_id": op_obj.id}
        
        else:
            raise ValueError(f"Unknown deployment type: {deploy_type}")
    
    except ValueError as e:
        await update_operation_status(op_obj.id, "failed", str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        await update_operation_status(op_obj.id, "failed", str(e))
        raise HTTPException(status_code=500, detail=str(e))

# ============= Test Connections =============

@api_router.post("/test-git-connection")
async def test_git_connection(request: TestConnectionRequest):
    try:
        temp_dir = tempfile.mkdtemp()
        auth_url = get_auth_url(request.url, request.provider, request.auth_type, request.auth_data)
        git.Repo.clone_from(auth_url, temp_dir, depth=1)
        shutil.rmtree(temp_dir, ignore_errors=True)
        return {"success": True, "message": "Successfully connected to repository!"}
    except Exception as e:
        error_msg = str(e).lower()
        if 'authentication' in error_msg:
            return {"success": False, "message": "Authentication failed."}
        elif 'not found' in error_msg:
            return {"success": False, "message": "Repository not found."}
        return {"success": False, "message": f"Connection failed: {str(e)}"}

@api_router.post("/test-ftp-connection")
async def test_ftp_connection(request: TestFTPRequest):
    try:
        ftp = FTP_TLS(request.host, timeout=10) if request.use_tls else FTP(request.host, timeout=10)
        ftp.login(request.username, request.password)
        ftp.quit()
        return {"success": True, "message": "Successfully connected to FTP server!"}
    except Exception as e:
        return {"success": False, "message": f"FTP connection failed: {str(e)}"}

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
async def shutdown_db_client():
    client.close()
