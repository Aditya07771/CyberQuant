import React from 'react';
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
import { Building2, Layers } from 'lucide-react';
import { formatCurrency, formatCompactCurrency } from '../../api/client';
import { Card } from '../ui/Card';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';

const CustomTooltip = ({ active, payload }) => {
  if (active && payload && payload.length) {
    const data = payload[0].payload;
    return (
      <div className="bg-th-surface-el p-3 rounded-lg border border-th-border shadow-elevated text-xs space-y-1.5 min-w-[210px] z-50">
        <div className="font-semibold text-th-text-primary border-b border-th-border pb-1.5 flex items-center justify-between font-serif">
          <span>{data.business_unit}</span>
          <span className="text-[10px] text-th-brand font-mono font-medium">BU Exposure</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-th-text-secondary">Expected Loss:</span>
          <span className="font-bold font-serif text-th-text-primary tabular-nums">
            {formatCurrency(data.total_EAL_usd)}
          </span>
        </div>
        {data.total_VaR95_usd_upper_bound && (
          <div className="flex items-center justify-between text-th-text-muted text-[11px]">
            <span>VaR 95% Bound:</span>
            <span className="font-mono tabular-nums">{formatCurrency(data.total_VaR95_usd_upper_bound)}</span>
          </div>
        )}
      </div>
    );
  }
  return null;
};

export const BusinessUnitChart = ({ data, loading, error, onRetry }) => {
  if (loading) {
    return (
      <Card className="p-6">
        <div className="flex items-center space-x-2 mb-4">
          <div className="w-4 h-4 bg-th-border rounded animate-pulse" />
          <div className="h-4 bg-th-border rounded w-40 animate-pulse" />
        </div>
        <div className="h-64 bg-th-surface-el rounded-lg animate-pulse" />
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="p-6 bg-th-danger-tint border-th-danger/30 text-center shadow-soft">
        <p className="text-sm font-semibold text-th-danger font-serif">Failed to Load Business Unit Risk</p>
        <p className="text-xs text-th-danger/90 mt-1 mb-4">{error}</p>
        {onRetry && (
          <Button onClick={onRetry} variant="danger" size="sm">
            Retry
          </Button>
        )}
      </Card>
    );
  }

  const sortedData = [...(data || [])].sort((a, b) => b.total_EAL_usd - a.total_EAL_usd);

  if (sortedData.length === 0) {
    return (
      <Card className="p-6 text-center text-th-text-muted">
        <Building2 className="w-8 h-8 mx-auto mb-2 opacity-50" />
        <p className="text-sm font-serif">No Business Unit Risk Data</p>
      </Card>
    );
  }

  return (
    <Card className="p-6 flex flex-col justify-between">
      <div className="flex items-center justify-between border-b border-th-border pb-4">
        <div className="flex items-center space-x-3">
          <div className="p-2 rounded-lg bg-th-brand-tint text-th-brand shadow-soft">
            <Building2 className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-th-text-primary font-serif">
              Risk Distribution by Business Unit
            </h3>
            <p className="text-xs text-th-text-secondary mt-0.5">
              Annualized loss magnitude across operational divisions
            </p>
          </div>
        </div>
        <Badge variant="brand">
          {sortedData.length} Units
        </Badge>
      </div>

      <div className="w-full h-[270px] mt-2">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={sortedData}
            layout="vertical"
            margin={{ top: 5, right: 20, left: 5, bottom: 5 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" horizontal={false} />
            <XAxis
              type="number"
              tickFormatter={formatCompactCurrency}
              stroke="var(--chart-axis)"
              fontSize={11}
              tickLine={false}
            />
            <YAxis
              type="category"
              dataKey="business_unit"
              stroke="var(--chart-axis)"
              fontSize={11}
              tickLine={false}
              axisLine={false}
              width={110}
            />
            <Tooltip content={<CustomTooltip />} cursor={{ fill: 'var(--surface-elevated)' }} />
            <Bar dataKey="total_EAL_usd" radius={[0, 4, 4, 0]}>
              {sortedData.map((entry, index) => {
                const fillVar = 
                  index === 0 ? 'var(--chart-bar-1)' :
                  index === 1 ? 'var(--chart-bar-2)' :
                  index === 2 ? 'var(--chart-bar-3)' :
                  'var(--chart-bar-4)';
                return <Cell key={`cell-${index}`} fill={fillVar} />;
              })}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
};
