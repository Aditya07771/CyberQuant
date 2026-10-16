import React, { useState, useRef } from 'react';
import {
  Upload,
  FileText,
  FileArchive,
  CheckCircle2,
  AlertCircle,
  FolderUp,
  Sparkles,
  ArrowRight,
  X,
  FileCode,
  FileSpreadsheet,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../ui/Card';
import { Button } from '../ui/Button';
import { Badge } from '../ui/Badge';
import { uploadDatasetFiles, loadDemoDataset } from '../../api/client';

const REQUIRED_TABLES = [
  { id: 'assets', label: 'assets.csv', description: 'Asset inventory & financial criticality' },
  { id: 'controls', label: 'controls.csv', description: 'Available security controls & ROSI cost' },
  { id: 'asset_controls', label: 'asset_controls.csv', description: 'Deployed controls mapping' },
  { id: 'threat_events', label: 'threat_events.csv', description: 'Historical threat log telemetry' },
  { id: 'vulnerabilities', label: 'vulnerabilities.csv', description: 'CVE, CVSS & EPSS telemetry' },
];

export const DatasetUploadBox = ({ onStartProcessing, onSuccess, onError, isProcessing }) => {
  const [dragActive, setDragActive] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [validationError, setValidationError] = useState(null);
  const fileInputRef = useRef(null);

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const processFileList = (files) => {
    setValidationError(null);
    const fileArray = Array.from(files);

    if (fileArray.length === 0) return;

    // Check if single JSON, ZIP, or Excel bundle
    if (fileArray.length === 1) {
      const name = fileArray[0].name.toLowerCase();
      if (
        name.endsWith('.zip') ||
        name.endsWith('.json') ||
        name.endsWith('.xlsx') ||
        name.endsWith('.xls') ||
        name.endsWith('.xlsm')
      ) {
        setSelectedFiles(fileArray);
        return;
      }
    }

    // Filter CSV files
    const csvFiles = fileArray.filter((f) => f.name.toLowerCase().endsWith('.csv'));
    if (csvFiles.length === 0) {
      setValidationError('Please upload .csv, .zip, .json, or .xlsx dataset files.');
      return;
    }

    setSelectedFiles((prev) => {
      // Merge unique by file name
      const map = new Map();
      [...prev, ...csvFiles].forEach((f) => map.set(f.name.toLowerCase(), f));
      return Array.from(map.values());
    });
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      processFileList(e.dataTransfer.files);
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      processFileList(e.target.files);
    }
  };

  const handleRemoveFile = (fileName) => {
    setSelectedFiles((prev) => prev.filter((f) => f.name !== fileName));
  };

  const handleClearAll = () => {
    setSelectedFiles([]);
    setValidationError(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  // Check which tables are covered by selected CSVs
  const bundleName = selectedFiles.length === 1 ? selectedFiles[0].name.toLowerCase() : '';
  const isExcelBundle =
    bundleName.endsWith('.xlsx') || bundleName.endsWith('.xls') || bundleName.endsWith('.xlsm');
  const isSingleBundle =
    selectedFiles.length === 1 &&
    (bundleName.endsWith('.zip') || bundleName.endsWith('.json') || isExcelBundle);

  const detectedTables = REQUIRED_TABLES.map((t) => {
    const isPresent = isSingleBundle
      ? true
      : selectedFiles.some((f) => f.name.toLowerCase().includes(t.id));
    return { ...t, isPresent };
  });

  const allTablesPresent = isSingleBundle || detectedTables.every((t) => t.isPresent);

  const handleSubmit = async () => {
    if (selectedFiles.length === 0) {
      setValidationError('Please select or drag dataset files first.');
      return;
    }

    if (!isSingleBundle && !allTablesPresent) {
      const missing = detectedTables.filter((t) => !t.isPresent).map((t) => t.label);
      setValidationError(`Missing required files: ${missing.join(', ')}.`);
      return;
    }

    setValidationError(null);
    onStartProcessing();

    try {
      const formData = new FormData();
      selectedFiles.forEach((file) => {
        formData.append('files', file);
      });

      const result = await uploadDatasetFiles(formData);
      onSuccess(result);
    } catch (err) {
      let msg =
        err.response?.data?.detail ||
        err.message ||
        'Failed to process dataset. Please ensure file schemas match specifications.';
      if (err.code === 'ECONNABORTED' || (err.message && err.message.toLowerCase().includes('timeout'))) {
        msg = 'The quantification pipeline is processing a large dataset and took longer than expected. Please check server logs or retry with fewer rows.';
      }
      setValidationError(msg);
      onError(msg);
    }
  };

  const handleDemoClick = async () => {
    setValidationError(null);
    onStartProcessing();
    try {
      const result = await loadDemoDataset();
      onSuccess(result);
    } catch (err) {
      const msg =
        err.response?.data?.detail ||
        err.message ||
        'Failed to load demo dataset.';
      setValidationError(msg);
      onError(msg);
    }
  };

  return (
    <section id="upload-section" className="py-12">
      <div className="max-w-4xl mx-auto px-4 sm:px-6">
        <Card className="border-2 border-th-border shadow-elevated">
          <CardHeader>
            <div>
              <CardTitle className="text-xl sm:text-2xl flex items-center gap-2">
                <FolderUp className="w-6 h-6 text-th-brand" />
                <span>Dataset Ingestion &amp; Quantification Pipeline</span>
              </CardTitle>
              <CardDescription>
                Upload your enterprise cyber dataset to run the FAIR Monte Carlo risk quantification engine.
              </CardDescription>
            </div>

            {/* Quick Demo Button */}
            <Button
              variant="secondary"
              size="sm"
              onClick={handleDemoClick}
              disabled={isProcessing}
              className="font-medium gap-1.5 shrink-0"
            >
              <Sparkles className="w-4 h-4 text-th-brand" />
              <span>Use Demo Dataset</span>
            </Button>
          </CardHeader>

          <CardContent className="space-y-6">
            {/* Dropzone Area */}
            <div
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              className={`relative border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all ${
                dragActive
                  ? 'border-th-brand bg-th-brand-tint/50 scale-[1.01]'
                  : 'border-th-border hover:border-th-brand/60 hover:bg-th-surface-el'
              }`}
            >
              <input
                ref={fileInputRef}
                type="file"
                multiple
                accept=".csv,.zip,.json,.xlsx,.xls,.xlsm"
                onChange={handleFileChange}
                className="hidden"
              />

              <div className="flex flex-col items-center justify-center space-y-3">
                <div className="w-14 h-14 rounded-full bg-th-brand-tint flex items-center justify-center text-th-brand shadow-soft">
                  <Upload className="w-6 h-6" />
                </div>
                <div className="space-y-1">
                  <p className="text-sm font-semibold text-th-text-primary">
                    <span className="text-th-brand underline underline-offset-2">Click to browse</span> or drag &amp; drop files here
                  </p>
                  <p className="text-xs text-th-text-muted">
                    Supports 5 CSV files, a single <code className="px-1 py-0.5 rounded bg-th-surface border border-th-border font-mono text-[11px]">.zip</code> archive, <code className="px-1 py-0.5 rounded bg-th-surface border border-th-border font-mono text-[11px]">compiled_risk_dataset.json</code>, or an <code className="px-1 py-0.5 rounded bg-th-surface border border-th-border font-mono text-[11px]">.xlsx</code> Excel workbook (auto-mapped)
                  </p>
                </div>
              </div>
            </div>

            {/* Selected Files & Table Requirements Checklist */}
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h4 className="text-xs font-semibold uppercase tracking-wider text-th-text-secondary">
                  {isExcelBundle ? 'Excel Workbook Ingestion' : 'Dataset Schema Requirements (5 Tables)'}
                </h4>
                {selectedFiles.length > 0 && (
                  <button
                    onClick={handleClearAll}
                    className="text-xs text-th-danger hover:underline font-medium"
                  >
                    Clear selection ({selectedFiles.length})
                  </button>
                )}
              </div>

              {/* Excel workbook explanatory note (card/account data auto-mapping) */}
              {isExcelBundle ? (
                <div className="flex items-start gap-3 p-4 rounded-lg bg-th-brand-tint border border-th-brand/20 text-xs">
                  <FileSpreadsheet className="w-5 h-5 text-th-brand shrink-0 mt-0.5" />
                  <div className="space-y-1">
                    <p className="font-semibold text-th-text-primary">Excel workbook detected</p>
                    <p className="text-th-text-secondary leading-relaxed">
                      The workbook is parsed server-side. A multi-sheet workbook containing the 5 risk
                      tables is loaded directly; a financial card/account sheet (e.g.{' '}
                      <span className="font-mono">Financial Transactions.xlsx</span>) is auto-mapped onto
                      the risk engine schema, and an Excel File Summary is shown on the dashboard.
                    </p>
                  </div>
                </div>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                  {detectedTables.map((table) => (
                    <div
                      key={table.id}
                      className={`flex items-start justify-between p-3 rounded-lg border text-xs transition-colors ${
                        table.isPresent
                          ? 'bg-th-success-tint/40 border-th-success/30 text-th-text-primary'
                          : 'bg-th-surface-el/60 border-th-border text-th-text-secondary'
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        {table.isPresent ? (
                          <CheckCircle2 className="w-4 h-4 text-th-success shrink-0" />
                        ) : (
                          <div className="w-4 h-4 rounded-full border border-th-text-muted/40 shrink-0" />
                        )}
                        <div>
                          <span className="font-mono font-semibold">{table.label}</span>
                          <p className="text-[11px] text-th-text-muted">{table.description}</p>
                        </div>
                      </div>

                      {table.isPresent && (
                        <Badge variant="success" className="text-[10px] py-0 px-1.5">
                          Ready
                        </Badge>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {/* Selected Files Pill List */}
              {selectedFiles.length > 0 && !isSingleBundle && (
                <div className="pt-2">
                  <div className="text-xs text-th-text-muted mb-2 font-medium">Selected Files:</div>
                  <div className="flex flex-wrap gap-2">
                    {selectedFiles.map((file) => (
                      <div
                        key={file.name}
                        className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-th-surface-el border border-th-border text-xs text-th-text-primary"
                      >
                        <FileText className="w-3.5 h-3.5 text-th-brand" />
                        <span className="font-mono truncate max-w-[200px]">{file.name}</span>
                        <button
                          type="button"
                          onClick={() => handleRemoveFile(file.name)}
                          className="text-th-text-muted hover:text-th-danger ml-1"
                        >
                          <X className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Single Bundle Pill */}
              {isSingleBundle && (
                <div className="p-3 rounded-lg bg-th-brand-tint border border-th-brand/20 flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2">
                    {bundleName.endsWith('.zip') ? (
                      <FileArchive className="w-4 h-4 text-th-brand" />
                    ) : isExcelBundle ? (
                      <FileSpreadsheet className="w-4 h-4 text-th-brand" />
                    ) : (
                      <FileCode className="w-4 h-4 text-th-brand" />
                    )}
                    <span className="font-mono font-semibold text-th-text-primary">
                      {selectedFiles[0].name}
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={handleClearAll}
                    className="text-th-text-muted hover:text-th-danger"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              )}
            </div>

            {/* Error Message Banner */}
            {validationError && (
              <div className="p-4 rounded-lg bg-th-danger-tint border border-th-danger/30 text-th-danger text-sm flex items-start gap-3 animate-in fade-in duration-300">
                <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
                <div className="space-y-1">
                  <p className="font-semibold">Dataset Ingestion Notice</p>
                  <p className="text-xs text-th-danger/90 leading-relaxed">{validationError}</p>
                </div>
              </div>
            )}

            {/* Submit Action Bar */}
            <div className="flex flex-col sm:flex-row items-center justify-between gap-4 pt-4 border-t border-th-border">
              <p className="text-xs text-th-text-muted text-center sm:text-left">
                Processing runs adaptive Monte Carlo risk quantification and recalculates ROSI investment models. This typically completes in under 30 seconds.
              </p>

              <Button
                size="lg"
                onClick={handleSubmit}
                disabled={isProcessing || (!isSingleBundle && !allTablesPresent)}
                isLoading={isProcessing}
                className="w-full sm:w-auto px-8 font-semibold shadow-card gap-2"
              >
                <span>Process &amp; Launch Insights</span>
                <ArrowRight className="w-4 h-4" />
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </section>
  );
};
