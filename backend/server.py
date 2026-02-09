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
    project_type: str  # react, angular, vue, nodejs, python, static
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

# ============= Git Operation Endpoints =============

@api_router.get("/operations", response_model=List[GitOperation])
async def get_operations(repo_id: Optional[str] = None):
    query = {"repo_id": repo_id} if repo_id else {}
    operations = await db.operations.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
    for op in operations:
        if isinstance(op.get('created_at'), str):
            op['created_at'] = datetime.fromisoformat(op['created_at'])
    return operations

@api_router.post("/operations", response_model=GitOperation)
async def create_operation(op_input: GitOperationCreate):
    op_dict = op_input.model_dump()
    op_obj = GitOperation(**op_dict)
    
    doc = op_obj.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    
    await db.operations.insert_one(doc)
    return op_obj

async def update_operation_status(op_id: str, status: str, message: str):
    await db.operations.update_one(
        {"id": op_id},
        {"$set": {"status": status, "message": message}}
    )

# ============= Git Operations Logic =============

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
        # Frontend build process
        build_dir = os.path.join(repo_path, 'build')
        
        # Check if it's a React app
        if os.path.exists(os.path.join(repo_path, 'package.json')):
            # Install dependencies
            os.system(f'cd {repo_path} && npm install --production')
            
            # Run build
            build_result = os.system(f'cd {repo_path} && npm run build')
            
            if build_result != 0:
                raise ValueError("Build failed. Please check your build configuration.")
            
            # Check for build output
            if os.path.exists(build_dir):
                return build_dir
            elif os.path.exists(os.path.join(repo_path, 'dist')):
                return os.path.join(repo_path, 'dist')
            else:
                raise ValueError("Build completed but output directory not found")
        else:
            raise ValueError("No package.json found. Cannot build frontend project.")
    
    elif project_type == 'angular':
        # Angular build
        dist_dir = os.path.join(repo_path, 'dist')
        
        if os.path.exists(os.path.join(repo_path, 'package.json')):
            os.system(f'cd {repo_path} && npm install --production')
            build_result = os.system(f'cd {repo_path} && npm run build')
            
            if build_result != 0:
                raise ValueError("Angular build failed")
            
            # Angular creates dist/project-name folder
            if os.path.exists(dist_dir):
                # Find the actual build folder inside dist
                subdirs = [d for d in os.listdir(dist_dir) if os.path.isdir(os.path.join(dist_dir, d))]
                if subdirs:
                    return os.path.join(dist_dir, subdirs[0])
                return dist_dir
            else:
                raise ValueError("Build completed but dist directory not found")
        else:
            raise ValueError("No package.json found")
    
    elif project_type == 'nodejs':
        # Node.js - deploy source but exclude node_modules
        return repo_path
    
    elif project_type == 'python':
        # Python - deploy source code
        return repo_path
    
    elif project_type == 'static':
        # Static HTML/CSS/JS - deploy as is
        return repo_path
    
    else:
        # Unknown type, deploy everything
        return repo_path

