import React, { useState, useEffect } from 'react';
import {
  Network,
  Share2,
  ShieldAlert,
  AlertTriangle,
  Server,
  Database,
  Monitor,
  Key,
  Flame,
  ArrowRight,
  Info,
  CheckCircle2,
  TrendingUp,
} from 'lucide-react';
import { Card, CardHeader, CardTitle, CardContent } from '../ui/Card';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';
import { formatCurrency, formatPercent, getDependencyGraph, getRiskPropagation } from '../../api/client';

export const SystemicRiskGraph = () => {
  const [graphData, setGraphData] = useState(null);
  const [propagationData, setPropagationData] = useState(null);
  const [selectedBreachedId, setSelectedBreachedId] = useState('AST-1000');
  const [loading, setLoading] = useState(true);
  const [propLoading, setPropLoading] = useState(false);
  const [error, setError] = useState(null);
  const [filterTier, setFilterTier] = useState('ALL');

  useEffect(() => {
    let unmounted = false;
    setLoading(true);

    getDependencyGraph()
      .then((res) => {
        if (!unmounted) {
          setGraphData(res);
          const initialId = res?.nodes?.[0]?.asset_id || 'AST-1000';
          setSelectedBreachedId(initialId);
          return getRiskPropagation(initialId);
        }
      })
      .then((propRes) => {
        if (!unmounted && propRes) {
          setPropagationData(propRes);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (!unmounted) {
          setError(err.message || 'Failed to load asset dependency graph');
          setLoading(false);
        }
      });

    return () => {
      unmounted = true;
    };
  }, []);

  const handleSelectBreachedAsset = (assetId) => {
    setSelectedBreachedId(assetId);
    setPropLoading(true);
    getRiskPropagation(assetId)
      .then((res) => {
        setPropagationData(res);
        setPropLoading(false);
      })
      .catch((err) => {
        console.error('Error calculating risk propagation:', err);
        setPropLoading(false);
      });
  };

  if (loading) {
    return (
      <Card className="w-full h-96 flex items-center justify-center">
        <div className="flex flex-col items-center text-th-text-secondary">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-th-brand mb-4" />
          <p>Constructing Active Directory asset dependency topology...</p>
        </div>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="w-full h-96 flex items-center justify-center border-red-200 bg-red-50/50">
        <div className="flex flex-col items-center text-red-600">
          <ShieldAlert className="w-8 h-8 mb-4" />
          <p>{error}</p>
        </div>
      </Card>
    );
  }

  const nodes = propagationData?.nodes || graphData?.nodes || [];
  const edges = propagationData?.edges || graphData?.edges || [];
  const initialAsset = propagationData?.initial_breached_asset || {};
  const cascadingEal = propagationData?.cascading_eal_usd || 0;
  const initialEal = propagationData?.initial_eal_usd || 0;
  const amplification = propagationData?.systemic_amplification_factor || 1.0;
  const highRiskCount = propagationData?.high_risk_downstream_count || 0;

  // Group nodes by AD Tier
  const tierMap = {
    0: { label: 'Tier 0: Identity & Domain Controllers', icon: Key, color: 'border-red-500 bg-red-50 dark:bg-red-950/20' },
    1: { label: 'Tier 1: Core Enterprise Databases', icon: Database, color: 'border-amber-500 bg-amber-50 dark:bg-amber-950/20' },
    2: { label: 'Tier 2: Application & Web Microservices', icon: Server, color: 'border-blue-500 bg-blue-50 dark:bg-blue-950/20' },
    3: { label: 'Tier 3: Admin Jump Hosts & Workstations', icon: Monitor, color: 'border-purple-500 bg-purple-50 dark:bg-purple-950/20' },
    4: { label: 'Tier 4: User Endpoints & Workstations', icon: Monitor, color: 'border-slate-400 bg-slate-50 dark:bg-slate-900/40' },
  };

  const getCompromiseBadge = (prob, isBreached) => {
    if (isBreached) {
      return (
        <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-red-600 text-white flex items-center gap-1">
          <Flame className="w-3 h-3" /> Initial Breach
        </span>
      );
    }
    if (prob >= 0.7) {
      return (
        <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-red-100 text-red-700 dark:bg-red-950/50 dark:text-red-400">
          {(prob * 100).toFixed(0)}% Risk
        </span>
      );
    }
    if (prob >= 0.4) {
      return (
        <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-amber-100 text-amber-700 dark:bg-amber-950/50 dark:text-amber-400">
          {(prob * 100).toFixed(0)}% Risk
        </span>
      );
    }
    if (prob > 0.05) {
      return (
        <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-blue-50 text-blue-700 dark:bg-blue-950/40 dark:text-blue-400">
          {(prob * 100).toFixed(0)}% Risk
        </span>
      );
    }
    return (
      <span className="px-1.5 py-0.5 rounded text-[10px] text-th-text-muted">
        Isolated
      </span>
    );
  };

  // Active lateral movement pathways
  const activePaths = edges.filter((e) => e.is_active_path);

  return (
    <div className="space-y-fluid-md animate-in fade-in slide-in-from-bottom-4 duration-500">
      {/* Header Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-th-border pb-4">
        <div>
          <div className="flex items-center space-x-2">
            <Share2 className="w-5 h-5 text-th-brand" />
            <h2 className="text-xl font-semibold text-th-text-primary font-serif">
              Active Directory Asset Dependency &amp; Systemic Lateral Movement Graph
            </h2>
          </div>
          <p className="text-xs text-th-text-secondary mt-1">
            Simulates cascading compromise propagation across trust boundaries, RPC links, and credential vectors.
          </p>
        </div>

        {/* Breached Asset Selector */}
        <div className="flex items-center space-x-2 bg-th-surface p-1.5 rounded-lg border border-th-border shadow-soft">
          <span className="text-xs font-medium text-th-text-secondary pl-2">Select Initial Breach Asset:</span>
          <select
            value={selectedBreachedId}
            onChange={(e) => handleSelectBreachedAsset(e.target.value)}
            className="text-xs font-mono font-semibold bg-th-bg border border-th-border rounded-md px-3 py-1.5 text-th-text-primary focus:outline-none focus:border-th-brand cursor-pointer"
          >
            {nodes.map((n) => (
              <option key={n.asset_id} value={n.asset_id}>
                {n.asset_id} — {n.role} ({n.business_unit})
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Systemic Financial Blast Radius KPI Tiles */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <Card className="p-4 shadow-soft border-l-4 border-l-th-brand">
          <span className="text-xs text-th-text-secondary font-medium">Initial Asset EAL</span>
          <div className="text-xl font-bold font-serif text-th-text-primary mt-1 font-mono">
            {formatCurrency(initialEal)}
          </div>
          <span className="text-[11px] text-th-text-muted mt-1 block">
            Direct standalone loss ({selectedBreachedId})
          </span>
        </Card>

        <Card className="p-4 shadow-soft border-l-4 border-l-red-500 bg-red-50/20 dark:bg-red-950/10">
          <span className="text-xs text-red-700 dark:text-red-400 font-medium flex items-center gap-1">
            <Flame className="w-3.5 h-3.5" /> Total Cascading Exposure
          </span>
          <div className="text-xl font-bold font-serif text-red-700 dark:text-red-400 mt-1 font-mono">
            {formatCurrency(cascadingEal)}
          </div>
          <span className="text-[11px] text-red-600/80 mt-1 block">
            Multi-hop lateral movement blast radius
          </span>
        </Card>

        <Card className="p-4 shadow-soft border-l-4 border-l-amber-500">
          <span className="text-xs text-amber-700 dark:text-amber-400 font-medium flex items-center gap-1">
            <TrendingUp className="w-3.5 h-3.5" /> Systemic Risk Multiplier
          </span>
          <div className="text-xl font-bold font-serif text-amber-700 dark:text-amber-400 mt-1 font-mono">
            {amplification.toFixed(1)}x
          </div>
          <span className="text-[11px] text-th-text-muted mt-1 block">
            Ratio of systemic loss to isolated EAL
          </span>
        </Card>

        <Card className="p-4 shadow-soft border-l-4 border-l-purple-500">
          <span className="text-xs text-purple-700 dark:text-purple-400 font-medium flex items-center gap-1">
            <AlertTriangle className="w-3.5 h-3.5" /> High-Risk Downstream Assets
          </span>
          <div className="text-xl font-bold font-serif text-purple-700 dark:text-purple-400 mt-1 font-mono">
            {highRiskCount} Assets
          </div>
          <span className="text-[11px] text-th-text-muted mt-1 block">
            Nodes with &gt; 40% compromise probability
          </span>
        </Card>
      </div>

      {/* Main Grid: Interactive AD Topology Map + Attack Vectors */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-fluid-md">
        {/* AD Topology Column */}
        <div className="lg:col-span-8 space-y-4">
          <Card className="border-th-border shadow-soft">
            <CardHeader className="pb-3 border-b border-th-border bg-th-surface-el flex flex-row items-center justify-between">
              <div>
                <CardTitle className="text-sm font-semibold text-th-text-primary font-serif flex items-center gap-2">
                  <Network className="w-4 h-4 text-th-brand" />
                  Active Directory Tier Hierarchy &amp; Compromise Propagation
                </CardTitle>
                <p className="text-xs text-th-text-secondary mt-0.5">
                  Click any asset card below to simulate breach origin and trace cascading lateral infection.
                </p>
              </div>

              {propLoading && (
                <div className="flex items-center space-x-1.5 text-xs text-th-brand font-medium">
                  <div className="w-3 h-3 border-2 border-th-brand border-t-transparent rounded-full animate-spin" />
                  <span>Propagating...</span>
                </div>
              )}
            </CardHeader>

            <CardContent className="p-4 space-y-4 max-h-[600px] overflow-y-auto">
              {[0, 1, 2, 3, 4].map((tierNum) => {
                const tierInfo = tierMap[tierNum];
                const tierNodes = nodes.filter((n) => n.tier === tierNum);
                if (tierNodes.length === 0) return null;

                const IconComponent = tierInfo.icon;

                return (
                  <div key={tierNum} className="space-y-2">
                    <div className="flex items-center space-x-2 text-xs font-semibold text-th-text-primary uppercase tracking-wider">
                      <IconComponent className="w-3.5 h-3.5 text-th-brand" />
                      <span>{tierInfo.label}</span>
                      <span className="text-[11px] text-th-text-muted font-normal lowercase">
                        ({tierNodes.length} nodes)
                      </span>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2">
                      {tierNodes.map((node) => {
                        const isBreached = node.asset_id === selectedBreachedId;
                        const prob = node.compromise_probability ?? 0;
                        const isHighRisk = prob >= 0.5;

                        return (
                          <div
                            key={node.asset_id}
                            onClick={() => handleSelectBreachedAsset(node.asset_id)}
                            className={`p-3 rounded-lg border text-xs cursor-pointer transition-all ${
                              isBreached
                                ? 'ring-2 ring-red-500 border-red-500 bg-red-50 dark:bg-red-950/40 shadow-md'
                                : isHighRisk
                                ? 'border-amber-300 dark:border-amber-800 bg-amber-50/50 dark:bg-amber-950/20 hover:border-amber-500'
                                : 'border-th-border bg-th-surface hover:border-th-brand hover:shadow-sm'
                            }`}
                          >
                            <div className="flex items-start justify-between gap-1 mb-1.5">
                              <div>
                                <span className="font-mono font-bold text-th-text-primary block">
                                  {node.asset_id}
                                </span>
                                <span className="text-[10px] text-th-text-muted truncate block max-w-[120px]">
                                  {node.hostname}
                                </span>
                              </div>
                              {getCompromiseBadge(prob, isBreached)}
                            </div>

                            <div className="pt-2 border-t border-th-border/60 flex items-center justify-between text-[11px]">
                              <span className="text-th-text-secondary">{node.business_unit}</span>
                              <span className="font-mono font-bold text-th-text-primary">
                                {formatCurrency(node.expected_cascading_eal_usd || node.EAL_usd)}
                              </span>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </CardContent>
          </Card>
        </div>

        {/* Lateral Movement Attack Path Inspector */}
        <div className="lg:col-span-4 space-y-4">
          <Card className="border-th-border shadow-soft h-full flex flex-col">
            <CardHeader className="pb-3 border-b border-th-border bg-th-surface-el">
              <CardTitle className="text-sm font-semibold text-th-text-primary font-serif flex items-center gap-2">
                <Flame className="w-4 h-4 text-red-500" />
                Active Lateral Attack Vectors ({activePaths.length})
              </CardTitle>
              <p className="text-xs text-th-text-secondary mt-0.5">
                Observed pathways linking breached asset to critical targets.
              </p>
            </CardHeader>

            <CardContent className="p-4 flex-1 overflow-y-auto space-y-2.5 max-h-[540px]">
              {activePaths.length === 0 ? (
                <div className="p-6 text-center text-th-text-muted text-xs flex flex-col items-center justify-center space-y-2">
                  <CheckCircle2 className="w-6 h-6 text-green-500" />
                  <p>No active lateral movement propagation paths from this asset.</p>
                </div>
              ) : (
                activePaths.map((edge, i) => (
                  <div
                    key={i}
                    className="p-3 rounded-lg bg-th-bg border border-th-border text-xs space-y-2 hover:border-red-300 transition-colors"
                  >
                    <div className="flex items-center justify-between font-mono font-bold">
                      <span className="text-th-text-primary">{edge.source}</span>
                      <div className="flex items-center text-red-500 px-1">
                        <span className="text-[10px] font-sans font-semibold mr-1">
                          {(edge.lateral_movement_probability * 100).toFixed(0)}%
                        </span>
                        <ArrowRight className="w-3.5 h-3.5" />
                      </div>
                      <span className="text-th-brand">{edge.target}</span>
                    </div>

                    <div className="flex items-center justify-between text-[11px] text-th-text-secondary pt-1 border-t border-th-border">
                      <Badge variant="secondary">{edge.protocol}</Badge>
                      <span className="truncate max-w-[170px] text-right font-medium text-th-text-primary">
                        {edge.attack_vector}
                      </span>
                    </div>
                  </div>
                ))
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
};
