import React, { useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Shield, RefreshCw, Upload, BarChart3, Bell, LogOut } from 'lucide-react';
import { getHealth } from '../../api/client';
import { ThemeToggle } from '../ui/ThemeToggle';
import { Button } from '../ui/Button';
import { Badge } from '../ui/Badge';
import { useDataset } from '../../context/DatasetContext';
import { useCurrency } from '../../context/CurrencyContext';
import { useAuth } from '../../context/AuthContext';

export const Header = ({ onRefreshAll, isRefreshing, activeTab, setActiveTab }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const { hasDataset, datasets, activeDatasetId, selectDataset } = useDataset();
  const { currency, setCurrency } = useCurrency();
  const { user, organization, signOut } = useAuth();
  const isInsightsPage = location.pathname === '/insights';

  const [backendOnline, setBackendOnline] = useState(null);

  const checkHealth = async () => {
    try {
      const res = await getHealth();
      setBackendOnline(res?.status === 'ok');
    } catch {
      setBackendOnline(false);
    }
  };

  useEffect(() => {
    checkHealth();
    const interval = setInterval(checkHealth, 15000);
    return () => clearInterval(interval);
  }, []);

  return (
    <header className="sticky top-0 z-40 w-full border-b border-th-border bg-th-surface/95 backdrop-blur-md">
      <div className="px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">

          {/* Logo */}
          <div
            onClick={() => navigate('/')}
            className="flex items-center space-x-3 cursor-pointer group"
          >
            <div className="w-8 h-8 rounded-lg bg-th-brand flex items-center justify-center text-white shadow-soft group-hover:bg-th-brand-hover transition-colors">
              <Shield className="w-4 h-4" />
            </div>
            <div className="flex items-center gap-2">
              <span className="text-lg font-semibold text-th-text-primary font-serif tracking-tight">
                CyberRisk
              </span>
              {hasDataset && isInsightsPage && (
                <Badge variant="brand" className="hidden sm:inline-flex text-[10px] py-0 px-1.5 font-normal">
                  Active Run
                </Badge>
              )}
            </div>
          </div>

          {/* Right actions: Currency Toggle + Theme toggle + Upload New + Refresh Report */}
          <div className="flex items-center space-x-2.5">
            {/* Active dataset selector */}
            {isInsightsPage && datasets.length > 1 && (
              <select
                value={activeDatasetId || ''}
                onChange={(e) => selectDataset(e.target.value)}
                className="hidden lg:block max-w-[180px] px-2 py-1 text-xs bg-th-surface border border-th-border rounded-lg text-th-text-primary focus:outline-none focus:ring-2 focus:ring-th-brand"
                title="Switch active dataset"
              >
                {datasets.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name}
                  </option>
                ))}
              </select>
            )}

            {/* Currency USD | INR Toggle */}
            <div className="flex items-center rounded-lg border border-th-border bg-th-surface-el p-0.5 text-xs font-mono font-medium shadow-soft">
              <button
                type="button"
                onClick={() => setCurrency('USD')}
                className={`px-2 py-0.5 rounded-md transition-colors ${
                  currency === 'USD'
                    ? 'bg-th-surface text-th-brand font-bold shadow-soft'
                    : 'text-th-text-muted hover:text-th-text-primary'
                }`}
                title="Switch to USD ($)"
              >
                USD
              </button>
              <button
                type="button"
                onClick={() => setCurrency('INR')}
                className={`px-2 py-0.5 rounded-md transition-colors ${
                  currency === 'INR'
                    ? 'bg-th-surface text-th-brand font-bold shadow-soft'
                    : 'text-th-text-muted hover:text-th-text-primary'
                }`}
                title="Switch to INR (₹)"
              >
                INR
              </button>
            </div>

            <ThemeToggle />

            <Button
              variant="secondary"
              size="sm"
              onClick={() => navigate('/alerts')}
              title="Risk alerts"
              className="text-xs font-medium gap-1.5"
            >
              <Bell className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Alerts</span>
            </Button>

            {organization?.name && (
              <Badge variant="default" className="hidden xl:inline-flex max-w-[160px]" title={organization.name}>
                <span className="truncate">{organization.name}</span>
              </Badge>
            )}

            <button
              type="button"
              onClick={signOut}
              title={user?.email ? `Sign out ${user.email}` : 'Sign out'}
              className="p-2 rounded-full text-th-text-muted hover:text-th-danger hover:bg-th-surface-el transition-colors"
            >
              <LogOut className="w-4 h-4" />
            </button>

            {isInsightsPage ? (
              <>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => navigate('/')}
                  title="Upload another dataset"
                  className="hidden sm:inline-flex text-xs font-medium gap-1.5"
                >
                  <Upload className="w-3.5 h-3.5" />
                  <span>Upload New</span>
                </Button>

                {onRefreshAll && (
                  <Button
                    onClick={onRefreshAll}
                    isLoading={isRefreshing}
                    size="sm"
                    title="Refresh Portfolio Risk Data"
                  >
                    {!isRefreshing && <RefreshCw className="w-3.5 h-3.5 mr-1.5" />}
                    Refresh Report
                  </Button>
                )}
              </>
            ) : (
              hasDataset && (
                <Button
                  size="sm"
                  onClick={() => navigate('/insights')}
                  className="font-medium gap-1.5"
                >
                  <BarChart3 className="w-3.5 h-3.5" />
                  <span>View Insights</span>
                </Button>
              )
            )}
          </div>

        </div>
      </div>
    </header>
  );
};
