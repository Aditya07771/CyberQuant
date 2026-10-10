/**
 * Normalization helpers.
 *
 * The canonical API contract describes risk responses wrapped in a `{ run, results }`
 * envelope and using lowercase monetary field names (e.g. `eal_usd`). The checked-in
 * backend currently returns raw arrays / objects with PascalCase names
 * (e.g. `EAL_usd`, `total_EAL_usd`). These helpers tolerate BOTH shapes so the UI can
 * consume a single canonical field set without silently fabricating values.
 *
 * Missing values are preserved as `undefined`/`null` — never defaulted to 0 — so the
 * render layer can surface an explicit "not reported by run" state.
 */

const num = (v) => {
  if (v === null || v === undefined || v === '') return undefined;
  const n = Number(v);
  return Number.isFinite(n) ? n : undefined;
};

const first = (obj, ...keys) => {
  for (const k of keys) {
    if (obj && obj[k] !== undefined && obj[k] !== null) return obj[k];
  }
  return undefined;
};

/**
 * Returns `{ run, results, raw }`.
 * - If the payload already has the `{ run, results }` envelope, it is honored.
 * - If it is a bare array, `results` is the array and `run` is null.
 * - Otherwise the payload is treated as a single object result.
 */
export function normalizeEnvelope(payload) {
  if (payload && typeof payload === 'object' && !Array.isArray(payload)
    && ('run' in payload || 'results' in payload)) {
    return {
      run: payload.run ?? null,
      results: payload.results ?? [],
      raw: payload,
    };
  }
  if (Array.isArray(payload)) {
    return { run: null, results: payload, raw: payload };
  }
  return { run: null, results: payload, raw: payload };
}

/** Same as normalizeEnvelope but for single-object payloads (`{ run, data }`). */
export function normalizeObjectEnvelope(payload) {
  if (payload && typeof payload === 'object' && !Array.isArray(payload) && 'run' in payload) {
    const { run, ...rest } = payload;
    // Some envelope responses put the object under `data` or `results`.
    return { run: run ?? null, data: rest.data ?? rest.results ?? rest, raw: payload };
  }
  return { run: null, data: payload, raw: payload };
}

export function normalizeAsset(row) {
  if (!row || typeof row !== 'object') return row;
  return {
    ...row,
    asset_id: first(row, 'asset_id', 'assetId'),
    asset_key: first(row, 'asset_key', 'assetKey'),
    hostname: first(row, 'hostname'),
    business_unit: first(row, 'business_unit', 'businessUnit'),
    criticality: first(row, 'criticality'),
    eal_usd: num(first(row, 'eal_usd', 'EAL_usd')),
    var95_usd: num(first(row, 'var95_usd', 'VaR95_usd', 'var_95_usd')),
    var99_usd: num(first(row, 'var99_usd', 'VaR99_usd', 'var_99_usd')),
    cvar95_usd: num(first(row, 'cvar95_usd', 'CVaR95_usd', 'cvar_95_usd')),
    eal_simple_usd: num(first(row, 'eal_simple_usd', 'EAL_simple_usd')),
    priority_score: num(first(row, 'priority_score')),
    confidence_status: first(row, 'confidence_status'),
    sample_count: num(first(row, 'sample_count')),
  };
}

export function normalizeBusinessUnit(row) {
  if (!row || typeof row !== 'object') return row;
  return {
    ...row,
    business_unit: first(row, 'business_unit', 'businessUnit'),
    eal_usd: num(first(row, 'eal_usd', 'EAL_usd', 'total_EAL_usd')),
    var95_usd: num(first(row, 'var95_usd', 'VaR95_usd', 'total_VaR95_usd')),
    var99_usd: num(first(row, 'var99_usd', 'VaR99_usd', 'total_VaR99_usd')),
    cvar95_usd: num(first(row, 'cvar95_usd', 'CVaR95_usd', 'total_CVaR95_usd')),
    asset_count: num(first(row, 'asset_count', 'assets_count', 'asset_count_total')),
  };
}

export function normalizeOrgSummary(payload) {
  const row = Array.isArray(payload) ? payload[0] : payload;
  if (!row || typeof row !== 'object') return null;
  return {
    ...row,
    eal_usd: num(first(row, 'eal_usd', 'EAL_usd', 'total_EAL_usd')),
    var95_usd: num(first(row, 'var95_usd', 'VaR95_usd', 'total_VaR95_usd')),
    var99_usd: num(first(row, 'var99_usd', 'VaR99_usd', 'total_VaR99_usd')),
    cvar95_usd: num(first(row, 'cvar95_usd', 'CVaR95_usd', 'total_CVaR95_usd')),
    total_assets_modeled: num(first(row, 'total_assets_modeled', 'asset_count', 'total_assets')),
  };
}

export function normalizePortfolio(payload) {
  if (!payload || typeof payload !== 'object') return payload;
  return {
    ...payload,
    total_eal_usd: num(first(payload, 'total_eal_usd', 'total_EAL_usd')),
    total_var95_usd: num(first(payload, 'total_var95_usd', 'total_VaR95_usd')),
    total_var99_usd: num(first(payload, 'total_var99_usd', 'total_VaR99_usd')),
    total_cvar95_usd: num(first(payload, 'total_cvar95_usd', 'total_CVaR95_usd')),
    max_probable_loss_usd: num(first(payload, 'max_probable_loss_usd')),
    total_assets_modeled: num(first(payload, 'total_assets_modeled')),
    lec_points: Array.isArray(payload.lec_points) ? payload.lec_points : [],
  };
}

export function normalizeTrendRow(row) {
  if (!row || typeof row !== 'object') return row;
  return {
    ...row,
    label: first(row, 'label', 'period', 'quarter', 'date'),
    eal_usd: num(first(row, 'eal_usd', 'EAL_usd', 'total_EAL_usd')),
    var95_usd: num(first(row, 'var95_usd', 'VaR95_usd', 'total_VaR95_usd')),
  };
}

export function normalizeControlRoi(row) {
  if (!row || typeof row !== 'object') return row;
  return {
    ...row,
    control_id: first(row, 'control_id'),
    control_name: first(row, 'control_name'),
    total_cost_usd: num(first(row, 'total_cost_usd')),
    total_risk_reduction_usd: num(first(row, 'total_risk_reduction_usd', 'Risk_Reduction_usd')),
    applicable_assets: num(first(row, 'applicable_assets')),
    rosi: num(first(row, 'overall_ROSI', 'rosi', 'ROSI')),
  };
}

export function normalizeGap(row) {
  if (!row || typeof row !== 'object') return row;
  return {
    ...row,
    framework_id: first(row, 'framework_id'),
    framework_name: first(row, 'framework_name'),
    gap_control_id: first(row, 'gap_control_id'),
    recommended_control_id: first(row, 'recommended_control_id'),
    recommended_control_name: first(row, 'recommended_control_name'),
    control_cost_usd: num(first(row, 'control_cost_usd')),
    risk_reduction_pct: num(first(row, 'risk_reduction_pct')),
    severity: first(row, 'severity'),
  };
}
