import React, { useState, useEffect } from 'react';
import { Plus, GitBranch, Trash2, ExternalLink, GitMerge, Upload } from 'lucide-react';
import axios from 'axios';
import { toast } from 'sonner';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const Repositories = () => {
  const [repos, setRepos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [showOperationDialog, setShowOperationDialog] = useState(false);
  const [selectedRepo, setSelectedRepo] = useState(null);
  const [operationType, setOperationType] = useState('');
  const [testingConnection, setTestingConnection] = useState(false);

  const [newRepo, setNewRepo] = useState({
    name: '',
    provider: 'github',
    url: '',
    auth_type: 'pat',
    auth_data: { token: '', username: '' },
    default_branch: 'main',
    is_local: false
  });

  const [operationData, setOperationData] = useState({
    branch_name: '',
    base_branch: '',
    commit_message: 'Auto commit',
    source_branch: '',
    target_branch: 'main'
  });

  useEffect(() => {
    fetchRepos();
  }, []);

  const fetchRepos = async () => {
    try {
      const response = await axios.get(`${API}/repos`);
      setRepos(response.data);
    } catch (error) {
      console.error('Error fetching repos:', error);
      toast.error('Failed to fetch repositories');
    } finally {
      setLoading(false);
    }
  };

  const handleAddRepo = async () => {
    try {
      await axios.post(`${API}/repos`, newRepo);
      toast.success('Repository added successfully');
      setShowAddDialog(false);
      fetchRepos();
      setNewRepo({
        name: '',
        provider: 'github',
        url: '',
        auth_type: 'pat',
        auth_data: { token: '', username: '' },
        default_branch: 'main',
        is_local: false
      });
    } catch (error) {
      console.error('Error adding repo:', error);
      toast.error('Failed to add repository');
    }
  };

  const handleDeleteRepo = async (repoId) => {
    if (!window.confirm('Are you sure you want to delete this repository?')) return;
    
    try {
      await axios.delete(`${API}/repos/${repoId}`);
      toast.success('Repository deleted successfully');
      fetchRepos();
    } catch (error) {
      console.error('Error deleting repo:', error);
      toast.error('Failed to delete repository');
    }
  };

  const handleOperation = async () => {
    try {
      let endpoint = '';
      let payload = {};

      switch (operationType) {
        case 'create_branch':
          endpoint = `${API}/repos/${selectedRepo.id}/create-branch`;
          payload = {
            branch_name: operationData.branch_name,
            base_branch: operationData.base_branch || selectedRepo.default_branch
          };
          break;
        case 'push':
          endpoint = `${API}/repos/${selectedRepo.id}/push`;
          payload = {
            branch_name: operationData.branch_name,
            commit_message: operationData.commit_message
          };
          break;
        case 'merge':
          endpoint = `${API}/repos/${selectedRepo.id}/merge`;
          payload = {
            source_branch: operationData.source_branch,
            target_branch: operationData.target_branch
          };
          break;
        default:
          return;
      }

      const response = await axios.post(endpoint, payload);
      toast.success(response.data.message);
      setShowOperationDialog(false);
      setOperationData({
        branch_name: '',
        base_branch: '',
        commit_message: 'Auto commit',
        source_branch: '',
        target_branch: 'main'
      });
    } catch (error) {
      console.error('Error performing operation:', error);
      toast.error(error.response?.data?.detail || 'Operation failed');
    }
  };

  const openOperationDialog = (repo, type) => {
    setSelectedRepo(repo);
    setOperationType(type);
    setShowOperationDialog(true);
  };

  return (
    <div className="h-full bg-background">
      {/* Header */}
      <div className="border-b border-border bg-card/50 backdrop-blur-md">
        <div className="container mx-auto px-12 py-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-4xl font-bold font-mono tracking-tight">Repositories</h1>
              <p className="text-sm text-muted-foreground mt-1">Manage your Git repositories</p>
            </div>
            <Dialog open={showAddDialog} onOpenChange={setShowAddDialog}>
              <DialogTrigger asChild>
                <Button data-testid="add-repository-btn" className="btn-primary flex items-center gap-2">
                  <Plus className="w-4 h-4" />
                  Add Repository
                </Button>
              </DialogTrigger>
              <DialogContent className="bg-card border-border">
                <DialogHeader>
                  <DialogTitle className="font-mono">Add New Repository</DialogTitle>
                </DialogHeader>
                <div className="space-y-4">
                  <div>
                    <Label htmlFor="repo-name">Repository Name</Label>
                    <Input
                      id="repo-name"
                      data-testid="repo-name-input"
                      value={newRepo.name}
                      onChange={(e) => setNewRepo({ ...newRepo, name: e.target.value })}
                      placeholder="my-awesome-project"
                      className="mt-1"
                    />
                  </div>
                  <div>
                    <Label htmlFor="provider">Provider</Label>
                    <Select value={newRepo.provider} onValueChange={(val) => setNewRepo({ ...newRepo, provider: val })}>
                      <SelectTrigger data-testid="provider-select" className="mt-1">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="github">GitHub</SelectItem>
                        <SelectItem value="gitlab">GitLab</SelectItem>
                        <SelectItem value="bitbucket">Bitbucket</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label htmlFor="repo-url">Repository URL</Label>
                    <Input
                      id="repo-url"
                      data-testid="repo-url-input"
                      value={newRepo.url}
                      onChange={(e) => setNewRepo({ ...newRepo, url: e.target.value })}
                      placeholder="https://github.com/user/repo.git"
                      className="mt-1"
                    />
                  </div>
                  <div>
                    <Label htmlFor="auth-type">Authentication Type</Label>
                    <Select value={newRepo.auth_type} onValueChange={(val) => setNewRepo({ ...newRepo, auth_type: val })}>
                      <SelectTrigger data-testid="auth-type-select" className="mt-1">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="pat">Personal Access Token</SelectItem>
                        <SelectItem value="ssh">SSH Key</SelectItem>
                        <SelectItem value="oauth">OAuth</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  {newRepo.auth_type === 'pat' && (
                    <div>
                      <Label htmlFor="token">Access Token</Label>
                      <Input
                        id="token"
                        data-testid="token-input"
                        type="password"
                        value={newRepo.auth_data.token}
                        onChange={(e) => setNewRepo({
                          ...newRepo,
                          auth_data: { ...newRepo.auth_data, token: e.target.value }
                        })}
                        placeholder="ghp_xxxxxxxxxxxx"
                        className="mt-1"
                      />
                    </div>
                  )}
                  <div>
                    <Label htmlFor="default-branch">Default Branch</Label>
                    <Input
                      id="default-branch"
                      data-testid="default-branch-input"
                      value={newRepo.default_branch}
                      onChange={(e) => setNewRepo({ ...newRepo, default_branch: e.target.value })}
                      placeholder="main"
                      className="mt-1"
                    />
                  </div>
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id="is-local"
                      data-testid="is-local-checkbox"
                      checked={newRepo.is_local}
                      onChange={(e) => setNewRepo({ ...newRepo, is_local: e.target.checked })}
                      className="w-4 h-4"
                    />
                    <Label htmlFor="is-local">This is the local /app codebase</Label>
                  </div>
                  <Button
                    data-testid="save-repository-btn"
                    onClick={handleAddRepo}
                    className="btn-primary w-full"
                  >
                    Add Repository
                  </Button>
                </div>
              </DialogContent>
            </Dialog>
          </div>
        </div>
      </div>

      {/* Repositories List */}
      <div className="container mx-auto px-12 py-8">
        {loading ? (
          <div className="text-center py-12">
            <div className="animate-pulse">
              <GitBranch className="w-12 h-12 mx-auto text-muted-foreground mb-3" />
              <p className="text-muted-foreground">Loading repositories...</p>
            </div>
          </div>
        ) : repos.length === 0 ? (
          <div className="git-card text-center py-12">
            <GitBranch className="w-16 h-16 mx-auto text-muted-foreground mb-4" strokeWidth={1.5} />
            <h3 className="font-semibold text-lg mb-2">No Repositories</h3>
            <p className="text-sm text-muted-foreground mb-4">Add your first repository to get started</p>
            <Button onClick={() => setShowAddDialog(true)} className="btn-primary">
              <Plus className="w-4 h-4 mr-2" />
              Add Repository
            </Button>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {repos.map((repo) => (
              <div key={repo.id} className="git-card">
                <div className="flex items-start justify-between mb-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <h3 className="text-xl font-bold font-mono">{repo.name}</h3>
                      {repo.is_local && (
                        <span className="status-badge info">LOCAL</span>
                      )}
                    </div>
                    <p className="text-sm text-muted-foreground font-mono mb-2">{repo.url}</p>
                    <div className="flex items-center gap-2">
                      <span className="status-badge success">{repo.provider}</span>
                      <span className="status-badge pending">{repo.auth_type}</span>
                      <span className="text-xs text-muted-foreground">• {repo.default_branch}</span>
                    </div>
                  </div>
                  <button
                    onClick={() => handleDeleteRepo(repo.id)}
                    data-testid={`delete-repo-${repo.id}`}
                    className="text-red-500 hover:text-red-400 p-2"
                  >
                    <Trash2 className="w-5 h-5" strokeWidth={1.5} />
                  </button>
                </div>

                <div className="grid grid-cols-3 gap-2">
                  <button
                    onClick={() => openOperationDialog(repo, 'create_branch')}
                    data-testid={`create-branch-${repo.id}`}
                    className="btn-secondary flex items-center justify-center gap-2 py-3"
                  >
                    <GitBranch className="w-4 h-4" />
                    <span className="text-xs">Branch</span>
                  </button>
                  <button
                    onClick={() => openOperationDialog(repo, 'push')}
                    data-testid={`push-${repo.id}`}
                    className="btn-secondary flex items-center justify-center gap-2 py-3"
                  >
                    <Upload className="w-4 h-4" />
                    <span className="text-xs">Push</span>
                  </button>
                  <button
                    onClick={() => openOperationDialog(repo, 'merge')}
                    data-testid={`merge-${repo.id}`}
                    className="btn-primary flex items-center justify-center gap-2 py-3"
                  >
                    <GitMerge className="w-4 h-4" />
                    <span className="text-xs">Merge</span>
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Operation Dialog */}
      <Dialog open={showOperationDialog} onOpenChange={setShowOperationDialog}>
        <DialogContent className="bg-card border-border">
          <DialogHeader>
            <DialogTitle className="font-mono">
              {operationType === 'create_branch' && 'Create Branch'}
              {operationType === 'push' && 'Push Changes'}
              {operationType === 'merge' && 'Merge Branches'}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            {operationType === 'create_branch' && (
              <>
                <div>
                  <Label>Branch Name</Label>
                  <Input
                    data-testid="branch-name-input"
                    value={operationData.branch_name}
                    onChange={(e) => setOperationData({ ...operationData, branch_name: e.target.value })}
                    placeholder="feature/new-feature"
                    className="mt-1"
                  />
                </div>
                <div>
                  <Label>Base Branch (optional)</Label>
                  <Input
                    data-testid="base-branch-input"
                    value={operationData.base_branch}
                    onChange={(e) => setOperationData({ ...operationData, base_branch: e.target.value })}
                    placeholder="main"
                    className="mt-1"
                  />
                </div>
              </>
            )}
            {operationType === 'push' && (
              <>
                <div>
                  <Label>Branch Name</Label>
                  <Input
                    data-testid="push-branch-input"
                    value={operationData.branch_name}
                    onChange={(e) => setOperationData({ ...operationData, branch_name: e.target.value })}
                    placeholder="feature/new-feature"
                    className="mt-1"
                  />
                </div>
                <div>
                  <Label>Commit Message</Label>
                  <Input
                    data-testid="commit-message-input"
                    value={operationData.commit_message}
                    onChange={(e) => setOperationData({ ...operationData, commit_message: e.target.value })}
                    placeholder="Auto commit"
                    className="mt-1"
                  />
                </div>
              </>
            )}
            {operationType === 'merge' && (
              <>
                <div>
                  <Label>Source Branch</Label>
                  <Input
                    data-testid="source-branch-input"
                    value={operationData.source_branch}
                    onChange={(e) => setOperationData({ ...operationData, source_branch: e.target.value })}
                    placeholder="feature/new-feature"
                    className="mt-1"
                  />
                </div>
                <div>
                  <Label>Target Branch</Label>
                  <Input
                    data-testid="target-branch-input"
                    value={operationData.target_branch}
                    onChange={(e) => setOperationData({ ...operationData, target_branch: e.target.value })}
                    placeholder="main"
                    className="mt-1"
                  />
                </div>
              </>
            )}
            <Button
              data-testid="execute-operation-btn"
              onClick={handleOperation}
              className="btn-primary w-full"
            >
              Execute
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default Repositories;