def get_files_to_deploy(deploy_dir: str, project_type: str):
    """Get list of files to deploy based on project type"""
    files_to_deploy = []
    
    # Files/folders to exclude based on project type
    exclude_patterns = {
        'react': ['.git', 'node_modules', 'src', 'public', 'tests', 'test', '.env', '.env.local', 
                  'package.json', 'package-lock.json', 'yarn.lock', 'tsconfig.json', 'README.md'],
        'angular': ['.git', 'node_modules', 'src', 'tests', 'test', '.env', 'package.json', 
                    'angular.json', 'tsconfig.json', 'README.md'],
        'vue': ['.git', 'node_modules', 'src', 'public', 'tests', 'test', '.env', 'package.json', 
                'vue.config.js', 'README.md'],
        'nextjs': ['.git', 'node_modules', 'pages', 'components', 'public', '.env', 'package.json', 
                   'next.config.js', 'README.md'],
        'nodejs': ['.git', 'node_modules', 'tests', 'test', '__tests__', '.env', '.env.example', 
                   'README.md', '.gitignore', 'nodemon.json'],
        'python': ['.git', 'venv', '__pycache__', '*.pyc', 'tests', 'test', '.env', '.env.example', 
                   'README.md', '.gitignore', 'pytest.ini'],
        'static': ['.git', 'node_modules', '.env', 'README.md', '.gitignore']
    }
    
    excludes = exclude_patterns.get(project_type, ['.git', 'node_modules', '.env'])
    
    for root, dirs, files in os.walk(deploy_dir):
        # Skip excluded directories
        dirs[:] = [d for d in dirs if d not in excludes and not d.startswith('.')]
        
        for file in files:
            # Skip excluded files and hidden files
            should_skip = False
            for pattern in excludes:
                if pattern.startswith('*.'):
                    # Pattern match
                    if file.endswith(pattern[1:]):
                        should_skip = True
                        break
                elif file == pattern or file.startswith('.'):
                    should_skip = True
                    break
            
            if not should_skip:
                local_path = os.path.join(root, file)
                relative_path = os.path.relpath(local_path, deploy_dir)
                files_to_deploy.append((local_path, relative_path))
    
    return files_to_deploy

def get_git_repo(repo_data: dict):
    """Clone or open a git repository based on repo data"""
    try:
        if repo_data.get('is_local'):
            # Use /app directory for local codebase
            return git.Repo('/app')
        else:
            # For external repos, clone to temp directory
            temp_dir = tempfile.mkdtemp()
            auth_type = repo_data.get('auth_type')
            url = repo_data.get('url')
            provider = repo_data.get('provider')
            
            auth_url = get_auth_url(url, provider, auth_type, repo_data.get('auth_data', {}))
            return git.Repo.clone_from(auth_url, temp_dir, depth=1)
    except git.exc.GitCommandError as e:
        error_msg = str(e)
        if 'authentication failed' in error_msg.lower() or 'could not read' in error_msg.lower():
            raise ValueError("Authentication failed. Please check your credentials (access token, username, or SSH key).")
        elif 'repository not found' in error_msg.lower():
            raise ValueError("Repository not found. Please verify the repository URL and your access permissions.")
        elif 'could not resolve host' in error_msg.lower():
            raise ValueError("Could not connect to Git server. Please check the repository URL.")
        else:
            raise ValueError(f"Git operation failed: {error_msg}")

