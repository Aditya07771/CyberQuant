import React from 'react';
import {
  FileSpreadsheet,
  Table2,
  Columns3,
  Layers,
  Database,
  Info,
  ListTree,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../ui/Card';
import { Badge } from '../ui/Badge';
import { useDataset } from '../../context/DatasetContext';

const StatTile = ({ icon: Icon, label, value, sub }) => (
  <div className="flex items-start gap-3 p-3 rounded-lg bg-th-surface-el border border-th-border">
    <div className="w-9 h-9 rounded-lg bg-th-brand-tint flex items-center justify-center text-th-brand shrink-0">
      <Icon className="w-4 h-4" />
    </div>
    <div className="min-w-0">
      <p className="text-[11px] uppercase tracking-wider text-th-text-muted font-semibold">{label}</p>
      <p className="text-base font-semibold text-th-text-primary truncate">{value}</p>
      {sub && <p className="text-[11px] text-th-text-muted truncate">{sub}</p>}
    </div>
  </div>
);

export const ExcelDatasetSummary = () => {
  const { excelSummary } = useDataset();

  if (!excelSummary) return null;

  const {
    file_name,
    total_rows,
    total_columns,
    worksheets = [],
    worksheet_count,
    dataset_type,
    column_details = [],
    risk_table_counts,
    notes = [],
  } = excelSummary;

  const roundedRows = Number(total_rows || 0).toLocaleString('en-US');
  const sheetLabel =
    worksheets.length > 0
      ? `${worksheet_count ?? worksheets.length} (${worksheets.join(', ')})`
      : `${worksheet_count ?? 0}`;

  return (
    <Card className="border-th-border">
      <CardHeader>
        <div>
          <CardTitle className="text-xl flex items-center gap-2">
            <FileSpreadsheet className="w-5 h-5 text-th-brand" />
            <span>Excel File Summary</span>
          </CardTitle>
          <CardDescription>
            Source workbook structure for the dataset currently driving these risk insights.
          </CardDescription>
        </div>
        {file_name && (
          <Badge variant="brand" className="font-mono shrink-0">
            {file_name}
          </Badge>
        )}
      </CardHeader>

      <CardContent className="space-y-5">
        {/* Stat tiles */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <StatTile icon={Table2} label="Total Rows" value={roundedRows} sub="data records" />
          <StatTile icon={Columns3} label="Total Columns" value={total_columns} sub="fields per record" />
          <StatTile icon={Layers} label="Worksheets" value={sheetLabel} sub="in the workbook" />
          <StatTile icon={Database} label="Dataset Type" value={dataset_type || 'Tabular dataset'} />
        </div>

        {/* Risk engine mapping counts */}
        {risk_table_counts && (
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-th-text-secondary">
              Risk Engine Tables
            </span>
            {Object.entries(risk_table_counts).map(([table, count]) => (
              <Badge key={table} variant="default" className="font-mono">
                {table}: {Number(count).toLocaleString('en-US')}
              </Badge>
            ))}
          </div>
        )}

        {/* Column details */}
        {column_details.length > 0 && (
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-th-text-secondary">
              <ListTree className="w-4 h-4 text-th-brand" />
              Column Details
            </div>
            <div className="overflow-hidden rounded-lg border border-th-border">
              <table className="w-full text-xs">
                <thead className="bg-th-surface-el">
                  <tr>
                    <th className="text-left px-3 py-2 font-semibold text-th-text-secondary w-1/3">Column</th>
                    <th className="text-left px-3 py-2 font-semibold text-th-text-secondary">Description</th>
                    <th className="text-left px-3 py-2 font-semibold text-th-text-secondary w-24">Type</th>
                  </tr>
                </thead>
                <tbody>
                  {column_details.map((col, idx) => (
                    <tr
                      key={`${col.column}-${idx}`}
                      className={idx % 2 === 0 ? 'bg-th-surface' : 'bg-th-surface-el/40'}
                    >
                      <td className="px-3 py-2 font-mono font-medium text-th-text-primary align-top">
                        {col.column}
                      </td>
                      <td className="px-3 py-2 text-th-text-secondary align-top">{col.description}</td>
                      <td className="px-3 py-2 font-mono text-th-text-muted align-top">{col.dtype}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Notes */}
        {notes.length > 0 && (
          <div className="space-y-2">
            {notes.map((note, idx) => (
              <div
                key={idx}
                className="flex items-start gap-2 p-3 rounded-lg bg-th-brand-tint border border-th-brand/20 text-xs text-th-text-secondary"
              >
                <Info className="w-4 h-4 text-th-brand shrink-0 mt-0.5" />
                <span className="leading-relaxed">{note}</span>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default ExcelDatasetSummary;
