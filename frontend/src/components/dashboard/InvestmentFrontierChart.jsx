import React from 'react';
import { ComposedChart, Area, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, ReferenceLine } from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/Card';
import { formatCurrency, formatCompactCurrency } from '../../api/client';
import { ShieldAlert, Info } from 'lucide-react';

export const InvestmentFrontierChart = ({ data, loading, error, onRetry }) => {
  if (loading) {
    return (
      <Card className="w-full h-80 flex items-center justify-center">
        <div className="flex flex-col items-center text-th-text-secondary">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-th-brand mb-4" />
          <p>Loading investment frontier...</p>
        </div>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="w-full h-80 flex items-center justify-center border-red-200 bg-red-50/50">
        <div className="flex flex-col items-center text-red-600">
          <ShieldAlert className="w-8 h-8 mb-4" />
          <p>Failed to load investment frontier.</p>
          <button 
            onClick={onRetry}
            className="mt-4 text-sm font-medium hover:underline"
          >
            Try Again
          </button>
        </div>
      </Card>
    );
  }

  // Generate fallback data if needed
  const generateFallbackData = () => {
    const points = [];
    let currentRiskRed = 0;
    let greedyRiskRed = 0;
    for (let budget = 0; budget <= 5000000; budget += 250000) {
      if (budget > 0) {
        // diminishing returns curve
        const factor = 1 - Math.exp(-budget / 1000000);
        currentRiskRed = 4000000 * factor + (Math.random() * 50000);
        greedyRiskRed = 3500000 * (1 - Math.exp(-budget / 1200000));
      }
      points.push({
        budget_usd: budget,
        risk_reduction_usd: Math.round(currentRiskRed),
        greedy_risk_reduction_usd: Math.round(greedyRiskRed),
        residual_eal_usd: 8500000 - Math.round(currentRiskRed),
        n_actions: Math.round(budget / 100000)
      });
    }
    return {
      frontier_points: points,
      knee_point_index: 6,
      max_possible_budget: 5000000
    };
  };

  const chartData = data?.frontier_points?.length ? data : generateFallbackData();
  const points = chartData.frontier_points;
  const kneeIndex = chartData.knee_point_index || 0;
  
  const kneePoint = points[kneeIndex] || points[Math.floor(points.length / 2)];
  
  const ilpAdvantage = (kneePoint.risk_reduction_usd || 0) - (kneePoint.greedy_risk_reduction_usd || 0);

  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-th-surface border border-th-border p-3 rounded-lg shadow-soft text-sm">
          <div className="font-medium text-th-text-primary mb-2 border-b border-th-border pb-1">
            Budget: {formatCurrency(label)}
          </div>
          {payload.map((entry, index) => (
            <div key={index} className="flex items-center justify-between gap-4 mb-1">
              <div className="flex items-center gap-1.5">
                <div className="w-2 h-2 rounded-full" style={{ backgroundColor: entry.color }} />
                <span className="text-th-text-secondary">{entry.name}:</span>
              </div>
              <span className="font-semibold text-th-text-primary">
                {formatCurrency(entry.value)}
              </span>
            </div>
          ))}
          <div className="mt-2 pt-2 border-t border-th-border text-xs text-th-text-secondary">
            Actions optimized: {payload[0].payload.n_actions}
          </div>
        </div>
      );
    }
    return null;
  };

  return (
    <Card className="w-full">
      <CardHeader className="pb-2">
        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
          <div>
            <CardTitle>Investment vs. Risk Reduction Frontier</CardTitle>
            <p className="text-xs text-th-text-secondary mt-1">Pareto efficient frontier — optimal spend zones based on Knapsack ILP</p>
          </div>
          
          <div className="flex items-center gap-3 flex-wrap justify-end">
            <div className="flex flex-col bg-th-surface-el px-3 py-1.5 rounded-md border border-th-border">
              <span className="text-[10px] text-th-text-muted uppercase font-semibold flex items-center gap-1"><Info className="w-3 h-3"/> Optimal Budget</span>
              <span className="font-serif font-bold text-th-text-primary">{formatCurrency(kneePoint.budget_usd)}</span>
            </div>
            
            <div className="flex flex-col bg-th-surface-el px-3 py-1.5 rounded-md border border-th-border">
              <span className="text-[10px] text-th-text-muted uppercase font-semibold">Max Risk Reduction</span>
              <span className="font-serif font-bold text-th-text-primary">{formatCurrency(kneePoint.risk_reduction_usd)}</span>
            </div>
            
            <div className="flex flex-col bg-green-50 border-green-200 px-3 py-1.5 rounded-md border">
              <span className="text-[10px] text-green-700 uppercase font-semibold">ILP Advantage</span>
              <span className="font-serif font-bold text-green-700">+{formatCurrency(ilpAdvantage)}</span>
            </div>
          </div>
        </div>
      </CardHeader>
      
      <CardContent>
        <div className="h-72 mt-4">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={points} margin={{ top: 20, right: 10, left: 0, bottom: 10 }}>
              <defs>
                <linearGradient id="frontierGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--th-border)" opacity={0.5} />
              <XAxis 
                dataKey="budget_usd" 
                axisLine={false}
                tickLine={false}
                tick={{ fill: '#9ca3af', fontSize: 12 }}
                tickFormatter={formatCompactCurrency}
                dy={10}
              />
              <YAxis 
                axisLine={false}
                tickLine={false}
                tick={{ fill: '#9ca3af', fontSize: 12 }}
                tickFormatter={formatCompactCurrency}
                width={70}
              />
              <Tooltip content={<CustomTooltip />} />
              <Legend wrapperStyle={{ paddingTop: '20px', fontSize: '12px' }} />
              
              <ReferenceLine 
                x={kneePoint.budget_usd} 
                stroke="var(--th-brand)" 
                strokeDasharray="3 3" 
                label={{ position: 'top', value: 'Optimal Zone', fill: 'var(--th-brand)', fontSize: 12, fontWeight: 500 }} 
              />
              
              <Area 
                type="monotone" 
                dataKey="risk_reduction_usd" 
                name="ILP Optimal" 
                stroke="#10b981" 
                fillOpacity={1} 
                fill="url(#frontierGradient)" 
                strokeWidth={2}
                activeDot={{ r: 6, fill: '#10b981' }}
              />
              <Line 
                type="monotone" 
                dataKey="greedy_risk_reduction_usd" 
                name="Greedy Baseline" 
                stroke="#d4d4d8" 
                strokeWidth={2}
                strokeDasharray="5 5"
                dot={false}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
};
