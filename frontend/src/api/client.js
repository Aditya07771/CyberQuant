import axios from 'axios';

const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export const apiClient = axios.create({
  baseURL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 120000,
});

/**
 * Health check endpoint
 */
export const getHealth = async () => {
  const response = await apiClient.get('/health');
  return response.data;
};

/**
 * Enterprise organization risk metrics
 */
export const getOrgRisk = async () => {
  const response = await apiClient.get('/risk/organization');
  // Returns list of records or single object
  if (Array.isArray(response.data)) {
    return response.data[0] || {};
  }
  return response.data || {};
};

/**
 * Business unit risk metrics
 */
export const getBusinessUnits = async () => {
  const response = await apiClient.get('/risk/business-units');
  return Array.isArray(response.data) ? response.data : [];
};

/**
 * All assets risk summary
 */
export const getAssets = async () => {
  const response = await apiClient.get('/risk/assets');
  return Array.isArray(response.data) ? response.data : [];
};

/**
 * Detailed single asset record
 */
export const getAssetDetail = async (assetId) => {
  const response = await apiClient.get(`/risk/assets/${encodeURIComponent(assetId)}`);
  return response.data;
};

/**
 * Asset EAL drivers (counterfactual analysis)
 */
export const getAssetDrivers = async (assetId) => {
  const response = await apiClient.get(`/risk/assets/${encodeURIComponent(assetId)}/drivers`);
  return response.data;
};

/**
 * Control scenarios raw list
 */
export const getControlsScenarios = async () => {
  const response = await apiClient.get('/controls/scenarios');
  return Array.isArray(response.data) ? response.data : [];
};

/**
 * Ranked controls by overall ROSI
 */
export const getControlsRoi = async () => {
  const response = await apiClient.get('/controls/roi');
  return Array.isArray(response.data) ? response.data : [];
};

/**
 * ILP-based Investment optimizer
 * @param {number} budget - Budget in USD
 * @param {boolean} oneControlPerAsset - Restrict to at most 1 control per asset
 */
export const getOptimizedPlan = async (budget, oneControlPerAsset = true) => {
  const response = await apiClient.get('/controls/optimize', {
    params: {
      budget,
      one_control_per_asset: oneControlPerAsset,
    },
  });
  return response.data;
};

/**
 * AI Chatbot assistant query
 * @param {string} message - User question
 * @param {Array<{role: string, content: string}>} history - Conversation history
 */
export const sendChatMessage = async (message, history = []) => {
  const response = await apiClient.post('/chat', {
    message,
    history,
  });
  return response.data;
};

/**
 * Upload dataset files (multi-part: CSVs, ZIP, or JSON)
 * @param {FormData} formData
 */
export const uploadDatasetFiles = async (formData) => {
  const response = await apiClient.post('/api/datasets/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    timeout: 300000,
  });
  return response.data;
};

/**
 * Upload dataset via direct JSON payload
 * @param {Object} payload
 */
export const uploadJsonDataset = async (payload) => {
  const response = await apiClient.post('/api/datasets/upload-json', payload, {
    timeout: 300000,
  });
  return response.data;
};

/**
 * Trigger built-in demo dataset load and execution
 */
export const loadDemoDataset = async () => {
  const response = await apiClient.post('/api/datasets/demo', {}, {
    timeout: 300000,
  });
  return response.data;
};

/**
 * Fetch current dataset and pipeline output readiness status
 */
export const getDatasetStatus = async () => {
  const response = await apiClient.get('/api/datasets/status');
  return response.data;
};

/**
 * Compliance posture across frameworks
 */
export const getCompliancePosture = async () => {
  const response = await apiClient.get('/compliance/posture');
  return response.data;
};

/**
 * Compliance gaps and uncovered requirements
 */
export const getComplianceGaps = async () => {
  const response = await apiClient.get('/compliance/gaps');
  return Array.isArray(response.data) ? response.data : [];
};

/**
 * Investment efficient frontier data
 */
export const getInvestmentFrontier = async () => {
  const response = await apiClient.get('/controls/frontier');
  return response.data;
};

/**
 * Risk trend over time
 */
export const getRiskTrend = async () => {
  const response = await apiClient.get('/risk/trend');
  return Array.isArray(response.data) ? response.data : [];
};

/**
 * ML vulnerability predictions
 */
export const getVulnPredictions = async () => {
  const response = await apiClient.get('/predictions/vulnerabilities');
  return response.data;
};

/**
 * Sequential LSTM Threat Event Frequency (TEF) & attack sequence forecast
 * @param {number} horizonDays - Forecast window in days
 */
