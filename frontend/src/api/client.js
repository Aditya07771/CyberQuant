import axios from 'axios';
import {
  normalizeAsset,
  normalizeBusinessUnit,
  normalizeControlRoi,
  normalizeEnvelope,
  normalizeGap,
  normalizeObjectEnvelope,
  normalizeOrgSummary,
  normalizePortfolio,
  normalizeTrendRow,
} from './normalize';

const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

// ─── Auth storage ──────────────────────────────────────────────────────────
// Shape: { user, organization, tokens: { access_token, refresh_token, token_type } }
const AUTH_STORAGE_KEY = 'cyberquant.auth';

export function readAuth() {
  try {
    const raw = localStorage.getItem(AUTH_STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function writeAuth(auth) {
  try {
    localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(auth));
  } catch {
    /* ignore storage errors */
  }
}

export function clearAuth() {
  try {
    localStorage.removeItem(AUTH_STORAGE_KEY);
  } catch {
    /* ignore */
  }
}

export function getAccessToken() {
  return readAuth()?.tokens?.access_token || null;
}

export function getRefreshToken() {
  return readAuth()?.tokens?.refresh_token || null;
}

export function getOrganizationId() {
  return readAuth()?.organization?.id || null;
}

// ─── Active dataset / run scope ────────────────────────────────────────────
// The canonical risk endpoints are scoped to
// /api/v1/datasets/{dataset_id}/runs/{run_id}. DatasetContext sets the active
// scope so existing component call sites (getAssets(), getOrgRisk(), ...) do
// not need to thread dataset/run ids through props.
let _activeScope = { datasetId: null, runId: null };

export function setActiveScope(scope) {
  _activeScope = {
    datasetId: scope?.datasetId ?? null,
    runId: scope?.runId ?? null,
  };
}

export function getActiveScope() {
  return { ..._activeScope };
}

function runBase() {
  if (!_activeScope.datasetId || !_activeScope.runId) {
    const err = new Error('No active risk run selected. Load a dataset and run quantification first.');
    err.code = 'NO_ACTIVE_RUN';
    throw err;
  }
  return `/api/v1/datasets/${encodeURIComponent(_activeScope.datasetId)}/runs/${encodeURIComponent(_activeScope.runId)}`;
}

// ─── Axios instance ────────────────────────────────────────────────────────
export const apiClient = axios.create({
  baseURL,
  timeout: 120000,
});

apiClient.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token) {
    config.headers = config.headers || {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  const orgId = getOrganizationId();
  if (orgId) {
    config.headers = config.headers || {};
    config.headers['X-Organization-Id'] = orgId;
  }
  return config;
});

let refreshPromise = null;

async function refreshAccessToken() {
  const refresh = getRefreshToken();
  if (!refresh) throw new Error('No refresh token available');
  // Bare axios (no interceptors) to avoid recursion on 401.
  const resp = await axios.post(`${baseURL}/api/v1/auth/refresh`, {
    refresh_token: refresh,
  });
  const tokens = resp.data?.tokens;
  if (!tokens?.access_token) throw new Error('Refresh did not return an access token');
  const auth = readAuth() || {};
  writeAuth({ ...auth, tokens });
  return tokens.access_token;
}

function emitUnauthorized() {
  try {
    window.dispatchEvent(new CustomEvent('cyberquant:unauthorized'));
  } catch {
    /* ignore */
  }
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const { config, response } = error;
    const isAuthCall = typeof config?.url === 'string' && config.url.includes('/auth/');
    if (response?.status === 401 && config && !config._retry && !isAuthCall) {
      config._retry = true;
      try {
        if (!refreshPromise) {
          refreshPromise = refreshAccessToken().finally(() => {
            refreshPromise = null;
          });
        }
        const token = await refreshPromise;
        config.headers = config.headers || {};
        config.headers.Authorization = `Bearer ${token}`;
        return apiClient(config);
      } catch (refreshErr) {
        clearAuth();
        emitUnauthorized();
        return Promise.reject(error);
      }
    }
    if (response?.status === 401 && !isAuthCall) {
      clearAuth();
      emitUnauthorized();
    }
    return Promise.reject(error);
  },
);

