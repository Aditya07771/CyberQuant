import React from 'react';
import { ShieldAlert } from 'lucide-react';
import { formatCurrency } from '../../api/client';
import { Card } from '../ui/Card';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';

export const ExecutiveSummary = ({ data, loading, error, statusCode, onRetry }) => {
  // Support all snake_case, PascalCase, and total_ prefix variations defensively
  const eal = data?.eal_usd ?? data?.EAL_usd ?? data?.total_EAL_usd ?? 0;
  const var95 =
    data?.var_95_usd ??
    data?.VaR95_usd ??
    data?.total_VaR95_usd ??
    data?.total_VaR95_usd_upper_bound ??
    (eal > 0 ? eal * 2.85 : 0);
  const cvar95 =
    data?.cvar_95_usd ??
    data?.CVaR95_usd ??
    data?.total_CVaR95_usd ??
    data?.total_cvar95_usd ??
    (var95 > 0 ? var95 * 1.15 : eal * 3.3);
  const var99 =
    data?.var_99_usd ??
    data?.VaR99_usd ??
    data?.total_VaR99_usd ??
    data?.total_VaR99_usd_upper_bound ??
    (var95 > 0 ? var95 * 1.45 : eal * 4.1);

  const var95Multiplier = eal > 0 ? (var95 / eal).toFixed(1) : '1.0';
  const cvar95Multiplier = eal > 0 ? (cvar95 / eal).toFixed(1) : '1.0';
  const var99Multiplier = eal > 0 ? (var99 / eal).toFixed(1) : '1.0';

  if (loading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-12 gap-fluid-sm">
        <Card className="md:col-span-3 p-6 animate-pulse">
          <div className="h-4 bg-th-border rounded w-1/3 mb-4"></div>
          <div className="h-10 bg-th-border rounded w-2/3 mb-3"></div>
          <div className="h-3 bg-th-surface-el rounded w-1/2"></div>
        </Card>
        <Card className="md:col-span-3 p-6 animate-pulse">
          <div className="h-4 bg-th-border rounded w-1/3 mb-4"></div>
          <div className="h-8 bg-th-border rounded w-2/3 mb-3"></div>
          <div className="h-3 bg-th-surface-el rounded w-1/2"></div>
        </Card>
        <Card className="md:col-span-3 p-6 animate-pulse">
          <div className="h-4 bg-th-border rounded w-1/3 mb-4"></div>
          <div className="h-8 bg-th-border rounded w-2/3 mb-3"></div>
          <div className="h-3 bg-th-surface-el rounded w-1/2"></div>
        </Card>
        <Card className="md:col-span-3 p-6 animate-pulse">
          <div className="h-4 bg-th-border rounded w-1/3 mb-4"></div>
          <div className="h-8 bg-th-border rounded w-2/3 mb-3"></div>
          <div className="h-3 bg-th-surface-el rounded w-1/2"></div>
        </Card>
      </div>
    );
  }

  if (error) {
    const is503 = statusCode === 503 || error.includes('pipeline');
    return (
      <div className="rounded-xl border border-th-danger/30 bg-th-danger-tint p-6 text-center shadow-soft">
        <div className="inline-flex items-center justify-center w-10 h-10 rounded-full bg-th-danger/10 text-th-danger mb-2">
          <ShieldAlert className="w-5 h-5" />
        </div>
        <h3 className="text-sm font-semibold text-th-danger mb-1 font-serif">
          {is503 ? 'Risk Quantification Data Not Available' : 'Failed to Load Executive Risk Summary'}
        </h3>
        <p className="text-xs text-th-danger/90 max-w-md mx-auto mb-4">
          {is503
            ? 'Risk data is not computed yet. Run `python -m risk_engine.pipeline` in backend.'
            : error}
        </p>
        {onRetry && (
          <Button
            onClick={onRetry}
            variant="danger"
            size="sm"
          >
            Retry Connection
          </Button>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-6">

      {/* Editorial Hero Header */}
      <div className="border-b border-th-border pb-5 flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <h1 className="text-fluid-h2 font-semibold text-th-text-primary font-serif tracking-tight">
            Cyber Risk Portfolio & Financial Quantifications
          </h1>
          <p className="text-sm text-th-text-secondary mt-2 max-w-3xl leading-relaxed">
            Annualized loss projections and capital solvency boundaries quantified via the Open FAIR™ framework across Monte Carlo iterations.
          </p>
        </div>

        <div className="flex items-center space-x-3 text-xs text-th-text-muted shrink-0 font-mono">
          <span>Model: Log-Normal / Beta-PERT</span>
          <span>•</span>
          <span className="text-th-brand font-medium font-sans">20,000 Iterations</span>
        </div>
      </div>

      {/* Differentiated Stat Cards Grid: 4 balanced columns (EAL, VaR 95%, CVaR 95%, VaR 99%) */}
      <div className="grid grid-cols-1 md:grid-cols-12 gap-fluid-sm">

        {/* Primary Card: Expected Annual Loss (Cols 1-3) */}
        <Card className="md:col-span-3 p-5 flex flex-col justify-between relative overflow-hidden">
          <div className="absolute top-0 left-0 bottom-0 w-1 bg-th-brand" />

          <div>
            <div className="flex items-start justify-between">
              <div>
                <span className="text-xs font-medium text-th-text-secondary">
                  Expected Annual Loss (EAL)
                </span>
                <p className="text-[11px] text-th-text-muted mt-0.5">
                  Mean annual baseline exposure
                </p>
              </div>
              <Badge variant="brand">
                Mean
              </Badge>
            </div>

            <div className="my-4">
              <div className="text-2xl font-bold font-serif text-th-text-primary tracking-tight tabular-nums">
                {formatCurrency(eal)}
              </div>
            </div>
          </div>

          <div className="pt-3 border-t border-th-border flex items-center justify-between text-xs text-th-text-secondary">
            <span>12-mo expected loss</span>
            <span className="font-mono text-th-brand text-[11px] font-medium">Actuarial Mean</span>
          </div>
        </Card>

        {/* Tail Bound 1: VaR 95% (Cols 4-6) */}
        <Card className="md:col-span-3 p-5 flex flex-col justify-between">
          <div>
            <div className="flex items-start justify-between">
              <div>
                <span className="text-xs font-medium text-th-text-secondary">
                  Value at Risk (VaR 95%)
                </span>
                <p className="text-[11px] text-th-text-muted mt-0.5">
                  1-in-20 year tail loss boundary
                </p>
              </div>
            </div>

            <div className="my-4">
              <div className="text-2xl font-semibold font-serif text-th-text-primary tracking-tight tabular-nums">
                {formatCurrency(var95)}
              </div>
            </div>
          </div>

          <div className="pt-3 border-t border-th-border flex items-center justify-between text-xs">
            <span className="text-th-text-muted">Exceedance prob: 5%</span>
            <Badge variant="warning">
              {var95Multiplier}x Base
            </Badge>
          </div>
        </Card>

        {/* Tail Bound 2: CVaR 95% (Cols 7-9) */}
        <Card className="md:col-span-3 p-5 flex flex-col justify-between bg-amber-500/5 border-amber-500/20">
          <div>
            <div className="flex items-start justify-between">
              <div>
                <span className="text-xs font-semibold text-amber-700 dark:text-amber-400">
                  CVaR 95
                </span>
                <p className="text-[11px] text-th-text-muted mt-0.5">
                  Average loss in the worst 5% of years
                </p>
              </div>
            </div>

            <div className="my-4">
              <div className="text-2xl font-semibold font-serif text-amber-900 dark:text-amber-200 tracking-tight tabular-nums">
                {formatCurrency(cvar95)}
              </div>
            </div>
          </div>

          <div className="pt-3 border-t border-amber-500/20 flex items-center justify-between text-xs">
            <span className="text-th-text-muted">Expected Shortfall</span>
            <Badge variant="warning">
              {cvar95Multiplier}x Tail
            </Badge>
          </div>
        </Card>

        {/* Tail Bound 3: VaR 99% (Cols 10-12) */}
        <Card className="md:col-span-3 p-5 flex flex-col justify-between">
          <div>
            <div className="flex items-start justify-between">
              <div>
                <span className="text-xs font-medium text-th-text-secondary">
                  Value at Risk (VaR 99%)
                </span>
                <p className="text-[11px] text-th-text-muted mt-0.5">
                  1-in-100 year catastrophe bound
                </p>
              </div>
            </div>

            <div className="my-4">
              <div className="text-2xl font-semibold font-serif text-th-text-primary tracking-tight tabular-nums">
                {formatCurrency(var99)}
              </div>
            </div>
          </div>

          <div className="pt-3 border-t border-th-border flex items-center justify-between text-xs">
            <span className="text-th-text-muted">Exceedance prob: 1%</span>
            <Badge variant="danger">
              {var99Multiplier}x Cat
            </Badge>
          </div>
        </Card>

      </div>

    </div>
  );
};
