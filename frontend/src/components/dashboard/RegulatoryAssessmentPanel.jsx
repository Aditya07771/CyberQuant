import React, { useState } from 'react';
import { Scale, ShieldAlert, RefreshCw, AlertCircle, Info } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/Card';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';
import { useApi } from '../../hooks/useApi';
import { useDataset } from '../../context/DatasetContext';
import {
  getRegulatoryAssessments,
  evaluateRegulatoryExposure,
  reviewRegulatoryAssessment,
  formatCurrency,
  getApiErrorMessage,
} from '../../api/client';

const STATUS_VARIANT = {
  gap: 'danger',
  potential_exposure: 'warning',
  needs_review: 'warning',
  reviewed: 'success',
  not_applicable: 'default',
  accepted_risk: 'accent',
};

const REVIEW_DECISIONS = ['reviewed', 'not_applicable', 'accepted_risk'];

export const RegulatoryAssessmentPanel = () => {
  const { activeDatasetId, activeRunId } = useDataset();
  const assessments = useApi(getRegulatoryAssessments, [activeRunId, activeDatasetId]);

  const [evaluating, setEvaluating] = useState(false);
  const [evaluateError, setEvaluateError] = useState(null);
  const [reviewingId, setReviewingId] = useState(null);
  const [decision, setDecision] = useState('reviewed');
  const [rationale, setRationale] = useState('');
  const [reviewError, setReviewError] = useState(null);
  const [reviewSaving, setReviewSaving] = useState(false);

  const rows = Array.isArray(assessments.data) ? assessments.data : [];

  const handleEvaluate = async () => {
    if (!activeDatasetId) return;
    setEvaluating(true);
    setEvaluateError(null);
    try {
      await evaluateRegulatoryExposure(activeDatasetId);
      await assessments.refetch();
    } catch (err) {
      setEvaluateError(getApiErrorMessage(err, 'Regulatory evaluation failed.'));
    } finally {
      setEvaluating(false);
    }
  };

  const beginReview = (id) => {
    setReviewingId(id);
    setDecision('reviewed');
    setRationale('');
    setReviewError(null);
  };

  const submitReview = async (id) => {
    if (!rationale.trim()) {
      setReviewError('A reviewer rationale is required.');
      return;
    }
    setReviewSaving(true);
    setReviewError(null);
    try {
      await reviewRegulatoryAssessment(id, { decision, rationale: rationale.trim() });
      setReviewingId(null);
      await assessments.refetch();
    } catch (err) {
      setReviewError(getApiErrorMessage(err, 'Could not record review decision.'));
    } finally {
      setReviewSaving(false);
    }
  };

  return (
    <Card className="w-full">
      <CardHeader className="border-b border-th-border flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <CardTitle className="flex items-center gap-2">
            <Scale className="w-4 h-4 text-th-brand" />
            Regulatory Exposure Assessments
          </CardTitle>
          <p className="text-xs text-th-text-secondary mt-0.5">
            Evidence-based findings mapped to versioned, source-linked regulatory provisions for this dataset.
          </p>
        </div>
        <Button
          variant="secondary"
          size="sm"
          onClick={handleEvaluate}
          isLoading={evaluating}
          disabled={!activeDatasetId}
          className="gap-1.5"
          title={!activeDatasetId ? 'Select a dataset first' : 'Re-run evidence evaluation against current rules'}
        >
          <RefreshCw className="w-3.5 h-3.5" />
          <span>Run evaluation</span>
        </Button>
      </CardHeader>

      <CardContent className="p-0">
        <div className="mx-4 mt-4 p-3 rounded-lg bg-th-surface-el border border-th-border text-[11px] text-th-text-secondary flex items-start gap-2">
          <Info className="w-3.5 h-3.5 text-th-brand shrink-0 mt-0.5" />
          <span>
            Exposure values are statutory maximum caps under the cited provision, not expected fines or likely
            liabilities. A detected CVE does not by itself establish a reportable incident or statutory violation;
            every finding requires qualified compliance/legal review.
          </span>
        </div>

        {evaluateError && (
          <div className="mx-4 mt-3 p-3 rounded-lg bg-th-danger-tint border border-th-danger/30 text-xs text-th-danger flex items-center gap-2">
            <AlertCircle className="w-3.5 h-3.5" />
            <span>{evaluateError}</span>
          </div>
        )}

        {assessments.loading ? (
          <div className="p-8 text-center text-th-text-secondary text-sm">Loading regulatory assessments…</div>
        ) : assessments.error ? (
          <div className="p-8 text-center text-th-danger text-sm flex flex-col items-center gap-2">
            <ShieldAlert className="w-6 h-6" />
            <span>{assessments.error}</span>
            <button onClick={assessments.refetch} className="text-xs font-medium hover:underline">
              Try again
            </button>
          </div>
        ) : rows.length === 0 ? (
          <div className="p-8 text-center text-th-text-muted text-sm">
            No regulatory assessments recorded for this dataset. Use “Run evaluation” to evaluate current evidence
            against applicable rules.
          </div>
        ) : (
          <div className="overflow-x-auto mt-4">
            <table className="w-full text-sm text-left">
              <thead className="text-xs text-th-text-secondary bg-th-surface-el border-y border-th-border uppercase">
                <tr>
                  <th className="px-4 py-3 font-medium">Framework</th>
                  <th className="px-4 py-3 font-medium">Provision</th>
                  <th className="px-4 py-3 font-medium">Finding</th>
                  <th className="px-4 py-3 font-medium text-center">Status</th>
                  <th className="px-4 py-3 font-medium text-right">Affected assets</th>
                  <th className="px-4 py-3 font-medium text-right">Statutory cap</th>
                  <th className="px-4 py-3 font-medium text-right">Review</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-th-border">
                {rows.map((a) => (
                  <React.Fragment key={a.id}>
                    <tr className="hover:bg-th-surface-el/30 transition-colors align-top">
                      <td className="px-4 py-3 text-th-text-secondary">{a.framework_name || '—'}</td>
                      <td className="px-4 py-3 font-mono text-xs text-th-text-secondary">
                        {a.provision_citation || '—'}
                      </td>
                      <td className="px-4 py-3 text-th-text-primary max-w-[260px]">{a.title || '—'}</td>
                      <td className="px-4 py-3 text-center">
                        <Badge variant={STATUS_VARIANT[a.status] || 'default'}>
                          {(a.status || 'unknown').replace(/_/g, ' ')}
                        </Badge>
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums">
                        {a.affected_assets_count ?? '—'}
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums text-th-text-secondary">
                        {formatCurrency(a.potential_exposure_max_usd)}
                      </td>
                      <td className="px-4 py-3 text-right">
                        {reviewingId === a.id ? (
                          <button
                            onClick={() => setReviewingId(null)}
                            className="text-xs text-th-text-muted hover:underline"
                          >
                            Cancel
                          </button>
                        ) : (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => beginReview(a.id)}
                            className="text-xs"
                          >
                            Record decision
                          </Button>
                        )}
                      </td>
                    </tr>

                    {reviewingId === a.id && (
                      <tr className="bg-th-surface-el/40">
                        <td colSpan={7} className="px-4 py-3">
                          <div className="space-y-3">
                            {a.rationale && (
                              <p className="text-xs text-th-text-secondary">
                                <strong className="text-th-text-primary">Current rationale:</strong> {a.rationale}
                              </p>
                            )}
                            <div className="flex flex-col sm:flex-row gap-3">
                              <select
                                value={decision}
                                onChange={(e) => setDecision(e.target.value)}
                                className="text-xs bg-th-bg border border-th-border rounded-md px-3 py-2 text-th-text-primary focus:outline-none focus:border-th-brand"
                              >
                                {REVIEW_DECISIONS.map((d) => (
                                  <option key={d} value={d}>
                                    {d.replace(/_/g, ' ')}
                                  </option>
                                ))}
                              </select>
                              <input
                                type="text"
                                value={rationale}
                                onChange={(e) => setRationale(e.target.value)}
                                placeholder="Reviewer rationale (required)"
                                className="flex-1 text-xs bg-th-bg border border-th-border rounded-md px-3 py-2 text-th-text-primary placeholder-th-text-muted focus:outline-none focus:border-th-brand"
                              />
                              <Button
                                size="sm"
                                variant="primary"
                                onClick={() => submitReview(a.id)}
                                isLoading={reviewSaving}
                              >
                                Submit
                              </Button>
                            </div>
                            {reviewError && (
                              <p className="text-xs text-th-danger flex items-center gap-1.5">
                                <AlertCircle className="w-3.5 h-3.5" />
                                {reviewError}
                              </p>
                            )}
                            <p className="text-[10px] text-th-text-muted">
                              Review decisions require analyst role and are written to the audit log.
                            </p>
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default RegulatoryAssessmentPanel;
