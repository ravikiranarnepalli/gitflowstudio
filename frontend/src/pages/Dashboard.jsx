import React, { useState, useEffect } from 'react';
import { GitBranch, GitPullRequest, GitMerge, Rocket, Activity } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const Dashboard = () => {
  const navigate = useNavigate();
  const [repos, setRepos] = useState([]);
  const [recentOps, setRecentOps] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [reposRes, opsRes] = await Promise.all([
        axios.get(`${API}/repos`),
        axios.get(`${API}/operations`)
      ]);
      setRepos(reposRes.data);
      setRecentOps(opsRes.data.slice(0, 5));
    } catch (error) {
      console.error('Error fetching data:', error);
    } finally {
      setLoading(false);
    }
  };

  const quickActions = [
    {
      title: 'Create Branch',
      icon: GitBranch,
      color: 'text-primary',
      description: 'Create a new branch from main',
      action: () => navigate('/repositories')
    },
    {
      title: 'Push Changes',
      icon: GitPullRequest,
      color: 'text-blue-500',
      description: 'Push commits to remote',
      action: () => navigate('/repositories')
    },
    {
      title: 'Merge Branch',
      icon: GitMerge,
      color: 'text-amber-500',
      description: 'Merge branch to main',
      action: () => navigate('/repositories')
    },
    {
      title: 'Deploy',
      icon: Rocket,
      color: 'text-red-500',
      description: 'Deploy to production',
      action: () => navigate('/deployment')
    },
  ];

  const getStatusColor = (status) => {
    switch (status) {
      case 'success': return 'text-primary';
      case 'failed': return 'text-red-500';
      case 'pending': return 'text-amber-500';
      default: return 'text-muted-foreground';
    }
  };

  return (
    <div className="h-full bg-background">
      {/* Header */}
      <div className="border-b border-border bg-card/50 backdrop-blur-md">
        <div className="container mx-auto px-12 py-6">
          <h1 className="text-4xl font-bold font-mono tracking-tight">Dashboard</h1>
          <p className="text-sm text-muted-foreground mt-1">Manage your Git operations and deployments</p>
        </div>
      </div>

      <div className="container mx-auto px-12 py-8">
        {/* Stats */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          <div className="git-card">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-muted-foreground uppercase tracking-widest mb-1">Total Repos</p>
                <p className="text-3xl font-bold font-mono">{repos.length}</p>
              </div>
              <div className="w-12 h-12 rounded-lg bg-primary/10 flex items-center justify-center">
                <GitBranch className="w-6 h-6 text-primary" strokeWidth={1.5} />
              </div>
            </div>
          </div>

          <div className="git-card">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-muted-foreground uppercase tracking-widest mb-1">Operations</p>
                <p className="text-3xl font-bold font-mono">{recentOps.length}</p>
              </div>
              <div className="w-12 h-12 rounded-lg bg-blue-500/10 flex items-center justify-center">
                <Activity className="w-6 h-6 text-blue-500" strokeWidth={1.5} />
              </div>
            </div>
          </div>

          <div className="git-card">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-muted-foreground uppercase tracking-widest mb-1">Success Rate</p>
                <p className="text-3xl font-bold font-mono">
                  {recentOps.length > 0
                    ? Math.round((recentOps.filter(op => op.status === 'success').length / recentOps.length) * 100)
                    : 0}%
                </p>
              </div>
              <div className="w-12 h-12 rounded-lg bg-primary/10 flex items-center justify-center">
                <Rocket className="w-6 h-6 text-primary" strokeWidth={1.5} />
              </div>
            </div>
          </div>
        </div>

        {/* Quick Actions */}
        <div className="mb-8">
          <h2 className="text-2xl font-semibold font-mono mb-4">Quick Actions</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {quickActions.map((action, index) => {
              const Icon = action.icon;
              return (
                <button
                  key={index}
                  onClick={action.action}
                  data-testid={`quick-action-${action.title.toLowerCase().replace(' ', '-')}`}
                  className="git-card text-left group cursor-pointer"
                >
                  <div className="flex items-start gap-4">
                    <div className={`w-10 h-10 rounded-lg bg-accent flex items-center justify-center ${action.color}`}>
                      <Icon className="w-5 h-5" strokeWidth={1.5} />
                    </div>
                    <div className="flex-1">
                      <h3 className="font-semibold text-foreground group-hover:text-primary transition-colors">
                        {action.title}
                      </h3>
                      <p className="text-sm text-muted-foreground mt-1">{action.description}</p>
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Recent Operations */}
        <div>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-2xl font-semibold font-mono">Recent Operations</h2>
            <button
              onClick={() => navigate('/operations')}
              data-testid="view-all-operations"
              className="text-sm text-primary hover:text-primary/80 font-medium"
            >
              View All →
            </button>
          </div>

          {loading ? (
            <div className="git-card text-center py-12">
              <div className="animate-pulse">
                <Activity className="w-8 h-8 mx-auto text-muted-foreground mb-2" />
                <p className="text-muted-foreground">Loading operations...</p>
              </div>
            </div>
          ) : recentOps.length === 0 ? (
            <div className="git-card text-center py-12">
              <Activity className="w-12 h-12 mx-auto text-muted-foreground mb-3" strokeWidth={1.5} />
              <h3 className="font-semibold text-lg mb-1">No Operations Yet</h3>
              <p className="text-sm text-muted-foreground">Start by creating a branch or pushing changes</p>
            </div>
          ) : (
            <div className="space-y-3">
              {recentOps.map((op) => (
                <div key={op.id} className="git-card flex items-center justify-between">
                  <div className="flex items-center gap-4 flex-1">
                    <div className={`w-10 h-10 rounded-lg bg-accent flex items-center justify-center ${getStatusColor(op.status)}`}>
                      {op.operation_type === 'create_branch' && <GitBranch className="w-5 h-5" strokeWidth={1.5} />}
                      {op.operation_type === 'push' && <GitPullRequest className="w-5 h-5" strokeWidth={1.5} />}
                      {op.operation_type === 'merge' && <GitMerge className="w-5 h-5" strokeWidth={1.5} />}
                      {op.operation_type === 'deploy' && <Rocket className="w-5 h-5" strokeWidth={1.5} />}
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-3">
                        <h3 className="font-semibold font-mono">{op.operation_type.replace('_', ' ').toUpperCase()}</h3>
                        {op.branch_name && (
                          <span className="text-sm text-muted-foreground font-mono">• {op.branch_name}</span>
                        )}
                      </div>
                      <p className="text-sm text-muted-foreground mt-1">{op.message}</p>
                    </div>
                  </div>
                  <span className={`status-badge ${op.status}`}>{op.status}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
