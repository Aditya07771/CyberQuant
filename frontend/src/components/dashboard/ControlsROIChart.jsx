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
import { Award, Zap } from 'lucide-react';
import { formatCurrency, formatMultiplier } from '../../api/client';
import { Card } from '../ui/Card';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';

const CustomTooltip = ({ active, payload }) => {
  if (active && payload && payload.length) {
    const d = payload[0].payload;
    return (
      <div className="bg-th-surface-el p-3 rounded-lg border border-th-border shadow-elevated text-xs space-y-1.5 min-w-[240px] z-50">
        <div className="font-semibold text-th-text-primary border-b border-th-border pb-1.5 flex items-center justify-between font-serif">
          <span className="truncate max-w-[170px]">{d.control_name || d.control_id}</span>
          <span className="text-[10px] text-th-brand font-mono font-bold">
            {formatMultiplier(d.overall_ROSI)} ROSI
          </span>
        </div>
        <div className="flex justify-between items-center text-th-text-secondary pt-1">
          <span>Investment Cost:</span>
          <span className="font-mono text-th-text-primary font-medium tabular-nums">{formatCurrency(d.total_cost_usd)}</span>
        </div>
        <div className="flex justify-between items-center text-th-text-secondary">
          <span>Risk Reduction:</span>
          <span className="font-mono text-th-brand font-semibold tabular-nums">
            {formatCurrency(d.total_risk_reduction_usd)}
          </span>
        </div>
        <div className="flex justify-between items-center text-th-text-secondary pt-2 mt-1 border-t border-th-border">
          <span>Applicable Assets:</span>
          <span className="font-mono text-th-text-muted">{d.applicable_assets || '—'}</span>
        </div>
      </div>
    );
  }
  return null;
};

export const ControlsROIChart = ({ data = [], loading, error, onRetry }) => {
  if (loading) {
    return (
      <Card className="h-[360px] flex flex-col justify-center items-center p-6">
        <div className="w-7 h-7 rounded-full border-2 border-th-brand border-t-transparent animate-spin mb-3"></div>
        <p className="text-sm text-th-text-muted font-medium">Calculating Return on Security Investment (ROSI)...</p>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="h-[360px] flex flex-col justify-center items-center p-6 border-th-danger/30 bg-th-danger-tint">
        <p className="text-sm font-semibold text-th-danger mb-2 font-serif">Error Loading Controls ROI</p>
        <p className="text-xs text-th-danger/90 mb-4 text-center max-w-sm">{error}</p>
        {onRetry && (
          <Button onClick={onRetry} variant="danger" size="sm">
            Retry
          </Button>
        )}
      </Card>
    );
  }

  if (!data || data.length === 0) {
    return (
      <Card className="h-[360px] flex flex-col justify-center items-center p-6 text-center">
        <Award className="w-8 h-8 text-th-text-muted mb-3" />
        <p className="text-sm font-semibold text-th-text-primary font-serif">No Controls ROI Data</p>
        <p className="text-xs text-th-text-muted mt-1">Run risk scenarios to evaluate control mitigations.</p>
      </Card>
    );
  }

  // Sort descending by overall_ROSI
  const sortedData = [...data].sort((a, b) => (b.overall_ROSI || 0) - (a.overall_ROSI || 0));

  return (
    <Card className="flex flex-col h-full justify-between p-5">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-3">
          <div className="p-2 rounded-lg bg-th-brand-tint text-th-brand shadow-soft">
            <Zap className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-th-text-primary font-serif">
              Security Controls Ranked by ROI (ROSI)
            </h3>
            <p className="text-xs text-th-text-secondary mt-0.5">
              ROSI = (Risk Reduction) / (Implementation Cost)
            </p>
          </div>
        </div>
        <Badge variant="brand">
          Ranked by ROI
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
              tickFormatter={(val) => `${val.toFixed(1)}x`}
              stroke="var(--chart-axis)"
              fontSize={11}
              tickLine={false}
            />
            <YAxis
              type="category"
              dataKey="control_name"
              stroke="var(--chart-axis)"
              fontSize={11}
              tickLine={false}
              axisLine={false}
              width={135}
              tickFormatter={(val) => (val && val.length > 18 ? `${val.substring(0, 18)}...` : val)}
            />
            <Tooltip content={<CustomTooltip />} cursor={{ fill: 'var(--surface-elevated)' }} />
            <Bar dataKey="overall_ROSI" radius={[0, 4, 4, 0]}>
              {sortedData.map((entry, index) => {
                const fillVar = 
                  index === 0 ? 'var(--chart-bar-alt-1)' :
                  index <= 2 ? 'var(--chart-bar-alt-2)' :
                  'var(--chart-bar-alt-3)';
                return <Cell key={`cell-ctrl-${index}`} fill={fillVar} />;
              })}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
};
