import React, { useEffect, useState } from 'react';
import {
  X,
  Server,
  TrendingUp,
  AlertTriangle,
  Database,
  BarChart2,
  DollarSign,
  Layers,
} from 'lucide-react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts';
import {
  getAssetDetail,
  getVulnPredictions,
  getAssetDrivers,
  formatCurrency,
  formatCompactCurrency,
} from '../../api/client';
import { Card } from '../ui/Card';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';

export const AssetDetailPanel = ({ assetId, onClose }) => {
  const [data, setData] = useState(null);
  const [drivers, setDrivers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [mlTab, setMlTab] = useState('rf');

  useEffect(() => {
    if (!assetId) return;

    let isMounted = true;
    setLoading(true);
    setError(null);

    Promise.all([
      getAssetDetail(assetId),
      getVulnPredictions().catch(() => []),
      getAssetDrivers(assetId).catch(() => ({ drivers: [] })),
    ])
      .then(([assetRes, vulnRes, driversRes]) => {
        if (isMounted) {
          const vulns = vulnRes?.data || vulnRes || [];
          const assetVulns = Array.isArray(vulns) ? vulns.filter((v) => v.asset_id === assetId) : [];
          assetRes.predicted_vulnerabilities = assetVulns;
          setData(assetRes);
          setDrivers(driversRes?.drivers || []);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (isMounted) {
          setError(err.response?.data?.detail || err.message || 'Failed to fetch asset detail');
          setLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [assetId]);

  if (!assetId) return null;

  const exceedancePoints = (() => {
    if (!data) return [];
    const raw = data.LEC_points || data.loss_exceedance_curve;
    if (!Array.isArray(raw)) return [];
    return raw.map((pt) => {
      const p = pt.probability ?? pt.prob_num;
      const probPct = p !== undefined && p <= 1 ? p * 100 : p;
      return {
        probability: probPct !== undefined ? `${Number(probPct).toFixed(1)}%` : '—',
        probNum: probPct,
        loss: pt.loss ?? pt.loss_usd,
        ...pt,
      };
    });
  })();

  // Impact breakdown components
  const impactItems = [
    { name: 'Downtime Interruption', value: data?.LM_downtime_usd || 0 },
    { name: 'Incident Response (IR)', value: data?.LM_ir_usd || 0 },
    { name: 'Data Breach Records', value: data?.LM_data_breach_usd || 0 },
    { name: 'Regulatory Penalty', value: data?.LM_regulatory_usd || 0 },
  ];
  const maxImpact = Math.max(...impactItems.map((i) => i.value), 1);

  // Drivers max delta for scaling bars
  const maxDriverDelta = Math.max(...drivers.map((d) => Math.abs(d.delta_usd)), 1);

  return (
    <div className="fixed inset-0 z-50 overflow-hidden bg-black/40 backdrop-blur-sm flex justify-end transition-opacity">
      <div className="w-full max-w-xl bg-th-surface border-l border-th-border shadow-2xl h-full flex flex-col overflow-hidden">

        {/* Header */}
        <div className="p-5 border-b border-th-border bg-th-surface-el flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="p-2 rounded-lg bg-th-brand-tint text-th-brand shadow-soft">
              <Server className="w-4 h-4" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h2 className="text-base font-semibold text-th-text-primary font-mono">
                  {assetId}
                </h2>
                <Badge variant="brand">
                  {data?.business_unit || 'Asset'}
                </Badge>
              </div>
              <p className="text-xs text-th-text-muted mt-0.5">Open FAIR™ Risk Quantification Breakdown</p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 rounded-full text-th-text-muted hover:text-th-text-primary hover:bg-th-bg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body Content */}
        <div className="flex-1 overflow-y-auto p-5 space-y-5">
          {loading ? (
            <div className="space-y-4 animate-pulse">
              <Card className="h-20 p-4 border-none bg-th-bg"></Card>
              <div className="grid grid-cols-2 gap-3">
                <Card className="h-24 p-4 border-none bg-th-bg"></Card>
                <Card className="h-24 p-4 border-none bg-th-bg"></Card>
              </div>
              <Card className="h-56 p-4 border-none bg-th-bg"></Card>
            </div>
          ) : error ? (
            <div className="p-5 rounded-xl bg-th-danger-tint border border-th-danger/30 text-center shadow-soft">
              <AlertTriangle className="w-6 h-6 text-th-danger mx-auto mb-2" />
              <p className="text-sm font-semibold text-th-danger font-serif">Error Loading Asset Data</p>
              <p className="text-xs text-th-danger/90 mt-1">{error}</p>
            </div>
          ) : data ? (
            <>
              {/* Primary Metrics Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                <Card className="p-4 shadow-soft">
                  <span className="text-xs text-th-text-secondary font-medium">Expected Loss (EAL)</span>
                  <div className="text-xl font-bold font-serif text-th-text-primary mt-1 tabular-nums">
                    {formatCurrency(data.EAL_usd)}
                  </div>
                  <span className="text-[11px] text-th-brand mt-1 block font-medium">Annualized Mean</span>
                </Card>

                <Card className="p-4 shadow-soft">
                  <span className="text-xs text-th-text-secondary font-medium">Value at Risk 95%</span>
                  <div className="text-xl font-bold font-serif text-th-warning mt-1 tabular-nums">
                    {formatCurrency(data.VaR95_usd)}
                  </div>
                  <span className="text-[11px] text-th-warning mt-1 block font-medium">1-in-20 Year Tail</span>
                </Card>

                <Card className="p-4 shadow-soft col-span-2 sm:col-span-1">
                  <span className="text-xs text-th-text-secondary font-medium">Value at Risk 99%</span>
                  <div className="text-xl font-bold font-serif text-th-danger mt-1 tabular-nums">
                    {formatCurrency(data.VaR99_usd)}
                  </div>
                  <span className="text-[11px] text-th-danger mt-1 block font-medium">1-in-100 Year Cat</span>
                </Card>
              </div>

              {/* Task 3.4: Simple Estimate vs Monte Carlo Comparison */}
              <Card className="p-4 shadow-soft bg-th-surface-el">
                <div className="flex items-center justify-between pb-2 border-b border-th-border">
                  <div className="flex items-center gap-1.5">
                    <Layers className="w-4 h-4 text-th-brand" />
                    <span className="text-xs font-semibold text-th-text-primary font-serif">
                      EAL Estimation Models
                    </span>
                  </div>
                  <Badge variant="brand" className="text-[10px]">Model Comparison</Badge>
                </div>
                <div className="grid grid-cols-2 gap-4 mt-3">
                  <div className="p-3 rounded-lg bg-th-surface border border-th-border">
                    <span className="text-[11px] text-th-text-secondary block font-medium">
                      Simple Estimate
                    </span>
                    <div className="text-lg font-bold font-serif text-th-text-primary mt-1 tabular-nums">
                      {formatCurrency(data.eal_simple_usd ?? data.EAL_simple_usd)}
                    </div>
                    <span className="text-[10px] text-th-text-muted block mt-0.5 font-mono">
                      TEF × Vuln × Mean LM
                    </span>
                  </div>
                  <div className="p-3 rounded-lg bg-th-brand-tint border border-th-brand/20">
                    <span className="text-[11px] text-th-brand block font-semibold">
                      Monte Carlo EAL
                    </span>
                    <div className="text-lg font-bold font-serif text-th-brand mt-1 tabular-nums">
                      {formatCurrency(data.EAL_usd)}
                    </div>
                    <span className="text-[10px] text-th-brand/80 block mt-0.5 font-medium">
                      Full simulation (tail risk)
                    </span>
                  </div>
                </div>
                <p className="text-[11px] text-th-text-muted italic mt-2.5 pt-2 border-t border-th-border">
                  Simple estimate vs Monte Carlo (includes bad years)
                </p>
              </Card>

              {/* Task 4.2: Cost per Incident Breakdown */}
              <Card className="p-5 shadow-card space-y-3">
                <div className="flex items-center justify-between">
                  <h4 className="text-sm font-semibold text-th-text-primary font-serif flex items-center gap-2">
                    <DollarSign className="w-4 h-4 text-th-brand" />
                    Cost per incident
                  </h4>
                  <span className="text-xs font-mono font-bold text-th-text-primary">
                    {formatCurrency(data.LM_total_mostlikely_usd || impactItems.reduce((s, i) => s + i.value, 0))}
                  </span>
                </div>
                <p className="text-xs text-th-text-secondary">
                  Primary and secondary financial loss components per security event
                </p>

                <div className="space-y-3 pt-2">
                  {impactItems.map((item, idx) => {
                    const pct = maxImpact > 0 ? (item.value / maxImpact) * 100 : 0;
                    return (
                      <div key={idx} className="space-y-1">
                        <div className="flex items-center justify-between text-xs">
                          <span className="text-th-text-secondary font-medium">{item.name}</span>
                          <span className="font-mono font-semibold text-th-text-primary tabular-nums">
                            {formatCurrency(item.value)}
                          </span>
                        </div>
                        <div className="w-full bg-th-border/60 rounded-full h-1.5 overflow-hidden">
                          <div
                            className="bg-th-brand h-1.5 rounded-full transition-all duration-300"
                            style={{ width: `${Math.min(100, Math.max(3, pct))}%` }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </Card>

              {/* Task 6.3: Top Drivers of Risk */}
              {drivers && drivers.length > 0 && (
                <Card className="p-5 shadow-card space-y-3">
                  <div className="flex items-center justify-between">
                    <h4 className="text-sm font-semibold text-th-text-primary font-serif flex items-center gap-2">
                      <BarChart2 className="w-4 h-4 text-th-brand" />
                      Top drivers of this asset's risk
                    </h4>
                    <Badge variant="brand" className="font-mono text-[10px]">Drivers</Badge>
                  </div>
                  <p className="text-xs text-th-text-secondary">
                    Counterfactual risk sensitivity — EAL impact when individual factors are neutralised
                  </p>

                  <div className="space-y-3 pt-2">
                    {drivers.map((d, i) => {
                      const pct = maxDriverDelta > 0 ? (Math.abs(d.delta_usd) / maxDriverDelta) * 100 : 0;
                      return (
                        <div key={i} className="space-y-1">
                          <div className="flex items-center justify-between text-xs">
                            <span className="text-th-text-primary font-medium">{d.driver}</span>
                            <span className="font-mono font-semibold text-th-brand tabular-nums">
                              {formatCurrency(d.delta_usd)}
                            </span>
                          </div>
                          <div className="w-full bg-th-border/60 rounded-full h-1.5 overflow-hidden">
                            <div
                              className="bg-th-brand h-1.5 rounded-full transition-all duration-300"
                              style={{ width: `${Math.min(100, Math.max(4, pct))}%` }}
                            />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </Card>
              )}

              {/* Asset Attribute Details */}
              <Card className="p-5 bg-th-surface-el shadow-soft">
                <h4 className="text-sm font-semibold text-th-text-primary font-serif flex items-center gap-2 mb-4">
                  <Database className="w-4 h-4 text-th-brand" />
                  Asset Metadata & Risk Parameters
                </h4>

                <div className="grid grid-cols-2 gap-y-3 gap-x-4 text-sm">
                  <div className="text-th-text-muted">Business Unit:</div>
                  <div className="text-th-text-primary font-medium">{data.business_unit || 'N/A'}</div>

                  <div className="text-th-text-muted">Criticality Rating:</div>
                  <div className="text-th-text-primary font-medium">{data.criticality || 'N/A'}</div>

                  <div className="text-th-text-muted">Risk Priority Score:</div>
                  <div className="text-th-brand font-mono font-bold">
                    {data.priority_score !== undefined ? Number(data.priority_score).toFixed(1) : 'N/A'}
                  </div>

                  {data.asset_type && (
                    <>
                      <div className="text-th-text-muted">Asset Type:</div>
                      <div className="text-th-text-primary">{data.asset_type}</div>
                    </>
                  )}
                </div>
              </Card>

              {/* Loss Exceedance Curve (LEC) Chart */}
              <Card className="p-5 shadow-card space-y-4">
                <div>
                  <h4 className="text-sm font-semibold text-th-text-primary font-serif flex items-center gap-2">
                    <TrendingUp className="w-4 h-4 text-th-brand" />
                    Loss Exceedance Curve (LEC)
                  </h4>
                  <p className="text-xs text-th-text-secondary mt-1">
                    Probability that annual loss exceeds threshold value
                  </p>
                </div>

                {exceedancePoints.length === 0 ? (
                  <div className="h-56 w-full mt-2 flex items-center justify-center rounded-lg border border-dashed border-th-border text-xs text-th-text-muted text-center px-6">
                    No loss exceedance curve was reported for this asset in the selected run.
                  </div>
                ) : (
                <div className="h-56 w-full mt-2">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={exceedancePoints} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                      <defs>
                        <linearGradient id="colorLossEmerald" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="var(--chart-area-fill-start)" />
                          <stop offset="95%" stopColor="var(--chart-area-fill-end)" />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" />
                      <XAxis dataKey="probability" stroke="var(--chart-axis)" fontSize={11} tickLine={false} />
                      <YAxis
                        stroke="var(--chart-axis)"
                        fontSize={11}
                        tickFormatter={formatCompactCurrency}
                        tickLine={false}
                        axisLine={false}
                      />
                      <Tooltip
                        formatter={(val) => [formatCurrency(val), 'Loss Threshold']}
                        contentStyle={{
                          backgroundColor: 'var(--surface-elevated)',
                          borderColor: 'var(--border)',
                          borderRadius: '8px',
                          fontSize: '12px',
                          color: 'var(--text-primary)',
                          boxShadow: 'var(--shadow-elevated)',
                        }}
                        itemStyle={{ color: 'var(--text-primary)' }}
                      />
                      <Area
                        type="monotone"
                        dataKey="loss"
                        stroke="var(--chart-area-stroke)"
                        strokeWidth={2}
                        fillOpacity={1}
                        fill="url(#colorLossEmerald)"
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
                )}
              </Card>
              
              {/* Vulnerability Exploit Predictions */}
              {data.predicted_vulnerabilities && data.predicted_vulnerabilities.length > 0 && (
                <Card className="p-5 shadow-card space-y-4">
                  <div className="flex items-center justify-between">
                    <h4 className="text-sm font-semibold text-th-text-primary font-serif flex items-center gap-2">
                      <AlertTriangle className="w-4 h-4 text-th-warning" />
                      Vulnerability Exploit Predictions (ML)
                    </h4>
                    <div className="flex items-center space-x-1 bg-th-bg rounded-lg p-1 border border-th-border">
                      <button 
                        onClick={() => setMlTab('rf')}
                        className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${mlTab === 'rf' ? 'bg-th-surface border border-th-border text-th-brand shadow-sm' : 'text-th-text-secondary hover:text-th-text-primary'}`}
                      >
                        Random Forest
                      </button>
                      <button 
                        onClick={() => setMlTab('xgb')}
                        className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${mlTab === 'xgb' ? 'bg-th-surface border border-th-border text-th-brand shadow-sm' : 'text-th-text-secondary hover:text-th-text-primary'}`}
                      >
                        XGBoost
                      </button>
                    </div>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-sm">
                      <thead className="border-b border-th-border text-th-text-secondary text-xs">
                        <tr>
                          <th className="pb-2 font-medium">CVE</th>
                          <th className="pb-2 font-medium">Severity</th>
                          <th className="pb-2 font-medium">CVSS</th>
                          <th className="pb-2 font-medium text-right">Exploit Prob (30d)</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-th-border">
                        {data.predicted_vulnerabilities.map((v, i) => {
                          const prob = mlTab === 'xgb' && v.exploit_probability_xgb !== undefined 
                            ? v.exploit_probability_xgb 
                            : (v.exploit_probability_rf !== undefined ? v.exploit_probability_rf : v.exploit_probability);
                          
                          return (
                          <tr key={i}>
                            <td className="py-2 text-th-text-primary font-mono text-xs">{v.cve_id}</td>
                            <td className="py-2">
                              <Badge variant={v.severity?.toLowerCase() === 'critical' || v.severity?.toLowerCase() === 'high' ? 'danger' : 'warning'}>
                                {v.severity}
                              </Badge>
                            </td>
                            <td className="py-2 text-th-text-secondary">{v.cvss_score}</td>
                            <td className="py-2 text-right">
                              <span className={`font-semibold ${prob > 0.5 ? 'text-th-danger' : prob > 0.2 ? 'text-th-warning' : 'text-th-brand'}`}>
                                {(prob * 100).toFixed(1)}%
                              </span>
                            </td>
                          </tr>
                        )})}
                      </tbody>
                    </table>
                  </div>
                </Card>
              )}
            </>
          ) : null}
        </div>

        {/* Footer */}
        <div className="p-5 border-t border-th-border bg-th-surface-el flex justify-end">
          <Button
            onClick={onClose}
            variant="secondary"
          >
            Close Panel
          </Button>
        </div>

      </div>
    </div>
  );
};
