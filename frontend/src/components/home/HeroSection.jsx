import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Shield, ArrowDown, Activity, DollarSign, TrendingUp, Sparkles } from 'lucide-react';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';

export const HeroSection = ({ onScrollToUpload, onQuickDemo, isProcessingDemo }) => {
  const navigate = useNavigate();
  return (
    <section className="relative overflow-hidden pt-8 pb-12 sm:pt-12 sm:pb-16 text-center">
      {/* Background ambient glow */}
      <div
        className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[350px] bg-th-brand/10 rounded-full blur-3xl pointer-events-none -z-10"
        aria-hidden="true"
      />

      <div className="max-w-4xl mx-auto px-4 sm:px-6 space-y-6">
        {/* Top Feature Pill */}
        <div className="inline-flex items-center gap-2">
          <Badge variant="brand" className="px-3.5 py-1 text-xs font-semibold shadow-soft animate-in fade-in duration-500">
            <Sparkles className="w-3.5 h-3.5 mr-1.5 text-th-brand" />
            Open FAIR™ Cyber Risk Quantification Engine
          </Badge>
        </div>

        {/* Hero Title */}
        <h1 className="text-4xl sm:text-5xl lg:text-6xl font-serif text-th-text-primary tracking-tight font-bold leading-tight">
          Transform Cyber Threats into <br className="hidden sm:inline" />
          <span className="text-th-brand">Actuarial Financial Insights</span>
        </h1>

        {/* Subtitle */}
        <p className="text-base sm:text-lg text-th-text-secondary max-w-2xl mx-auto leading-relaxed">
          Move beyond qualitative heatmaps. Quantify Expected Annual Loss (EAL), 95% &amp; 99% Value at Risk (VaR), and mathematically optimize security capital allocation using adaptive Monte Carlo simulations.
        </p>

        {/* CTA Actions */}
        <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
          <Button
            size="lg"
            onClick={onScrollToUpload}
            className="px-6 py-3 font-semibold shadow-card gap-2"
          >
            <span>Upload Your Dataset</span>
            <ArrowDown className="w-4 h-4" />
          </Button>

          <Button
            variant="secondary"
            size="lg"
            onClick={() => navigate('/insights')}
            isLoading={isProcessingDemo}
            className="px-6 py-3 font-semibold"
          >
            <span>Explore Demo Data</span>
          </Button>
        </div>

        {/* Highlights Row */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-8 border-t border-th-border mt-8">
          <div className="flex items-center justify-center sm:justify-start gap-3 p-3 rounded-lg bg-th-surface border border-th-border">
            <div className="w-10 h-10 rounded-lg bg-th-brand-tint flex items-center justify-center text-th-brand shrink-0">
              <DollarSign className="w-5 h-5" />
            </div>
            <div className="text-left">
              <div className="text-xs text-th-text-muted font-medium">Financial Metrics</div>
              <div className="text-sm font-semibold text-th-text-primary">Annualized Risk in USD</div>
            </div>
          </div>

          <div className="flex items-center justify-center sm:justify-start gap-3 p-3 rounded-lg bg-th-surface border border-th-border">
            <div className="w-10 h-10 rounded-lg bg-th-brand-tint flex items-center justify-center text-th-brand shrink-0">
              <Activity className="w-5 h-5" />
            </div>
            <div className="text-left">
              <div className="text-xs text-th-text-muted font-medium">Probabilistic Engine</div>
              <div className="text-sm font-semibold text-th-text-primary">Adaptive Monte Carlo Engine</div>
            </div>
          </div>

          <div className="flex items-center justify-center sm:justify-start gap-3 p-3 rounded-lg bg-th-surface border border-th-border">
            <div className="w-10 h-10 rounded-lg bg-th-brand-tint flex items-center justify-center text-th-brand shrink-0">
              <TrendingUp className="w-5 h-5" />
            </div>
            <div className="text-left">
              <div className="text-xs text-th-text-muted font-medium">Capital Allocation</div>
              <div className="text-sm font-semibold text-th-text-primary">ROSI &amp; Knapsack ILP</div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};
