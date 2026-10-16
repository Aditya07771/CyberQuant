import React from 'react';
import { RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar, ResponsiveContainer, Tooltip } from 'recharts';
import { FileCheck, ShieldAlert, CheckCircle2, AlertTriangle, AlertCircle } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/Card';
import { Badge } from '../ui/Badge';
import { useApi } from '../../hooks/useApi';
import { getCompliancePosture, getComplianceGaps } from '../../api/client';

export const ComplianceDashboard = () => {
  const posture = useApi(getCompliancePosture);
  const gaps = useApi(getComplianceGaps);

  const loading = posture.loading || gaps.loading;
  const error = posture.error || gaps.error;

  if (loading) {
    return (
      <Card className="w-full h-64 flex items-center justify-center">
        <div className="flex flex-col items-center text-th-text-secondary">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-th-brand mb-4" />
          <p>Loading compliance data...</p>
        </div>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="w-full h-64 flex items-center justify-center border-red-200 bg-red-50/50">
        <div className="flex flex-col items-center text-red-600">
          <ShieldAlert className="w-8 h-8 mb-4" />
          <p>Failed to load compliance data.</p>
          <button 
            onClick={() => { posture.refetch(); gaps.refetch(); }}
            className="mt-4 text-sm font-medium hover:underline"
          >
            Try Again
          </button>
        </div>
      </Card>
    );
  }

  // Fallback default data for posture
  const defaultFrameworks = [
    { name: 'NIST CSF 2.0', score: 75, mapped: 82, total: 108 },
    { name: 'ISO/IEC 27001', score: 60, mapped: 56, total: 93 },
    { name: 'CIS Controls', score: 85, mapped: 130, total: 153 },
    { name: 'RBI Cyber', score: 92, mapped: 65, total: 70 },
    { name: 'SEBI CSCRF', score: 45, mapped: 30, total: 68 },
  ];

  const frameworks = posture.data?.frameworks?.map(fw => ({
    name: fw.short_name || fw.name,
    score: fw.coverage_pct,
    mapped: fw.controls_covered,
    total: fw.controls_total
  })) || defaultFrameworks;
  
  const defaultGaps = [
    { id: '1', framework: 'SEBI CSCRF', reqId: 'SC-01', description: 'Real-time threat intelligence feeds missing', control: 'Threat Intel Platform', severity: 'High' },
    { id: '2', framework: 'ISO/IEC 27001', reqId: 'A.8.1.1', description: 'Inventory of assets not fully automated', control: 'Asset Discovery Tool', severity: 'Medium' },
    { id: '3', framework: 'NIST CSF 2.0', reqId: 'PR.DS-1', description: 'Data-at-rest encryption not enforced across all DBs', control: 'Database Encryption', severity: 'High' },
  ];
  
  const gapsList = gaps.data ? gaps.data.map((g, i) => ({
    id: i.toString(),
    framework: g.framework_name,
    reqId: g.gap_control_id,
    description: `Missing control for requirement ${g.gap_control_id}`,
    control: g.recommended_control_name,
    severity: g.severity
  })) : defaultGaps;

  const getScoreColor = (score) => {
    if (score < 50) return 'bg-red-500';
    if (score < 80) return 'bg-yellow-500';
    return 'bg-green-500';
  };
  
  const getScoreTextClass = (score) => {
    if (score < 50) return 'text-red-500';
    if (score < 80) return 'text-yellow-600';
    return 'text-green-600';
  };

  const getSeverityIcon = (severity) => {
    switch(severity?.toLowerCase()) {
      case 'high': return <AlertCircle className="w-4 h-4 text-red-500" />;
      case 'medium': return <AlertTriangle className="w-4 h-4 text-yellow-500" />;
      case 'low': return <CheckCircle2 className="w-4 h-4 text-blue-500" />;
      default: return <ShieldAlert className="w-4 h-4 text-th-text-muted" />;
    }
  };

  const getSeverityClass = (severity) => {
    switch(severity?.toLowerCase()) {
      case 'high': return 'bg-red-50 text-red-700 border-red-200';
      case 'medium': return 'bg-yellow-50 text-yellow-700 border-yellow-200';
      case 'low': return 'bg-blue-50 text-blue-700 border-blue-200';
      default: return 'bg-gray-50 text-gray-700 border-gray-200';
    }
  };

  return (
    <div className="space-y-6">
      {/* Header section */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 border-b border-th-border pb-4">
        <div>
          <h2 className="text-xl font-semibold text-th-text-primary font-serif flex items-center gap-2">
            <FileCheck className="w-5 h-5 text-th-brand" />
            <span>Regulatory Compliance &amp; Framework Mapping</span>
          </h2>
          <p className="text-xs text-th-text-secondary mt-0.5">
            Continuous compliance posture mapping to ISO/NIST/CIS/RBI/SEBI standards.
          </p>
        </div>
      </div>

      {/* Framework Coverage Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-4">
        {frameworks.map((fw, idx) => (
          <Card key={idx} className="flex flex-col">
            <CardContent className="p-4 flex-1 flex flex-col">
              <div className="text-sm font-semibold text-th-text-primary mb-2 line-clamp-1 truncate" title={fw.name}>{fw.name}</div>
              <div className="flex items-baseline gap-1 mt-auto">
                <span className={`text-3xl font-bold font-serif ${getScoreTextClass(fw.score)}`}>
                  {Math.round(fw.score)}%
                </span>
              </div>
              <div className="w-full h-1.5 bg-th-surface-el rounded-full mt-3 mb-2 overflow-hidden">
                <div 
                  className={`h-full rounded-full transition-all duration-1000 ${getScoreColor(fw.score)}`} 
                  style={{ width: `${fw.score}%` }}
                />
              </div>
              <div className="text-xs text-th-text-secondary mt-1">
                {fw.mapped} of {fw.total} controls mapped
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Radar Chart */}
        <div className="lg:col-span-5">
          <Card className="h-full">
            <CardHeader>
              <CardTitle>Framework Coverage Profile</CardTitle>
            </CardHeader>
            <CardContent className="flex items-center justify-center h-72">
              <ResponsiveContainer width="100%" height="100%">
                <RadarChart cx="50%" cy="50%" outerRadius="70%" data={frameworks}>
                  <PolarGrid stroke="#374151" />
                  <PolarAngleAxis dataKey="name" tick={{ fill: '#e5e7eb', fontSize: 12, fontWeight: 500 }} />
                  <PolarRadiusAxis angle={30} domain={[0, 100]} tick={{ fill: '#9ca3af', fontSize: 10 }} />
                  <Radar
                    name="Coverage %"
                    dataKey="score"
                    stroke="#10b981"
                    fill="#10b981"
                    fillOpacity={0.6}
                  />
                  <Tooltip 
                    contentStyle={{ backgroundColor: '#1f2937', borderColor: '#374151', borderRadius: '0.5rem', color: '#e5e7eb' }}
                    itemStyle={{ color: '#10b981' }}
                  />
                </RadarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </div>

        {/* Compliance Gaps Table */}
        <div className="lg:col-span-7">
          <Card className="h-full flex flex-col">
            <CardHeader className="border-b border-th-border bg-th-surface-el/50 pb-4">
              <CardTitle>Critical Compliance Gaps</CardTitle>
            </CardHeader>
            <CardContent className="p-0 flex-1 overflow-auto">
              <table className="w-full text-sm text-left whitespace-nowrap">
                <thead className="text-xs text-th-text-secondary bg-th-surface-el border-b border-th-border uppercase sticky top-0 z-10">
                  <tr>
                    <th className="px-4 py-3 font-medium">Framework</th>
                    <th className="px-4 py-3 font-medium">Req ID</th>
                    <th className="px-4 py-3 font-medium">Description</th>
                    <th className="px-4 py-3 font-medium">Recommended Control</th>
                    <th className="px-4 py-3 font-medium text-right">Severity</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-th-border">
                  {gapsList.map((gap, i) => (
                    <tr key={i} className="hover:bg-th-surface-el/30 transition-colors">
                      <td className="px-4 py-3 font-medium text-th-text-primary">{gap.framework}</td>
                      <td className="px-4 py-3 text-th-text-secondary">{gap.reqId}</td>
                      <td className="px-4 py-3 text-th-text-secondary truncate max-w-[200px]" title={gap.description}>
                        {gap.description}
                      </td>
                      <td className="px-4 py-3 text-th-text-secondary">{gap.control}</td>
                      <td className="px-4 py-3 text-right">
                        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium border ${getSeverityClass(gap.severity)}`}>
                          {getSeverityIcon(gap.severity)}
                          {gap.severity}
                        </span>
                      </td>
                    </tr>
                  ))}
                  {gapsList.length === 0 && (
                    <tr>
                      <td colSpan="5" className="px-4 py-8 text-center text-th-text-secondary">
                        No critical compliance gaps detected.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
};
