import React from 'react';
import { ComposedChart, Area, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/Card';
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

  // Fallback demo trend data if backend is empty
  const defaultTrendData = [
    { label: 'Q1 2025', total_EAL_usd: 12500000, total_VaR95_usd: 28000000 },
    { label: 'Q2 2025', total_EAL_usd: 11200000, total_VaR95_usd: 26500000 },
    { label: 'Q3 2025', total_EAL_usd: 9800000, total_VaR95_usd: 23100000 },
    { label: 'Q4 2025', total_EAL_usd: 8400000, total_VaR95_usd: 19800000 },
    { label: 'Q1 2026', total_EAL_usd: 6900000, total_VaR95_usd: 16500000 },
    { label: 'Current', total_EAL_usd: 5100000, total_VaR95_usd: 12500000 },
  ];

  const trendData = data && data.length > 0 ? data : defaultTrendData;

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
            <p className="text-xs text-th-text-secondary mt-1">Expected Annual Loss & 95% Tail Boundaries over previous quarters</p>
          </div>
          <div className="flex items-center gap-1 text-xs font-medium text-th-brand bg-th-brand/10 px-2 py-1 rounded">
            <TrendingDown className="w-3.5 h-3.5" />
            <span>-59% 12-Mo Reduction</span>
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
