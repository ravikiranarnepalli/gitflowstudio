import React, { useState, useEffect } from 'react';
import { Activity, GitBranch, GitPullRequest, GitMerge, Rocket, RefreshCw } from 'lucide-react';
import axios from 'axios';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const Operations = () => {
  const [operations, setOperations] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchOperations();
  }, []);

  const fetchOperations = async () => {
    try {
      const response = await axios.get(`${API}/operations`);
      setOperations(response.data);
    } catch (error) {
      console.error('Error fetching operations:', error);
      toast.error('Failed to fetch operations');
    } finally {
      setLoading(false);
    }
  };

  const getOperationIcon = (type) => {
    switch (type) {
      case 'create_branch':
        return GitBranch;
      case 'push':
        return GitPullRequest;
      case 'merge':
        return GitMerge;
      case 'deploy':
        return Rocket;
      default:
        return Activity;
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'success':
        return 'text-primary';
      case 'failed':
        return 'text-red-500';
      case 'pending':
        return 'text-amber-500';
      default:
        return 'text-muted-foreground';
    }
  };

  const formatDate = (dateString) => {
    const date = new Date(dateString);
    return new Intl.DateTimeFormat('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    }).format(date);
  };

  return (
    <div className="h-full bg-background">
      {/* Header */}
      <div className="border-b border-border bg-card/50 backdrop-blur-md">
        <div className="container mx-auto px-12 py-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-4xl font-bold font-mono tracking-tight">Operations</h1>
              <p className="text-sm text-muted-foreground mt-1">Track all your Git operations</p>
            </div>
            <button
              onClick={fetchOperations}
              data-testid="refresh-operations"
              className="btn-secondary flex items-center gap-2"
            >
              <RefreshCw className="w-4 h-4" />
              Refresh
            </button>
          </div>
        </div>
      </div>

      {/* Operations List */}
      <div className="container mx-auto px-12 py-8">
        {loading ? (
          <div className="text-center py-12">
            <div className="animate-pulse">
              <Activity className="w-12 h-12 mx-auto text-muted-foreground mb-3" />
              <p className="text-muted-foreground">Loading operations...</p>
            </div>
          </div>
        ) : operations.length === 0 ? (
          <div className="git-card text-center py-12">
            <Activity className="w-16 h-16 mx-auto text-muted-foreground mb-4" strokeWidth={1.5} />
            <h3 className="font-semibold text-lg mb-2">No Operations Yet</h3>
            <p className="text-sm text-muted-foreground">Start by creating a branch or pushing changes</p>
          </div>
        ) : (
          <div className="space-y-4">
            {operations.map((op) => {
              const Icon = getOperationIcon(op.operation_type);
              return (
                <div key={op.id} data-testid={`operation-${op.id}`} className="git-card">
                  <div className="flex items-start gap-4">
                    <div className={`w-12 h-12 rounded-lg bg-accent flex items-center justify-center flex-shrink-0 ${getStatusColor(op.status)}`}>
                      <Icon className="w-6 h-6" strokeWidth={1.5} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-3 mb-2">
                        <h3 className="text-lg font-semibold font-mono uppercase">
                          {op.operation_type.replace('_', ' ')}
                        </h3>
                        <span className={`status-badge ${op.status}`}>{op.status}</span>
                        {op.branch_name && (
                          <span className="text-sm text-muted-foreground font-mono truncate">
                            • {op.branch_name}
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-muted-foreground mb-2">{op.message}</p>
                      <div className="flex items-center gap-4 text-xs text-muted-foreground">
                        <span>{formatDate(op.created_at)}</span>
                        <span>•</span>
                        <span className="font-mono">{op.repo_id.substring(0, 8)}</span>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

export default Operations;
