import React, { useState, useEffect } from 'react';
import { Cpu, CheckCircle, Loader2 } from 'lucide-react';
import { Card, CardContent } from '../ui/Card';
import { Badge } from '../ui/Badge';

const PIPELINE_STEPS = [
  { id: 'ingest', title: 'Phase B: Ingesting & Normalizing Data', detail: 'Parsing assets, vulnerabilities, events, and controls...' },
  { id: 'likelihood', title: 'Phase C & D: Threat Frequency & EPSS', detail: 'Annualizing event rates and computing exploit likelihoods...' },
  { id: 'simulate', title: 'Phase F: Monte Carlo Loss Simulation', detail: 'Running 20,000 actuarial loss iterations per asset...' },
  { id: 'controls', title: 'Phase H: Control Scenarios & ROSI', detail: 'Evaluating return on investment and risk reduction per dollar...' },
  { id: 'parquet', title: 'Phase I: Generating Parquet Outputs', detail: 'Serializing executive summaries and preparing dashboard cache...' },
];

export const ProcessingOverlay = ({ isVisible }) => {
  const [currentStepIndex, setCurrentStepIndex] = useState(0);

  useEffect(() => {
    if (!isVisible) {
      setCurrentStepIndex(0);
      return;
    }

    // Progress through steps visually while backend runs
    const interval = setInterval(() => {
      setCurrentStepIndex((prev) => {
        if (prev < PIPELINE_STEPS.length - 1) {
          return prev + 1;
        }
        return prev;
      });
    }, 1800);

    return () => clearInterval(interval);
  }, [isVisible]);

  if (!isVisible) return null;

  const progressPercent = Math.min(
    100,
    Math.round(((currentStepIndex + 0.5) / PIPELINE_STEPS.length) * 100)
  );

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-md animate-in fade-in duration-300"
      role="dialog"
      aria-modal="true"
      aria-label="Quantification Pipeline Processing"
    >
      <Card className="max-w-lg w-full border-2 border-th-brand/30 shadow-elevated overflow-hidden bg-th-surface">
        {/* Top Gradient Bar */}
        <div className="h-1.5 w-full bg-th-border overflow-hidden">
          <div
            className="h-full bg-th-brand transition-all duration-700 ease-out"
            style={{ width: `${progressPercent}%` }}
          />
        </div>

        <CardContent className="p-6 sm:p-8 space-y-6">
          {/* Header */}
          <div className="flex items-center space-x-3.5">
            <div className="w-12 h-12 rounded-xl bg-th-brand-tint flex items-center justify-center text-th-brand shrink-0">
              <Cpu className="w-6 h-6 animate-pulse text-th-brand" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-lg font-serif font-bold text-th-text-primary">
                  Quantification Engine Active
                </h3>
                <Badge variant="brand" className="text-[10px]">
                  {progressPercent}%
                </Badge>
              </div>
              <p className="text-xs text-th-text-secondary mt-0.5">
                Executing full FAIR-aligned actuarial simulation on uploaded data...
              </p>
            </div>
          </div>

          {/* Stepper list */}
          <div className="space-y-3 pt-2">
            {PIPELINE_STEPS.map((step, idx) => {
              const isDone = idx < currentStepIndex;
              const isCurrent = idx === currentStepIndex;

              return (
                <div
                  key={step.id}
                  className={`flex items-start gap-3 p-3 rounded-lg border transition-all text-xs ${
                    isCurrent
                      ? 'bg-th-brand-tint/60 border-th-brand/40 text-th-text-primary shadow-soft'
                      : isDone
                      ? 'bg-th-surface-el/80 border-th-border text-th-text-muted'
                      : 'opacity-40 border-transparent text-th-text-muted'
                  }`}
                >
                  <div className="mt-0.5 shrink-0">
                    {isDone ? (
                      <CheckCircle className="w-4 h-4 text-th-success" />
                    ) : isCurrent ? (
                      <Loader2 className="w-4 h-4 text-th-brand animate-spin" />
                    ) : (
                      <div className="w-4 h-4 rounded-full border border-th-text-muted/40" />
                    )}
                  </div>

                  <div className="space-y-0.5 flex-1">
                    <div className="font-semibold">{step.title}</div>
                    <div className="text-[11px] text-th-text-secondary">{step.detail}</div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Footer status text */}
          <div className="text-center pt-2">
            <p className="text-xs text-th-text-muted font-mono animate-pulse">
              Please wait while the simulation reaches convergence...
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};
