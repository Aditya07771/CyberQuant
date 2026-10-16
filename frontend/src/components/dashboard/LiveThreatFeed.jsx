import React, { useState, useEffect, useRef } from 'react';
import {
  Activity,
  Radio,
  Wifi,
  WifiOff,
  AlertTriangle,
  ShieldCheck,
  ShieldAlert,
  ArrowUpRight,
  ArrowDownRight,
  Pause,
  Play,
  Zap,
  Clock,
  Filter,
} from 'lucide-react';
import { Card, CardHeader, CardTitle, CardContent } from '../ui/Card';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';
import { formatCurrency, getLiveFeedWsUrl, getRecentLiveEvents } from '../../api/client';

export const LiveThreatFeed = ({ onAssetRiskUpdate }) => {
  const [events, setEvents] = useState([]);
  const [isConnected, setIsConnected] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [severityFilter, setSeverityFilter] = useState('ALL');
  const [fallbackMode, setFallbackMode] = useState(false);
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const isPausedRef = useRef(isPaused);
  isPausedRef.current = isPaused;

  useEffect(() => {
    let unmounted = false;

    const connectWebSocket = () => {
      try {
        const wsUrl = getLiveFeedWsUrl();
        const socket = new WebSocket(wsUrl);
        wsRef.current = socket;

        socket.onopen = () => {
          if (unmounted) return;
          setIsConnected(true);
          setFallbackMode(false);
        };

        socket.onmessage = (eventMsg) => {
          if (unmounted || isPausedRef.current) return;
          try {
            const data = JSON.parse(eventMsg.data);
            if (data.type === 'INITIAL_STATE') {
              if (data.recent_events && Array.isArray(data.recent_events)) {
                setEvents((prev) => {
                  const combined = [...data.recent_events, ...prev];
                  const unique = Array.from(new Map(combined.map((item) => [item.event_id, item])).values());
                  return unique.slice(0, 30);
                });
              }
            } else if (data.type === 'THREAT_EVENT' && data.event) {
              const newEvent = data.event;
              setEvents((prev) => [newEvent, ...prev.slice(0, 29)]);

              // Reactively propagate incremental risk update to parent dashboard if handler provided
              if (onAssetRiskUpdate && newEvent.asset_id && newEvent.impact) {
                onAssetRiskUpdate(newEvent.asset_id, {
                  EAL_usd: newEvent.impact.new_eal_usd,
                  VaR95_usd: newEvent.impact.new_var95_usd,
                  priority_score: newEvent.impact.new_priority_score,
                });
              }
            }
          } catch (e) {
            console.error('Error parsing live feed message:', e);
          }
        };

        socket.onerror = () => {
          if (unmounted) return;
          setIsConnected(false);
          setFallbackMode(true);
        };

        socket.onclose = () => {
          if (unmounted) return;
          setIsConnected(false);
          // Try reconnecting in 5 seconds if not unmounted
          reconnectTimeoutRef.current = setTimeout(() => {
            if (!unmounted) connectWebSocket();
          }, 5000);
        };
      } catch (err) {
        setIsConnected(false);
        setFallbackMode(true);
      }
    };

    connectWebSocket();

    // Initial load fallback from REST endpoint in case WS is delayed
    getRecentLiveEvents()
      .then((res) => {
        if (!unmounted && res?.events) {
          setEvents((prev) => {
            if (prev.length > 0) return prev;
            return res.events;
          });
        }
      })
      .catch(() => {});

    return () => {
      unmounted = true;
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [onAssetRiskUpdate]);

  const filteredEvents = events.filter((ev) => {
    if (severityFilter === 'ALL') return true;
    return ev.severity?.toUpperCase() === severityFilter;
  });

  const getEventBadge = (eventType, severity) => {
    switch (eventType) {
      case 'new_vuln_detected':
        return <Badge variant="danger">Vuln Detected</Badge>;
      case 'exploit_attempt':
        return <Badge variant="warning">Exploit Probe</Badge>;
      case 'patch_applied':
        return <Badge variant="success">Patch Deployed</Badge>;
      case 'control_activated':
        return <Badge variant="brand">Control Active</Badge>;
      case 'ransomware_indicator':
        return <Badge variant="danger">Ransomware Heuristic</Badge>;
      default:
        return <Badge variant="secondary">{eventType}</Badge>;
    }
  };

  const formatTime = (isoString) => {
    if (!isoString) return '';
    try {
      const d = new Date(isoString);
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    } catch {
      return '';
    }
  };

  return (
    <Card className="w-full border-th-border shadow-soft overflow-hidden">
      <CardHeader className="pb-3 border-b border-th-border bg-th-surface-el flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div className="flex items-center space-x-3">
          <div className="p-2 rounded-lg bg-th-brand-tint text-th-brand shadow-soft relative">
            <Radio className="w-4 h-4 animate-pulse" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <CardTitle className="text-base font-semibold text-th-text-primary font-serif">
                Real-Time Threat Telemetry &amp; Incremental Risk Feed
              </CardTitle>
              <div className="flex items-center space-x-1.5 px-2 py-0.5 rounded-full text-[11px] font-medium bg-th-bg border border-th-border">
                {isConnected ? (
                  <>
                    <span className="w-2 h-2 rounded-full bg-green-500 animate-ping inline-block" />
                    <span className="text-green-600 font-mono">Live WebSocket</span>
                  </>
                ) : fallbackMode ? (
                  <>
                    <span className="w-2 h-2 rounded-full bg-yellow-500 inline-block" />
                    <span className="text-yellow-600 font-mono">Telemetry Polling</span>
                  </>
                ) : (
                  <>
                    <span className="w-2 h-2 rounded-full bg-slate-400 inline-block" />
                    <span className="text-th-text-muted font-mono">Connecting...</span>
                  </>
                )}
              </div>
            </div>
            <p className="text-xs text-th-text-secondary mt-0.5">
              Live streaming SIEM/EDR events with instant, asset-specific FAIR EAL re-calculation.
            </p>
          </div>
        </div>

        {/* Controls */}
        <div className="flex items-center space-x-2">
          {/* Severity filter */}
          <div className="flex items-center bg-th-bg rounded-lg p-0.5 border border-th-border text-xs">
            {['ALL', 'CRITICAL', 'HIGH'].map((sev) => (
              <button
                key={sev}
                onClick={() => setSeverityFilter(sev)}
                className={`px-2 py-1 rounded text-[11px] font-medium transition-colors ${
                  severityFilter === sev
                    ? 'bg-th-surface text-th-brand shadow-sm font-semibold'
                    : 'text-th-text-secondary hover:text-th-text-primary'
                }`}
              >
                {sev}
              </button>
            ))}
          </div>

          {/* Pause / Resume Button */}
          <button
            onClick={() => setIsPaused(!isPaused)}
            className={`flex items-center space-x-1 px-2.5 py-1 text-xs rounded-lg border font-medium transition-colors ${
              isPaused
                ? 'bg-amber-50 text-amber-700 border-amber-300'
                : 'bg-th-bg text-th-text-secondary border-th-border hover:text-th-text-primary'
            }`}
            title={isPaused ? 'Resume live feed' : 'Pause live feed'}
          >
            {isPaused ? (
              <>
                <Play className="w-3 h-3 text-amber-600" />
                <span>Resume</span>
              </>
            ) : (
              <>
                <Pause className="w-3 h-3" />
                <span>Pause</span>
              </>
            )}
          </button>
        </div>
      </CardHeader>

      <CardContent className="p-0">
        {filteredEvents.length === 0 ? (
          <div className="p-8 text-center text-th-text-muted text-sm flex flex-col items-center justify-center space-y-2">
            <Activity className="w-6 h-6 animate-spin text-th-brand opacity-60" />
            <p>Listening for real-time threat stream events...</p>
          </div>
        ) : (
          <div className="max-h-72 overflow-y-auto divide-y divide-th-border">
            {filteredEvents.map((ev, idx) => {
              const deltaEal = ev.impact?.delta_eal_usd ?? 0;
              const deltaPct = ev.impact?.delta_pct ?? 0;
              const isRiskIncrease = deltaEal > 0;
              const isFirst = idx === 0;

              return (
                <div
                  key={ev.event_id || idx}
                  className={`p-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs hover:bg-th-surface-el transition-colors ${
                    isFirst ? 'bg-th-brand-tint/30' : ''
                  }`}
                >
                  <div className="flex items-start space-x-3 min-w-0">
                    <div className="pt-0.5">
                      {isRiskIncrease ? (
                        <div className="p-1 rounded bg-red-100 dark:bg-red-950/40 text-red-600">
                          <ArrowUpRight className="w-3.5 h-3.5" />
                        </div>
                      ) : (
                        <div className="p-1 rounded bg-green-100 dark:bg-green-950/40 text-green-600">
                          <ArrowDownRight className="w-3.5 h-3.5" />
                        </div>
                      )}
                    </div>

                    <div className="min-w-0 space-y-1">
                      <div className="flex items-center space-x-2 flex-wrap gap-y-1">
                        {getEventBadge(ev.event_type, ev.severity)}
                        <span className="font-mono font-bold text-th-text-primary">
                          {ev.asset_id}
                        </span>
                        <span className="text-th-text-muted text-[11px]">
                          ({ev.business_unit})
                        </span>
                        <span className="text-th-text-muted text-[11px] flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          {formatTime(ev.timestamp)}
                        </span>
                      </div>
                      <p className="text-th-text-secondary truncate text-xs">
                        {ev.description}
                      </p>
                    </div>
                  </div>

                  {/* Reactive Financial Impact Metric */}
                  <div className="flex items-center sm:text-right space-x-3 sm:space-x-4 shrink-0 pl-7 sm:pl-0">
                    <div>
                      <span className="text-[10px] text-th-text-muted uppercase block">
                        New EAL
                      </span>
                      <span className="font-mono font-bold text-th-text-primary">
                        {formatCurrency(ev.impact?.new_eal_usd)}
                      </span>
                    </div>

                    <div
                      className={`px-2 py-1 rounded text-right border ${
                        isRiskIncrease
                          ? 'bg-red-50 dark:bg-red-950/30 text-red-700 dark:text-red-400 border-red-200 dark:border-red-900/40'
                          : 'bg-green-50 dark:bg-green-950/30 text-green-700 dark:text-green-400 border-green-200 dark:border-green-900/40'
                      }`}
                    >
                      <span className="text-[10px] uppercase font-semibold block">
                        Impact Delta
                      </span>
                      <span className="font-mono font-bold">
                        {isRiskIncrease ? '+' : ''}
                        {deltaPct.toFixed(1)}% ({formatCurrency(deltaEal)})
                      </span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
};
