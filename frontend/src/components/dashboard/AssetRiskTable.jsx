import React, { useState, useMemo } from 'react';
import {
  Search,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  Server,
  AlertCircle,
  ChevronRight,
  Filter,
  ShieldCheck,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import { formatCurrency } from '../../api/client';
import { Card } from '../ui/Card';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export const AssetRiskTable = ({
  assets = [],
  loading,
  error,
  onSelectAsset,
  selectedAssetId,
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [sortField, setSortField] = useState('EAL_usd');
  const [sortAsc, setSortAsc] = useState(false);
  const [selectedBU, setSelectedBU] = useState('ALL');
  const [showZeroRisk, setShowZeroRisk] = useState(false);

  // Identify top 5 EAL assets across entire portfolio
  const top5AssetIds = useMemo(() => {
    if (!assets || assets.length === 0) return new Set();
    const sorted = [...assets].sort((a, b) => (b.EAL_usd || 0) - (a.EAL_usd || 0));
    return new Set(sorted.slice(0, 5).map((a) => a.asset_id));
  }, [assets]);

  // Unique Business Units for quick filter pill
  const businessUnits = useMemo(() => {
    if (!assets) return [];
    const bus = new Set(assets.map((a) => a.business_unit).filter(Boolean));
    return ['ALL', ...Array.from(bus)];
  }, [assets]);

  // Total count of 0 EAL assets across the dataset
  const zeroRiskAssetsCount = useMemo(() => {
    if (!assets) return 0;
    return assets.filter((a) => (a.EAL_usd || 0) === 0).length;
  }, [assets]);

  // Filtered & Sorted list
  const processedAssets = useMemo(() => {
    let list = [...(assets || [])];

    // Filter by search
    const hasSearch = Boolean(searchTerm.trim());
    if (hasSearch) {
      const q = searchTerm.toLowerCase();
      list = list.filter(
        (a) =>
          a.asset_id?.toLowerCase().includes(q) ||
          a.business_unit?.toLowerCase().includes(q) ||
          a.criticality?.toLowerCase().includes(q)
      );
    }

    // Filter by BU
    if (selectedBU !== 'ALL') {
      list = list.filter((a) => a.business_unit === selectedBU);
    }

    // Hide 0 EAL assets by default unless toggled ON or user is searching
    if (!showZeroRisk && !hasSearch) {
      list = list.filter((a) => (a.EAL_usd || 0) > 0);
    }

    // Sort
    list.sort((a, b) => {
      let valA = a[sortField];
      let valB = b[sortField];

      if (typeof valA === 'string') {
        valA = valA.toLowerCase();
        valB = (valB || '').toLowerCase();
        return sortAsc ? valA.localeCompare(valB) : valB.localeCompare(valA);
      }

      valA = Number(valA) || 0;
      valB = Number(valB) || 0;
      return sortAsc ? valA - valB : valB - valA;
    });

    return list;
  }, [assets, searchTerm, selectedBU, showZeroRisk, sortField, sortAsc]);

  const handleSort = (field) => {
    if (sortField === field) {
      setSortAsc(!sortAsc);
    } else {
      setSortField(field);
      setSortAsc(false);
    }
  };

  const getSortIcon = (field) => {
    if (sortField !== field) {
      return <ArrowUpDown className="w-3.5 h-3.5 text-th-text-muted opacity-60 group-hover:opacity-100 transition-opacity" />;
    }
    return sortAsc ? (
      <ArrowUp className="w-3.5 h-3.5 text-th-brand" />
    ) : (
      <ArrowDown className="w-3.5 h-3.5 text-th-brand" />
    );
  };

  const getCriticalityBadge = (crit) => {
    const c = String(crit || '').toUpperCase();
    if (c === 'HIGH' || c === 'CRITICAL' || c === 'TIER 1') {
      return <Badge variant="danger">{crit}</Badge>;
    }
    if (c === 'MEDIUM' || c === 'TIER 2') {
      return <Badge variant="warning">{crit}</Badge>;
    }
    return <Badge variant="success">{crit || 'Low'}</Badge>;
  };

  if (loading) {
    return (
      <Card className="p-6 animate-pulse">
        <div className="h-5 bg-th-border rounded w-1/4 mb-4"></div>
        <div className="space-y-2.5">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div key={i} className="h-10 bg-th-bg rounded"></div>
          ))}
        </div>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="p-6 border-th-danger/30 bg-th-danger-tint text-center">
        <AlertCircle className="w-6 h-6 text-th-danger mx-auto mb-2" />
        <p className="text-sm font-semibold text-th-danger font-serif">Failed to load asset inventory</p>
        <p className="text-xs text-th-danger/90 mt-1">{error}</p>
      </Card>
    );
  }

  return (
    <Card className="flex flex-col">
      {/* Header controls & Filters */}
      <div className="p-4 sm:p-5 border-b border-th-border bg-th-surface space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center space-x-3">
            <div className="p-2 rounded-lg bg-th-brand-tint text-th-brand shadow-soft">
              <Server className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm sm:text-base font-semibold text-th-text-primary font-serif flex items-center gap-2">
                <span>Asset Cyber Risk Portfolio</span>
                <Badge variant="default" className="font-mono hidden sm:inline-flex">
                  {processedAssets.length} displayed ({assets.length} total)
                </Badge>
              </h3>
              <p className="text-xs text-th-text-secondary mt-0.5">
                Displaying assets with quantified financial exposure. Click any row to inspect loss exceedance curves.
              </p>
            </div>
          </div>

          {/* Search Box & Quick Toggle */}
          <div className="flex items-center space-x-2 w-full sm:w-auto">
            <div className="relative w-full sm:w-64">
              <Search className="w-3.5 h-3.5 text-th-text-muted absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
              <input
                type="text"
                placeholder="Search asset, BU, or criticality..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-8 pr-3 py-1.5 text-xs bg-th-surface border border-th-border rounded-full text-th-text-primary placeholder-th-text-muted focus:outline-none focus:ring-2 focus:ring-th-brand focus:border-transparent transition-all shadow-soft"
              />
            </div>

            {zeroRiskAssetsCount > 0 && !searchTerm.trim() && (
              <Button
                variant={showZeroRisk ? 'primary' : 'secondary'}
                size="sm"
                className="hidden md:inline-flex whitespace-nowrap"
                onClick={() => setShowZeroRisk(!showZeroRisk)}
                title={showZeroRisk ? 'Hide assets with $0 EAL' : 'Show assets with $0 EAL'}
              >
                {showZeroRisk ? 'Hide $0 EAL' : `+${zeroRiskAssetsCount} Zero-Risk`}
              </Button>
            )}
          </div>
        </div>

        {/* Business Unit Quick Filter Pills */}
        {businessUnits.length > 2 && (
          <div className="flex items-center space-x-1.5 overflow-x-auto pb-1 text-xs">
            <span className="text-th-text-muted text-[11px] font-medium flex items-center mr-1 shrink-0">
              <Filter className="w-3 h-3 mr-1" /> Filter BU:
            </span>
            {businessUnits.map((bu) => (
              <button
                key={bu}
                onClick={() => setSelectedBU(bu)}
                className={twMerge(
                  'px-3 py-1 rounded-full text-xs font-medium whitespace-nowrap transition-colors border',
                  selectedBU === bu
                    ? 'bg-th-brand text-white border-th-brand'
                    : 'bg-th-surface text-th-text-secondary hover:text-th-text-primary hover:bg-th-surface-el border-th-border shadow-soft'
                )}
              >
                {bu === 'ALL' ? 'All Units' : bu}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Table Content */}
      <div className="overflow-x-auto max-h-[520px] overflow-y-auto">
        <table className="w-full text-left border-collapse">
          <thead className="sticky top-0 z-10 bg-th-bg border-b border-th-border text-[11px] font-semibold text-th-text-secondary uppercase tracking-wider">
            <tr>
              <th
                onClick={() => handleSort('asset_id')}
                className="py-3 px-4 cursor-pointer hover:text-th-text-primary group transition-colors"
              >
                <div className="flex items-center space-x-1.5">
                  <span>Asset ID</span>
                  {getSortIcon('asset_id')}
                </div>
              </th>
              <th
                onClick={() => handleSort('business_unit')}
                className="py-3 px-4 cursor-pointer hover:text-th-text-primary group transition-colors"
              >
                <div className="flex items-center space-x-1.5">
                  <span>Business Unit</span>
                  {getSortIcon('business_unit')}
                </div>
              </th>
              <th
                onClick={() => handleSort('criticality')}
                className="py-3 px-4 cursor-pointer hover:text-th-text-primary group transition-colors"
              >
                <div className="flex items-center space-x-1.5">
                  <span>Criticality</span>
                  {getSortIcon('criticality')}
                </div>
              </th>
              <th
                onClick={() => handleSort('EAL_usd')}
                className="py-3 px-4 cursor-pointer hover:text-th-text-primary group transition-colors text-right"
              >
                <div className="flex items-center justify-end space-x-1.5">
                  <span>Expected Loss (EAL)</span>
                  {getSortIcon('EAL_usd')}
                </div>
              </th>
              <th
                onClick={() => handleSort('VaR95_usd')}
                className="py-3 px-4 cursor-pointer hover:text-th-text-primary group transition-colors text-right"
              >
                <div className="flex items-center justify-end space-x-1.5">
                  <span>VaR 95%</span>
                  {getSortIcon('VaR95_usd')}
                </div>
              </th>
              <th
                onClick={() => handleSort('priority_score')}
                className="py-3 px-4 cursor-pointer hover:text-th-text-primary group transition-colors text-right"
              >
                <div className="flex items-center justify-end space-x-1.5">
                  <span>Priority Score</span>
                  {getSortIcon('priority_score')}
                </div>
              </th>
              <th className="py-3 px-3 text-center w-8"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-th-border text-xs bg-th-surface">
            {processedAssets.length === 0 ? (
              <tr>
                <td colSpan={7} className="py-8 text-center text-th-text-muted">
                  No assets match the search criteria.
                </td>
              </tr>
            ) : (
              processedAssets.map((asset) => {
                const isTop5 = top5AssetIds.has(asset.asset_id);
                const isSelected = selectedAssetId === asset.asset_id;
                const isZeroEal = (asset.EAL_usd || 0) === 0;

                return (
                  <tr
                    key={asset.asset_id}
                    onClick={() => onSelectAsset(asset.asset_id)}
                    className={clsx(
                      'cursor-pointer transition-colors',
                      isSelected
                        ? 'bg-th-brand-tint border-l-4 border-l-th-brand'
                        : isTop5
                        ? 'bg-th-danger-tint hover:bg-th-danger-tint/80'
                        : isZeroEal
                        ? 'bg-th-bg hover:bg-th-surface-el'
                        : 'hover:bg-th-surface-el'
                    )}
                  >
                    {/* Asset ID */}
                    <td className="py-3 px-4 font-mono font-medium text-th-text-primary">
                      <div className="flex items-center space-x-2">
                        <span>{asset.asset_id}</span>
                        {isTop5 && (
                          <span
                            className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-mono font-bold bg-th-danger-tint text-th-danger border border-th-danger/20"
                            title="Top 5 Enterprise Risk Contributor"
                          >
                            TOP 5
                          </span>
                        )}
                        {isZeroEal && (
                          <span
                            className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-mono text-th-text-muted bg-th-surface-el border border-th-border"
                            title="Zero quantified baseline risk"
                          >
                            $0 EAL
                          </span>
                        )}
                      </div>
                    </td>

                    {/* Business Unit */}
                    <td className="py-3 px-4 text-th-text-secondary">
                      {asset.business_unit}
                    </td>

                    {/* Criticality */}
                    <td className="py-3 px-4">
                      {getCriticalityBadge(asset.criticality)}
                    </td>

                    {/* EAL */}
                    <td className="py-3 px-4 text-right font-mono font-bold text-th-text-primary tabular-nums">
                      {isZeroEal ? (
                        <span className="text-th-text-muted font-normal">$0</span>
                      ) : (
                        formatCurrency(asset.EAL_usd)
                      )}
                    </td>

                    {/* VaR95 */}
                    <td className="py-3 px-4 text-right font-mono text-th-warning font-medium tabular-nums">
                      {isZeroEal ? (
                        <span className="text-th-text-muted font-normal">$0</span>
                      ) : (
                        formatCurrency(asset.VaR95_usd)
                      )}
                    </td>

                    {/* Priority Score */}
                    <td className="py-3 px-4 text-right font-mono tabular-nums">
                      <Badge variant="default" className="font-mono inline-flex">
                        {asset.priority_score !== undefined
                          ? Number(asset.priority_score).toFixed(1)
                          : '—'}
                      </Badge>
                    </td>

                    {/* Action Icon */}
                    <td className="py-3 px-3 text-center text-th-text-muted group-hover:text-th-brand">
                      <ChevronRight className="w-4 h-4 mx-auto" />
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Interactive Collapsible Banner for 0 EAL Assets */}
      {zeroRiskAssetsCount > 0 && !searchTerm.trim() && (
        <div className="p-4 bg-th-bg border-t border-th-border flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-sm text-th-text-secondary">
          <div className="flex items-center space-x-2.5">
            <ShieldCheck className="w-5 h-5 text-th-brand shrink-0" />
            <span>
              {showZeroRisk ? (
                <>
                  Showing all <strong className="text-th-text-primary">{zeroRiskAssetsCount} assets</strong> with zero quantified loss ($0 EAL).
                </>
              ) : (
                <>
                  <strong className="text-th-text-primary">{zeroRiskAssetsCount} assets</strong> have zero active vulnerabilities or zero quantified loss ($0 EAL) and are hidden from the primary view.
                </>
              )}
            </span>
          </div>

          <Button
            variant="secondary"
            size="sm"
            onClick={() => setShowZeroRisk(!showZeroRisk)}
            className="self-start sm:self-auto whitespace-nowrap"
          >
            <span>{showZeroRisk ? 'Hide $0 EAL Assets' : `Show ${zeroRiskAssetsCount} Zero-Risk Assets`}</span>
            {showZeroRisk ? (
              <ChevronUp className="w-4 h-4 ml-1.5 text-th-brand" />
            ) : (
              <ChevronDown className="w-4 h-4 ml-1.5 text-th-brand" />
            )}
          </Button>
        </div>
      )}
    </Card>
  );
};
