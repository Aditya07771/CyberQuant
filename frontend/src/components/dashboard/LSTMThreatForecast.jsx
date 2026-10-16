import React, { useState, useEffect } from 'react';
import {
  Cpu,
  TrendingUp,
  AlertTriangle,
  ArrowRight,
  ShieldAlert,
  Layers,
  Activity,
  CheckCircle2,
  RefreshCw,
  Info,
} from 'lucide-react';
import {
  ResponsiveContainer,
  ComposedChart,
  Area,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
} from 'recharts';
import { getThreatForecast } from '../../api/client';
import { Card, CardHeader, CardTitle, CardContent } from '../ui/Card';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';

export const LSTMThreatForecast = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeView, setActiveView] = useState('combined'); // 'combined', 'forecast_only', 'killchain'

  const fetchForecast = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getThreatForecast(14);
      setData(res);
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Failed to fetch LSTM threat forecast');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchForecast();
  }, []);

  // Format combined data points for continuous timeline
  const chartData = React.useMemo(() => {
    if (!data) return [];
    const historical = (data.historical_series || []).map((h) => ({
      date: h.date,
      observed: h.total_events,
      critical: h.critical_events,
      allowed: h.allowed_events,
      isForecast: false,
    }));

    const forecast = (data.forecast_series || []).map((f) => ({
      date: f.date,
      predicted: f.predicted_events,
      lowerBound: f.lower_bound,
      upperBound: f.upper_bound,
      alertLevel: f.alert_level,
      isForecast: true,
    }));

    // Bridge the last historical point to forecast to avoid a disconnected line
    if (historical.length > 0 && forecast.length > 0) {
      const lastHist = historical[historical.length - 1];
      const bridgedPoint = {
        date: lastHist.date,
        observed: lastHist.observed,
        predicted: lastHist.observed,
        lowerBound: lastHist.observed,
        upperBound: lastHist.observed,
        isForecast: false,
      };
      return [...historical.slice(0, -1), bridgedPoint, ...forecast];
    }

    return [...historical, ...forecast];
  }, [data]);

  const summary = data?.summary || {};
  const isSurging = summary.trend_direction === 'Surging';

  return (
    <div className="space-y-fluid-md animate-in fade-in slide-in-from-bottom-4 duration-500">
      {/* Title & Top Toolbar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-th-border pb-4">
        <div>
          <div className="flex items-center space-x-2">
            <div className="p-2 rounded-lg bg-th-brand-tint text-th-brand shadow-soft">
              <Cpu className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-xl font-semibold text-th-text-primary font-serif">
                  Sequential Neural Network (LSTM) Threat Telemetry Forecaster
                </h2>
                <Badge variant={isSurging ? 'warning' : 'brand'}>
                  {summary.trend_direction || 'Active'}
                </Badge>
              </div>
              <p className="text-xs text-th-text-secondary mt-0.5">
                Deep Recurrent Multi-Period Threat Event Frequency (TEF) prediction &amp; MITRE ATT&amp;CK kill-chain sequence modeling.
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={fetchForecast}
            isLoading={loading}
            className="text-xs gap-1.5"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Retrain &amp; Refresh</span>
          </Button>
        </div>
      </div>

      {loading ? (
        <div className="space-y-4 animate-pulse">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {[1, 2, 3, 4].map((i) => (
              <Card key={i} className="h-24 bg-th-surface-el border-none"></Card>
            ))}
          </div>
          <Card className="h-80 bg-th-surface-el border-none"></Card>
        </div>
      ) : error ? (
        <Card className="p-6 text-center border-th-danger/30 bg-th-danger-tint">
          <AlertTriangle className="w-8 h-8 text-th-danger mx-auto mb-2" />
          <h3 className="text-base font-semibold text-th-danger font-serif">Forecast Engine Offline</h3>
          <p className="text-xs text-th-danger/90 mt-1">{error}</p>
          <Button onClick={fetchForecast} size="sm" variant="secondary" className="mt-4">
            Retry Connection
          </Button>
        </Card>
      ) : (
        <>
          {/* Top KPI Stat Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <Card className="p-4 shadow-soft bg-th-surface">
              <div className="flex items-center justify-between text-th-text-secondary">
                <span className="text-xs font-medium">Historical Baseline TEF</span>
                <Activity className="w-4 h-4 text-th-text-muted" />
              </div>
              <div className="text-2xl font-bold font-serif text-th-text-primary mt-2 tabular-nums">
                {summary.baseline_daily_events ?? 0}
                <span className="text-xs font-normal text-th-text-muted ml-1 font-sans">events/day</span>
              </div>
              <p className="text-[11px] text-th-text-secondary mt-1">
                Empirical mean across 30-day telemetry ({summary.total_observed_events} total)
              </p>
            </Card>

            <Card className="p-4 shadow-soft bg-th-surface">
              <div className="flex items-center justify-between text-th-text-secondary">
                <span className="text-xs font-medium">LSTM Projected TEF (14d)</span>
                <TrendingUp className={`w-4 h-4 ${isSurging ? 'text-th-warning' : 'text-th-brand'}`} />
              </div>
              <div className="text-2xl font-bold font-serif text-th-text-primary mt-2 tabular-nums">
                {summary.forecasted_daily_events ?? 0}
                <span className="text-xs font-normal text-th-text-muted ml-1 font-sans">events/day</span>
              </div>
              <div className="flex items-center gap-1 mt-1">
                <Badge variant={isSurging ? 'warning' : 'brand'}>
                  {summary.tef_shift_pct > 0 ? `+${summary.tef_shift_pct}%` : `${summary.tef_shift_pct}%`} Shift
                </Badge>
                <span className="text-[11px] text-th-text-muted">vs historical mean</span>
              </div>
            </Card>

            <Card className="p-4 shadow-soft bg-th-surface">
              <div className="flex items-center justify-between text-th-text-secondary">
                <span className="text-xs font-medium">Predicted Surge Peak</span>
                <AlertTriangle className="w-4 h-4 text-th-warning" />
              </div>
              <div className="text-2xl font-bold font-serif text-th-warning mt-2 tabular-nums">
                {summary.peak_forecast_value ?? 0}
                <span className="text-xs font-normal text-th-text-muted ml-1 font-sans">events</span>
              </div>
              <p className="text-[11px] text-th-text-secondary mt-1">
                Estimated peak on <strong className="text-th-text-primary">{summary.peak_forecast_date}</strong>
              </p>
            </Card>

            <Card className="p-4 shadow-soft bg-th-surface">
              <div className="flex items-center justify-between text-th-text-secondary">
                <span className="text-xs font-medium">Model Architecture &amp; Loss</span>
                <Cpu className="w-4 h-4 text-th-brand" />
              </div>
              <div className="text-sm font-semibold font-mono text-th-brand mt-2 truncate">
                2-Layer PyTorch LSTM
              </div>
              <div className="flex items-center gap-2 mt-1 text-[11px] text-th-text-secondary">
                <span>Seq Window: <strong className="text-th-text-primary">{summary.sequence_window_days}d</strong></span>
                <span>•</span>
                <span>MSE: <strong className="text-th-text-primary font-mono">{summary.training_loss_mse}</strong></span>
              </div>
            </Card>
          </div>

          {/* Main Time-Series Forecast Chart */}
          <Card className="p-5 shadow-card space-y-4 bg-th-surface">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-th-border pb-3">
              <div>
                <CardTitle className="text-base font-semibold font-serif text-th-text-primary flex items-center gap-2">
                  <Activity className="w-4 h-4 text-th-brand" />
                  Telemetry Time-Series &amp; Forward 14-Day LSTM Rollout
                </CardTitle>
                <p className="text-xs text-th-text-secondary mt-0.5">
                  Historical SIEM event frequency concatenated with autoregressive LSTM forward projections and 90% confidence interval band.
                </p>
              </div>

              {/* View filter buttons */}
              <div className="flex items-center space-x-1 bg-th-bg rounded-lg p-1 border border-th-border self-start">
                <button
                  onClick={() => setActiveView('combined')}
                  className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${
                    activeView === 'combined'
                      ? 'bg-th-surface border border-th-border text-th-brand shadow-sm'
                      : 'text-th-text-secondary hover:text-th-text-primary'
                  }`}
                >
                  Full Timeline
                </button>
                <button
                  onClick={() => setActiveView('forecast_only')}
                  className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${
                    activeView === 'forecast_only'
                      ? 'bg-th-surface border border-th-border text-th-brand shadow-sm'
                      : 'text-th-text-secondary hover:text-th-text-primary'
                  }`}
                >
                  Forecast Horizon Only
                </button>
              </div>
            </div>

            <div className="h-80 w-full pt-2">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart
                  data={
                    activeView === 'forecast_only'
                      ? chartData.filter((d) => d.isForecast || d.predicted !== undefined)
                      : chartData
                  }
                  margin={{ top: 10, right: 20, left: 0, bottom: 20 }}
                >
                  <defs>
                    <linearGradient id="colorUncertainty" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.25} />
                      <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0.05} />
                    </linearGradient>
                    <linearGradient id="colorObserved" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="var(--chart-area-fill-start)" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="var(--chart-area-fill-end)" stopOpacity={0.0} />
                    </linearGradient>
                  </defs>

                  <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" vertical={false} />
                  <XAxis
                    dataKey="date"
                    stroke="var(--chart-axis)"
                    fontSize={11}
                    tickLine={false}
                    tickFormatter={(val) => {
                      if (!val) return '';
                      const parts = val.split('-');
                      return `${parts[1]}/${parts[2]}`;
                    }}
                  />
                  <YAxis
                    stroke="var(--chart-axis)"
                    fontSize={11}
                    tickLine={false}
                    axisLine={false}
                    label={{
                      value: 'Events / Day',
                      angle: -90,
                      position: 'insideLeft',
                      style: { fontSize: 10, fill: 'var(--text-secondary)' },
                    }}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'var(--surface-elevated)',
                      borderColor: 'var(--border)',
                      borderRadius: '8px',
                      fontSize: '12px',
                      color: 'var(--text-primary)',
                      boxShadow: 'var(--shadow-elevated)',
                    }}
                    labelFormatter={(label) => `Date: ${label}`}
                  />
                  <Legend
                    wrapperStyle={{ fontSize: '11px', paddingTop: '10px' }}
                    iconType="circle"
                  />

                  {/* 90% Confidence Interval Band (Area) */}
                  <Area
                    type="monotone"
                    dataKey="upperBound"
                    name="90% Confidence Band (Upper)"
                    stroke="transparent"
                    fill="url(#colorUncertainty)"
                    isAnimationActive={false}
                  />

                  {/* Historical Observed Telemetry */}
                  <Line
                    type="monotone"
                    dataKey="observed"
                    name="Historical Observed Attacks"
                    stroke="var(--chart-area-stroke)"
                    strokeWidth={2.5}
                    dot={{ r: 2 }}
                    activeDot={{ r: 5 }}
                  />

                  {/* LSTM Model Forward Prediction */}
                  <Line
                    type="monotone"
                    dataKey="predicted"
                    name="LSTM Forecast Projection"
                    stroke="#8b5cf6"
                    strokeWidth={2.5}
                    strokeDasharray="4 4"
                    dot={{ r: 3, fill: '#8b5cf6' }}
                    activeDot={{ r: 6 }}
                  />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
            
            <div className="flex flex-wrap items-center justify-between text-xs text-th-text-secondary pt-2 border-t border-th-border/60">
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-th-brand inline-block"></span>
                Historical Observed Telemetry
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-purple-500 inline-block"></span>
                Autoregressive LSTM Prediction
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-sm bg-purple-500/20 border border-purple-500/40 inline-block"></span>
                Uncertainty Envelope (Lower / Upper Bounds)
              </span>
            </div>
          </Card>

          {/* Lower Grid: MITRE ATT&CK Sequence Transitions & Actuarial Context */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-fluid-md">
            {/* MITRE ATT&CK Sequential Kill-Chain Prediction */}
            <div className="lg:col-span-7">
              <Card className="p-5 shadow-soft h-full flex flex-col justify-between bg-th-surface">
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <CardTitle className="text-base font-semibold font-serif text-th-text-primary flex items-center gap-2">
                      <ShieldAlert className="w-4 h-4 text-th-danger" />
                      MITRE ATT&amp;CK Sequential Intrusion Transitions
                    </CardTitle>
                    <Badge variant="secondary" className="text-[10px]">
                      Markovian Chain
                    </Badge>
                  </div>
                  <p className="text-xs text-th-text-secondary mb-4 leading-relaxed">
                    Conditional transition probabilities $P(T_{'{t+1}'} \mid T_t)$ calculated from multi-stage attack telemetry sequences. Enables proactive control placement before attackers progress to impact phases.
                  </p>

                  <div className="space-y-3">
                    {(data.mitre_transitions || []).map((trans, idx) => (
                      <div
                        key={idx}
                        className="p-3 rounded-lg border border-th-border bg-th-surface-el flex items-center justify-between gap-3 text-xs"
                      >
                        <div className="flex-1 min-w-0">
                          <div className="font-semibold text-th-text-primary truncate">
                            {trans.from_name}
                          </div>
                          <span className="text-[11px] font-mono text-th-text-muted">
                            {trans.from_technique}
                          </span>
                        </div>

                        <div className="flex items-center space-x-1.5 text-th-brand px-1">
                          <ArrowRight className="w-4 h-4 flex-shrink-0" />
                          <span className="font-mono font-bold text-xs">
                            {(trans.transition_probability * 100).toFixed(0)}%
                          </span>
                        </div>

                        <div className="flex-1 min-w-0 text-right">
                          <div className="font-semibold text-th-text-primary truncate">
                            {trans.to_name}
                          </div>
                          <span className="text-[11px] font-mono text-th-danger font-medium">
                            {trans.to_technique}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="mt-4 p-3 rounded-lg bg-th-brand-tint text-th-brand text-xs flex items-start gap-2">
                  <Info className="w-4 h-4 flex-shrink-0 mt-0.5" />
                  <span>
                    <strong>Defensive Recommendation:</strong> Highest transition flow leads to <strong>T1486 (Ransomware)</strong>. Enforcing Immutable Backups and EDR agent isolation disrupts this kill-chain sequence.
                  </span>
                </div>
              </Card>
            </div>

            {/* Actuarial Rationale & Model Comparison */}
            <div className="lg:col-span-5">
              <Card className="p-5 shadow-soft h-full flex flex-col justify-between bg-th-surface">
                <div className="space-y-4">
                  <div className="flex items-center space-x-2 text-th-brand">
                    <Layers className="w-5 h-5" />
                    <h3 className="text-sm font-semibold text-th-text-primary font-serif">
                      Actuarial &amp; Machine Learning Methodology
                    </h3>
                  </div>

                  <div className="space-y-3 text-xs text-th-text-secondary leading-relaxed">
                    <div className="p-3 rounded-lg bg-th-surface-el border border-th-border">
                      <span className="font-semibold text-th-text-primary block mb-1">
                        1. Why Sequential Neural Networks for Telemetry?
                      </span>
                      Traditional Open FAIR™ calculates Threat Event Frequency (TEF) using static annualization. The PyTorch LSTM captures non-linear attack bursts and seasonal incident acceleration, dynamically recalibrating Monte Carlo iterations.
                    </div>

                    <div className="p-3 rounded-lg bg-th-surface-el border border-th-border">
                      <span className="font-semibold text-th-text-primary block mb-1">
                        2. Model Selection: Tree-Based vs. Recurrent
                      </span>
                      While <strong>XGBoost / Random Forest</strong> excel at tabular CVE snapshot scoring (CVSS, EPSS, sensitivity), <strong>LSTM Recurrent Networks</strong> dominate sequential temporal telemetry (sliding time windows and kill-chain paths).
                    </div>

                    <div className="p-3 rounded-lg bg-th-surface-el border border-th-border">
                      <span className="font-semibold text-th-text-primary block mb-1">
                        3. FAIR TEF Modulation Factor
                      </span>
                      Current forecasted trend indicates a <strong className="text-th-text-primary">+{summary.tef_shift_pct}%</strong> variance in threat volume, updating the triangular distribution mode for upcoming quarter simulations.
                    </div>
                  </div>
                </div>

                <div className="mt-4 pt-3 border-t border-th-border flex items-center justify-between text-[11px] text-th-text-muted">
                  <span>Engine: {summary.engine}</span>
                  <span className="flex items-center gap-1 text-th-brand font-medium">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    Continuous Inference Ready
                  </span>
                </div>
              </Card>
            </div>
          </div>
        </>
      )}
    </div>
  );
};