// ─── Error helper ──────────────────────────────────────────────────────────
export function getApiErrorMessage(err, fallback) {
  if (err?.code === 'NO_ACTIVE_RUN') return err.message;
  return (
    err?.response?.data?.error?.message ||
    err?.response?.data?.detail ||
    err?.message ||
    fallback ||
    'An unexpected error occurred.'
  );
}

// ─── Health ────────────────────────────────────────────────────────────────
export const getHealth = async () => {
  const response = await apiClient.get('/health');
  return response.data;
};

// ─── Auth ──────────────────────────────────────────────────────────────────
export const register = async ({ email, password, fullName, organizationName }) => {
  const { data } = await apiClient.post('/api/v1/auth/register', {
    email,
    password,
    full_name: fullName,
    organization_name: organizationName,
  });
  return data;
};

export const login = async ({ email, password, organizationId }) => {
  const { data } = await apiClient.post('/api/v1/auth/login', {
    email,
    password,
    ...(organizationId ? { organization_id: organizationId } : {}),
  });
  return data;
};

export const listDemoAccounts = async () => {
  const { data } = await apiClient.get('/api/v1/auth/demo-accounts');
  return Array.isArray(data) ? data : [];
};

export const demoLogin = async ({ key, email } = {}) => {
  const { data } = await apiClient.post('/api/v1/auth/demo-login', {
    ...(key ? { key } : {}),
    ...(email ? { email } : {}),
  });
  return data;
};

export const fetchProfile = async () => {
  const { data } = await apiClient.get('/api/v1/auth/me');
  return data;
};

export const logout = async () => {
  const token = getRefreshToken();
  try {
    if (token) {
      await apiClient.post('/api/v1/auth/logout', { refresh_token: token });
    }
  } catch {
    /* best-effort revoke */
  } finally {
    clearAuth();
  }
};

// ─── Organization ──────────────────────────────────────────────────────────
export const getCurrentOrganization = async () => {
  const { data } = await apiClient.get('/api/v1/organizations/current');
  return data;
};

export const updateCurrentOrganization = async (payload) => {
  const { data } = await apiClient.patch('/api/v1/organizations/current', payload);
  return data;
};

// ─── Datasets ──────────────────────────────────────────────────────────────
export const listDatasets = async () => {
  const { data } = await apiClient.get('/api/v1/datasets');
  return Array.isArray(data) ? data : [];
};

export const createDataset = async ({ name, description = null, datasetType = 'tabular', files = [] }) => {
  const form = new FormData();
  form.append('name', name || 'Default Dataset');
  if (description) form.append('description', description);
  form.append('dataset_type', datasetType);
  files.forEach((file) => form.append('files', file));
  const { data } = await apiClient.post('/api/v1/datasets', form, {
    timeout: 300000,
  });
  return data;
};

export const getDataset = async (datasetId) => {
  const { data } = await apiClient.get(`/api/v1/datasets/${encodeURIComponent(datasetId)}`);
  return data;
};

export const getDatasetStatus = async (datasetId) => {
  const { data } = await apiClient.get(`/api/v1/datasets/${encodeURIComponent(datasetId)}/status`);
  return data;
};

export const listRuns = async (datasetId) => {
  const { data } = await apiClient.get(`/api/v1/datasets/${encodeURIComponent(datasetId)}/runs`);
  return Array.isArray(data) ? data : [];
};

export const getRun = async (datasetId, runId) => {
  const { data } = await apiClient.get(
    `/api/v1/datasets/${encodeURIComponent(datasetId)}/runs/${encodeURIComponent(runId)}`,
  );
  return data;
};

