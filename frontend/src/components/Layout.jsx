import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { GitBranch, Database, Activity, Settings, Code } from 'lucide-react';

const Layout = ({ children }) => {
  const location = useLocation();

  const navItems = [
    { path: '/', label: 'Dashboard', icon: Code },
    { path: '/repositories', label: 'Repositories', icon: Database },
    { path: '/operations', label: 'Operations', icon: Activity },
    { path: '/deployment', label: 'Deployment', icon: Settings },
  ];

  const isActive = (path) => location.pathname === path;

  return (
    <div className="flex h-screen bg-background">
      {/* Sidebar */}
      <aside className="w-64 bg-card border-r border-border flex flex-col">
        <div className="p-6 border-b border-border">
          <div className="flex items-center gap-3">
            <GitBranch className="w-8 h-8 text-primary" strokeWidth={1.5} />
            <h1 className="text-xl font-bold font-mono tracking-tight">SourceCtrl</h1>
          </div>
          <p className="text-xs text-muted-foreground mt-1 uppercase tracking-widest">Git Flow Manager</p>
        </div>

        <nav className="flex-1 p-4">
          <ul className="space-y-2">
            {navItems.map((item) => {
              const Icon = item.icon;
              return (
                <li key={item.path}>
                  <Link
                    to={item.path}
                    data-testid={`nav-${item.label.toLowerCase()}`}
                    className={`flex items-center gap-3 px-4 py-3 rounded-md transition-all duration-200 ${
                      isActive(item.path)
                        ? 'bg-primary/10 text-primary border border-primary/20'
                        : 'text-muted-foreground hover:bg-accent hover:text-foreground'
                    }`}
                  >
                    <Icon className="w-5 h-5" strokeWidth={1.5} />
                    <span className="font-medium text-sm">{item.label}</span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>

        <div className="p-4 border-t border-border">
          <div className="px-4 py-3 bg-accent/50 rounded-md">
            <p className="text-xs text-muted-foreground uppercase tracking-widest mb-1">Status</p>
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 bg-primary rounded-full animate-pulse"></div>
              <span className="text-sm font-mono font-medium">Connected</span>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-auto">
        <div className="h-full">
          {children}
        </div>
      </main>
    </div>
  );
};

export default Layout;
