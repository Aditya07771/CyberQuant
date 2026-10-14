import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Activity,
  Radio,
  Pause,
  Play,
  Clock,
  Crosshair,
  ShieldCheck,
} from 'lucide-react';
import { Card, CardHeader, CardTitle, CardContent } from '../ui/Card';
import { Badge } from '../ui/Badge';
import { getLiveFeedWsUrl, getRecentLiveEvents } from '../../api/client';

const severityVariant = (severity) => {
  switch (severity?.toLowerCase()) {
    case 'critical':
      return 'danger';
    case 'high':
      return 'danger';
    case 'medium':
      return 'warning';
    case 'low':
      return 'brand';
    default:
      return 'secondary';
  }
};

export const LiveThreatFeed = () => {
  const [events, setEvents] = useState([]);
  const [sourceType, setSourceType] = useState(null);
  const [feedState, setFeedState] = useState('connecting'); // connecting | live | polling
  const [isPaused, setIsPaused] = useState(false);
  const [severityFilter, setSeverityFilter] = useState('ALL');
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const isPausedRef = useRef(isPaused);
  isPausedRef.current = isPaused;

  const mergeEvents = useCallback((incoming) => {
    if (!Array.isArray(incoming) || incoming.length === 0) return;
    setEvents((prev) => {
      const combined = [...incoming, ...prev];
      const unique = Array.from(
        new Map(combined.map((item) => [item.event_id || `${item.asset_id}-${item.timestamp}`, item])).values(),
      );
      return unique
        .sort((a, b) => new Date(b.timestamp || 0) - new Date(a.timestamp || 0))
        .slice(0, 40);
    });
  }, []);

  useEffect(() => {
    let unmounted = false;

    const connectWebSocket = () => {
      try {
        const socket = new WebSocket(getLiveFeedWsUrl());
        wsRef.current = socket;

        socket.onopen = () => {
          if (unmounted) return;
          setFeedState('live');
        };

        socket.onmessage = (eventMsg) => {
          if (unmounted || isPausedRef.current) return;
          try {
            const data = JSON.parse(eventMsg.data);
            if (data.type === 'INITIAL_STATE' && Array.isArray(data.recent_events)) {
              setSourceType(data.source_type ?? null);
              mergeEvents(data.recent_events);
            } else if (data.type === 'THREAT_EVENT' && data.event) {
              if (data.event.source_type) setSourceType(data.event.source_type);
              mergeEvents([data.event]);
            }
          } catch (e) {
            console.error('Error parsing live feed message:', e);
          }
        };

        socket.onerror = () => {
          if (unmounted) return;
          setFeedState('polling');
        };

        socket.onclose = () => {
          if (unmounted) return;
          setFeedState((prev) => (prev === 'live' ? 'polling' : prev));
          reconnectTimeoutRef.current = setTimeout(() => {
            if (!unmounted) connectWebSocket();
          }, 5000);
        };
      } catch {
        setFeedState('polling');
      }
    };

    connectWebSocket();

    // Load recent events (observed or clearly-labeled synthetic_demo) via REST.
    getRecentLiveEvents()
      .then((res) => {
        if (unmounted || !res) return;
        if (res.source_type) setSourceType(res.source_type);
        mergeEvents(res.events);
      })
      .catch(() => {});

    return () => {
      unmounted = true;
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, [mergeEvents]);

  const filteredEvents = events.filter((ev) => {
    if (severityFilter === 'ALL') return true;
    return ev.severity?.toUpperCase() === severityFilter;
  });

  const formatTime = (isoString) => {
    if (!isoString) return '';
    const d = new Date(isoString);
    return Number.isNaN(d.getTime()) ? '' : d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  };

  const isSynthetic = sourceType === 'synthetic_demo';

  return (
    <Card className="w-full border-th-border shadow-soft overflow-hidden">
      <CardHeader className="pb-3 border-b border-th-border bg-th-surface-el flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div className="flex items-center space-x-3">
          <div className="p-2 rounded-lg bg-th-brand-tint text-th-brand shadow-soft relative">
            <Radio className="w-4 h-4 animate-pulse" />
          </div>
          <div>
            <div className="flex items-center space-x-2 flex-wrap gap-y-1">
              <CardTitle className="text-base font-semibold text-th-text-primary font-serif">
                Threat Telemetry Feed
              </CardTitle>
              <div className="flex items-center space-x-1.5 px-2 py-0.5 rounded-full text-[11px] font-medium bg-th-bg border border-th-border">
                {feedState === 'live' ? (
                  <>
                    <span className="w-2 h-2 rounded-full bg-green-500 animate-ping inline-block" />
                    <span className="text-green-600 font-mono">WebSocket stream</span>
                  </>
                ) : feedState === 'polling' ? (
                  <>
                    <span className="w-2 h-2 rounded-full bg-yellow-500 inline-block" />
                    <span className="text-yellow-600 font-mono">REST polling</span>
                  </>
                ) : (
                  <>
                    <span className="w-2 h-2 rounded-full bg-slate-400 inline-block" />
                    <span className="text-th-text-muted font-mono">Connecting…</span>
                  </>
                )}
              </div>
              {isSynthetic && (
                <Badge variant="warning" title="Endpoint returned labeled synthetic demo events, not observed telemetry">
                  Synthetic demo data
                </Badge>
              )}
            </div>
            <p className="text-xs text-th-text-secondary mt-0.5">
              Security telemetry events associated with this dataset version.
            </p>
          </div>
        </div>

        {/* Controls */}
        <div className="flex items-center space-x-2">
          <div className="flex items-center bg-th-bg rounded-lg p-0.5 border border-th-border text-xs">
            {['ALL', 'CRITICAL', 'HIGH', 'MEDIUM'].map((sev) => (
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

          <button
            onClick={() => setIsPaused(!isPaused)}
            className={`flex items-center space-x-1 px-2.5 py-1 text-xs rounded-lg border font-medium transition-colors ${
              isPaused
                ? 'bg-amber-50 text-amber-700 border-amber-300'
                : 'bg-th-bg text-th-text-secondary border-th-border hover:text-th-text-primary'
            }`}
            title={isPaused ? 'Resume feed' : 'Pause feed'}
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
            <Activity className="w-6 h-6 text-th-brand opacity-60" />
            <p>
              {events.length === 0
                ? 'No threat events reported for this dataset version.'
                : 'No events match the selected severity filter.'}
            </p>
          </div>
        ) : (
          <div className="max-h-72 overflow-y-auto divide-y divide-th-border">
            {filteredEvents.map((ev, idx) => (
              <div
                key={ev.event_id || idx}
                className={`p-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs hover:bg-th-surface-el transition-colors ${
                  idx === 0 ? 'bg-th-brand-tint/30' : ''
                }`}
              >
                <div className="flex items-start space-x-3 min-w-0">
                  <div className="pt-0.5">
                    <div className="p-1 rounded bg-th-bg text-th-text-secondary border border-th-border">
                      <Crosshair className="w-3.5 h-3.5" />
                    </div>
                  </div>

                  <div className="min-w-0 space-y-1">
                    <div className="flex items-center space-x-2 flex-wrap gap-y-1">
                      <Badge variant={severityVariant(ev.severity)} dot>
                        {ev.severity || 'Unknown'}
                      </Badge>
                      <span className="font-mono font-bold text-th-text-primary">
                        {ev.asset_id || '—'}
                      </span>
                      {ev.mitre_technique_id && (
                        <span className="font-mono text-[11px] text-th-text-muted px-1.5 py-0.5 rounded bg-th-bg border border-th-border">
                          {ev.mitre_technique_id}
                        </span>
                      )}
                      <span className="text-th-text-muted text-[11px] flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {formatTime(ev.timestamp) || '—'}
                      </span>
                    </div>
                    <p className="text-th-text-secondary truncate text-xs">
                      {ev.description || 'No description provided.'}
                    </p>
                  </div>
                </div>

                <div className="flex items-center sm:text-right shrink-0 pl-7 sm:pl-0">
                  {ev.action_taken ? (
                    <div className="px-2 py-1 rounded text-right border bg-th-bg border-th-border">
                      <span className="text-[10px] text-th-text-muted uppercase font-semibold block">
                        Action taken
                      </span>
                      <span className="font-medium text-th-text-primary inline-flex items-center gap-1">
                        <ShieldCheck className="w-3 h-3 text-th-brand" />
                        {ev.action_taken}
                      </span>
                    </div>
                  ) : (
                    <span className="text-[11px] text-th-text-muted">Action: —</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
};