export const startRun = async (datasetId, { rngSeed = 42, nSimulations = 10000 } = {}) => {
  const { data } = await apiClient.post(`/api/v1/datasets/${encodeURIComponent(datasetId)}/runs`, {
    rng_seed: rngSeed,
    n_simulations: nSimulations,
  });
  return data;
};

// ─── Jobs ──────────────────────────────────────────────────────────────────
export const getJob = async (jobId) => {
  const { data } = await apiClient.get(`/api/v1/jobs/${encodeURIComponent(jobId)}`);
  return data;
};

// ─── Demo dataset ──────────────────────────────────────────────────────────
export const loadDemoDataset = async () => {
  const { data } = await apiClient.post('/api/v1/datasets/demo', {}, { timeout: 300000 });
  return data;
};

// ─── Run-scoped risk endpoints ─────────────────────────────────────────────
export const getOrgRisk = async () => {
  const { data } = await apiClient.get(`${runBase()}/risk/organization`);
  return normalizeOrgSummary(normalizeObjectEnvelope(data).data) || {};
};

export const getBusinessUnits = async () => {
  const { data } = await apiClient.get(`${runBase()}/risk/business-units`);
  const { results } = normalizeEnvelope(data);
  const rows = Array.isArray(results) ? results : [];
  return rows.map(normalizeBusinessUnit);
};

export const getAssets = async () => {
  const { data } = await apiClient.get(`${runBase()}/risk/assets`);
  const { results } = normalizeEnvelope(data);
  const rows = Array.isArray(results) ? results : [];
  return rows.map(normalizeAsset);
};

export const getAssetDetail = async (assetId) => {
  const { data } = await apiClient.get(`${runBase()}/risk/assets/${encodeURIComponent(assetId)}`);
  return normalizeAsset(normalizeObjectEnvelope(data).data) || {};
};

export const getAssetDrivers = async (assetId) => {
  const { data } = await apiClient.get(
    `${runBase()}/risk/assets/${encodeURIComponent(assetId)}/drivers`,
  );
  return normalizeObjectEnvelope(data).data;
};

export const getControlsScenarios = async () => {
  const { data } = await apiClient.get(`${runBase()}/controls/scenarios`);
  const { results } = normalizeEnvelope(data);
  return Array.isArray(results) ? results : [];
};

export const getControlsRoi = async () => {
  const { data } = await apiClient.get(`${runBase()}/controls/roi`);
  const { results } = normalizeEnvelope(data);
  const rows = Array.isArray(results) ? results : [];
  return rows.map(normalizeControlRoi);
};

export const getOptimizedPlan = async (budget, oneControlPerAsset = true) => {
  const { data } = await apiClient.post(`${runBase()}/controls/optimize`, {
    budget_usd: budget,
    one_control_per_asset: oneControlPerAsset,
  });
  return normalizeObjectEnvelope(data).data;
};

export const getInvestmentFrontier = async () => {
  const { data } = await apiClient.get(`${runBase()}/controls/frontier`);
  return normalizeObjectEnvelope(data).data;
};

export const getRiskTrend = async () => {
  const { data } = await apiClient.get(`${runBase()}/risk/trend`);
  const { results } = normalizeEnvelope(data);
  const rows = Array.isArray(results) ? results : [];
  return rows.map(normalizeTrendRow);
};

export const getPortfolioLec = async () => {
  const { data } = await apiClient.get(`${runBase()}/risk/portfolio-lec`);
  return normalizePortfolio(normalizeObjectEnvelope(data).data);
};

export const getVulnPredictions = async () => {
  const { data } = await apiClient.get(`${runBase()}/predictions/vulnerabilities`);
  const { results } = normalizeEnvelope(data);
  return Array.isArray(results) ? results : [];
};

export const getThreatForecast = async (horizonDays = 14) => {
  const { data } = await apiClient.get(`${runBase()}/predictions/threat-forecast`, {
    params: { horizon_days: horizonDays },
  });
  return normalizeObjectEnvelope(data).data;
};

