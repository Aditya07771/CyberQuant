import React from 'react';
import { ComposedChart, Area, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/Card';
import { Badge } from '../ui/Badge';
import { formatCurrency, formatCompactCurrency } from '../../api/client';
import { TrendingDown, ShieldAlert } from 'lucide-react';

export const RiskTrendChart = ({ data, loading, error, onRetry }) => {
  if (loading) {
    return (
      <Card className="w-full h-80 flex items-center justify-center">
        <div className="flex flex-col items-center text-th-text-secondary">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-th-brand mb-4" />
          <p>Loading risk trend data...</p>
        </div>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="w-full h-80 flex items-center justify-center border-red-200 bg-red-50/50">
        <div className="flex flex-col items-center text-red-600">
          <ShieldAlert className="w-8 h-8 mb-4" />
          <p>Failed to load risk trend.</p>
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

  const trendData = Array.isArray(data) ? data : [];

  if (trendData.length === 0) {
    return (
      <Card className="w-full h-80 flex items-center justify-center">
        <div className="flex flex-col items-center text-th-text-secondary text-center px-6">
          <TrendingDown className="w-8 h-8 mb-4 opacity-60" />
          <p className="font-medium text-th-text-primary">No historical risk trend reported</p>
          <p className="text-xs mt-1 max-w-sm">
            This run did not produce a risk trend series. Complete a quantification run to populate it.
          </p>
        </div>
      </Card>
    );
  }

  const firstPoint = trendData[0];
  const lastPoint = trendData[trendData.length - 1];
  const reductionPct =
    firstPoint?.total_EAL_usd > 0 && lastPoint
      ? ((firstPoint.total_EAL_usd - lastPoint.total_EAL_usd) / firstPoint.total_EAL_usd) * 100
      : null;

  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-th-surface border border-th-border p-3 rounded-lg shadow-soft text-sm">
          <div className="font-semibold text-th-text-primary mb-2 border-b border-th-border pb-1">
            {label} Risk Posture
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
        </div>
      );
    }
    return null;
  };

  return (
    <Card className="w-full">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>Historical Risk & Solvency Trajectory</CardTitle>
            <p className="text-xs text-th-text-secondary mt-1">Expected Annual Loss &amp; 95% Tail Boundaries over previous months</p>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant="warning" title="Backend-generated simulated historical snapshots, not observed history">
              Simulated history
            </Badge>
            {reductionPct !== null && (
              <div
                className={`flex items-center gap-1 text-xs font-medium px-2 py-1 rounded ${
                  reductionPct >= 0 ? 'text-th-brand bg-th-brand/10' : 'text-th-danger bg-th-danger/10'
                }`}
              >
                {reductionPct >= 0 ? <TrendingDown className="w-3.5 h-3.5" /> : <ShieldAlert className="w-3.5 h-3.5" />}
                <span>
                  {reductionPct >= 0 ? '-' : '+'}
                  {Math.abs(reductionPct).toFixed(1)}% {firstPoint?.label} → {lastPoint?.label}
                </span>
              </div>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="h-72 mt-4">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={trendData} margin={{ top: 10, right: 10, left: 0, bottom: 10 }}>
              <defs>
                <linearGradient id="ealGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="var(--th-brand)" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="var(--th-brand)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--th-border)" opacity={0.5} />
              <XAxis 
                dataKey="label" 
                axisLine={false} 
                tickLine={false} 
                tick={{ fill: '#9ca3af', fontSize: 12 }} 
                dy={10} 
              />
              <YAxis 
                yAxisId="left" 
                axisLine={false} 
                tickLine={false} 
                tick={{ fill: '#9ca3af', fontSize: 12 }} 
                tickFormatter={formatCompactCurrency} 
                width={70} 
              />
              <Tooltip content={<CustomTooltip />} />
              <Legend wrapperStyle={{ paddingTop: '20px', fontSize: '12px' }} />
              <Area 
                yAxisId="left" 
                type="monotone" 
                dataKey="total_EAL_usd" 
                name="EAL" 
                stroke="var(--th-brand)" 
                fillOpacity={1} 
                fill="url(#ealGradient)" 
                strokeWidth={2} 
              />
              <Line 
                yAxisId="left" 
                type="monotone" 
                dataKey="total_VaR95_usd" 
                name="95% VaR" 
                stroke="#eab308" 
                strokeWidth={2} 
                dot={{ r: 3, fill: '#eab308' }} 
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
};