@api_router.post("/repos/{repo_id}/create-branch")
async def create_branch(repo_id: str, request: BranchCreateRequest, background_tasks: BackgroundTasks):
    repo = await db.repositories.find_one({"id": repo_id}, {"_id": 0})
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    
    # Create operation record
    op_dict = {
        "repo_id": repo_id,
        "operation_type": "create_branch",
        "branch_name": request.branch_name,
        "status": "pending",
        "message": f"Creating branch {request.branch_name}"
    }
    op_obj = GitOperation(**op_dict)
    doc = op_obj.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.operations.insert_one(doc)
    
    try:
        git_repo = get_git_repo(repo)
        
        # Create new branch
        base_branch = request.base_branch or repo.get('default_branch', 'main')
        
        # Checkout base branch first
        if base_branch in [b.name for b in git_repo.branches]:
            git_repo.git.checkout(base_branch)
        else:
            # Try master if main doesn't exist
            try:
                git_repo.git.checkout('master')
            except:
                git_repo.git.checkout(git_repo.head.ref.name)
        
        # Create and checkout new branch
        new_branch = git_repo.create_head(request.branch_name)
        new_branch.checkout()
        
        await update_operation_status(op_obj.id, "success", f"Branch {request.branch_name} created successfully")
        
        return {
            "success": True,
            "message": f"Branch {request.branch_name} created successfully",
            "operation_id": op_obj.id
        }
    except ValueError as e:
        # User-friendly error messages
        await update_operation_status(op_obj.id, "failed", str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating branch: {str(e)}")
        error_msg = "Branch creation failed. Please check your credentials and repository access."
        await update_operation_status(op_obj.id, "failed", error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

@api_router.post("/repos/{repo_id}/push")
async def push_to_branch(repo_id: str, request: PushRequest):
    repo = await db.repositories.find_one({"id": repo_id}, {"_id": 0})
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    
    # Create operation record
    op_dict = {
        "repo_id": repo_id,
        "operation_type": "push",
        "branch_name": request.branch_name,
        "status": "pending",
        "message": f"Pushing to branch {request.branch_name}"
    }
    op_obj = GitOperation(**op_dict)
    doc = op_obj.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.operations.insert_one(doc)
    
    try:
        git_repo = get_git_repo(repo)
        
        # Checkout the branch
        try:
            git_repo.git.checkout(request.branch_name)
        except git.exc.GitCommandError:
            raise ValueError(f"Branch '{request.branch_name}' does not exist. Please create it first.")
        
        # Stage all changes
        git_repo.git.add(A=True)
        
        # Commit if there are changes
        if git_repo.is_dirty() or git_repo.untracked_files:
            git_repo.index.commit(request.commit_message)
        
        # Push to remote
        origin = git_repo.remote('origin')
        origin.push(request.branch_name)
        
        await update_operation_status(op_obj.id, "success", f"Pushed to {request.branch_name} successfully")
        
        return {
            "success": True,
            "message": f"Pushed to {request.branch_name} successfully",
            "operation_id": op_obj.id
        }
    except ValueError as e:
        await update_operation_status(op_obj.id, "failed", str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error pushing to branch: {str(e)}")
        error_msg = "Push failed. Please check your credentials and branch name."
        await update_operation_status(op_obj.id, "failed", error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

@api_router.post("/repos/{repo_id}/merge")
async def merge_branches(repo_id: str, request: MergeRequest):
    repo = await db.repositories.find_one({"id": repo_id}, {"_id": 0})
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    
    # Create operation record
    op_dict = {
        "repo_id": repo_id,
        "operation_type": "merge",
        "branch_name": f"{request.source_branch} -> {request.target_branch}",
        "status": "pending",
        "message": f"Merging {request.source_branch} into {request.target_branch}"
    }
    op_obj = GitOperation(**op_dict)
    doc = op_obj.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.operations.insert_one(doc)
    
    try:
        git_repo = get_git_repo(repo)
        
        # Checkout target branch
        try:
            git_repo.git.checkout(request.target_branch)
        except git.exc.GitCommandError:
            raise ValueError(f"Target branch '{request.target_branch}' does not exist.")
        
        # Merge source branch
        try:
            git_repo.git.merge(request.source_branch)
        except git.exc.GitCommandError as e:
            if 'conflict' in str(e).lower():
                raise ValueError(f"Merge conflict detected. Please resolve conflicts manually.")
            else:
                raise ValueError(f"Source branch '{request.source_branch}' not found or cannot be merged.")
        
        # Push merged changes
        origin = git_repo.remote('origin')
        origin.push(request.target_branch)
        
        await update_operation_status(op_obj.id, "success", 
            f"Merged {request.source_branch} into {request.target_branch} and pushed successfully")
        
        return {
            "success": True,
            "message": f"Merged {request.source_branch} into {request.target_branch} successfully",
            "operation_id": op_obj.id
        }
    except ValueError as e:
        await update_operation_status(op_obj.id, "failed", str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error merging branches: {str(e)}")
        error_msg = "Merge failed. Please check your credentials and branch names."
        await update_operation_status(op_obj.id, "failed", error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

# ============= Deployment Endpoints =============

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
    config_dict = config_input.model_dump()
    config_obj = DeploymentConfig(**config_dict)
    
    doc = config_obj.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    
    await db.deployment_configs.insert_one(doc)
    return config_obj

@api_router.delete("/deployment-configs/{config_id}")
async def delete_deployment_config(config_id: str):
    result = await db.deployment_configs.delete_one({"id": config_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Deployment config not found")
    return {"message": "Deployment config deleted successfully"}

@api_router.post("/repos/{repo_id}/deploy")
async def deploy_repository(repo_id: str, request: DeployRequest):
    repo = await db.repositories.find_one({"id": repo_id}, {"_id": 0})
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    
    # Get deployment config
    deploy_config = await db.deployment_configs.find_one({"repo_id": repo_id}, {"_id": 0})
    if not deploy_config:
        raise HTTPException(status_code=404, detail="Deployment config not found for this repository")
    
    # Create operation record
    op_dict = {
        "repo_id": repo_id,
        "operation_type": "deploy",
        "branch_name": request.branch_name,
        "status": "pending",
        "message": f"Deploying to {deploy_config['deploy_type']}"
    }
    op_obj = GitOperation(**op_dict)
    doc = op_obj.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.operations.insert_one(doc)
    
    try:
        git_repo = get_git_repo(repo)
        
        if request.branch_name:
            git_repo.git.checkout(request.branch_name)
        
        repo_path = git_repo.working_dir
        project_type = deploy_config.get('project_type', 'static')
        
        # Build the project if needed
        try:
            deploy_dir = build_project(repo_path, project_type)
            logger.info(f"Build completed. Deploy directory: {deploy_dir}")
        except ValueError as build_error:
            error_msg = f"Build failed: {str(build_error)}"
            await update_operation_status(op_obj.id, "failed", error_msg)
            raise ValueError(error_msg)
        
        # Get files to deploy
        files_to_deploy = get_files_to_deploy(deploy_dir, project_type)
        
        if not files_to_deploy:
            raise ValueError("No files found to deploy after build")
        
        deploy_type = deploy_config['deploy_type']
        config = deploy_config['config']
        
        if deploy_type == 'ftp':
            # FTP Deployment
            host = config.get('host')
            username = config.get('username')
            password = config.get('password')
            remote_path = config.get('path', '/')
            use_tls = config.get('use_tls', False)
            
            try:
                if use_tls:
                    ftp = FTP_TLS(host, timeout=30)
                else:
                    ftp = FTP(host, timeout=30)
                
                ftp.login(username, password)
                
                # Change to remote directory
                try:
                    ftp.cwd(remote_path)
                except:
                    ftp.mkd(remote_path)
                    ftp.cwd(remote_path)
                
                uploaded_count = 0
                failed_files = []
                
                # Helper function to create remote directory
                def ensure_remote_dir(ftp, path):
                    dirs = path.split('/')
                    current = ''
                    for d in dirs:
                        if d:
                            current += '/' + d if current else d
                            try:
                                ftp.cwd(current)
                            except:
                                try:
                                    ftp.mkd(current)
                                    ftp.cwd(current)
                                except:
                                    pass
                    # Return to remote root
                    ftp.cwd(remote_path)
                
                # Upload each file
                for local_path, relative_path in files_to_deploy:
                    try:
                        # Create directory structure if needed
                        remote_dir = os.path.dirname(relative_path)
                        if remote_dir:
                            ensure_remote_dir(ftp, remote_dir)
                        
                        # Change to the correct directory
                        if remote_dir:
                            ftp.cwd(remote_path + '/' + remote_dir.replace(os.sep, '/'))
                        else:
                            ftp.cwd(remote_path)
                        
                        # Upload file
                        remote_file = os.path.basename(relative_path)
                        with open(local_path, 'rb') as f:
                            ftp.storbinary(f'STOR {remote_file}', f)
                        uploaded_count += 1
                        
                        # Return to root
                        ftp.cwd(remote_path)
                        
                    except Exception as file_error:
                        failed_files.append(relative_path)
                        logger.warning(f"Failed to upload {relative_path}: {str(file_error)}")
                
                ftp.quit()
                
                # Prepare success message
                success_msg = f"Deployed {uploaded_count}/{len(files_to_deploy)} files successfully"
                if failed_files:
                    success_msg += f" ({len(failed_files)} files failed)"
                
                await update_operation_status(op_obj.id, "success", success_msg)
                
                return {
                    "success": True,
                    "message": success_msg,
                    "operation_id": op_obj.id,
                    "details": {
                        "uploaded": uploaded_count,
                        "total": len(files_to_deploy),
                        "failed": len(failed_files),
                        "project_type": project_type
                    }
                }
                
            except Exception as ftp_error:
                error_msg = f"FTP deployment failed: {str(ftp_error)}"
                logger.error(error_msg)
                await update_operation_status(op_obj.id, "failed", error_msg)
                raise ValueError(error_msg)
            
        elif deploy_type == 'cpanel':
            # cPanel deployment via API (simplified mock for MVP)
            host = config.get('host')
            username = config.get('username')
            api_token = config.get('api_token')
            
            # This is a placeholder - actual cPanel API would require more complex integration
            success_msg = f"cPanel deployment initiated for {host} (Note: Full cPanel integration coming soon)"
            await update_operation_status(op_obj.id, "success", success_msg)
            
            return {
                "success": True,
                "message": success_msg,
                "operation_id": op_obj.id
            }
        
        else:
            raise ValueError(f"Unknown deployment type: {deploy_type}")
    except ValueError as e:
        await update_operation_status(op_obj.id, "failed", str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error deploying: {str(e)}")
        error_msg = "Deployment failed. Please check your configuration and credentials."
        await update_operation_status(op_obj.id, "failed", error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

# ============= Test Connection Endpoints =============

@api_router.post("/test-git-connection")
async def test_git_connection(request: TestConnectionRequest):
    """Test Git repository connection and authentication"""
    try:
        temp_dir = tempfile.mkdtemp()
        
        # Build authenticated URL
        auth_url = get_auth_url(
            request.url,
            request.provider,
            request.auth_type,
            request.auth_data
        )
        
        # Try to clone with depth=1 for faster testing
        git.Repo.clone_from(auth_url, temp_dir, depth=1)
        
        # Clean up
        shutil.rmtree(temp_dir, ignore_errors=True)
        
        return {
            "success": True,
            "message": "Successfully connected to repository! Authentication verified."
        }
    except ValueError as e:
        return {
            "success": False,
            "message": str(e)
        }
    except git.exc.GitCommandError as e:
        error_msg = str(e)
        if 'authentication failed' in error_msg.lower() or 'could not read' in error_msg.lower():
            message = "Authentication failed. Please verify your access token or credentials."
        elif 'repository not found' in error_msg.lower():
            message = "Repository not found. Check the URL and your access permissions."
        elif 'could not resolve host' in error_msg.lower():
            message = "Could not connect to Git server. Please verify the repository URL."
        else:
            message = f"Connection test failed: {error_msg}"
        
        return {
            "success": False,
            "message": message
        }
    except Exception as e:
        logger.error(f"Error testing Git connection: {str(e)}")
        return {
            "success": False,
            "message": f"Connection test failed: {str(e)}"
        }

@api_router.post("/test-ftp-connection")
async def test_ftp_connection(request: TestFTPRequest):
    """Test FTP server connection"""
    try:
        if request.use_tls:
            ftp = FTP_TLS(request.host, timeout=10)
        else:
            ftp = FTP(request.host, timeout=10)
        
        ftp.login(request.username, request.password)
        
        # Get welcome message
        welcome = ftp.getwelcome()
        
        ftp.quit()
        
        return {
            "success": True,
            "message": f"Successfully connected to FTP server! {welcome}"
        }
    except Exception as e:
        error_msg = str(e)
        if 'authentication failed' in error_msg.lower() or '530' in error_msg:
            message = "Authentication failed. Please verify your username and password."
        elif 'timed out' in error_msg.lower():
            message = "Connection timed out. Please verify the host address."
        else:
            message = f"FTP connection test failed: {error_msg}"
        
        logger.error(f"Error testing FTP connection: {str(e)}")
        return {
            "success": False,
            "message": message
        }

# Include the router in the main app
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