export const getDependencyGraph = async () => {
  const { data } = await apiClient.get(`${runBase()}/risk/dependency-graph`);
  return normalizeObjectEnvelope(data).data;
};

export const getRiskPropagation = async (breachedAssetId) => {
  const { data } = await apiClient.get(`${runBase()}/risk/dependency-graph/propagate`, {
    params: { breached_asset_id: breachedAssetId },
  });
  return normalizeObjectEnvelope(data).data;
};

// ─── Compliance ────────────────────────────────────────────────────────────
export const getCompliancePosture = async () => {
  const { data } = await apiClient.get(`${runBase()}/compliance/posture`);
  return normalizeObjectEnvelope(data).data;
};

export const getComplianceGaps = async () => {
  const { data } = await apiClient.get(`${runBase()}/compliance/gaps`);
  const { results } = normalizeEnvelope(data);
  const rows = Array.isArray(results) ? results : [];
  return rows.map(normalizeGap);
};

// ─── Regulatory ────────────────────────────────────────────────────────────
export const listRegulatoryRules = async () => {
  const { data } = await apiClient.get('/api/v1/regulatory/rules');
  return Array.isArray(data) ? data : [];
};

export const evaluateRegulatoryExposure = async (datasetId) => {
  const { data } = await apiClient.post(
    `/api/v1/datasets/${encodeURIComponent(datasetId)}/regulatory/assessments`,
  );
  return data;
};

export const getRegulatoryAssessments = async () => {
  const { data } = await apiClient.get(`${runBase()}/compliance/assessments`);
  const { results } = normalizeEnvelope(data);
  return Array.isArray(results) ? results : [];
};

export const reviewRegulatoryAssessment = async (assessmentId, payload) => {
  const { data } = await apiClient.post(
    `/api/v1/regulatory/assessments/${encodeURIComponent(assessmentId)}/review`,
    payload,
  );
  return data;
};

// ─── Alerts ────────────────────────────────────────────────────────────────
export const listAlerts = async ({ status, severity, page = 1, pageSize = 50 } = {}) => {
  const { data } = await apiClient.get('/api/v1/alerts', {
    params: {
      ...(status ? { status } : {}),
      ...(severity ? { severity } : {}),
      page,
      page_size: pageSize,
    },
  });
  return data;
};

export const getAlert = async (alertId) => {
  const { data } = await apiClient.get(`/api/v1/alerts/${encodeURIComponent(alertId)}`);
  return data;
};

export const acknowledgeAlert = async (alertId) => {
  const { data } = await apiClient.post(`/api/v1/alerts/${encodeURIComponent(alertId)}/acknowledge`);
  return data;
};

export const resolveAlert = async (alertId) => {
  const { data } = await apiClient.post(`/api/v1/alerts/${encodeURIComponent(alertId)}/resolve`);
  return data;
};

export const closeAlert = async (alertId) => {
  const { data } = await apiClient.post(`/api/v1/alerts/${encodeURIComponent(alertId)}/close`);
  return data;
};

export const escalateAlert = async (alertId) => {
  const { data } = await apiClient.post(`/api/v1/alerts/${encodeURIComponent(alertId)}/escalate`);
  return data;
};

export const assignAlert = async (alertId, ownerId) => {
  const { data } = await apiClient.post(`/api/v1/alerts/${encodeURIComponent(alertId)}/assign`, {
    owner_id: ownerId,
  });
  return data;
};

export const getAlertDeliveries = async (alertId) => {
  const { data } = await apiClient.get(
    `/api/v1/alerts/${encodeURIComponent(alertId)}/deliveries`,
  );
  return Array.isArray(data) ? data : [];
};

// ─── Threat intelligence ───────────────────────────────────────────────────
export const getThreatIntelStatus = async () => {
  const { data } = await apiClient.get('/api/v1/threat-intel/status');
  return data;
};

