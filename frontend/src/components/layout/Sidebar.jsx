import React from 'react';
import {
  BarChart3,
  Server,
  Award,
  FileCheck,
  Zap,
  Share2,
  Lock,
  ChevronLeft,
  ChevronRight,
  Cpu,
} from 'lucide-react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useDataset } from '../../context/DatasetContext';

const navItems = [
  { id: 'overview',   label: 'Executive Overview',  icon: BarChart3 },
  { id: 'assets',     label: 'Asset Portfolio',      icon: Server    },
  { id: 'forecasting',label: 'LSTM Threat Forecast', icon: Cpu       },
  { id: 'graph',      label: 'Systemic Risk',        icon: Share2    },
  { id: 'controls',   label: 'Controls',             icon: Award     },
  { id: 'compliance', label: 'Compliance',           icon: FileCheck },
  { id: 'optimizer',  label: 'Investment Optimizer', icon: Zap       },
];

export const Sidebar = ({ activeTab, setActiveTab, isOpen, onToggle }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const { hasDataset } = useDataset();
  const isInsightsPage = location.pathname === '/insights';

  const handleNavClick = (tabId) => {
    if (!hasDataset && !isInsightsPage) return;
    if (!isInsightsPage) navigate('/insights');
    if (setActiveTab) setActiveTab(tabId);
  };

  return (
    <>
      {/* Sidebar panel */}
      <aside
        style={{ width: isOpen ? '14rem' : '3.5rem' }}
        className="fixed top-16 left-0 h-[calc(100vh-4rem)] z-30 bg-th-surface border-r border-th-border flex flex-col transition-all duration-300 ease-in-out overflow-hidden"
      >
        {/* Toggle collapse button */}
        <button
          onClick={onToggle}
          title={isOpen ? 'Collapse sidebar' : 'Expand sidebar'}
          className="flex items-center h-10 mt-3 mb-2 mx-2 px-2 rounded-lg text-th-text-muted hover:text-th-brand hover:bg-th-surface-el transition-colors"
        >
          {isOpen ? (
            <>
              <span className="flex-1 text-xs font-semibold uppercase tracking-widest text-th-text-muted text-left">
                Navigation
              </span>
              <ChevronLeft className="w-4 h-4 flex-shrink-0" />
            </>
          ) : (
            <ChevronRight className="w-4 h-4 mx-auto" />
          )}
        </button>

        <nav className="flex flex-col gap-1 px-2 flex-1">
          {navItems.map((tab) => {
            const Icon = tab.icon;
            const isActive   = isInsightsPage && activeTab === tab.id;
            const isDisabled = !hasDataset && !isInsightsPage;

            return (
              <button
                key={tab.id}
                disabled={isDisabled}
                onClick={() => handleNavClick(tab.id)}
                title={tab.label}
                className={`
                  flex items-center gap-3 px-2 py-2.5 rounded-lg text-sm font-medium
                  transition-all duration-200 w-full text-left whitespace-nowrap
                  ${isActive
                    ? 'bg-th-brand-tint text-th-brand'
                    : isDisabled
                    ? 'text-th-text-muted/50 opacity-50 cursor-not-allowed'
                    : 'text-th-text-secondary hover:text-th-text-primary hover:bg-th-surface-el cursor-pointer'
                  }
                `}
              >
                {isDisabled ? (
                  <Lock className="w-4 h-4 flex-shrink-0 text-th-text-muted/40" />
                ) : (
                  <Icon
                    className={`w-4 h-4 flex-shrink-0 ${isActive ? 'text-th-brand' : 'text-th-text-muted'}`}
                  />
                )}
                {isOpen && (
                  <span className="truncate leading-tight">{tab.label}</span>
                )}
              </button>
            );
          })}
        </nav>
      </aside>

      {/* Invisible spacer so the flex layout pushes content right */}
      <div
        style={{ width: isOpen ? '14rem' : '3.5rem' }}
        className="flex-shrink-0 transition-all duration-300"
        aria-hidden="true"
      />
    </>
  );
};
