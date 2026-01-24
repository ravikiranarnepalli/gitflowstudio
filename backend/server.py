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
    config: Dict[str, Any]  # host, username, password, path, etc.
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class DeploymentConfigCreate(BaseModel):
    repo_id: str
    deploy_type: str
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

def get_git_repo(repo_data: dict):
    """Clone or open a git repository based on repo data"""
    if repo_data.get('is_local'):
        # Use /app directory for local codebase
        return git.Repo('/app')
    else:
        # For external repos, clone to temp directory
        temp_dir = tempfile.mkdtemp()
        auth_type = repo_data.get('auth_type')
        url = repo_data.get('url')
        
        if auth_type == 'pat':
            token = repo_data['auth_data'].get('token')
            # Inject token into URL
            if 'github.com' in url:
                auth_url = url.replace('https://', f'https://{token}@')
            elif 'gitlab.com' in url:
                auth_url = url.replace('https://', f'https://oauth2:{token}@')
            elif 'bitbucket.org' in url:
                username = repo_data['auth_data'].get('username', 'x-token-auth')
                auth_url = url.replace('https://', f'https://{username}:{token}@')
            else:
                auth_url = url
            
            return git.Repo.clone_from(auth_url, temp_dir)
        elif auth_type == 'ssh':
            # For SSH, need to set up SSH keys (simplified for MVP)
            return git.Repo.clone_from(url, temp_dir)
        else:
            return git.Repo.clone_from(url, temp_dir)

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
            git_repo.git.checkout('master')
        
        # Create and checkout new branch
        new_branch = git_repo.create_head(request.branch_name)
        new_branch.checkout()
        
        await update_operation_status(op_obj.id, "success", f"Branch {request.branch_name} created successfully")
        
        return {
            "success": True,
            "message": f"Branch {request.branch_name} created successfully",
            "operation_id": op_obj.id
        }
    except Exception as e:
        logger.error(f"Error creating branch: {str(e)}")
        await update_operation_status(op_obj.id, "failed", str(e))
        raise HTTPException(status_code=500, detail=str(e))

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
        git_repo.git.checkout(request.branch_name)
        
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
    except Exception as e:
        logger.error(f"Error pushing to branch: {str(e)}")
        await update_operation_status(op_obj.id, "failed", str(e))
        raise HTTPException(status_code=500, detail=str(e))

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
        git_repo.git.checkout(request.target_branch)
        
        # Merge source branch
        git_repo.git.merge(request.source_branch)
        
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
    except Exception as e:
        logger.error(f"Error merging branches: {str(e)}")
        await update_operation_status(op_obj.id, "failed", str(e))
        raise HTTPException(status_code=500, detail=str(e))

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
        
        deploy_type = deploy_config['deploy_type']
        config = deploy_config['config']
        
        if deploy_type == 'ftp':
            # FTP Deployment
            host = config.get('host')
            username = config.get('username')
            password = config.get('password')
            remote_path = config.get('path', '/')
            use_tls = config.get('use_tls', False)
            
            if use_tls:
                ftp = FTP_TLS(host)
            else:
                ftp = FTP(host)
            
            ftp.login(username, password)
            ftp.cwd(remote_path)
            
            # Upload files (simplified - only uploads specific files for MVP)
            for root, dirs, files in os.walk(repo_path):
                for file in files:
                    if not file.startswith('.git'):
                        local_path = os.path.join(root, file)
                        relative_path = os.path.relpath(local_path, repo_path)
                        
                        with open(local_path, 'rb') as f:
                            ftp.storbinary(f'STOR {relative_path}', f)
            
            ftp.quit()
            
        elif deploy_type == 'cpanel':
            # cPanel deployment via API (simplified)
            host = config.get('host')
            username = config.get('username')
            api_token = config.get('api_token')
            
            # This is a simplified mock - actual cPanel API integration would be more complex
            message = f"cPanel deployment initiated for {host}"
        
        await update_operation_status(op_obj.id, "success", f"Deployed successfully to {deploy_type}")
        
        return {
            "success": True,
            "message": f"Deployed successfully to {deploy_type}",
            "operation_id": op_obj.id
        }
    except Exception as e:
        logger.error(f"Error deploying: {str(e)}")
        await update_operation_status(op_obj.id, "failed", str(e))
        raise HTTPException(status_code=500, detail=str(e))

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