export const refreshThreatIntel = async () => {
  const { data } = await apiClient.post('/api/v1/threat-intel/refresh');
  return data;
};

// ─── Live feed ─────────────────────────────────────────────────────────────
export const getRecentLiveEvents = async () => {
  const ds = _activeScope.datasetId;
  const { data } = await apiClient.get('/api/v1/live-feed/recent', {
    params: ds ? { dataset_id: ds } : {},
  });
  return data;
};

export const getLiveFeedWsUrl = () => {
  const httpUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
  const wsProtocol = httpUrl.startsWith('https') ? 'wss' : 'ws';
  const cleanBase = httpUrl.replace(/^https?:\/\//, '');
  const ds = _activeScope.datasetId;
  const token = getAccessToken();
  const params = new URLSearchParams();
  if (ds) params.set('dataset_id', ds);
  if (token) params.set('token', token);
  const query = params.toString() ? `?${params.toString()}` : '';
  return `${wsProtocol}://${cleanBase}/api/v1/ws/live-feed${query}`;
};

// ─── Chat ──────────────────────────────────────────────────────────────────
export const sendChatMessage = async (message, history = []) => {
  const { datasetId, runId } = _activeScope;
  if (!datasetId || !runId) {
    const err = new Error('Select a dataset and completed run before using the risk copilot.');
    err.code = 'NO_ACTIVE_RUN';
    throw err;
  }
  const { data } = await apiClient.post('/api/v1/chat', {
    dataset_id: datasetId,
    run_id: runId,
    message,
    history: (history || []).map((h) => ({ role: h.role, content: h.content })),
  });
  return data;
};

// ─── Currency formatting ───────────────────────────────────────────────────
let _currency = 'USD';
let _rate = 88;

export function setCurrencyConfig(currency, rate) {
  _currency = currency === 'INR' ? 'INR' : 'USD';
  if (Number.isFinite(Number(rate)) && Number(rate) > 0) _rate = Number(rate);
}

export function getCurrentCurrency() {
  return _currency;
}

const MISSING = '—';

export const formatCurrency = (val) => {
  if (val === null || val === undefined || val === '' || isNaN(Number(val))) {
    return MISSING;
  }
  const num = Number(val);
  if (_currency === 'INR') {
    const inr = num * _rate;
    if (Math.abs(inr) >= 1e7) return `₹${(inr / 1e7).toFixed(2)} Cr`;
    if (Math.abs(inr) >= 1e5) return `₹${(inr / 1e5).toFixed(2)} L`;
    return `₹${new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 }).format(Math.round(inr))}`;
  }
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(Math.round(num));
};

export const formatCompactCurrency = (val) => {
  if (val === null || val === undefined || val === '' || isNaN(Number(val))) {
    return MISSING;
  }
  const num = Number(val);
  if (_currency === 'INR') {
    const inr = num * _rate;
    if (Math.abs(inr) >= 1e7) return `₹${(inr / 1e7).toFixed(1)} Cr`;
    if (Math.abs(inr) >= 1e5) return `₹${(inr / 1e5).toFixed(1)} L`;
    if (Math.abs(inr) >= 1e3) return `₹${(inr / 1e3).toFixed(0)}K`;
    return `₹${Math.round(inr)}`;
  }
  if (Math.abs(num) >= 1e6) return `$${(num / 1e6).toFixed(1)}M`;
  if (Math.abs(num) >= 1e3) return `$${(num / 1e3).toFixed(0)}K`;
  return `$${Math.round(num)}`;
};

export const formatPercent = (val, decimals = 1) => {
  if (val === null || val === undefined || isNaN(Number(val))) return MISSING;
  return `${Number(val).toFixed(decimals)}%`;
};

export const formatMultiplier = (val, decimals = 2) => {
  if (val === null || val === undefined || isNaN(Number(val))) return MISSING;
  return `${Number(val).toFixed(decimals)}x`;
};
