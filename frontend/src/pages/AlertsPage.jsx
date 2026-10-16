import React, { useState, useCallback } from 'react';
import { Bell, AlertCircle, CheckCircle2, RefreshCw, Shield, ChevronLeft, ChevronRight } from 'lucide-react';
import { Header } from '../components/layout/Header';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { useApi } from '../hooks/useApi';
import {
  listAlerts,
  acknowledgeAlert,
  resolveAlert,
  closeAlert,
  escalateAlert,
  getApiErrorMessage,
} from '../api/client';

const PAGE_SIZE = 25;

const severityVariant = (severity) => {
  switch (String(severity || '').toLowerCase()) {
    case 'critical':
    case 'high':
      return 'danger';
    case 'medium':
      return 'warning';
    case 'low':
      return 'success';
    default:
      return 'default';
  }
};

const statusVariant = (status) => {
  switch (String(status || '').toLowerCase()) {
    case 'closed':
    case 'resolved':
      return 'success';
    case 'acknowledged':
    case 'in_progress':
      return 'warning';
    default:
      return 'brand';
  }
};

export function AlertsPage() {
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState('');
  const [severityFilter, setSeverityFilter] = useState('');
  const [actionError, setActionError] = useState(null);
  const [busyId, setBusyId] = useState(null);

  const fetcher = useCallback(
    () =>
      listAlerts({
        status: statusFilter || undefined,
        severity: severityFilter || undefined,
        page,
        pageSize: PAGE_SIZE,
      }),
    [statusFilter, severityFilter, page],
  );

  const alerts = useApi(fetcher, [statusFilter, severityFilter, page]);

  const data = alerts.data || {};
  const items = Array.isArray(data.alerts) ? data.alerts : [];
  const total = data.total || 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const runAction = async (id, fn) => {
    setBusyId(id);
    setActionError(null);
    try {
      await fn(id);
      await alerts.refetch();
    } catch (err) {
      setActionError(getApiErrorMessage(err, 'Unable to update alert status.'));
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="min-h-screen flex flex-col font-sans theme-transition bg-th-bg">
      <Header />

      <main className="flex-1 px-4 sm:px-6 lg:px-8 py-6 space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-th-border pb-4">
          <div>
            <h1 className="text-xl font-semibold text-th-text-primary font-serif flex items-center gap-2">
              <Bell className="w-5 h-5 text-th-brand" />
              <span>Risk Alerts</span>
            </h1>
            <p className="text-xs text-th-text-secondary mt-0.5">
              Persistent risk alerts scoped to your organization.
            </p>
          </div>
          <Button variant="secondary" size="sm" onClick={alerts.refetch} isLoading={alerts.loading} className="gap-1.5">
            <RefreshCw className="w-3.5 h-3.5" />
            Refresh
          </Button>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2 text-xs">
            <label className="text-th-text-secondary font-medium">Status</label>
            <select
              value={statusFilter}
              onChange={(e) => {
                setPage(1);
                setStatusFilter(e.target.value);
              }}
              className="px-2 py-1.5 text-xs bg-th-surface border border-th-border rounded-lg text-th-text-primary focus:outline-none focus:ring-2 focus:ring-th-brand"
            >
              <option value="">All</option>
              <option value="open">Open</option>
              <option value="acknowledged">Acknowledged</option>
              <option value="in_progress">In progress</option>
              <option value="resolved">Resolved</option>
              <option value="closed">Closed</option>
            </select>
          </div>

          <div className="flex items-center gap-2 text-xs">
            <label className="text-th-text-secondary font-medium">Severity</label>
            <select
              value={severityFilter}
              onChange={(e) => {
                setPage(1);
                setSeverityFilter(e.target.value);
              }}
              className="px-2 py-1.5 text-xs bg-th-surface border border-th-border rounded-lg text-th-text-primary focus:outline-none focus:ring-2 focus:ring-th-brand"
            >
              <option value="">All</option>
              <option value="critical">Critical</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </select>
          </div>

          <span className="text-xs text-th-text-muted ml-auto">
            {total.toLocaleString('en-US')} alert{total === 1 ? '' : 's'}
          </span>
        </div>

        {actionError && (
          <div className="flex items-start gap-2 p-3 rounded-lg bg-th-danger-tint border border-th-danger/30 text-th-danger text-xs">
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            <span>{actionError}</span>
          </div>
        )}

        {alerts.loading && !alerts.data ? (
          <Card>
            <CardContent className="py-12 text-center text-th-text-muted text-sm">
              Loading alerts...
            </CardContent>
          </Card>
        ) : alerts.error ? (
          <Card className="border-th-danger/30 bg-th-danger-tint">
            <CardContent className="py-10 text-center text-th-danger text-sm flex flex-col items-center gap-2">
              <Shield className="w-6 h-6" />
              <span>{alerts.error}</span>
            </CardContent>
          </Card>
        ) : items.length === 0 ? (
          <Card>
            <CardContent className="py-12 text-center text-th-text-muted text-sm flex flex-col items-center gap-2">
              <CheckCircle2 className="w-7 h-7 text-th-success" />
              <span>No alerts match the current filters.</span>
            </CardContent>
          </Card>
        ) : (
          <Card>
            <CardHeader className="hidden md:flex">
              <CardTitle className="text-sm">Active queue</CardTitle>
              <CardDescription>Most recent alerts first</CardDescription>
            </CardHeader>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-th-surface-el border-b border-th-border text-[11px] uppercase tracking-wider text-th-text-secondary">
                  <tr>
                    <th className="px-4 py-3 font-semibold">Severity</th>
                    <th className="px-4 py-3 font-semibold">Category</th>
                    <th className="px-4 py-3 font-semibold">Title</th>
                    <th className="px-4 py-3 font-semibold">Status</th>
                    <th className="px-4 py-3 font-semibold">Opened</th>
                    <th className="px-4 py-3 font-semibold text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-th-border">
                  {items.map((alert) => (
                    <tr key={alert.id} className="hover:bg-th-surface-el/50 transition-colors align-top">
                      <td className="px-4 py-3">
                        <Badge variant={severityVariant(alert.severity)}>{alert.severity}</Badge>
                      </td>
                      <td className="px-4 py-3 text-th-text-secondary text-xs">{alert.category}</td>
                      <td className="px-4 py-3">
                        <div className="font-medium text-th-text-primary">{alert.title}</div>
                        {alert.description && (
                          <div className="text-xs text-th-text-muted mt-0.5 max-w-md">{alert.description}</div>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <Badge variant={statusVariant(alert.status)}>{alert.status}</Badge>
                      </td>
                      <td className="px-4 py-3 text-xs text-th-text-muted font-mono">
                        {alert.opened_at ? new Date(alert.opened_at).toLocaleDateString() : '—'}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center justify-end gap-1.5">
                          <Button
                            variant="ghost"
                            size="sm"
                            disabled={busyId === alert.id || alert.status !== 'open'}
                            onClick={() => runAction(alert.id, acknowledgeAlert)}
                          >
                            Ack
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            disabled={busyId === alert.id}
                            onClick={() => runAction(alert.id, escalateAlert)}
                          >
                            Escalate
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            disabled={busyId === alert.id}
                            onClick={() => runAction(alert.id, resolveAlert)}
                          >
                            Resolve
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            disabled={busyId === alert.id}
                            onClick={() => runAction(alert.id, closeAlert)}
                          >
                            Close
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="flex items-center justify-between px-4 py-3 border-t border-th-border text-xs text-th-text-secondary">
              <span>
                Page {page} of {totalPages}
              </span>
              <div className="flex items-center gap-1.5">
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                >
                  <ChevronLeft className="w-3.5 h-3.5" />
                  Prev
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                >
                  Next
                  <ChevronRight className="w-3.5 h-3.5" />
                </Button>
              </div>
            </div>
          </Card>
        )}
      </main>
    </div>
  );
}

export default AlertsPage;