export const getThreatForecast = async (horizonDays = 14) => {
  const response = await apiClient.get('/predictions/threat-forecast', {
    params: { horizon_days: horizonDays },
  });
  return response.data;
};

/**
 * Live streaming threat events fallback REST endpoint
 */
export const getRecentLiveEvents = async () => {
  const response = await apiClient.get('/api/live-feed/recent');
  return response.data;
};

/**
 * Active Directory dependency graph topology
 */
export const getDependencyGraph = async () => {
  const response = await apiClient.get('/risk/dependency-graph');
  return response.data;
};

/**
 * Systemic lateral movement risk propagation from breached asset
 * @param {string} breachedAssetId - e.g. "AST-1000"
 */
export const getRiskPropagation = async (breachedAssetId) => {
  const response = await apiClient.get('/risk/dependency-graph/propagate', {
    params: { breached_asset_id: breachedAssetId },
  });
  return response.data;
};

/**
 * Enterprise-wide aggregate Loss Exceedance Curve (LEC) data
 */
export const getPortfolioLec = async () => {
  const response = await apiClient.get('/risk/portfolio-lec');
  return response.data;
};

/**
 * Constructs the WebSocket endpoint URL for live streaming threat telemetry
 */
export const getLiveFeedWsUrl = () => {
  const httpUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
  const wsProtocol = httpUrl.startsWith('https') ? 'wss' : 'ws';
  const cleanBase = httpUrl.replace(/^https?:\/\//, '');
  return `${wsProtocol}://${cleanBase}/ws/live-feed`;
};

// ─── Currency formatting ───────────────────────────────────────────────────
// The CurrencyProvider calls setCurrencyConfig() when currency/rate changes.
// All components that import formatCurrency() will automatically use the
// active currency without needing prop-drilling.

let _currency = 'USD';
let _rate = 88;

/**
 * Called by CurrencyProvider to sync the formatter with the selected currency.
 * @param {'USD'|'INR'} currency
 * @param {number} rate - USD→INR exchange rate
 */
export function setCurrencyConfig(currency, rate) {
  _currency = currency;
  _rate = rate;
}

/**
 * Current currency code
 */
export function getCurrentCurrency() {
  return _currency;
}

/**
 * Currency formatter — currency-aware via module-level state.
 * USD: $1,234,567
 * INR: ₹2.52 Cr  /  ₹12.00 L  /  ₹12,345
 * @param {number|string|null} val - USD value (backend always sends USD)
 */
export const formatCurrency = (val) => {
  if (val === null || val === undefined || isNaN(Number(val))) {
    return _currency === 'INR' ? '₹0' : '$0';
  }
  const num = Number(val);

  if (_currency === 'INR') {
    const inr = num * _rate;
    if (inr >= 1e7) {
      return `₹${(inr / 1e7).toFixed(2)} Cr`;
    } else if (inr >= 1e5) {
      return `₹${(inr / 1e5).toFixed(2)} L`;
    }
    return `₹${new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 }).format(Math.round(inr))}`;
  }

  // USD
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(Math.round(num));
};

/**
 * Compact currency formatter for chart axes and tooltips.
 * USD: $2.5M, $500K
 * INR: ₹2.2 Cr, ₹44.0 L, ₹50K
 * @param {number|string|null} val - USD value
 */
export const formatCompactCurrency = (val) => {
  if (val === null || val === undefined || isNaN(Number(val))) {
    return _currency === 'INR' ? '₹0' : '$0';
  }
  const num = Number(val);
  if (_currency === 'INR') {
    const inr = num * _rate;
    if (inr >= 1e7) {
      return `₹${(inr / 1e7).toFixed(1)} Cr`;
    } else if (inr >= 1e5) {
      return `₹${(inr / 1e5).toFixed(1)} L`;
    } else if (inr >= 1e3) {
      return `₹${(inr / 1e3).toFixed(0)}K`;
    }
    return `₹${Math.round(inr)}`;
  }

  // USD
  if (num >= 1e6) {
    return `$${(num / 1e6).toFixed(1)}M`;
  } else if (num >= 1e3) {
    return `$${(num / 1e3).toFixed(0)}K`;
  }
  return `$${Math.round(num)}`;
};

/**
 * Percentage formatter: 94.2%
 */
export const formatPercent = (val, decimals = 1) => {
  if (val === null || val === undefined || isNaN(Number(val))) return '0%';
  return `${Number(val).toFixed(decimals)}%`;
};

/**
 * ROSI multiplier formatter: 4.25x
 */
export const formatMultiplier = (val, decimals = 2) => {
  if (val === null || val === undefined || isNaN(Number(val))) return '0.00x';
  return `${Number(val).toFixed(decimals)}x`;
};
