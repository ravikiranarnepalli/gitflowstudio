import React, { useState, useEffect } from 'react';
import { Plus, Rocket, Trash2, Server, HardDrive, Edit, Eye, FileText, Folder, X } from 'lucide-react';
import axios from 'axios';
import { toast } from 'sonner';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const DeploymentConfig = () => {
  const [repos, setRepos] = useState([]);
  const [configs, setConfigs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [testingFTP, setTestingFTP] = useState(false);
  const [deployingId, setDeployingId] = useState(null);
  const [editingConfig, setEditingConfig] = useState(null);
  const [previewingId, setPreviewingId] = useState(null);
  const [previewData, setPreviewData] = useState(null);
  const [showPreviewDialog, setShowPreviewDialog] = useState(false);

  const [newConfig, setNewConfig] = useState({
    repo_id: '',
    deploy_type: 'ftp',
    project_type: 'react',
    config: {
      host: '',
      username: '',
      password: '',
      path: '/',
      use_tls: false
    }
  });

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [reposRes, configsRes] = await Promise.all([
        axios.get(`${API}/repos`),
        axios.get(`${API}/deployment-configs`)
      ]);
      setRepos(reposRes.data);
      setConfigs(configsRes.data);
    } catch (error) {
      console.error('Error fetching data:', error);
      toast.error('Failed to fetch data');
    } finally {
      setLoading(false);
    }
  };

  const handleAddConfig = async () => {
    try {
      if (editingConfig) {
        // Update existing config
        await axios.put(`${API}/deployment-configs/${editingConfig.id}`, newConfig);
        toast.success('Deployment config updated successfully');
      } else {
        // Create new config
        await axios.post(`${API}/deployment-configs`, newConfig);
        toast.success('Deployment config added successfully');
      }
      setShowAddDialog(false);
      setEditingConfig(null);
      fetchData();
      setNewConfig({
        repo_id: '',
        deploy_type: 'ftp',
        project_type: 'react',
        config: {
          host: '',
          username: '',
          password: '',
          path: '/',
          use_tls: false
        }
      });
    } catch (error) {
      console.error('Error saving config:', error);
      toast.error(error.response?.data?.detail || 'Failed to save deployment config');
    }
  };

  const handleEditConfig = (config) => {
    setEditingConfig(config);
    setNewConfig({
      repo_id: config.repo_id,
      deploy_type: config.deploy_type,
      project_type: config.project_type || 'static',
      config: config.config
    });
    setShowAddDialog(true);
  };

  const handleTestFTP = async () => {
    if (!newConfig.config.host || !newConfig.config.username || !newConfig.config.password) {
      toast.error('Please fill in all FTP credentials');
      return;
    }

    setTestingFTP(true);
    try {
      const response = await axios.post(`${API}/test-ftp-connection`, {
        host: newConfig.config.host,
        username: newConfig.config.username,
        password: newConfig.config.password,
        use_tls: newConfig.config.use_tls
      });

      if (response.data.success) {
        toast.success(response.data.message);
      } else {
        toast.error(response.data.message);
      }
    } catch (error) {
      console.error('Error testing FTP:', error);
      toast.error('FTP connection test failed');
    } finally {
      setTestingFTP(false);
    }
  };

  const handleDeleteConfig = async (configId) => {
    if (!window.confirm('Are you sure you want to delete this deployment config?')) return;
    
    try {
      await axios.delete(`${API}/deployment-configs/${configId}`);
      toast.success('Deployment config deleted successfully');
      fetchData();
    } catch (error) {
      console.error('Error deleting config:', error);
      toast.error('Failed to delete deployment config');
    }
  };

  const handleDeploy = async (config) => {
    setDeployingId(config.id);
    toast.loading('Starting deployment...', { id: 'deploy-toast' });
    
    try {
      const response = await axios.post(`${API}/repos/${config.repo_id}/deploy`, {});
      toast.success(response.data.message, { id: 'deploy-toast' });
      
      // Refresh operations to show deployment status
      setTimeout(() => {
        window.location.href = '/operations';
      }, 1500);
    } catch (error) {
      console.error('Error deploying:', error);
      toast.error(error.response?.data?.detail || 'Deployment failed', { id: 'deploy-toast' });
    } finally {
      setDeployingId(null);
    }
  };

  const handlePreview = async (config) => {
    setPreviewingId(config.id);
    toast.loading('Generating deployment preview...', { id: 'preview-toast' });
    
    try {
      const response = await axios.post(`${API}/repos/${config.repo_id}/preview-deploy`, {});
      setPreviewData(response.data.preview);
      setShowPreviewDialog(true);
      toast.success('Preview generated!', { id: 'preview-toast' });
    } catch (error) {
      console.error('Error generating preview:', error);
      toast.error(error.response?.data?.detail || 'Failed to generate preview', { id: 'preview-toast' });
    } finally {
      setPreviewingId(null);
    }
  };

  const getRepoName = (repoId) => {
    const repo = repos.find(r => r.id === repoId);
    return repo ? repo.name : 'Unknown';
  };

  return (
    <div className="h-full bg-background">
      {/* Header */}
      <div className="border-b border-border bg-card/50 backdrop-blur-md">
        <div className="container mx-auto px-12 py-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-4xl font-bold font-mono tracking-tight">Deployment</h1>
              <p className="text-sm text-muted-foreground mt-1">Configure deployment targets</p>
            </div>
            <Dialog open={showAddDialog} onOpenChange={(open) => {
              setShowAddDialog(open);
              if (!open) {
                setEditingConfig(null);
                setNewConfig({
                  repo_id: '',
                  deploy_type: 'ftp',
                  project_type: 'react',
                  config: {
                    host: '',
                    username: '',
                    password: '',
                    path: '/',
                    use_tls: false
                  }
                });
              }
            }}>
              <DialogTrigger asChild>
                <Button data-testid="add-deployment-btn" className="btn-primary flex items-center gap-2">
                  <Plus className="w-4 h-4" />
                  Add Deployment
                </Button>
              </DialogTrigger>
              <DialogContent className="bg-card border-border max-h-[90vh] overflow-y-auto">
                <DialogHeader>
                  <DialogTitle className="font-mono">
                    {editingConfig ? 'Edit Deployment Config' : 'Add Deployment Config'}
                  </DialogTitle>
                </DialogHeader>
                <div className="space-y-4">
                  <div>
                    <Label>Repository</Label>
                    <Select
                      value={newConfig.repo_id}
                      onValueChange={(val) => setNewConfig({ ...newConfig, repo_id: val })}
                    >
                      <SelectTrigger data-testid="repo-select" className="mt-1">
                        <SelectValue placeholder="Select repository" />
                      </SelectTrigger>
                      <SelectContent>
                        {repos.map(repo => (
                          <SelectItem key={repo.id} value={repo.id}>{repo.name}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label>Deployment Type</Label>
                    <Select
                      value={newConfig.deploy_type}
                      onValueChange={(val) => setNewConfig({ ...newConfig, deploy_type: val })}
                    >
                      <SelectTrigger data-testid="deploy-type-select" className="mt-1">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="ftp">FTP</SelectItem>
                        <SelectItem value="cpanel">cPanel</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label>Project Type</Label>
                    <Select
                      value={newConfig.project_type}
                      onValueChange={(val) => setNewConfig({ ...newConfig, project_type: val })}
                    >
                      <SelectTrigger data-testid="project-type-select" className="mt-1">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="react">React (build → deploy build/)</SelectItem>
                        <SelectItem value="angular">Angular (build → deploy dist/)</SelectItem>
                        <SelectItem value="vue">Vue.js (build → deploy dist/)</SelectItem>
                        <SelectItem value="nextjs">Next.js (build → deploy .next/)</SelectItem>
                        <SelectItem value="nodejs">Node.js (exclude node_modules)</SelectItem>
                        <SelectItem value="python">Python (exclude venv)</SelectItem>
                        <SelectItem value="static">Static HTML/CSS/JS</SelectItem>
                      </SelectContent>
                    </Select>
                    <p className="text-xs text-muted-foreground mt-1">
                      Frontend projects will be built automatically before deployment
                    </p>
                  </div>

                  {newConfig.deploy_type === 'ftp' && (
                    <>
                      <div>
                        <Label>FTP Host</Label>
                        <Input
                          data-testid="ftp-host-input"
                          value={newConfig.config.host}
                          onChange={(e) => setNewConfig({
                            ...newConfig,
                            config: { ...newConfig.config, host: e.target.value }
                          })}
                          placeholder="ftp.example.com"
                          className="mt-1"
                        />
                      </div>
                      <div>
                        <Label>Username</Label>
                        <Input
                          data-testid="ftp-username-input"
                          value={newConfig.config.username}
                          onChange={(e) => setNewConfig({
                            ...newConfig,
                            config: { ...newConfig.config, username: e.target.value }
                          })}
                          placeholder="username"
                          className="mt-1"
                        />
                      </div>
                      <div>
                        <Label>Password</Label>
                        <Input
                          data-testid="ftp-password-input"
                          type="password"
                          value={newConfig.config.password}
                          onChange={(e) => setNewConfig({
                            ...newConfig,
                            config: { ...newConfig.config, password: e.target.value }
                          })}
                          placeholder="••••••••"
                          className="mt-1"
                        />
                      </div>
                      <div>
                        <Label>Remote Path</Label>
                        <Input
                          data-testid="ftp-path-input"
                          value={newConfig.config.path}
                          onChange={(e) => setNewConfig({
                            ...newConfig,
                            config: { ...newConfig.config, path: e.target.value }
                          })}
                          placeholder="/public_html"
                          className="mt-1"
                        />
                      </div>
                      <div className="flex items-center gap-2">
                        <input
                          type="checkbox"
                          id="use-tls"
                          data-testid="use-tls-checkbox"
                          checked={newConfig.config.use_tls}
                          onChange={(e) => setNewConfig({
                            ...newConfig,
                            config: { ...newConfig.config, use_tls: e.target.checked }
                          })}
                          className="w-4 h-4"
                        />
                        <Label htmlFor="use-tls">Use TLS/SSL</Label>
                      </div>
                    </>
                  )}

                  {newConfig.deploy_type === 'cpanel' && (
                    <>
                      <div>
                        <Label>cPanel Host</Label>
                        <Input
                          data-testid="cpanel-host-input"
                          value={newConfig.config.host}
                          onChange={(e) => setNewConfig({
                            ...newConfig,
                            config: { ...newConfig.config, host: e.target.value }
                          })}
                          placeholder="cpanel.example.com"
                          className="mt-1"
                        />
                      </div>
                      <div>
                        <Label>Username</Label>
                        <Input
                          data-testid="cpanel-username-input"
                          value={newConfig.config.username}
                          onChange={(e) => setNewConfig({
                            ...newConfig,
                            config: { ...newConfig.config, username: e.target.value }
                          })}
                          placeholder="username"
                          className="mt-1"
                        />
                      </div>
                      <div>
                        <Label>API Token</Label>
                        <Input
                          data-testid="cpanel-token-input"
                          type="password"
                          value={newConfig.config.api_token || ''}
                          onChange={(e) => setNewConfig({
                            ...newConfig,
                            config: { ...newConfig.config, api_token: e.target.value }
                          })}
                          placeholder="API Token"
                          className="mt-1"
                        />
                      </div>
                    </>
                  )}

                  {newConfig.deploy_type === 'ftp' && (
                    <div className="flex gap-2">
                      <Button
                        data-testid="test-ftp-btn"
                        onClick={handleTestFTP}
                        disabled={testingFTP || !newConfig.config.host}
                        className="btn-secondary flex-1"
                        type="button"
                      >
                        {testingFTP ? 'Testing...' : 'Test FTP Connection'}
                      </Button>
                      <Button
                        data-testid="save-deployment-btn"
                        onClick={handleAddConfig}
                        className="btn-primary flex-1"
                      >
                        {editingConfig ? 'Update Configuration' : 'Save Configuration'}
                      </Button>
                    </div>
                  )}

                  {newConfig.deploy_type === 'cpanel' && (
                    <Button
                      data-testid="save-deployment-btn"
                      onClick={handleAddConfig}
                      className="btn-primary w-full"
                    >
                      {editingConfig ? 'Update Configuration' : 'Save Configuration'}
                    </Button>
                  )}
                </div>
              </DialogContent>
            </Dialog>
          </div>
        </div>
      </div>

      {/* Deployment Configs */}
      <div className="container mx-auto px-12 py-8">
        {loading ? (
          <div className="text-center py-12">
            <div className="animate-pulse">
              <Rocket className="w-12 h-12 mx-auto text-muted-foreground mb-3" />
              <p className="text-muted-foreground">Loading configurations...</p>
            </div>
          </div>
        ) : configs.length === 0 ? (
          <div className="git-card text-center py-12">
            <Rocket className="w-16 h-16 mx-auto text-muted-foreground mb-4" strokeWidth={1.5} />
            <h3 className="font-semibold text-lg mb-2">No Deployment Configs</h3>
            <p className="text-sm text-muted-foreground mb-4">Add a deployment configuration to get started</p>
            <Button onClick={() => setShowAddDialog(true)} className="btn-primary">
              <Plus className="w-4 h-4 mr-2" />
              Add Deployment
            </Button>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {configs.map((config) => (
              <div key={config.id} className="git-card">
                <div className="flex items-start justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <div className="w-12 h-12 rounded-lg bg-accent flex items-center justify-center">
                      {config.deploy_type === 'ftp' ? (
                        <Server className="w-6 h-6 text-blue-500" strokeWidth={1.5} />
                      ) : (
                        <HardDrive className="w-6 h-6 text-amber-500" strokeWidth={1.5} />
                      )}
                    </div>
                    <div>
                      <h3 className="text-lg font-bold font-mono">{getRepoName(config.repo_id)}</h3>
                      <p className="text-sm text-muted-foreground">{config.config.host}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => handleEditConfig(config)}
                      data-testid={`edit-config-${config.id}`}
                      className="text-primary hover:text-primary/80 p-2"
                      title="Edit configuration"
                    >
                      <Edit className="w-5 h-5" strokeWidth={1.5} />
                    </button>
                    <button
                      onClick={() => handleDeleteConfig(config.id)}
                      data-testid={`delete-config-${config.id}`}
                      className="text-red-500 hover:text-red-400 p-2"
                      title="Delete configuration"
                    >
                      <Trash2 className="w-5 h-5" strokeWidth={1.5} />
                    </button>
                  </div>
                </div>

                <div className="space-y-2 mb-4">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">Type:</span>
                    <span className="status-badge info">{config.deploy_type.toUpperCase()}</span>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">Project:</span>
                    <span className="status-badge success">{(config.project_type || 'static').toUpperCase()}</span>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">Username:</span>
                    <span className="font-mono">{config.config.username}</span>
                  </div>
                  {config.config.path && (
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">Path:</span>
                      <span className="font-mono">{config.config.path}</span>
                    </div>
                  )}
                </div>

                <div className="flex gap-2">
                  <button
                    onClick={() => handlePreview(config)}
                    data-testid={`preview-${config.id}`}
                    disabled={previewingId === config.id}
                    className="btn-secondary flex-1 flex items-center justify-center gap-2"
                  >
                    <Eye className="w-4 h-4" />
                    {previewingId === config.id ? 'Loading...' : 'Preview'}
                  </button>
                  <button
                    onClick={() => handleDeploy(config)}
                    data-testid={`deploy-${config.id}`}
                    disabled={deployingId === config.id}
                    className="btn-primary flex-1 flex items-center justify-center gap-2"
                  >
                    <Rocket className="w-4 h-4" />
                    {deployingId === config.id ? 'Deploying...' : 'Deploy'}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Preview Dialog */}
      <Dialog open={showPreviewDialog} onOpenChange={setShowPreviewDialog}>
        <DialogContent className="bg-card border-border max-w-4xl max-h-[85vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle className="font-mono flex items-center gap-2">
              <Eye className="w-5 h-5" />
              Deployment Preview
            </DialogTitle>
          </DialogHeader>
          
          {previewData && (
            <div className="flex-1 overflow-hidden flex flex-col">
              {/* Summary Stats */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                <div className="bg-accent/50 rounded-lg p-3 text-center">
                  <div className="text-2xl font-bold text-primary">{previewData.total_files}</div>
                  <div className="text-xs text-muted-foreground">Total Files</div>
                </div>
                <div className="bg-accent/50 rounded-lg p-3 text-center">
                  <div className="text-2xl font-bold text-blue-400">{previewData.total_size}</div>
                  <div className="text-xs text-muted-foreground">Total Size</div>
                </div>
                <div className="bg-accent/50 rounded-lg p-3 text-center">
                  <div className="text-2xl font-bold text-green-400">{previewData.directories?.length || 0}</div>
                  <div className="text-xs text-muted-foreground">Directories</div>
                </div>
                <div className="bg-accent/50 rounded-lg p-3 text-center">
                  <div className="text-2xl font-bold text-amber-400">{previewData.project_type?.toUpperCase()}</div>
                  <div className="text-xs text-muted-foreground">Project Type</div>
                </div>
              </div>

              {/* Target Info */}
              <div className="bg-accent/30 rounded-lg p-3 mb-4">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Deploy to:</span>
                  <span className="font-mono text-primary">{previewData.target_host}{previewData.target_path}</span>
                </div>
              </div>

              {/* Directories */}
              {previewData.directories && previewData.directories.length > 0 && (
                <div className="mb-4">
                  <h4 className="text-sm font-semibold mb-2 flex items-center gap-2">
                    <Folder className="w-4 h-4 text-amber-400" />
                    Directories to Create ({previewData.directories.length})
                  </h4>
                  <div className="flex flex-wrap gap-2">
                    {previewData.directories.slice(0, 10).map((dir, idx) => (
                      <span key={idx} className="text-xs bg-accent px-2 py-1 rounded font-mono">
                        {dir}
                      </span>
                    ))}
                    {previewData.directories.length > 10 && (
                      <span className="text-xs text-muted-foreground">
                        +{previewData.directories.length - 10} more
                      </span>
                    )}
                  </div>
                </div>
              )}

              {/* Files List */}
              <div className="flex-1 overflow-hidden flex flex-col">
                <h4 className="text-sm font-semibold mb-2 flex items-center gap-2">
                  <FileText className="w-4 h-4 text-blue-400" />
                  Files to Upload ({previewData.files?.length || 0})
                </h4>
                <div className="flex-1 overflow-y-auto bg-background/50 rounded-lg border border-border">
                  <table className="w-full text-sm">
                    <thead className="sticky top-0 bg-card border-b border-border">
                      <tr>
                        <th className="text-left p-2 font-medium">File Path</th>
                        <th className="text-right p-2 font-medium w-24">Size</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/50">
                      {previewData.files?.map((file, idx) => (
                        <tr key={idx} className="hover:bg-accent/30">
                          <td className="p-2 font-mono text-xs truncate max-w-md" title={file.path}>
                            {file.path}
                          </td>
                          <td className="p-2 text-right text-xs text-muted-foreground">
                            {file.size}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex gap-3 mt-4 pt-4 border-t border-border">
                <Button
                  onClick={() => setShowPreviewDialog(false)}
                  className="btn-secondary flex-1"
                >
                  Cancel
                </Button>
                <Button
                  onClick={() => {
                    setShowPreviewDialog(false);
                    const config = configs.find(c => c.repo_id === previewData.repo_id) || configs[0];
                    if (config) handleDeploy(config);
                  }}
                  className="btn-primary flex-1 flex items-center justify-center gap-2"
                >
                  <Rocket className="w-4 h-4" />
                  Deploy Now
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default DeploymentConfig;
