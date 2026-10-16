import React, { useState, useEffect } from 'react';
import {
  Sliders,
  Play,
  TrendingDown,
  CheckCircle,
  Cpu,
  ShieldCheck,
  ArrowRight,
  Sparkles,
} from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Cell,
} from 'recharts';
import {
  getOptimizedPlan,
  formatCurrency,
  formatCompactCurrency,
  formatPercent,
  formatMultiplier,
} from '../../api/client';
import { Card, CardHeader, CardTitle, CardContent } from '../ui/Card';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';
import { useCurrency } from '../../context/CurrencyContext';

export const WhatIfOptimizer = ({ orgEal = 0 }) => {
  const { currency, rate } = useCurrency();
  const initialBudget = currency === 'INR' ? Math.round(500000 * rate) : 500000;
  const [budget, setBudget] = useState(initialBudget);
  const [oneControlPerAsset, setOneControlPerAsset] = useState(true);
  const [optimizationResult, setOptimizationResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const runOptimizer = async (targetBudget = budget, targetOnePerAsset = oneControlPerAsset) => {
    if (targetBudget <= 0) {
      setError(`Please specify a security budget greater than ${currency === 'INR' ? '₹0' : '$0'}.`);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      // Backend only understands USD
      const budgetUsd = currency === 'INR' ? targetBudget / rate : targetBudget;
      const data = await getOptimizedPlan(budgetUsd, targetOnePerAsset);
      setOptimizationResult(data);
    } catch (err) {
      setError(
        err.response?.data?.detail ||
        err.message ||
        'Failed to run ILP investment optimizer'
      );
    } finally {
      setLoading(false);
    }
  };

  // Run initial optimization once on mount
  useEffect(() => {
    runOptimizer(initialBudget, true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSliderChange = (e) => {
    setBudget(Number(e.target.value));
  };

  const handleInputChange = (e) => {
    const val = Number(e.target.value);
    if (!isNaN(val) && val >= 0) {
      setBudget(val);
    }
  };

  // Quick budget presets in active currency
  const usdPresets = [250000, 500000, 750000, 1000000, 1500000];
  const presets = usdPresets.map((uVal) => {
    const valInCurr = currency === 'INR' ? Math.round(uVal * rate) : uVal;
    let label;
    if (currency === 'INR') {
      const inrCr = valInCurr / 1e7;
      const inrL = valInCurr / 1e5;
      label = inrCr >= 1 ? `₹${inrCr.toFixed(1)} Cr` : `₹${inrL.toFixed(0)} L`;
    } else {
      label = uVal >= 1000000 ? `$${(uVal / 1e6).toFixed(1)}M` : `$${Math.round(uVal / 1000)}k`;
    }
    return {
      label,
      value: valInCurr,
      usdValue: uVal,
    };
  });

  const sliderMin = 10000 * (currency === 'INR' ? rate : 1);
  const sliderMax = 2000000 * (currency === 'INR' ? rate : 1);
  const sliderStep = 10000 * (currency === 'INR' ? rate : 1);
  const inputStep = 5000 * (currency === 'INR' ? rate : 1);

  // Comparison data for Residual EAL Before vs After
  const residualChartData = (() => {
    if (!optimizationResult) return [];
    const totalRiskReduction = optimizationResult.total_risk_reduction_usd || 0;
    const initialEal = optimizationResult.residual_eal_usd
      ? optimizationResult.residual_eal_usd + totalRiskReduction
      : orgEal > 0
        ? orgEal
        : totalRiskReduction * 1.5;
    const residualEal = optimizationResult.residual_eal_usd || Math.max(0, initialEal - totalRiskReduction);

    return [
      { name: 'Initial EAL', eal: initialEal, fill: 'var(--danger)' },
      { name: 'Residual EAL', eal: residualEal, fill: 'var(--success)' },
    ];
  })();

  // Comparison data for Optimal ILP vs Naive Greedy
  const greedy = optimizationResult?.greedy_comparison || {};
  const optimalRiskRed = optimizationResult?.total_risk_reduction_usd || 0;
  const greedyRiskRed = greedy.total_risk_reduction_usd || 0;
  const ilpAdvantageUsd = optimalRiskRed - greedyRiskRed;
  const ilpAdvantagePct =
    greedyRiskRed > 0 ? ((ilpAdvantageUsd / greedyRiskRed) * 100).toFixed(1) : '0.0';

  return (
    <div className="space-y-6">
      {/* Top Configuration Panel */}
      <Card className="p-6 space-y-5 shadow-card">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 pb-4 border-b border-th-border">
          <div>
            <div className="flex items-center space-x-3">
              <div className="p-2 rounded-lg bg-th-brand-tint text-th-brand shadow-soft">
                <Sliders className="w-4 h-4" />
              </div>
              <h2 className="text-lg font-semibold text-th-text-primary font-serif">
                Security Investment Optimization Workbench
              </h2>
            </div>
            <p className="text-xs text-th-text-secondary mt-1">
              Integer Linear Programming (ILP) solver finding the optimal combination of mitigations under capital budget constraints.
            </p>
          </div>

          <div className="flex items-center space-x-2">
            <Badge variant="brand" className="font-mono flex items-center gap-1.5 py-1">
              <Cpu className="w-3.5 h-3.5 text-th-brand" />
              Knapsack ILP Engine
            </Badge>
          </div>
        </div>

        {/* Workflow Breadcrumbs */}
        <div className="hidden sm:flex items-center space-x-2 text-xs text-th-text-secondary bg-th-surface-el p-3 rounded-lg border border-th-border">
          <span className="font-semibold text-th-text-primary">1. Budget Allocation</span>
          <ArrowRight className="w-3.5 h-3.5 text-th-text-muted" />
          <span>2. Constraints & Dependencies</span>
          <ArrowRight className="w-3.5 h-3.5 text-th-text-muted" />
          <span>3. Global Optimization Solver</span>
          <ArrowRight className="w-3.5 h-3.5 text-th-text-muted" />
          <span className="text-th-brand font-semibold">4. Risk Reduction & ROSI</span>
        </div>

        {/* Interactive Controls Bar */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-center pt-1">

          {/* Budget Input & Slider (Cols 1-7) */}
          <div className="lg:col-span-7 space-y-3">
            <div className="flex items-center justify-between">
              <label className="text-xs font-semibold text-th-text-primary">
                Security Budget Allocation ({currency})
              </label>
              <div className="flex items-center space-x-1.5">
                {presets.map((p) => (
                  <button
                    key={p.label}
                    onClick={() => {
                      setBudget(p.value);
                      runOptimizer(p.value, oneControlPerAsset);
                    }}
                    className={twMerge(
                      'px-3 py-1 text-xs font-mono rounded-full transition-colors border shadow-soft',
                      budget === p.value
                        ? 'bg-th-brand text-white border-th-brand font-semibold'
                        : 'bg-th-surface text-th-text-secondary hover:text-th-text-primary border-th-border'
                    )}
                  >
                    {p.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="flex items-center space-x-4">
              <input
                type="range"
                min={sliderMin}
                max={sliderMax}
                step={sliderStep}
                value={budget}
                onChange={handleSliderChange}
                className="w-full h-2.5 bg-th-border rounded-full appearance-none cursor-pointer accent-th-brand"
              />
              <div className="relative min-w-[140px]">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-xs font-mono text-th-text-muted">
                  {currency === 'INR' ? '₹' : '$'}
                </span>
                <input
                  type="number"
                  min="0"
                  step={inputStep}
                  value={budget}
                  onChange={handleInputChange}
                  className="w-full pl-6 pr-3 py-1.5 text-sm font-mono font-bold bg-th-surface-el border border-th-border rounded-lg text-th-text-primary focus:outline-none focus:bg-th-surface focus:border-th-accent focus:ring-1 focus:ring-th-accent tabular-nums transition-all"
                />
              </div>
            </div>
          </div>

          {/* Toggle Switch + Run Button (Cols 8-12) */}
          <div className="lg:col-span-5 flex flex-wrap sm:flex-nowrap items-center justify-between sm:justify-end gap-4 mt-2 lg:mt-0">
            {/* Modern Toggle Switch */}
            <label className="inline-flex items-center gap-2.5 cursor-pointer select-none">
              <div className="relative inline-flex items-center">
                <input
                  type="checkbox"
                  checked={oneControlPerAsset}
                  onChange={(e) => setOneControlPerAsset(e.target.checked)}
                  className="sr-only peer"
                />
                <div className="w-10 h-5 bg-th-border peer-focus:ring-2 peer-focus:ring-th-brand/30 rounded-full peer peer-checked:bg-th-brand transition-colors duration-200"></div>
                <div className="absolute left-0.5 top-0.5 bg-white w-4 h-4 rounded-full transition-transform duration-200 peer-checked:translate-x-5 shadow-sm"></div>
              </div>
              <span className="text-xs text-th-text-primary font-medium">
                Max 1 control / asset
              </span>
            </label>

            {/* Run Button */}
            <Button
              onClick={() => runOptimizer(budget, oneControlPerAsset)}
              isLoading={loading}
              className="px-5 py-2"
            >
              {!loading && <Play className="w-3.5 h-3.5 fill-current mr-2" />}
              {loading ? 'Optimizing...' : 'Run Optimizer'}
            </Button>
          </div>

        </div>

      </Card>

      {error && (
        <Card className="p-4 bg-th-danger-tint border-th-danger/30 text-xs text-th-danger font-medium shadow-soft">
          {error}
        </Card>
      )}

      {optimizationResult && (
        <>
          {/* Key Metric Summary Tiles */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">

            {/* Allocated Cost */}
            <Card className="p-5">
              <span className="text-xs text-th-text-secondary font-medium">Optimal Allocated Cost</span>
              <div className="text-2xl sm:text-3xl font-bold font-serif text-th-text-primary mt-1.5 tabular-nums">
                {formatCurrency(optimizationResult.total_cost_usd)}
              </div>
              <div className="text-xs text-th-text-muted mt-2 flex items-center justify-between">
                <span>Budget: {formatCurrency(optimizationResult.budget_usd)}</span>
                <span className="text-th-brand font-mono font-medium">
                  {formatPercent(optimizationResult.budget_utilization_pct)}
                </span>
              </div>
            </Card>

            {/* Total Risk Reduction */}
            <Card className="p-5 bg-th-brand-tint border-th-brand/20">
              <span className="text-xs text-th-brand font-medium">Total Risk Reduction</span>
              <div className="text-2xl sm:text-3xl font-bold font-serif text-th-brand mt-1.5 tabular-nums">
                {formatCurrency(optimizationResult.total_risk_reduction_usd)}
              </div>
              <div className="text-xs text-th-brand mt-2 flex items-center gap-1.5 font-medium">
                <TrendingDown className="w-3.5 h-3.5" />
                <span>Annualized Loss Mitigated</span>
              </div>
            </Card>

            {/* Controls Implemented */}
            <Card className="p-5">
              <span className="text-xs text-th-text-secondary font-medium">Controls Implemented</span>
              <div className="text-2xl sm:text-3xl font-bold font-serif text-th-text-primary mt-1.5 tabular-nums">
                {optimizationResult.n_actions_selected} Actions
              </div>
              <div className="text-xs text-th-text-muted mt-2">
                Across target critical assets
              </div>
            </Card>

            {/* Residual EAL */}
            <Card className="p-5 bg-th-warning-tint border-th-warning/20">
              <span className="text-xs text-th-warning font-medium">Residual EAL (Post-Mitigation)</span>
              <div className="text-2xl sm:text-3xl font-bold font-serif text-th-warning mt-1.5 tabular-nums">
                {formatCurrency(optimizationResult.residual_eal_usd)}
              </div>
              <div className="text-xs text-th-warning mt-2">
                Remaining portfolio risk
              </div>
            </Card>

          </div>

          {/* Solid Emerald Callout Banner (Actuarial Value Guarantee) */}
          <div className="bg-th-brand rounded-xl p-6 text-white shadow-elevated flex flex-col md:flex-row md:items-center justify-between gap-5 overflow-hidden relative">
            <div className="absolute -right-10 -top-10 opacity-10 pointer-events-none">
              <Cpu className="w-64 h-64" />
            </div>
            
            <div className="space-y-2.5 max-w-xl relative z-10">
              <div className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-full bg-white/10 text-white text-[11px] font-medium border border-white/20 backdrop-blur-md">
                <Sparkles className="w-3.5 h-3.5 text-th-accent-sec" />
                <span>Exact Knapsack ILP Optimization</span>
              </div>
              <h3 className="text-xl sm:text-2xl font-semibold font-serif">
                Exact Knapsack vs Naive Greedy Selection
              </h3>
              <p className="text-sm text-white/90 leading-relaxed max-w-lg">
                At your {formatCurrency(optimizationResult.budget_usd || (currency === 'INR' ? budget / rate : budget))} capital budget, the mathematical solver delivers an additional{' '}
                <strong className="text-white font-bold underline decoration-th-accent-sec decoration-2">
                  {formatCurrency(Math.max(0, ilpAdvantageUsd))}
                </strong>{' '}
                in risk reduction (+{formatPercent(ilpAdvantagePct)}) with zero increase in expenditure.
              </p>
            </div>

            <div className="flex items-center gap-3 shrink-0 relative z-10">
              <div className="bg-black/20 border border-white/10 rounded-lg p-4 text-center min-w-[140px] backdrop-blur-md">
                <span className="text-[10px] text-white/70 uppercase font-semibold block mb-1">Greedy Heuristic</span>
                <span className="text-lg font-bold font-mono text-white/80 tabular-nums">{formatCurrency(greedyRiskRed)}</span>
              </div>
              <div className="bg-white rounded-lg p-4 text-center min-w-[150px] shadow-soft">
                <span className="text-[10px] text-th-brand uppercase font-bold block mb-1">Knapsack ILP</span>
                <span className="text-lg font-bold font-mono text-th-brand tabular-nums">{formatCurrency(optimalRiskRed)}</span>
              </div>
            </div>
          </div>

          {/* Comparison Charts */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">

            {/* Left: Residual EAL Comparison (6 Cols) */}
            <Card className="lg:col-span-6 p-5 flex flex-col justify-between">
              <div>
                <h3 className="text-sm font-semibold text-th-text-primary font-serif">
                  Pre vs Post Mitigation Exposure
                </h3>
                <p className="text-xs text-th-text-secondary mt-0.5">
                  Expected Annual Loss before and after optimal control deployments
                </p>
              </div>

              <div className="h-56 w-full mt-4">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={residualChartData} margin={{ top: 10, right: 15, left: 0, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" />
                    <XAxis dataKey="name" stroke="var(--chart-axis)" fontSize={11} tickLine={false} />
                    <YAxis
                      stroke="var(--chart-axis)"
                      fontSize={11}
                      tickFormatter={formatCompactCurrency}
                      tickLine={false}
                      axisLine={false}
                    />
                    <Tooltip
                      formatter={(v) => [formatCurrency(v), 'Expected Annual Loss']}
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
                    <Bar dataKey="eal" radius={[4, 4, 0, 0]}>
                      {residualChartData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.fill} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Card>

            {/* Right: Selected Actions Summary Card (6 Cols) */}
            <Card className="lg:col-span-6 p-5 flex flex-col justify-between">
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-th-text-primary font-serif">
                    Portfolio Allocation Strategy
                  </h3>
                  <Badge variant="brand" className="font-mono">
                    {optimizationResult.selected_actions?.length || 0} Controls Selected
                  </Badge>
                </div>

                <p className="text-sm text-th-text-secondary leading-relaxed">
                  The optimizer evaluated all feasible combinations across the asset inventory and allocated capital to controls providing the maximum system-wide risk reduction factor.
                </p>

                <div className="grid grid-cols-2 gap-4 pt-2">
                  <div className="p-4 rounded-xl bg-th-surface-el border border-th-border">
                    <span className="text-[11px] text-th-text-secondary font-medium">Budget Efficiency</span>
                    <div className="text-lg font-bold text-th-text-primary font-mono mt-1">
                      {formatPercent(optimizationResult.budget_utilization_pct)}
                    </div>
                  </div>
                  <div className="p-4 rounded-xl bg-th-brand-tint border border-th-brand/20">
                    <span className="text-[11px] text-th-brand font-medium">Risk Mitigated</span>
                    <div className="text-lg font-bold text-th-brand font-mono mt-1">
                      {formatCurrency(optimizationResult.total_risk_reduction_usd)}
                    </div>
                  </div>
                </div>
              </div>

              <div className="mt-5 p-4 rounded-lg bg-th-accent-sec/10 border border-th-accent-sec/20 text-xs text-th-accent-sec flex items-center gap-2">
                <ShieldCheck className="w-5 h-5 text-th-accent-sec shrink-0" />
                <span className="font-medium">Review prioritized mitigation deployments in the table below.</span>
              </div>
            </Card>

          </div>

          {/* Selected Actions Table */}
          <Card className="overflow-hidden">
            <div className="p-5 border-b border-th-border bg-th-surface flex items-center justify-between">
              <div className="flex items-center space-x-3">
                <div className="p-2 rounded-lg bg-th-brand-tint text-th-brand shadow-soft">
                  <CheckCircle className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-th-text-primary font-serif">
                    Recommended Implementation Plan
                  </h3>
                  <p className="text-xs text-th-text-secondary mt-0.5">
                    Optimal asset-to-control assignments generated by the optimizer
                  </p>
                </div>
              </div>
              <Badge variant="brand" className="font-mono">
                {optimizationResult.selected_actions?.length || 0} Actions Selected
              </Badge>
            </div>

            <div className="overflow-x-auto max-h-80 overflow-y-auto">
              <table className="w-full text-left text-sm border-collapse">
                <thead className="sticky top-0 bg-th-bg border-b border-th-border text-xs font-semibold text-th-text-secondary">
                  <tr>
                    <th className="py-3 px-5">Asset ID</th>
                    <th className="py-3 px-5">Control Name</th>
                    <th className="py-3 px-5 text-right">Implementation Cost</th>
                    <th className="py-3 px-5 text-right">Risk Reduction</th>
                    <th className="py-3 px-5 text-right">ROSI</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-th-border font-mono text-xs bg-th-surface">
                  {optimizationResult.selected_actions &&
                    optimizationResult.selected_actions.length > 0 ? (
                    optimizationResult.selected_actions.map((action, idx) => {
                      const cost = action.cost_usd || action.cost || 0;
                      const red = action.Risk_Reduction_usd || action.risk_reduction_usd || 0;
                      const rosi = action.ROSI || (cost > 0 ? (red - cost) / cost : 0);

                      return (
                        <tr key={idx} className="hover:bg-th-surface-el transition-colors">
                          <td className="py-3 px-5 text-th-text-primary font-bold">
                            {action.asset_id}
                          </td>
                          <td className="py-3 px-5 text-th-text-secondary font-sans font-medium">
                            {action.control_name || action.control_id}
                          </td>
                          <td className="py-3 px-5 text-right text-th-text-primary tabular-nums">
                            {formatCurrency(cost)}
                          </td>
                          <td className="py-3 px-5 text-right text-th-brand font-bold tabular-nums">
                            {formatCurrency(red)}
                          </td>
                          <td className="py-3 px-5 text-right text-th-brand font-bold tabular-nums">
                            {formatMultiplier(rosi)}
                          </td>
                        </tr>
                      );
                    })
                  ) : (
                    <tr>
                      <td colSpan={5} className="py-10 text-center text-th-text-muted font-sans">
                        No actions selected for this budget level. Increase budget to see allocations.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      )}
    </div>
  );
};
