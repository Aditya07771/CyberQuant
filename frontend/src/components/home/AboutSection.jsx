import React from 'react';
import { Card, CardContent } from '../ui/Card';
import { Badge } from '../ui/Badge';
import {
  ShieldCheck,
  Cpu,
  BarChart3,
  Scale,
  Database,
  Lock,
} from 'lucide-react';

export const AboutSection = () => {
  const features = [
    {
      icon: ShieldCheck,
      title: 'Open FAIR™ Quantification',
      badge: 'Standardized',
      description:
        'Translates technical vulnerability telemetry (CVSS & EPSS) and real-world threat events into concrete financial terms: Expected Annual Loss (EAL) and Value at Risk (VaR).',
    },
    {
      icon: Cpu,
      title: 'Monte Carlo Actuarial Engine',
      badge: '20,000 Iterations',
      description:
        'Simulates thousands of loss scenarios using triangular threat frequencies and beta vulnerability distributions to compute defensible percentiles and Loss Exceedance Curves.',
    },
    {
      icon: BarChart3,
      title: 'ROSI Benchmark Analysis',
      badge: 'ROI Analytics',
      description:
        'Calculates Return on Security Investment for candidate controls (EDR, MFA, Segmentation, Patching) based on dollar-for-dollar risk reduction over control deployment costs.',
    },
    {
      icon: Scale,
      title: 'Knapsack ILP Budget Optimizer',
      badge: 'Integer Programming',
      description:
        'Solves the exact 0/1 Knapsack optimization problem to maximize risk mitigation across your asset fleet given any strict dollar budget constraint.',
    },
    {
      icon: Database,
      title: 'Multi-Source Telemetry Ingestion',
      badge: 'Automated Ingest',
      description:
        'Seamlessly ingests asset inventories, vulnerability scans, SIEM threat event logs, and existing security control deployments with strict schema verification.',
    },
    {
      icon: Lock,
      title: 'Executive & Board Reporting',
      badge: 'Decision Ready',
      description:
        'Empowers CISOs and CFOs to justify cybersecurity budgets with transparent mathematical formulas and interactive what-if portfolio simulations.',
    },
  ];

  return (
    <section className="py-12 border-t border-th-border">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-8">
        <div className="text-center max-w-3xl mx-auto space-y-3">
          <Badge variant="default" className="text-xs font-semibold">
            Methodology &amp; Architecture
          </Badge>
          <h2 className="text-2xl sm:text-3xl font-serif text-th-text-primary font-bold">
            Rigorous Cyber Risk Economics for Modern Security Teams
          </h2>
          <p className="text-sm sm:text-base text-th-text-secondary leading-relaxed">
            Stop relying on arbitrary 5x5 color grids. Our quantitative pipeline combines actuarial science, vulnerability exploit likelihoods, and mathematical optimization.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {features.map((feature, idx) => {
            const Icon = feature.icon;
            return (
              <Card key={idx} className="h-full hover:border-th-border-strong transition-all">
                <CardContent className="p-6 space-y-4 flex flex-col justify-between h-full">
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <div className="w-10 h-10 rounded-lg bg-th-brand-tint flex items-center justify-center text-th-brand">
                        <Icon className="w-5 h-5" />
                      </div>
                      <Badge variant="brand" className="text-[11px]">
                        {feature.badge}
                      </Badge>
                    </div>
                    <h3 className="text-base font-semibold text-th-text-primary font-serif">
                      {feature.title}
                    </h3>
                    <p className="text-sm text-th-text-secondary leading-relaxed">
                      {feature.description}
                    </p>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </div>
    </section>
  );
};
