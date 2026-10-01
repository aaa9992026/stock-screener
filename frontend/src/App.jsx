import { useEffect, useRef, useState } from "react";
import {
  createChart,
  CandlestickSeries,
  LineSeries,
  HistogramSeries,
} from "lightweight-charts";
import axios from "axios";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ResponsiveContainer,
} from "recharts";
import "./App.css";

const API = "/api";

const chartLimitForTimeframe = (timeframe) => timeframe === "daily" ? 1040 : timeframe === "weekly" ? 260 : 300;

const formatPctChange = (value) => {
  if (value === null || value === undefined || value === "") return "-";
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "-";
  const prefix = numeric > 0 ? "+" : "";
  return `${prefix}${numeric.toFixed(2)}%`;
};

const formatMarketMoney = (value, exchange) => {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return "-";
  const currency = exchange === "US" ? "USD" : "INR";
  return new Intl.NumberFormat(exchange === "US" ? "en-US" : "en-IN", {
    style: "currency",
    currency,
    notation: "compact",
    maximumFractionDigits: 2,
  }).format(Number(value));
};

const defaultScoreWeights = { fundamental: 30, technical: 25, relative_strength: 25, ownership: 15, sector: 5 };
const defaultRsWeights = { "1w": 30, "2w": 0, "1m": 25, "2m": 0, "3m": 20, "6m": 15, "1y": 10, "sector": 0 };
const SCORE_WEIGHTS_STORAGE_VERSION = "m2-client-composite-100-v1";
const RS_WEIGHTS_STORAGE_VERSION = "m2-rs-market-universe-v2";


const universeColumnOptions = [
  ["symbol", "Symbol"], ["name", "Company"], ["isin", "ISIN"], ["exchange", "Exchange"],
  ["sector", "Sector"], ["industry", "Industry"], ["close", "LTP"],
  ["volume", "Volume"], ["market_cap", "Market Cap"], ["trailing_eps", "EPS"],
  ["forward_eps", "Forward EPS"], ["revenue", "Revenue"], ["net_income", "Net Income"],
  ["profit_margin", "Profit Margin"], ["return_on_equity", "ROE"], ["return_on_assets", "ROA"],
  ["institution_percent", "Institutional Holding"], ["insider_percent", "Insider Holding"],
  ["shares_outstanding", "Shares Outstanding"], ["float_shares", "Float Shares"],
  ["distance_52w_high", "Distance From 52W High"], ["distance_52w_low", "Distance From 52W Low"],
  ["volume_ratio", "Volume / 52W Avg"], ["latest_date", "Latest Price Date"],
  ["data_coverage", "Data Coverage"],
];

const universeDefaultColumns = [
  "symbol", "name", "isin", "close", "market_cap", "trailing_eps", "profit_margin",
  "return_on_equity", "institution_percent", "distance_52w_high", "volume_ratio", "data_coverage",
];

const emptyUniverseFilters = {
  market: "ALL", q: "", sector: "", industry: "", market_cap_min: "", market_cap_max: "",
  eps_min: "", revenue_min: "", net_income_min: "", roe_min: "", roa_min: "",
  profit_margin_min: "", institution_min: "", insider_min: "", close_min: "", close_max: "",
  distance_52w_high_max: "", distance_52w_low_max: "", volume_ratio_min: "",
  sort_by: "data_coverage", sort_dir: "desc",
};

const formatUniverseCell = (key, value, row) => {
  if (value === null || value === undefined || value === "") return "N/A";
  if (["profit_margin", "return_on_equity", "return_on_assets", "institution_percent", "insider_percent", "distance_52w_high", "distance_52w_low", "data_coverage"].includes(key)) {
    return `${Number(value).toFixed(2)}%`;
  }
  if (["market_cap", "revenue", "net_income", "shares_outstanding", "float_shares"].includes(key)) {
    return new Intl.NumberFormat(row?.exchange === "US" ? "en-US" : "en-IN", { notation: "compact", maximumFractionDigits: 2 }).format(Number(value));
  }
  if (key === "volume") return Number(value).toLocaleString();
  if (["close", "trailing_eps", "forward_eps", "volume_ratio"].includes(key)) return Number(value).toFixed(2);
  return String(value);
};

const compareNumeric = (left, comparator, right) => {
  const a = Number(left);
  const b = Number(right);
  if (!Number.isFinite(a) || !Number.isFinite(b)) return null;
  if (comparator === ">=") return a >= b;
  if (comparator === "<=") return a <= b;
  if (comparator === "<") return a < b;
  return a > b;
};

const filterScoreText = (score) => {
  if (score === null || score === undefined || !Number.isFinite(Number(score))) return "N/A";
  return `${Number(score).toFixed(0)}/100`;
};

const formatClientFilterValue = (key, value) => {
  if (key === "delivery_percent" && value && typeof value === "object") {
    if (!value.available) return "N/A";
    const day = value.day?.percent;
    const week = value.weekly?.percent;
    const month = value.monthly?.percent;
    const parts = [
      day != null ? `Day ${Number(day).toFixed(2)}%` : null,
      week != null ? `Week ${Number(week).toFixed(2)}%` : null,
      month != null ? `Month ${Number(month).toFixed(2)}%` : null,
    ].filter(Boolean);
    return parts.length ? parts.join(" • ") : "N/A";
  }
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (value === null || value === undefined) return "N/A";
  if (typeof value === "number") return Number(value).toFixed(2);
  if (typeof value === "object") return "N/A";
  return String(value);
};
const defaultRankingSubweights = {
  technical: { ema20: 20, ema50: 20, ema150: 20, ema200: 20, rsi: 20 },
  fundamental: { eps: 20, net_income: 20, profit_margin: 20, roe: 20, roa: 20 },
  ownership: { institution: 70, insider: 30 },
};

// Final client revision: only the factors written in the client's handwritten
// scoring sheets are exposed in the ranking UI.  Values and weightages remain
// editable; unavailable source data is never estimated.
const defaultHandwrittenFactors = {
  technical: {
    bb_width: { weight: 10, threshold: 10, comparator: "<=" },
    atr5_lt20: { weight: 10, comparator: "<" },
    atr10_lt20: { weight: 5, comparator: "<" },
    rsi14: { weight: 5, enabled: true, t1: 30, t2: 40, t3: 50, p1: 2, p2: 3, p3: 4, p4: 5 },
    volume10_lt20: { weight: 10, comparator: "<" },
    volume20_lt40: { weight: 5, comparator: "<" },
    distance52: { weight: 10, t1: 10, t2: 17, t3: 20, p1: 10, p2: 8, p3: 6, p4: 3 },
    ema20_gt50: { weight: 8, comparator: ">" },
    ema50_gt150: { weight: 4, comparator: ">" },
  },
  fundamental: {
    q_eps_yoy: { weight: 10, threshold: 30, comparator: ">" },
    q_eps_yoy_rising: { weight: 6, comparator: ">" },
    q_pat_yoy: { weight: 6, threshold: 30, comparator: ">" },
    q_pat_rising: { weight: 4, comparator: ">" },
    q_pat_yoy_rising: { weight: 6, comparator: ">" },
    q_npm_yoy: { weight: 4, threshold: 20, comparator: ">" },
    q_sales_yoy: { weight: 7, threshold: 30, comparator: ">" },
    q_sales_rising: { weight: 4, comparator: ">" },
    a_eps_yoy: { weight: 6, threshold: 20, comparator: ">" },
    a_eps_rising: { weight: 4, comparator: ">" },
    a_pat_yoy: { weight: 5, threshold: 20, comparator: ">" },
    a_pat_rising: { weight: 4, comparator: ">" },
    a_sales_yoy: { weight: 5, threshold: 20, comparator: ">" },
    a_sales_rising: { weight: 4, comparator: ">" },
    a_ocf_yoy: { weight: 4, threshold: 10, comparator: ">" },
    a_npm_rising: { weight: 3, comparator: ">" },
    roe_above: { weight: 0, threshold: 20, comparator: ">", enabled: true },
    roce_above: { weight: 0, threshold: 30, comparator: ">", enabled: true },
    cashflow_per_share: { weight: 0, threshold: 0, comparator: ">", enabled: false },
    shares_outstanding: { weight: 0, threshold: 0, comparator: "<", enabled: false },
    float_shares: { weight: 0, threshold: 0, comparator: "<", enabled: false },
  },
  ownership: {
    promoter_qoq: { weight: 10, threshold: 0.3, comparator: ">" },
    promoter_above: { weight: 8, threshold: 50, comparator: ">" },
    promoter_rising: { weight: 5, comparator: ">" },
    pledge: { weight: 5, t1: 5, t2: 10, t3: 15, t4: 20 },
    fii_qoq: { weight: 10, threshold: 0.3, comparator: ">" },
    fii_rising: { weight: 10, comparator: ">" },
    dii_mf_qoq: { weight: 10, threshold: 0.1, comparator: ">" },
    dii_mf_rising: { weight: 10, comparator: ">" },
    insider_activity: { weight: 10 },
  },
};

const handwrittenFactorMeta = {
  technical: [
    ["bb_width", "Upper BB - Lower BB", "BB width ≤ editable threshold", ["threshold"]],
    ["atr5_lt20", "5-day ATR% average < 20-day ATR% average", "ATR contraction", []],
    ["atr10_lt20", "10-day ATR% average < 20-day ATR% average", "ATR contraction", []],
    ["rsi14", "RSI (14)", "RSI > 50 = 5 points; 40-50 = 4; 30-40 = 3; below 30 = 2", ["t1", "t2", "t3", "p1", "p2", "p3", "p4"]],
    ["volume10_lt20", "10-day volume average < 20-day volume average", "Volume contraction", []],
    ["volume20_lt40", "20-day volume average < 40-day volume average", "Longer-volume comparison", []],
    ["distance52", "Distance from 52-week high", "Handwritten 10 / 17 / 20% distance bands", ["t1", "t2", "t3"]],
    ["ema20_gt50", "20 EMA > 50 EMA", "EMA trend factor", []],
    ["ema50_gt150", "50 EMA > 150 EMA", "EMA trend factor", []],
  ],
  fundamental: [
    ["q_eps_yoy", "Latest quarter EPS (YoY)", "Latest quarterly EPS YoY growth", ["threshold"], "EPS"],
    ["q_eps_yoy_rising", "Quarterly EPS YoY trend rising", "Latest YoY > prior YoY > second-prior YoY", [], "EPS"],
    ["a_eps_yoy", "Latest year EPS (YoY)", "Latest annual EPS growth", ["threshold"], "EPS"],
    ["a_eps_rising", "Annual EPS trend rising", "Latest EPS > prior year > second-prior year", [], "EPS"],
    ["q_pat_yoy", "Latest quarter PAT (YoY)", "Latest quarterly PAT YoY growth", ["threshold"], "PAT"],
    ["q_pat_rising", "Quarterly PAT rising", "Latest PAT > prior PAT > second-prior PAT", [], "PAT"],
    ["q_pat_yoy_rising", "Quarterly PAT YoY trend rising", "Latest YoY > prior YoY > second-prior YoY", [], "PAT"],
    ["a_pat_yoy", "Latest year PAT (YoY)", "Latest annual PAT growth", ["threshold"], "PAT"],
    ["a_pat_rising", "Annual PAT trend rising", "Latest PAT > prior year > second-prior year", [], "PAT"],
    ["q_sales_yoy", "Latest quarter Sales (YoY)", "Latest quarterly sales YoY growth", ["threshold"], "Sales"],
    ["q_sales_rising", "Quarterly Sales trend rising", "Latest sales > prior sales > second-prior sales", [], "Sales"],
    ["a_sales_yoy", "Latest year Sales (YoY)", "Latest annual sales growth", ["threshold"], "Sales"],
    ["a_sales_rising", "Annual Sales trend rising", "Latest sales > prior year > second-prior year", [], "Sales"],
    ["q_npm_yoy", "Quarterly NPM growth (YoY)", "Latest NPM vs year-ago quarter", ["threshold"], "NPM"],
    ["a_npm_rising", "Annual NPM rising", "Latest year NPM > prior year NPM", [], "NPM"],
    ["a_ocf_yoy", "Cash flow from operating activities (YoY)", "Latest annual operating cash flow growth", ["threshold"], "CFO"],
    ["cashflow_per_share", "Cash flow per share", "Editable threshold; disabled until client confirms the exact rule", ["threshold"], "CFO"],
    ["roe_above", "ROE", "Client note: ROE > 20; weight remains editable", ["threshold"], "Other"],
    ["roce_above", "ROCE", "Client note: ROCE > 30; weight remains editable", ["threshold"], "Other"],
    ["shares_outstanding", "Outstanding shares", "Editable threshold; disabled until client confirms the exact rule", ["threshold"], "Other"],
    ["float_shares", "Float shares", "Editable threshold; disabled until client confirms the exact rule", ["threshold"], "Other"],
  ],
  ownership: [
    ["promoter_qoq", "Promoter holding change (QoQ)", "Latest quarter promoter change", ["threshold"]],
    ["promoter_above", "Promoter holding", "Promoter holding above editable level", ["threshold"]],
    ["promoter_rising", "Promoter yearly holding rising", "Latest-year promoter holding > previous-year promoter holding", []],
    ["pledge", "Promoter holding pledge", "Handwritten pledge bands: <5, 5-10, 10-15, 15-20, >20", ["t1", "t2", "t3", "t4"]],
    ["fii_qoq", "FII holding change (QoQ)", "Latest quarter FII change", ["threshold"]],
    ["fii_rising", "FII holding rising", "Latest-year FII holding > previous-year holding AND prior-quarter holding > second-prior-quarter holding", []],
    ["dii_mf_qoq", "DII / MF holding change (QoQ)", "Latest DII/MF change", ["threshold"]],
    ["dii_mf_rising", "DII / MF holding rising", "Prior-quarter holding > second-prior-quarter holding", []],
    ["insider_activity", "Insider activity", "Repeated buy / repeated sell factor", []],
  ],
};

const readLocalObject = (key, fallback) => {
  try {
    const value = JSON.parse(localStorage.getItem(key));
    return value && typeof value === "object" ? { ...fallback, ...value } : fallback;
  } catch {
    return fallback;
  }
};

function App() {
  const [symbol, setSymbol] = useState("AAPL");
  const [symbolInput, setSymbolInput] = useState("AAPL");
  const [exchange, setExchange] = useState("US");
  const [timeframe, setTimeframe] = useState("daily");
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [fundamentals, setFundamentals] = useState(null);
  const [dataStale, setDataStale] = useState(false);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [dataStatus, setDataStatus] = useState("connected");
  const [indicators, setIndicators] = useState(null);
  const [fundamentalHistory, setFundamentalHistory] = useState(null);
  const [secEdgar, setSecEdgar] = useState(null);
  const [secEdgarError, setSecEdgarError] = useState("");
  const [smaShort, setSmaShort] = useState(20);
  const [smaLong, setSmaLong] = useState(50);
  const [rsiPeriod, setRsiPeriod] = useState(14);
  const chartContainerRef = useRef(null);
  const symbolSearchRef = useRef(null);
  const suggestionRequestRef = useRef(0);
  const activeSelectionRef = useRef("");
  activeSelectionRef.current = `${exchange}:${symbol}:${timeframe}`;
  const [suggestions, setSuggestions] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [benchmark, setBenchmark] = useState(null);
  const [dashboard, setDashboard] = useState(null);
  const [technicalSummary, setTechnicalSummary] = useState(null);
  const [ownershipDetails, setOwnershipDetails] = useState(null);
  const [indiaShareholding, setIndiaShareholding] = useState(null);
  const [chartInfo, setChartInfo] = useState(null);
  const [selectedCompany, setSelectedCompany] = useState({ name: "Apple Inc.", isin: null });
  const [scoreWeights, setScoreWeights] = useState(() => {
    try {
      if (localStorage.getItem("scoreWeightsVersion") !== SCORE_WEIGHTS_STORAGE_VERSION) {
        return { ...defaultScoreWeights };
      }
      const saved = JSON.parse(localStorage.getItem("scoreWeights")) || {};
      return {
        technical: Number(saved.technical ?? defaultScoreWeights.technical),
        fundamental: Number(saved.fundamental ?? defaultScoreWeights.fundamental),
        relative_strength: Number(saved.relative_strength ?? defaultScoreWeights.relative_strength),
        ownership: Number(saved.ownership ?? defaultScoreWeights.ownership),
        sector: Number(saved.sector ?? defaultScoreWeights.sector),
      };
    } catch {
      return { ...defaultScoreWeights };
    }
  });
  const [rsWeights, setRsWeights] = useState(() => {
    if (localStorage.getItem("rsWeightsVersion") !== RS_WEIGHTS_STORAGE_VERSION) {
      return { ...defaultRsWeights };
    }
    const saved = readLocalObject("rsWeights", defaultRsWeights);
    return { ...defaultRsWeights, ...saved };
  });
  const [rsVisibility, setRsVisibility] = useState(() => readLocalObject("rsVisibility", { "1w": true, "2w": false, "1m": true, "2m": false, "3m": true, "6m": true, "1y": true, "sector": true }));
  const [rankingSubweights, setRankingSubweights] = useState(() => {
    const saved = readLocalObject("rankingSubweights", defaultRankingSubweights);
    return {
      technical: { ...defaultRankingSubweights.technical, ...(saved.technical || {}) },
      fundamental: { ...defaultRankingSubweights.fundamental, ...(saved.fundamental || {}) },
      ownership: { ...defaultRankingSubweights.ownership, ...(saved.ownership || {}) },
    };
  });
  const [handwrittenFactors, setHandwrittenFactors] = useState(() => {
    const saved = readLocalObject("handwrittenFactors", {});
    const mergeGroup = (group) => Object.fromEntries(
      Object.entries(defaultHandwrittenFactors[group]).map(([key, defaults]) => [key, { ...defaults, ...((saved[group] || {})[key] || {}) }])
    );
    return { technical: mergeGroup("technical"), fundamental: mergeGroup("fundamental"), ownership: mergeGroup("ownership") };
  });
  const [showRankingDetails, setShowRankingDetails] = useState(true);
  const [showExcelHelp, setShowExcelHelp] = useState(false);
  const [excelCopyMessage, setExcelCopyMessage] = useState("");
  const [universeTab, setUniverseTab] = useState("Popular");
  const [universeFilters, setUniverseFilters] = useState({ ...emptyUniverseFilters });
  const [universeRows, setUniverseRows] = useState([]);
  const [universeMeta, setUniverseMeta] = useState({ total: 0, pages: 1, facets: { sectors: [], industries: [] }, coverage: {} });
  const [universeLoading, setUniverseLoading] = useState(false);
  const universeRequestRef = useRef(0);
  const [universeSyncing, setUniverseSyncing] = useState(false);
  const [universeError, setUniverseError] = useState("");
  const [sectorAnalysis, setSectorAnalysis] = useState({ rows: [], formula: "", aggregation: "", data_rule: "" });
  const [sectorAnalysisLoading, setSectorAnalysisLoading] = useState(false);
  const [sectorAnalysisError, setSectorAnalysisError] = useState("");
  const [universePage, setUniversePage] = useState(1);
  const [universePageSize, setUniversePageSize] = useState(25);
  const [universeColumns, setUniverseColumns] = useState([...universeDefaultColumns]);
  const [showUniverseColumns, setShowUniverseColumns] = useState(false);
  const [chartOverlays, setChartOverlays] = useState({
    ema: true, sma: true, bollinger: true, volume: true, eps: true, rs: true
  });


  const buildUniverseParams = (page = universePage, includePage = true, filterOverride = universeFilters, pageSizeOverride = universePageSize) => {
    const params = { page_size: pageSizeOverride };
    if (includePage) params.page = page;
    Object.entries(filterOverride).forEach(([key, value]) => {
      if (value !== "" && value !== null && value !== undefined) params[key] = value;
    });
    return params;
  };

  const loadUniverseScreener = async (page = 1, filterOverride = universeFilters, pageSizeOverride = universePageSize) => {
    const requestId = ++universeRequestRef.current;
    setUniverseLoading(true);
    setUniverseError("");
    let lastError = null;

    try {
      // Railway can briefly reject a read while startup/background sync work is
      // committing. Retry the same request once, but never erase a valid table
      // because of one transient failure.
      for (let attempt = 0; attempt < 2; attempt += 1) {
        try {
          const res = await axios.get(`${API}/market/screener`, {
            params: buildUniverseParams(page, true, filterOverride, pageSizeOverride),
            timeout: 30000,
          });
          if (requestId !== universeRequestRef.current) return false;
          setUniverseRows(res.data.rows || []);
          setUniverseMeta({
            total: res.data.total || 0,
            pages: res.data.pages || 1,
            facets: res.data.facets || { sectors: [], industries: [] },
            coverage: res.data.coverage || {},
          });
          setUniversePage(res.data.page || page);
          setUniverseError("");
          return true;
        } catch (error) {
          lastError = error;
          if (attempt === 0) {
            await new Promise((resolve) => window.setTimeout(resolve, 900));
          }
        }
      }

      if (requestId === universeRequestRef.current) {
        setUniverseError(lastError?.response?.data?.detail || "The stock-universe screener could not be loaded. Please retry.");
      }
      return false;
    } finally {
      if (requestId === universeRequestRef.current) setUniverseLoading(false);
    }
  };

  const loadSectorAnalysis = async (filterOverride = universeFilters) => {
    setSectorAnalysisLoading(true);
    setSectorAnalysisError("");
    try {
      const params = { market: filterOverride.market || "ALL" };
      if (filterOverride.sector) params.sector = filterOverride.sector;
      const res = await axios.get(`${API}/market/sector-analysis`, { params, timeout: 30000 });
      setSectorAnalysis({
        rows: res.data.rows || [],
        formula: res.data.formula || "",
        aggregation: res.data.aggregation || "",
        data_rule: res.data.data_rule || "",
      });
    } catch (error) {
      setSectorAnalysisError(error?.response?.data?.detail || "Sector analysis could not be loaded.");
    } finally {
      setSectorAnalysisLoading(false);
    }
  };

  const resetUniverseFilters = () => {
    const next = { ...emptyUniverseFilters };
    setUniverseFilters(next);
    setUniversePage(1);
    loadUniverseScreener(1, next, universePageSize);
  };

  const downloadUniverseExcel = async () => {
    try {
      setUniverseError("");
      const params = buildUniverseParams(universePage, false);
      params.columns = universeColumns.join(",");
      const res = await axios.get(`${API}/market/screener-export`, { params, responseType: "blob" });
      const blob = new Blob([res.data], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${(universeFilters.market || "ALL").toUpperCase()}_filtered_stock_screener.xlsx`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    } catch (error) {
      setUniverseError(error?.response?.data?.detail || "Filtered Excel export failed.");
    }
  };

  const refreshUniverseMissingData = async () => {
    setUniverseSyncing(true);
    setUniverseError("");
    try {
      const market = (universeFilters.market || "ALL").toUpperCase();
      const endpoint = market === "ALL"
        ? `${API}/companies/data-backfill/run-all`
        : `${API}/companies/data-backfill/run`;
      const params = market === "ALL" ? { batch_size: 8 } : { market, batch_size: 8 };
      await axios.post(endpoint, null, { params });
      await loadUniverseScreener(universePage);
    } catch (error) {
      setUniverseError(error?.response?.data?.detail || "Missing-data refresh could not be completed right now.");
    } finally {
      setUniverseSyncing(false);
    }
  };

  const openUniverseStock = (row) => {
    if (!row?.symbol || !row?.exchange) return;
    suggestionRequestRef.current += 1;
    setExchange(row.exchange);
    setSymbolInput(row.symbol);
    setSymbol(row.symbol);
    setSelectedCompany({ name: row.name || row.symbol, isin: row.isin || null });
    setData([]);
    setDashboard(null);
    setFundamentals(null);
    setFundamentalHistory(null);
    setTechnicalSummary(null);
    setIndicators(null);
    setOwnershipDetails(null);
    setIndiaShareholding(null);
    setSecEdgar(null);
    setMessage("");
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  useEffect(() => {
    // One guarded load is enough. loadUniverseScreener itself retries once on
    // a transient backend failure. A second unconditional delayed request used
    // to overwrite a successful first response with an error/empty table.
    loadUniverseScreener(1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (universeTab === "Sector Analysis") loadSectorAnalysis(universeFilters);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [universeTab, universeFilters.market, universeFilters.sector]);

  useEffect(() => {
    const handleOutsideClick = (event) => {
      if (
        symbolSearchRef.current &&
        !symbolSearchRef.current.contains(event.target)
      ) {
        setShowSuggestions(false);
      }
    };

    const handleEscape = (event) => {
      if (event.key === "Escape") {
        setShowSuggestions(false);
      }
    };

    document.addEventListener("mousedown", handleOutsideClick);
    document.addEventListener("keydown", handleEscape);

    return () => {
      document.removeEventListener("mousedown", handleOutsideClick);
      document.removeEventListener("keydown", handleEscape);
    };
  }, []);

  const loadCompanyProfile = async () => {
    const requestKey = `${exchange}:${symbol}:${timeframe}`;
    try {
      const res = await axios.get(`${API}/companies/search?q=${encodeURIComponent(symbol)}&exchange=${exchange}&limit=10`);
      if (activeSelectionRef.current !== requestKey) return;
      const exact = (res.data || []).find((item) => String(item.symbol).toUpperCase() === String(symbol).toUpperCase());
      if (exact) {
        setSelectedCompany({ name: exact.name || symbol, isin: exact.isin || null });
      } else if (activeSelectionRef.current === requestKey) {
        // Correctness over stale display: never leave another ticker's identity
        // visible when the current symbol has no exact profile match.
        setSelectedCompany({ name: symbol, isin: null });
      }
    } catch {
      if (activeSelectionRef.current === requestKey) {
        setSelectedCompany({ name: symbol, isin: null });
      }
    }
  };

  const loadDashboard = async () => {
    const requestKey = `${exchange}:${symbol}:${timeframe}`;
    try {
      const params = new URLSearchParams({
        exchange,
        technical_weight: scoreWeights.technical,
        fundamental_weight: scoreWeights.fundamental,
        relative_strength_weight: scoreWeights.relative_strength,
        ownership_weight: scoreWeights.ownership,
        sector_weight: scoreWeights.sector,
        technical_ema20_weight: rankingSubweights.technical.ema20,
        technical_ema50_weight: rankingSubweights.technical.ema50,
        technical_ema150_weight: rankingSubweights.technical.ema150,
        technical_ema200_weight: rankingSubweights.technical.ema200,
        technical_rsi_weight: rankingSubweights.technical.rsi,
        fundamental_eps_weight: rankingSubweights.fundamental.eps,
        fundamental_net_income_weight: rankingSubweights.fundamental.net_income,
        fundamental_profit_margin_weight: rankingSubweights.fundamental.profit_margin,
        fundamental_roe_weight: rankingSubweights.fundamental.roe,
        fundamental_roa_weight: rankingSubweights.fundamental.roa,
        ownership_institution_weight: rankingSubweights.ownership.institution,
        ownership_insider_weight: rankingSubweights.ownership.insider,
        rs_1w_weight: rsWeights["1w"],
        rs_2w_weight: rsWeights["2w"],
        rs_1m_weight: rsWeights["1m"],
        rs_2m_weight: rsWeights["2m"],
        rs_3m_weight: rsWeights["3m"],
        rs_6m_weight: rsWeights["6m"],
        rs_1y_weight: rsWeights["1y"],
        rs_sector_weight: rsWeights["sector"],
      });
      const res = await axios.get(`${API}/market/dashboard/${symbol}?${params.toString()}`);
      if (activeSelectionRef.current !== requestKey) return;
      setDashboard(res.data);
      if (res.data?.name || res.data?.isin) {
        setSelectedCompany({ name: res.data?.name || symbol, isin: res.data?.isin || null });
      }
    } catch {
      if (activeSelectionRef.current !== requestKey) return;
      setDashboard(null);
    }
  };

  const loadTechnicalSummary = async () => {
    const requestKey = `${exchange}:${symbol}:${timeframe}`;
    try {
      const res = await axios.get(
        `${API}/market/technical-summary/${symbol}?exchange=${exchange}&timeframe=${timeframe}` +
        `&rs_1w_weight=${rsWeights["1w"]}&rs_2w_weight=${rsWeights["2w"]}&rs_1m_weight=${rsWeights["1m"]}&rs_2m_weight=${rsWeights["2m"]}` +
        `&rs_3m_weight=${rsWeights["3m"]}&rs_6m_weight=${rsWeights["6m"]}&rs_1y_weight=${rsWeights["1y"]}&rs_sector_weight=${rsWeights["sector"]}`
      );
      if (activeSelectionRef.current !== requestKey) return;
      setTechnicalSummary(res.data);
    } catch {
      if (activeSelectionRef.current !== requestKey) return;
      setTechnicalSummary(null);
    }
  };

  const loadOwnershipDetails = async () => {
    const requestKey = `${exchange}:${symbol}:${timeframe}`;
    if (exchange !== "US") {
      setOwnershipDetails(null);
      return;
    }
    try {
      const res = await axios.get(
        `${API}/market/ownership-details/${symbol}?exchange=${exchange}`
      );
      if (activeSelectionRef.current !== requestKey) return;
      setOwnershipDetails(res.data);
    } catch {
      if (activeSelectionRef.current !== requestKey) return;
      setOwnershipDetails(null);
    }
  };

  const loadIndiaShareholding = async () => {
    const requestKey = `${exchange}:${symbol}:${timeframe}`;
    if (exchange === "US") {
      setIndiaShareholding(null);
      return;
    }
    try {
      const res = await axios.get(
        `${API}/market/india-shareholding/${symbol}?exchange=${exchange}&limit=12`
      );
      if (activeSelectionRef.current !== requestKey) return;
      setIndiaShareholding(res.data);
    } catch {
      if (activeSelectionRef.current !== requestKey) return;
      setIndiaShareholding(null);
    }
  };

  const loadIndicators = async () => {
    const requestKey = `${exchange}:${symbol}:${timeframe}`;
    try {
      const res = await axios.get(
        `${API}/market/indicators/${symbol}?exchange=${exchange}&timeframe=${timeframe}&sma_short=${smaShort}&sma_long=${smaLong}&rsi_period=${rsiPeriod}`
      );

      if (activeSelectionRef.current !== requestKey) return;
      setIndicators(res.data);
    } catch {
      if (activeSelectionRef.current !== requestKey) return;
      setIndicators(null);
    }
  };

  const searchCompanies = async (value) => {
    const normalized = value.toUpperCase();
    setSymbolInput(normalized);
    const requestId = ++suggestionRequestRef.current;

    if (value.trim().length < 2) {
      setSuggestions([]);
      setShowSuggestions(false);
      return;
    }

    try {
      const res = await axios.get(
        `${API}/companies/search?q=${encodeURIComponent(value)}&exchange=${exchange}&limit=10`
      );

      if (requestId !== suggestionRequestRef.current) return;
      setSuggestions(res.data);
      setShowSuggestions(true);
    } catch {
      if (requestId !== suggestionRequestRef.current) return;
      setSuggestions([]);
      setShowSuggestions(false);
    }
  };

  const loadFundamentals = async () => {
    const requestKey = `${exchange}:${symbol}:${timeframe}`;
    try {
      // Refresh from the configured provider. For NSE/BSE this uses the Yahoo
      // statement fallback until the client's Kotak Neo credentials are wired
      // into the live Indian market-data adapter.
      const res = await axios.post(
        `${API}/market/fundamentals/${symbol}?exchange=${exchange}`
      );

      if (activeSelectionRef.current !== requestKey) return;
      if (res.data?.fundamentals?.name || res.data?.fundamentals?.isin) {
        setSelectedCompany({
          name: res.data?.fundamentals?.name || symbol,
          isin: res.data?.fundamentals?.isin || null,
        });
      }
      setFundamentals({
        symbol: res.data.symbol,
        exchange: res.data.exchange,
        fundamentals: {
          market_cap: res.data.fundamentals.market_cap,
          trailing_eps: res.data.fundamentals.trailing_eps,
          forward_eps: res.data.fundamentals.forward_eps,
          revenue: res.data.fundamentals.revenue,
          net_income: res.data.fundamentals.net_income,
          profit_margin: res.data.fundamentals.profit_margin,
          return_on_equity: res.data.fundamentals.return_on_equity,
          return_on_assets: res.data.fundamentals.return_on_assets,
        },
        ownership: {
          insider_percent: res.data.fundamentals.insider_percent,
          institution_percent: res.data.fundamentals.institution_percent,
          shares_outstanding: res.data.fundamentals.shares_outstanding,
          float_shares: res.data.fundamentals.float_shares,
        }
      });
      loadDashboard();
    } catch {
      try {
        const res = await axios.get(
          `${API}/market/fundamentals/${symbol}?exchange=${exchange}`
        );
        if (activeSelectionRef.current !== requestKey) return;
        setFundamentals(res.data);
        if (res.data?.name || res.data?.isin) {
          setSelectedCompany({ name: res.data?.name || symbol, isin: res.data?.isin || null });
        }
        loadDashboard();
      } catch {
        if (activeSelectionRef.current !== requestKey) return;
        setFundamentals(null);
      }
    }
  };

  const loadFundamentalHistory = async () => {
    const requestKey = `${exchange}:${symbol}:${timeframe}`;
    try {
      const res = await axios.get(
        `${API}/market/fundamentals-history/${symbol}?exchange=${exchange}`
      );

      if (activeSelectionRef.current !== requestKey) return;
      setFundamentalHistory(res.data);
    } catch {
      if (activeSelectionRef.current !== requestKey) return;
      setFundamentalHistory(null);
    }
  };

  const loadSecEdgar = async () => {
    const requestKey = `${exchange}:${symbol}:${timeframe}`;
    if (exchange !== "US") {
      setSecEdgar(null);
      setSecEdgarError("");
      return;
    }
    try {
      setSecEdgarError("");
      const res = await axios.get(
        `${API}/market/sec-edgar/${symbol}?exchange=US&filings_limit=12`
      );
      if (activeSelectionRef.current !== requestKey) return;
      setSecEdgar(res.data);
    } catch (error) {
      if (activeSelectionRef.current !== requestKey) return;
      setSecEdgar(null);
      setSecEdgarError(
        error?.response?.data?.detail ||
        "SEC EDGAR is temporarily unavailable. Stored market and fundamental data remain available; no SEC values are substituted."
      );
    }
  };

  const loadChart = async () => {
    const requestKey = `${exchange}:${symbol}:${timeframe}`;
    try {
      setLoading(true);
      if (activeSelectionRef.current === requestKey) {
        setDataStatus("loading");
      }

      const res = await axios.get(
        `${API}/market/chart/${symbol}?exchange=${exchange}&timeframe=${timeframe}&limit=${chartLimitForTimeframe(timeframe)}`
      );

      const rows = (res.data.data || []).filter((row) => (
        Number(row.open) > 0 &&
        Number(row.high) > 0 &&
        Number(row.low) > 0 &&
        Number(row.close) > 0
      ));

      if (activeSelectionRef.current !== requestKey) return;
      setData(rows);

      if (rows.length > 0) {
        setDataStale(false);
        setDataStatus("fresh");
        setMessage("");
      } else {
        setDataStale(true);
        setDataStatus("stale");
        setMessage("No market data is currently available.");
      }

    } catch (err) {
      console.error("Chart load error:", err);

      if (activeSelectionRef.current !== requestKey) return;
      setData([]);
      setDataStale(true);
      setDataStatus("stale");

      setMessage(
        err.response?.data?.detail ||
        "Market data could not be loaded."
      );
    } finally {
      if (activeSelectionRef.current === requestKey) {
        setLoading(false);
      }
    }
  };

  const loadBenchmark = async () => {
    const requestKey = `${exchange}:${symbol}:${timeframe}`;
    try {
      const res = await axios.get(
        `${API}/market/benchmark/${exchange}?limit=1400`
      );

      if (activeSelectionRef.current !== requestKey) return;
      setBenchmark(res.data);
    } catch {
      if (activeSelectionRef.current !== requestKey) return;
      setBenchmark(null);
    }
  };

  const refreshData = async () => {
    setShowSuggestions(false);
    setSuggestions([]);
    suggestionRequestRef.current += 1;

    const requestedSymbol = symbolInput.trim().toUpperCase() || symbol;
    const requestExchange = exchange;
    const selectionChanged = requestedSymbol !== symbol;

    if (selectionChanged) {
      setData([]);
      setDashboard(null);
      setFundamentals(null);
      setFundamentalHistory(null);
      setTechnicalSummary(null);
      setIndicators(null);
      setOwnershipDetails(null);
      setIndiaShareholding(null);
      setSecEdgar(null);
      // Never carry a previous ticker's company identity into a new selection.
      // Until the exact profile/dashboard response arrives, show only the new
      // ticker itself rather than a stale company name or ISIN.
      setSelectedCompany({ name: requestedSymbol, isin: null });
      setSymbol(requestedSymbol);
    }

    setLoading(true);

    try {
      const res = await axios.post(
        `${API}/market/refresh/${requestedSymbol}?exchange=${requestExchange}`
      );

      const usedCachedData = res.data?.status === "cached" || res.data?.provider_refresh_ok === false;
      if (res.data?.company_name || res.data?.isin) {
        setSelectedCompany((current) => ({
          name: res.data?.company_name || current?.name || requestedSymbol,
          isin: res.data?.isin || current?.isin || null,
        }));
      }
      setDataStale(false);
      setDataStatus(usedCachedData ? "cached" : "fresh");
      if (!usedCachedData) setLastUpdated(new Date());

      setMessage(
        usedCachedData
          ? `${res.data?.warning || "Live refresh is temporarily unavailable."} Showing verified stored data${res.data?.latest_date ? ` through ${res.data.latest_date}` : ""}.`
          : `Updated successfully: ${res.data.added} added, ${res.data.updated} updated`
      );

      if (!selectionChanged) {
        await loadChart();
        await loadIndicators();
        await loadFundamentals();
        await loadFundamentalHistory();
        await loadDashboard();
        await loadTechnicalSummary();
        if (exchange !== "US") await loadIndiaShareholding();
        if (exchange === "US") await loadSecEdgar();
      }

    } catch (err) {
      console.error("Refresh error:", err);

      const detail =
        err.response?.data?.detail ??
        "Live refresh is temporarily unavailable.";

      // A provider refresh failure must not discard or label already verified
      // stored candles as stale. Check the chart endpoint before showing an
      // error state; this also covers temporary Railway/provider network errors.
      try {
        const cachedRes = await axios.get(
          `${API}/market/chart/${requestedSymbol}?exchange=${requestExchange}&timeframe=${timeframe}&limit=${chartLimitForTimeframe(timeframe)}`
        );
        const cachedRows = (cachedRes.data?.data || []).filter((row) => (
          Number(row.open) > 0 &&
          Number(row.high) > 0 &&
          Number(row.low) > 0 &&
          Number(row.close) > 0
        ));
        if (cachedRows.length > 0) {
          setData(cachedRows);
          setDataStale(false);
          setDataStatus("cached");
          setMessage(`${detail} Showing verified stored market data instead.`);
        } else {
          setDataStale(true);
          setDataStatus("stale");
          setMessage(detail);
        }
      } catch {
        setDataStale(true);
        setDataStatus("stale");
        setMessage(detail);
      }

    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCompanyProfile();
    loadChart();
    loadIndicators();
    loadBenchmark();
    loadDashboard();
    loadTechnicalSummary();
    loadOwnershipDetails();
    loadIndiaShareholding();

    loadFundamentals();
    loadFundamentalHistory();
    if (exchange === "US") {
      loadSecEdgar();
    } else {
      setSecEdgar(null);
    }
  }, [symbol, timeframe, exchange]);

  useEffect(() => {
    if (!chartContainerRef.current || !data?.length) return;

    chartContainerRef.current.innerHTML = "";

    const chart = createChart(chartContainerRef.current, {
      width: chartContainerRef.current.clientWidth,
      height: 520,
      layout: {
        background: { color: "#ffffff" },
        textColor: "#334155",
      },
      grid: {
        vertLines: { color: "#e2e8f0" },
        horzLines: { color: "#e2e8f0" },
      },
      rightPriceScale: {
        borderColor: "#cbd5e1",
        scaleMargins: { top: 0.05, bottom: 0.28 },
      },
      timeScale: {
        borderColor: "#cbd5e1",
        timeVisible: true,
      },
      localization: {
        dateFormat: "MM/dd/yyyy",
      },
    });

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#16a34a",
      downColor: "#dc2626",
      wickUpColor: "#16a34a",
      wickDownColor: "#dc2626",
      borderVisible: false,
    });

    const candleData = data.map((row) => ({
      time: String(row.date).slice(0, 10),
      open: Number(row.open),
      high: Number(row.high),
      low: Number(row.low),
      close: Number(row.close),
    }));

    candleSeries.setData(candleData);

    const calculateEmaSeries = (rows, period) => {
      if (rows.length < period) return [];
      const multiplier = 2 / (period + 1);
      let ema = rows.slice(0, period).reduce((sum, row) => sum + row.close, 0) / period;
      const result = [{ time: rows[period - 1].time, value: ema }];
      for (let i = period; i < rows.length; i += 1) {
        ema = ((rows[i].close - ema) * multiplier) + ema;
        result.push({ time: rows[i].time, value: ema });
      }
      return result;
    };

    if (chartOverlays.ema) {
      const emaColors = {
        20: "#2563eb",
        30: "#f59e0b",
        50: "#7c3aed",
        100: "#0891b2",
        150: "#db2777",
        200: "#92400e",
      };

      [20, 30, 50, 100, 150, 200].forEach((period) => {
        const values = calculateEmaSeries(candleData, period);
        if (!values.length) return;
        const series = chart.addSeries(LineSeries, {
          color: emaColors[period],
          lineWidth: period <= 50 ? 2 : 1,
          priceLineVisible: false,
          lastValueVisible: false,
          title: `EMA ${period}`,
        });
        series.setData(values);
      });
    }

    const calculateSmaSeries = (rows, period) => {
      const result = [];
      for (let i = period - 1; i < rows.length; i += 1) {
        const window = rows.slice(i - period + 1, i + 1);
        const value = window.reduce((sum, row) => sum + row.close, 0) / period;
        result.push({ time: rows[i].time, value });
      }
      return result;
    };

    if (chartOverlays.sma) {
      [20, 50].forEach((period) => {
        const values = calculateSmaSeries(candleData, period);
        if (!values.length) return;
        const series = chart.addSeries(LineSeries, {
          lineWidth: 1,
          lineStyle: 2,
          priceLineVisible: false,
          lastValueVisible: false,
        });
        series.setData(values);
      });
    }

    // Bollinger Bands: 20-period SMA +/- 2 standard deviations.
    if (chartOverlays.bollinger && candleData.length >= 20) {
      const upper = [];
      const lower = [];
      for (let i = 19; i < candleData.length; i += 1) {
        const window = candleData.slice(i - 19, i + 1).map((row) => row.close);
        const mean = window.reduce((a, b) => a + b, 0) / window.length;
        const variance = window.reduce((sum, value) => sum + ((value - mean) ** 2), 0) / window.length;
        const sd = Math.sqrt(variance);
        upper.push({ time: candleData[i].time, value: mean + (2 * sd) });
        lower.push({ time: candleData[i].time, value: mean - (2 * sd) });
      }
      const bbUpper = chart.addSeries(LineSeries, { lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
      const bbLower = chart.addSeries(LineSeries, { lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
      bbUpper.setData(upper);
      bbLower.setData(lower);
    }

    // Volume plus 50-period average volume in a lower pane-like scale.
    if (chartOverlays.volume) {
      const volumeSeries = chart.addSeries(HistogramSeries, {
        priceScaleId: "volume",
        priceFormat: { type: "volume" },
        priceLineVisible: false,
        lastValueVisible: false,
      });
      volumeSeries.setData(data.map((row) => ({
        time: String(row.date).slice(0, 10),
        value: Number(row.volume || 0),
        color: Number(row.close) >= Number(row.open) ? "#16a34a" : "#dc2626",
      })));
      chart.priceScale("volume").applyOptions({ scaleMargins: { top: 0.78, bottom: 0 } });

      if (data.length >= 50) {
        const avg50 = [];
        for (let i = 49; i < data.length; i += 1) {
          const window = data.slice(i - 49, i + 1);
          avg50.push({
            time: String(data[i].date).slice(0, 10),
            value: window.reduce((sum, row) => sum + Number(row.volume || 0), 0) / 50,
          });
        }
        const volumeAvg = chart.addSeries(LineSeries, {
          priceScaleId: "volume",
          color: "#475569",
          lineWidth: 2,
          priceLineVisible: false,
          lastValueVisible: false,
          title: "Volume 50P Avg",
        });
        volumeAvg.setData(avg50);
      }
    }

    // IBD-style relative-strength line: (stock / broad-market index), visually
    // rebased to the stock's first overlapping close so it can share the price chart.
    if (chartOverlays.rs && benchmark?.data?.length && candleData.length) {
      const benchmarkRows = benchmark.data
        .map((row) => ({ time: String(row.date).slice(0, 10), value: Number(row.close) }))
        .filter((row) => Number.isFinite(row.value));

      const nearestBenchmark = (dateText) => {
        const target = new Date(`${dateText}T00:00:00Z`).getTime();
        let best = null;
        let bestDiff = Infinity;
        for (const row of benchmarkRows) {
          const diff = Math.abs(new Date(`${row.time}T00:00:00Z`).getTime() - target);
          if (diff < bestDiff) {
            bestDiff = diff;
            best = row;
          }
        }
        const maxGap = timeframe === "monthly" ? 35 : timeframe === "weekly" ? 8 : 4;
        return best && bestDiff <= maxGap * 86400000 ? best : null;
      };

      const rsRaw = candleData.map((row) => {
        const bench = nearestBenchmark(row.time);
        if (!bench || !bench.value) return null;
        return { time: row.time, ratio: row.close / bench.value, close: row.close };
      }).filter(Boolean);

      if (rsRaw.length) {
        const firstRatio = rsRaw[0].ratio;
        const firstClose = rsRaw[0].close;
        const rsSeries = chart.addSeries(LineSeries, {
          lineWidth: 2,
          priceLineVisible: false,
          lastValueVisible: false,
        });
        rsSeries.setData(rsRaw.map((row) => ({
          time: row.time,
          value: (row.ratio / firstRatio) * firstClose,
        })));
      }
    }

    // Quarterly EPS points/line on its own scale. Quarter-end dates are snapped
    // to the nearest visible bar so weekend/fiscal dates still render.
    if (chartOverlays.eps && fundamentalHistory?.quarterly?.length && candleData.length) {
      const nearestCandle = (dateText) => {
        const target = new Date(`${String(dateText).slice(0, 10)}T00:00:00Z`).getTime();
        let best = null;
        let bestDiff = Infinity;
        candleData.forEach((row) => {
          const diff = Math.abs(new Date(`${row.time}T00:00:00Z`).getTime() - target);
          if (diff < bestDiff) {
            bestDiff = diff;
            best = row.time;
          }
        });
        return best;
      };

      const epsData = [...fundamentalHistory.quarterly]
        .filter((row) => row.eps != null)
        .map((row) => ({ time: nearestCandle(row.period), value: Number(row.eps) }))
        .filter((row) => row.time && Number.isFinite(row.value))
        .sort((a, b) => a.time.localeCompare(b.time));

      if (epsData.length) {
        const unique = [];
        epsData.forEach((row) => {
          if (unique.length && unique[unique.length - 1].time === row.time) unique[unique.length - 1] = row;
          else unique.push(row);
        });
        const epsSeries = chart.addSeries(LineSeries, {
          priceScaleId: "eps",
          lineWidth: 2,
          pointMarkersVisible: true,
          pointMarkersRadius: 4,
          priceLineVisible: false,
        });
        epsSeries.setData(unique);
        chart.priceScale("eps").applyOptions({ scaleMargins: { top: 0.05, bottom: 0.78 } });
      }
    }

    const latestRow = data[data.length - 1];
    setChartInfo(latestRow ? {
      date: String(latestRow.date).slice(0, 10),
      open: Number(latestRow.open), high: Number(latestRow.high), low: Number(latestRow.low), close: Number(latestRow.close),
    } : null);

    chart.subscribeCrosshairMove((param) => {
      const point = param.seriesData?.get(candleSeries);
      if (point && "open" in point) {
        setChartInfo({
          date: typeof param.time === "string" ? param.time : String(param.time ?? ""),
          open: Number(point.open), high: Number(point.high), low: Number(point.low), close: Number(point.close),
        });
      }
    });

    chart.timeScale().fitContent();

    const handleResize = () => {
      if (chartContainerRef.current) {
        chart.applyOptions({ width: chartContainerRef.current.clientWidth });
      }
    };

    window.addEventListener("resize", handleResize);
    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
    };
  }, [data, benchmark, timeframe, fundamentalHistory, chartOverlays]);

  const latest = !dataStale && data.length
    ? data[data.length - 1]
    : null;
  const currency = exchange === "US" ? "$" : "₹";

  // Final client ranking: calculate the visible score only from the factors in
  // the handwritten sheets. Missing source fields are excluded rather than
  // guessed; Indian fundamental data remains a required category when weighted.
  const dashboardView = (() => {
    if (!dashboard) return null;

    const finite = (value) => {
      if (value === null || value === undefined || value === "") return null;
      const n = Number(value);
      return Number.isFinite(n) ? n : null;
    };
    const isRising3 = (a, b, c) => [a,b,c].every((v) => finite(v) != null) && Number(a) > Number(b) && Number(b) > Number(c);
    const factorScore = (group, rawScores) => {
      let points = 0;
      let weights = 0;
      Object.entries(rawScores).forEach(([key, score]) => {
        const factor = handwrittenFactors[group]?.[key] || {};
        const weight = Number(factor.weight) || 0;
        const enabled = factor.enabled !== false;
        if (!enabled || weight <= 0 || score == null || !Number.isFinite(Number(score))) return;
        points += Number(score) * weight;
        weights += weight;
      });
      return weights > 0 ? Math.max(0, Math.min(100, points / weights)) : null;
    };

    const tech = handwrittenFactors.technical;
    const em = technicalSummary?.ema || {};
    const d52 = finite(technicalSummary?.distance_from_52w_high_percent);
    let distanceScore = null;
    if (d52 != null) {
      const cfg = tech.distance52;
      const rawPoints = d52 <= Number(cfg.t1) ? Number(cfg.p1) : d52 <= Number(cfg.t2) ? Number(cfg.p2) : d52 <= Number(cfg.t3) ? Number(cfg.p3) : Number(cfg.p4);
      distanceScore = Number(cfg.p1) > 0 ? (rawPoints / Number(cfg.p1)) * 100 : 0;
    }
    const rsiValue = finite(technicalSummary?.rsi_14 ?? indicators?.rsi);
    let rsiScore = null;
    if (rsiValue != null) {
      const cfg = tech.rsi14;
      const rawPoints = rsiValue < Number(cfg.t1)
        ? Number(cfg.p1)
        : rsiValue < Number(cfg.t2)
          ? Number(cfg.p2)
          : rsiValue <= Number(cfg.t3)
            ? Number(cfg.p3)
            : Number(cfg.p4);
      const maxPoints = Math.max(Number(cfg.p1) || 0, Number(cfg.p2) || 0, Number(cfg.p3) || 0, Number(cfg.p4) || 0);
      rsiScore = maxPoints > 0 ? (rawPoints / maxPoints) * 100 : 0;
    }
    const technicalComponent = factorScore("technical", {
      bb_width: finite(technicalSummary?.bollinger_width_percent) == null ? null : (compareNumeric(technicalSummary.bollinger_width_percent, tech.bb_width.comparator || "<=", tech.bb_width.threshold) ? 100 : 0),
      atr5_lt20: finite(technicalSummary?.average_atr_percent_5) == null || finite(technicalSummary?.average_atr_percent_20) == null ? null : (Number(technicalSummary.average_atr_percent_5) < Number(technicalSummary.average_atr_percent_20) ? 100 : 0),
      atr10_lt20: finite(technicalSummary?.average_atr_percent_10) == null || finite(technicalSummary?.average_atr_percent_20) == null ? null : (Number(technicalSummary.average_atr_percent_10) < Number(technicalSummary.average_atr_percent_20) ? 100 : 0),
      rsi14: rsiScore,
      volume10_lt20: finite(technicalSummary?.average_volume_10) == null || finite(technicalSummary?.average_volume_20) == null ? null : (Number(technicalSummary.average_volume_10) < Number(technicalSummary.average_volume_20) ? 100 : 0),
      volume20_lt40: finite(technicalSummary?.average_volume_20) == null || finite(technicalSummary?.average_volume_40) == null ? null : (Number(technicalSummary.average_volume_20) < Number(technicalSummary.average_volume_40) ? 100 : 0),
      distance52: distanceScore,
      ema20_gt50: finite(em["20"]) == null || finite(em["50"]) == null ? null : (Number(em["20"]) > Number(em["50"]) ? 100 : 0),
      ema50_gt150: finite(em["50"]) == null || finite(em["150"]) == null ? null : (Number(em["50"]) > Number(em["150"]) ? 100 : 0),
    });

    const q = Array.isArray(fundamentalHistory?.quarterly) ? fundamentalHistory.quarterly : [];
    const a = Array.isArray(fundamentalHistory?.annual) ? fundamentalHistory.annual : [];
    const fcfg = handwrittenFactors.fundamental;
    let qNpmGrowth = null;
    if (q.length >= 5 && finite(q[0]?.npm) != null && finite(q[4]?.npm) != null && Number(q[4].npm) !== 0) {
      qNpmGrowth = ((Number(q[0].npm) - Number(q[4].npm)) / Math.abs(Number(q[4].npm))) * 100;
    }
    const comparable = (field) => q.map((row) => finite(row?.[field])).filter((v) => v != null).slice(0, 3);
    let annualOcfGrowth = null;
    if (a.length >= 2 && finite(a[0]?.operating_cash_flow) != null && finite(a[1]?.operating_cash_flow) != null && Number(a[1].operating_cash_flow) !== 0) {
      annualOcfGrowth = ((Number(a[0].operating_cash_flow) - Number(a[1].operating_cash_flow)) / Math.abs(Number(a[1].operating_cash_flow))) * 100;
    }
    const roeFilterValue = finite(a[0]?.roe) ?? (finite(fundamentals?.fundamentals?.return_on_equity) != null ? Number(fundamentals.fundamentals.return_on_equity) * 100 : null);
    const roceFilterValue = finite(a[0]?.roce);
    const sharesOutstandingFilterValue = finite(fundamentals?.ownership?.shares_outstanding);
    const floatSharesFilterValue = finite(fundamentals?.ownership?.float_shares);
    const latestOcfFilterValue = finite(a[0]?.operating_cash_flow);
    const cashflowPerShareFilterValue = latestOcfFilterValue != null && sharesOutstandingFilterValue != null && sharesOutstandingFilterValue !== 0
      ? latestOcfFilterValue / sharesOutstandingFilterValue
      : null;
    const fundamentalComponent = factorScore("fundamental", {
      q_eps_yoy: finite(q[0]?.yoy_eps) == null ? null : (compareNumeric(q[0]?.yoy_eps, fcfg.q_eps_yoy.comparator || ">", fcfg.q_eps_yoy.threshold) ? 100 : 0),
      q_eps_yoy_rising: comparable("yoy_eps").length < 3 ? null : (isRising3(...comparable("yoy_eps")) ? 100 : 0),
      q_pat_yoy: finite(q[0]?.yoy_pat) == null ? null : (compareNumeric(q[0]?.yoy_pat, fcfg.q_pat_yoy.comparator || ">", fcfg.q_pat_yoy.threshold) ? 100 : 0),
      q_pat_rising: q.length < 3 ? null : (isRising3(q[0]?.pat, q[1]?.pat, q[2]?.pat) ? 100 : 0),
      q_pat_yoy_rising: comparable("yoy_pat").length < 3 ? null : (isRising3(...comparable("yoy_pat")) ? 100 : 0),
      q_npm_yoy: qNpmGrowth == null ? null : (compareNumeric(qNpmGrowth, fcfg.q_npm_yoy.comparator || ">", fcfg.q_npm_yoy.threshold) ? 100 : 0),
      q_sales_yoy: finite(q[0]?.yoy_sales) == null ? null : (compareNumeric(q[0]?.yoy_sales, fcfg.q_sales_yoy.comparator || ">", fcfg.q_sales_yoy.threshold) ? 100 : 0),
      q_sales_rising: q.length < 3 ? null : (isRising3(q[0]?.sales, q[1]?.sales, q[2]?.sales) ? 100 : 0),
      a_eps_yoy: finite(a[0]?.yoy_eps) == null ? null : (compareNumeric(a[0]?.yoy_eps, fcfg.a_eps_yoy.comparator || ">", fcfg.a_eps_yoy.threshold) ? 100 : 0),
      a_eps_rising: a.length < 3 ? null : (isRising3(a[0]?.eps, a[1]?.eps, a[2]?.eps) ? 100 : 0),
      a_pat_yoy: finite(a[0]?.yoy_pat) == null ? null : (compareNumeric(a[0]?.yoy_pat, fcfg.a_pat_yoy.comparator || ">", fcfg.a_pat_yoy.threshold) ? 100 : 0),
      a_pat_rising: a.length < 3 ? null : (isRising3(a[0]?.pat, a[1]?.pat, a[2]?.pat) ? 100 : 0),
      a_sales_yoy: finite(a[0]?.yoy_sales) == null ? null : (compareNumeric(a[0]?.yoy_sales, fcfg.a_sales_yoy.comparator || ">", fcfg.a_sales_yoy.threshold) ? 100 : 0),
      a_sales_rising: a.length < 3 ? null : (isRising3(a[0]?.sales, a[1]?.sales, a[2]?.sales) ? 100 : 0),
      a_ocf_yoy: annualOcfGrowth == null ? null : (compareNumeric(annualOcfGrowth, fcfg.a_ocf_yoy.comparator || ">", fcfg.a_ocf_yoy.threshold) ? 100 : 0),
      a_npm_rising: a.length < 2 || finite(a[0]?.npm) == null || finite(a[1]?.npm) == null ? null : (Number(a[0].npm) > Number(a[1].npm) ? 100 : 0),
      roe_above: roeFilterValue == null ? null : (compareNumeric(roeFilterValue, fcfg.roe_above.comparator || ">", fcfg.roe_above.threshold) ? 100 : 0),
      roce_above: roceFilterValue == null ? null : (compareNumeric(roceFilterValue, fcfg.roce_above.comparator || ">", fcfg.roce_above.threshold) ? 100 : 0),
      cashflow_per_share: fcfg.cashflow_per_share?.enabled === false || cashflowPerShareFilterValue == null ? null : (compareNumeric(cashflowPerShareFilterValue, fcfg.cashflow_per_share.comparator || ">", fcfg.cashflow_per_share.threshold) ? 100 : 0),
      shares_outstanding: fcfg.shares_outstanding?.enabled === false || sharesOutstandingFilterValue == null ? null : (compareNumeric(sharesOutstandingFilterValue, fcfg.shares_outstanding.comparator || "<", fcfg.shares_outstanding.threshold) ? 100 : 0),
      float_shares: fcfg.float_shares?.enabled === false || floatSharesFilterValue == null ? null : (compareNumeric(floatSharesFilterValue, fcfg.float_shares.comparator || "<", fcfg.float_shares.threshold) ? 100 : 0),
    });

    let ownershipComponent = null;
    if (exchange !== "US" && Array.isArray(indiaShareholding?.history) && indiaShareholding.history.length) {
      const h = indiaShareholding.history;
      const latestH = h[0] || {};
      const priorQuarterH = h[1] || {};
      const secondPriorQuarterH = h[2] || {};
      const previousYearH = h[4] || {};
      const ocfg = handwrittenFactors.ownership;
      const diiMf = (row) => {
        const values = [finite(row?.dii), finite(row?.mutual_funds)].filter((v) => v != null);
        return values.length ? values.reduce((x, y) => x + y, 0) : null;
      };
      const priorDiiMf = diiMf(priorQuarterH);
      const secondPriorDiiMf = diiMf(secondPriorQuarterH);
      const latestDiiMfChange = [finite(latestH.dii_change), finite(latestH.mutual_funds_change)].filter((v) => v != null);
      const changeSum = latestDiiMfChange.length ? latestDiiMfChange.reduce((x, y) => x + y, 0) : null;
      ownershipComponent = factorScore("ownership", {
        promoter_qoq: finite(latestH.promoter_change) == null ? null : (compareNumeric(latestH.promoter_change, ocfg.promoter_qoq.comparator || ">", ocfg.promoter_qoq.threshold) ? 100 : 0),
        promoter_above: finite(latestH.promoter) == null ? null : (compareNumeric(latestH.promoter, ocfg.promoter_above.comparator || ">", ocfg.promoter_above.threshold) ? 100 : 0),
        promoter_rising: finite(latestH.promoter) == null || finite(previousYearH.promoter) == null ? null : (Number(latestH.promoter) > Number(previousYearH.promoter) ? 100 : 0),
        pledge: null,
        fii_qoq: finite(latestH.fii_change) == null ? null : (compareNumeric(latestH.fii_change, ocfg.fii_qoq.comparator || ">", ocfg.fii_qoq.threshold) ? 100 : 0),
        fii_rising:
          finite(latestH.fii) == null || finite(previousYearH.fii) == null ||
          finite(priorQuarterH.fii) == null || finite(secondPriorQuarterH.fii) == null
            ? null
            : (Number(latestH.fii) > Number(previousYearH.fii) && Number(priorQuarterH.fii) > Number(secondPriorQuarterH.fii) ? 100 : 0),
        dii_mf_qoq: changeSum == null ? null : (compareNumeric(changeSum, ocfg.dii_mf_qoq.comparator || ">", ocfg.dii_mf_qoq.threshold) ? 100 : 0),
        dii_mf_rising: priorDiiMf == null || secondPriorDiiMf == null ? null : (priorDiiMf > secondPriorDiiMf ? 100 : 0),
        insider_activity: null,
      });
    } else if (exchange === "US") {
      // US ownership uses the market-appropriate Institutional + Insider
      // aggregate score calculated by the backend. Retail/Public is displayed
      // as the transparent remainder when both aggregates are available.
      ownershipComponent = finite(dashboard?.score_components?.ownership);
    }

    const components = {
      technical: technicalComponent,
      fundamental: fundamentalComponent,
      relative_strength: technicalSummary?.rs_available === false ? null : finite(technicalSummary?.rs_rating),
      ownership: ownershipComponent,
      sector: finite(dashboard?.score_components?.sector),
    };
    const enteredTotal = Object.values(scoreWeights).reduce((sum, value) => sum + Math.max(0, Number(value) || 0), 0);
    const normalizedWeights = Object.fromEntries(Object.entries(scoreWeights).map(([key,value]) => [key, enteredTotal > 0 ? Math.max(0, Number(value) || 0) / enteredTotal * 100 : 0]));
    let points = 0;
    let availableWeight = 0;
    Object.entries(normalizedWeights).forEach(([key, weight]) => {
      const value = components[key];
      if (weight <= 0 || value == null || !Number.isFinite(Number(value))) return;
      points += Number(value) * weight;
      availableWeight += weight;
    });
    const missingIndianFundamental = exchange !== "US" && normalizedWeights.fundamental > 0 && fundamentalComponent == null;
    const missingIndianOwnership = exchange !== "US" && normalizedWeights.ownership > 0 && ownershipComponent == null;
    const score = missingIndianFundamental || missingIndianOwnership || availableWeight <= 0
      ? null
      : Math.max(0, Math.min(100, Math.round(points / availableWeight)));
    const signal = score == null ? "Insufficient Data" : score >= 70 ? "Buy" : score >= 45 ? "Watch" : "Sell";
    return {
      ...dashboard,
      score, signal,
      score_coverage_percent: Math.round(availableWeight),
      score_components: components,
      score_weights: normalizedWeights,
      handwritten_ranking: true,
    };
  })();

  const factorEvaluationRows = (() => {
    const finite = (value) => {
      if (value === null || value === undefined || value === "") return null;
      const n = Number(value);
      return Number.isFinite(n) ? n : null;
    };
    const trend3 = (x, y, z) => [x, y, z].every((v) => finite(v) != null) ? (Number(x) > Number(y) && Number(y) > Number(z)) : null;
    const passScore = (value, factor) => {
      const result = compareNumeric(value, factor?.comparator || ">", factor?.threshold);
      return result == null ? null : (result ? 100 : 0);
    };
    const resultRow = (currentValue, score, targetText = null) => ({ currentValue, score, targetText });

    const tech = handwrittenFactors.technical;
    const em = technicalSummary?.ema || {};
    const d52 = finite(technicalSummary?.distance_from_52w_high_percent);
    const rsiValue = finite(technicalSummary?.rsi_14 ?? indicators?.rsi);
    let distanceScore = null;
    if (d52 != null) {
      const cfg = tech.distance52;
      const rawPoints = d52 <= Number(cfg.t1) ? Number(cfg.p1) : d52 <= Number(cfg.t2) ? Number(cfg.p2) : d52 <= Number(cfg.t3) ? Number(cfg.p3) : Number(cfg.p4);
      const maxPoints = Math.max(Number(cfg.p1) || 0, Number(cfg.p2) || 0, Number(cfg.p3) || 0, Number(cfg.p4) || 0);
      distanceScore = maxPoints > 0 ? (rawPoints / maxPoints) * 100 : null;
    }
    let rsiScore = null;
    if (rsiValue != null) {
      const cfg = tech.rsi14;
      const rawPoints = rsiValue < Number(cfg.t1) ? Number(cfg.p1) : rsiValue < Number(cfg.t2) ? Number(cfg.p2) : rsiValue <= Number(cfg.t3) ? Number(cfg.p3) : Number(cfg.p4);
      const maxPoints = Math.max(Number(cfg.p1) || 0, Number(cfg.p2) || 0, Number(cfg.p3) || 0, Number(cfg.p4) || 0);
      rsiScore = maxPoints > 0 ? (rawPoints / maxPoints) * 100 : null;
    }
    const technical = {
      bb_width: resultRow(finite(technicalSummary?.bollinger_width_percent), passScore(technicalSummary?.bollinger_width_percent, tech.bb_width)),
      atr5_lt20: resultRow(finite(technicalSummary?.average_atr_percent_5), finite(technicalSummary?.average_atr_percent_5) == null || finite(technicalSummary?.average_atr_percent_20) == null ? null : (Number(technicalSummary.average_atr_percent_5) < Number(technicalSummary.average_atr_percent_20) ? 100 : 0), finite(technicalSummary?.average_atr_percent_20)),
      atr10_lt20: resultRow(finite(technicalSummary?.average_atr_percent_10), finite(technicalSummary?.average_atr_percent_10) == null || finite(technicalSummary?.average_atr_percent_20) == null ? null : (Number(technicalSummary.average_atr_percent_10) < Number(technicalSummary.average_atr_percent_20) ? 100 : 0), finite(technicalSummary?.average_atr_percent_20)),
      rsi14: resultRow(rsiValue, rsiScore, "Bands"),
      volume10_lt20: resultRow(finite(technicalSummary?.average_volume_10), finite(technicalSummary?.average_volume_10) == null || finite(technicalSummary?.average_volume_20) == null ? null : (Number(technicalSummary.average_volume_10) < Number(technicalSummary.average_volume_20) ? 100 : 0), finite(technicalSummary?.average_volume_20)),
      volume20_lt40: resultRow(finite(technicalSummary?.average_volume_20), finite(technicalSummary?.average_volume_20) == null || finite(technicalSummary?.average_volume_40) == null ? null : (Number(technicalSummary.average_volume_20) < Number(technicalSummary.average_volume_40) ? 100 : 0), finite(technicalSummary?.average_volume_40)),
      distance52: resultRow(d52, distanceScore, "Bands"),
      ema20_gt50: resultRow(finite(em["20"]), finite(em["20"]) == null || finite(em["50"]) == null ? null : (Number(em["20"]) > Number(em["50"]) ? 100 : 0), finite(em["50"])),
      ema50_gt150: resultRow(finite(em["50"]), finite(em["50"]) == null || finite(em["150"]) == null ? null : (Number(em["50"]) > Number(em["150"]) ? 100 : 0), finite(em["150"])),
    };

    const q = Array.isArray(fundamentalHistory?.quarterly) ? fundamentalHistory.quarterly : [];
    const a = Array.isArray(fundamentalHistory?.annual) ? fundamentalHistory.annual : [];
    const fcfg = handwrittenFactors.fundamental;
    const comparable = (field) => q.map((row) => finite(row?.[field])).filter((v) => v != null).slice(0, 3);
    let qNpmGrowth = null;
    if (q.length >= 5 && finite(q[0]?.npm) != null && finite(q[4]?.npm) != null && Number(q[4].npm) !== 0) {
      qNpmGrowth = ((Number(q[0].npm) - Number(q[4].npm)) / Math.abs(Number(q[4].npm))) * 100;
    }
    let annualOcfGrowth = null;
    if (a.length >= 2 && finite(a[0]?.operating_cash_flow) != null && finite(a[1]?.operating_cash_flow) != null && Number(a[1].operating_cash_flow) !== 0) {
      annualOcfGrowth = ((Number(a[0].operating_cash_flow) - Number(a[1].operating_cash_flow)) / Math.abs(Number(a[1].operating_cash_flow))) * 100;
    }
    const roeValue = finite(a[0]?.roe) ?? (finite(fundamentals?.fundamentals?.return_on_equity) != null ? Number(fundamentals.fundamentals.return_on_equity) * 100 : null);
    const roceValue = finite(a[0]?.roce);
    const sharesOutstanding = finite(fundamentals?.ownership?.shares_outstanding);
    const floatShares = finite(fundamentals?.ownership?.float_shares);
    const latestOcf = finite(a[0]?.operating_cash_flow);
    const cashflowPerShare = latestOcf != null && sharesOutstanding != null && sharesOutstanding !== 0 ? latestOcf / sharesOutstanding : null;

    const fundamental = {
      q_eps_yoy: resultRow(finite(q[0]?.yoy_eps), passScore(q[0]?.yoy_eps, fcfg.q_eps_yoy)),
      q_eps_yoy_rising: resultRow(finite(q[0]?.yoy_eps), comparable("yoy_eps").length < 3 ? null : (trend3(...comparable("yoy_eps")) ? 100 : 0), "Prior 2 YoY values"),
      a_eps_yoy: resultRow(finite(a[0]?.yoy_eps), passScore(a[0]?.yoy_eps, fcfg.a_eps_yoy)),
      a_eps_rising: resultRow(finite(a[0]?.eps), a.length < 3 ? null : (trend3(a[0]?.eps, a[1]?.eps, a[2]?.eps) ? 100 : 0), "Prior 2 years"),
      q_pat_yoy: resultRow(finite(q[0]?.yoy_pat), passScore(q[0]?.yoy_pat, fcfg.q_pat_yoy)),
      q_pat_rising: resultRow(finite(q[0]?.pat), q.length < 3 ? null : (trend3(q[0]?.pat, q[1]?.pat, q[2]?.pat) ? 100 : 0), "Prior 2 quarters"),
      q_pat_yoy_rising: resultRow(finite(q[0]?.yoy_pat), comparable("yoy_pat").length < 3 ? null : (trend3(...comparable("yoy_pat")) ? 100 : 0), "Prior 2 YoY values"),
      a_pat_yoy: resultRow(finite(a[0]?.yoy_pat), passScore(a[0]?.yoy_pat, fcfg.a_pat_yoy)),
      a_pat_rising: resultRow(finite(a[0]?.pat), a.length < 3 ? null : (trend3(a[0]?.pat, a[1]?.pat, a[2]?.pat) ? 100 : 0), "Prior 2 years"),
      q_sales_yoy: resultRow(finite(q[0]?.yoy_sales), passScore(q[0]?.yoy_sales, fcfg.q_sales_yoy)),
      q_sales_rising: resultRow(finite(q[0]?.sales), q.length < 3 ? null : (trend3(q[0]?.sales, q[1]?.sales, q[2]?.sales) ? 100 : 0), "Prior 2 quarters"),
      a_sales_yoy: resultRow(finite(a[0]?.yoy_sales), passScore(a[0]?.yoy_sales, fcfg.a_sales_yoy)),
      a_sales_rising: resultRow(finite(a[0]?.sales), a.length < 3 ? null : (trend3(a[0]?.sales, a[1]?.sales, a[2]?.sales) ? 100 : 0), "Prior 2 years"),
      q_npm_yoy: resultRow(qNpmGrowth, passScore(qNpmGrowth, fcfg.q_npm_yoy)),
      a_npm_rising: resultRow(finite(a[0]?.npm), a.length < 2 || finite(a[0]?.npm) == null || finite(a[1]?.npm) == null ? null : (Number(a[0].npm) > Number(a[1].npm) ? 100 : 0), finite(a[1]?.npm)),
      a_ocf_yoy: resultRow(annualOcfGrowth, passScore(annualOcfGrowth, fcfg.a_ocf_yoy)),
      cashflow_per_share: resultRow(cashflowPerShare, fcfg.cashflow_per_share?.enabled === false ? null : passScore(cashflowPerShare, fcfg.cashflow_per_share)),
      roe_above: resultRow(roeValue, passScore(roeValue, fcfg.roe_above)),
      roce_above: resultRow(roceValue, passScore(roceValue, fcfg.roce_above)),
      shares_outstanding: resultRow(sharesOutstanding, fcfg.shares_outstanding?.enabled === false ? null : passScore(sharesOutstanding, fcfg.shares_outstanding)),
      float_shares: resultRow(floatShares, fcfg.float_shares?.enabled === false ? null : passScore(floatShares, fcfg.float_shares)),
    };

    const ownership = {};
    if (exchange !== "US" && Array.isArray(indiaShareholding?.history) && indiaShareholding.history.length) {
      const h = indiaShareholding.history;
      const latestH = h[0] || {};
      const priorH = h[1] || {};
      const secondPriorH = h[2] || {};
      const previousYearH = h[4] || {};
      const ocfg = handwrittenFactors.ownership;
      const diiMf = (row) => {
        const values = [finite(row?.dii), finite(row?.mutual_funds)].filter((v) => v != null);
        return values.length ? values.reduce((sum, v) => sum + v, 0) : null;
      };
      const latestDiiMfChangeVals = [finite(latestH.dii_change), finite(latestH.mutual_funds_change)].filter((v) => v != null);
      const latestDiiMfChange = latestDiiMfChangeVals.length ? latestDiiMfChangeVals.reduce((sum, v) => sum + v, 0) : null;
      const priorDiiMf = diiMf(priorH);
      const secondPriorDiiMf = diiMf(secondPriorH);
      ownership.promoter_qoq = resultRow(finite(latestH.promoter_change), passScore(latestH.promoter_change, ocfg.promoter_qoq));
      ownership.promoter_above = resultRow(finite(latestH.promoter), passScore(latestH.promoter, ocfg.promoter_above));
      ownership.promoter_rising = resultRow(finite(latestH.promoter), finite(latestH.promoter) == null || finite(previousYearH.promoter) == null ? null : (Number(latestH.promoter) > Number(previousYearH.promoter) ? 100 : 0), finite(previousYearH.promoter));
      ownership.pledge = resultRow(null, null, "Bands");
      ownership.fii_qoq = resultRow(finite(latestH.fii_change), passScore(latestH.fii_change, ocfg.fii_qoq));
      ownership.fii_rising = resultRow(finite(latestH.fii), finite(latestH.fii) == null || finite(previousYearH.fii) == null || finite(priorH.fii) == null || finite(secondPriorH.fii) == null ? null : (Number(latestH.fii) > Number(previousYearH.fii) && Number(priorH.fii) > Number(secondPriorH.fii) ? 100 : 0), "Year + quarter trend");
      ownership.dii_mf_qoq = resultRow(latestDiiMfChange, passScore(latestDiiMfChange, ocfg.dii_mf_qoq));
      ownership.dii_mf_rising = resultRow(priorDiiMf, priorDiiMf == null || secondPriorDiiMf == null ? null : (priorDiiMf > secondPriorDiiMf ? 100 : 0), secondPriorDiiMf);
      ownership.insider_activity = resultRow(null, null, "Requires provider event history");
    }

    const scoreGroup = (group, rows) => {
      let weighted = 0;
      let weights = 0;
      Object.entries(rows).forEach(([key, row]) => {
        const cfg = handwrittenFactors[group]?.[key];
        const weight = Number(cfg?.weight) || 0;
        if (cfg?.enabled === false || weight <= 0 || row?.score == null || !Number.isFinite(Number(row.score))) return;
        weighted += Number(row.score) * weight;
        weights += weight;
      });
      return weights > 0 ? weighted / weights : null;
    };

    const fundamentalGroups = {};
    for (const [, , , , category = "Other"] of handwrittenFactorMeta.fundamental) {
      if (!(category in fundamentalGroups)) fundamentalGroups[category] = { weighted: 0, weight: 0 };
    }
    for (const [key, , , , category = "Other"] of handwrittenFactorMeta.fundamental) {
      const row = fundamental[key];
      const cfg = handwrittenFactors.fundamental[key];
      const weight = Number(cfg?.weight) || 0;
      if (cfg?.enabled === false || weight <= 0 || row?.score == null || !Number.isFinite(Number(row.score))) continue;
      fundamentalGroups[category].weighted += Number(row.score) * weight;
      fundamentalGroups[category].weight += weight;
    }
    const groupedFundamentalScores = Object.fromEntries(Object.entries(fundamentalGroups).map(([name, value]) => [name, value.weight > 0 ? value.weighted / value.weight : null]));

    return {
      technical,
      fundamental,
      ownership,
      groupScores: {
        technical: scoreGroup("technical", technical),
        fundamental: scoreGroup("fundamental", fundamental),
        ownership: scoreGroup("ownership", ownership),
      },
      fundamentalGroupScores: groupedFundamentalScores,
    };
  })();

  const selectedFundamentalQualification = (() => {
    const rows = factorEvaluationRows.fundamental || {};
    let considered = 0;
    let passed = 0;
    let missing = 0;
    Object.entries(rows).forEach(([key, row]) => {
      const cfg = handwrittenFactors.fundamental[key];
      if (!cfg || cfg.enabled === false || (Number(cfg.weight) || 0) <= 0) return;
      considered += 1;
      if (row.score == null) missing += 1;
      else if (Number(row.score) > 0) passed += 1;
    });
    return {
      considered,
      passed,
      missing,
      status: considered === 0 ? "No active filters" : missing > 0 ? "Insufficient Data" : passed === considered ? "Qualified" : "Not Qualified",
    };
  })();

  const excelLiveCsvUrl = `${window.location.origin}${API}/market/excel-live-csv/${symbol}?exchange=${exchange}&limit=1500`;

  const copyExcelFeedUrl = async () => {
    try {
      await navigator.clipboard.writeText(excelLiveCsvUrl);
      setExcelCopyMessage("Live Excel data URL copied");
    } catch {
      setExcelCopyMessage(excelLiveCsvUrl);
    }
    window.setTimeout(() => setExcelCopyMessage(""), 3500);
  };

  const downloadExcelLiveConnector = () => {
    const requestedSymbol = String(symbol || "").trim().toUpperCase();
    if (!requestedSymbol) {
      setExcelCopyMessage("Enter a stock symbol before creating the live Excel connection.");
      window.setTimeout(() => setExcelCopyMessage(""), 4000);
      return;
    }

    // Excel Internet Query (.iqy): open it once in desktop Excel and save the
    // workbook. The external web connection is retained, so Data -> Refresh All
    // re-requests the current screener data instead of downloading a new file.
    const queryUrl = `${window.location.origin}${API}/market/excel-live-csv/${encodeURIComponent(requestedSymbol)}?exchange=${encodeURIComponent(exchange)}&limit=1500`;
    const iqy = [
      "WEB",
      "1",
      queryUrl,
      "",
      "Selection=EntirePage",
      "Formatting=None",
      "PreFormattedTextToColumns=True",
      "ConsecutiveDelimitersAsOne=False",
      "SingleBlockTextImport=False",
      "DisableDateRecognition=False",
      "DisableRedirections=False",
      "",
    ].join("\r\n");

    const blob = new Blob([iqy], { type: "text/x-ms-iqy;charset=utf-8" });
    const objectUrl = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = objectUrl;
    link.download = `${requestedSymbol}_${exchange}_LIVE_5Y.iqy`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(objectUrl);
    setExcelCopyMessage("Live Excel connector created. Open it in Excel, then save the workbook and use Refresh All.");
    window.setTimeout(() => setExcelCopyMessage(""), 6000);
  };

  const downloadExcelSnapshot = async () => {
    const requestedSymbol = String(symbol || "").trim().toUpperCase();
    if (!requestedSymbol) {
      setExcelCopyMessage("Enter a stock symbol before downloading Excel.");
      window.setTimeout(() => setExcelCopyMessage(""), 3500);
      return;
    }

    const url = `${API}/market/excel-export/${encodeURIComponent(requestedSymbol)}?exchange=${encodeURIComponent(exchange)}`;
    try {
      setExcelCopyMessage("Preparing Excel file…");
      const response = await fetch(url, {
        method: "GET",
        headers: { Accept: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" },
        cache: "no-store",
      });
      if (!response.ok) {
        let detail = `Excel export failed (HTTP ${response.status})`;
        try {
          const payload = await response.json();
          if (payload?.detail) detail = String(payload.detail);
        } catch {
          // Keep the HTTP status fallback if the proxy returned a non-JSON error.
        }
        throw new Error(detail);
      }

      const blob = await response.blob();
      if (!blob.size) throw new Error("Excel export returned an empty file.");

      const disposition = response.headers.get("content-disposition") || "";
      const match = disposition.match(/filename\*?=(?:UTF-8''|")?([^";]+)/i);
      const filename = match?.[1] ? decodeURIComponent(match[1].replace(/"/g, "")) : `${requestedSymbol}_${exchange}_screener.xlsx`;
      const objectUrl = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = objectUrl;
      link.download = filename;
      link.style.display = "none";
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
      setExcelCopyMessage(`Downloaded ${filename}`);
    } catch (error) {
      setExcelCopyMessage(error?.message || "Excel export failed. Please try again.");
    }
    window.setTimeout(() => setExcelCopyMessage(""), 4500);
  };

  const relativeStrengthChartData = (() => {
    const rows = technicalSummary?.rs_chart;
    if (!Array.isArray(rows)) return [];
    return rows
      .map((row) => ({
        date: String(row.date).slice(0, 10),
        rs: Number(row.rs),
      }))
      .filter((row) => Number.isFinite(row.rs) && row.rs > 0);
  })();

  const changeExchange = (value) => {
    setShowSuggestions(false);
    setSuggestions([]);
    setExchange(value);
    setData([]);
    setMessage("");
    setIndicators(null);
    setFundamentals(null);
    setFundamentalHistory(null);
    setDashboard(null);
    setTechnicalSummary(null);
    setOwnershipDetails(null);
    setIndiaShareholding(null);
    setSecEdgar(null);
    setSecEdgarError("");

    if (value === "US") {
      setSelectedCompany({ name: "AAPL", isin: null });
      setSymbol("AAPL");
      setSymbolInput("AAPL");
    } else if (value === "NSE") {
      setSelectedCompany({ name: "RELIANCE", isin: null });
      setSymbol("RELIANCE");
      setSymbolInput("RELIANCE");
    } else {
      setSelectedCompany({ name: "INFY", isin: null });
      setSymbol("INFY");
      setSymbolInput("INFY");
    }
  };

  const updateHandwrittenFactor = (group, key, field, value) => {
    setHandwrittenFactors((prev) => ({
      ...prev,
      [group]: {
        ...prev[group],
        [key]: { ...prev[group][key], [field]: value },
      },
    }));
  };

  const formatFilterCurrent = (key, value) => {
    if (value === null || value === undefined || !Number.isFinite(Number(value))) return "N/A";
    const n = Number(value);
    if (["shares_outstanding", "float_shares", "volume10_lt20", "volume20_lt40", "ema20_gt50", "ema50_gt150"].includes(key) && Math.abs(n) >= 1000000) {
      return new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 2 }).format(n);
    }
    if (Math.abs(n) >= 1000000) return new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 2 }).format(n);
    return Number(n.toFixed(2)).toLocaleString();
  };

  const renderUSOwnershipTable = () => {
    const institution = fundamentals?.ownership?.institution_percent != null ? Number(fundamentals.ownership.institution_percent) * 100 : null;
    const insider = fundamentals?.ownership?.insider_percent != null ? Number(fundamentals.ownership.insider_percent) * 100 : null;
    const retail = institution != null && insider != null ? Math.max(0, 100 - institution - insider) : null;
    const rows = [
      ["Institutional Ownership", institution, rankingSubweights.ownership.institution, "Provider aggregate"],
      ["Insider Ownership", insider, rankingSubweights.ownership.insider, "Provider aggregate"],
      ["Retail / Public Investors", retail, 0, "100% - institutional - insider"],
    ];
    return (
      <div className="compact-filter-card">
        <div className="compact-filter-header">
          <div><h3>Ownership Filters (US)</h3><p>US-market ownership categories. Missing provider values remain N/A.</p></div>
          <div className="compact-filter-score"><span>Group score</span><strong>{filterScoreText(dashboardView?.score_components?.ownership)}</strong></div>
        </div>
        <div className="compact-table-scroll">
          <table className="filter-config-table">
            <thead><tr><th>Ownership type</th><th>Current</th><th>Weight</th><th>Source / method</th></tr></thead>
            <tbody>
              {rows.map(([label, value, weight, source]) => (
                <tr key={label}>
                  <td className="filter-name-cell"><strong>{label}</strong></td>
                  <td>{value != null && Number.isFinite(Number(value)) ? `${Number(value).toFixed(2)}%` : "N/A"}</td>
                  <td>{weight}%</td>
                  <td><span className="filter-target-text">{source}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  };

  const renderFilterTable = (group, title, subtitle) => {
    const periodWord = timeframe === "weekly" ? "week" : timeframe === "monthly" ? "month" : "day";
    const rows = (handwrittenFactorMeta[group] || []).map((row) => {
      if (group !== "technical") return row;
      const [key, label, description, editableValues, category] = row;
      const timeframeLabel = label
        .replace(/5-day/g, `5-${periodWord}`)
        .replace(/10-day/g, `10-${periodWord}`)
        .replace(/20-day/g, `20-${periodWord}`)
        .replace(/40-day/g, `40-${periodWord}`);
      return [key, timeframeLabel, description, editableValues, category];
    });
    const evalRows = factorEvaluationRows[group] || {};
    return (
      <div className="compact-filter-card" key={group}>
        <div className="compact-filter-header">
          <div>
            <h3>{title}</h3>
            <p>{subtitle}</p>
          </div>
          <div className="compact-filter-score">
            <span>Group score</span>
            <strong>{filterScoreText(factorEvaluationRows.groupScores?.[group])}</strong>
          </div>
        </div>
        <div className="compact-table-scroll">
          <table className="filter-config-table">
            <thead>
              <tr>
                {group === "fundamental" && <th>Group</th>}
                <th>Filter name</th>
                <th>Compare</th>
                <th>Value / target</th>
                <th>Current</th>
                <th>Weight</th>
                <th>Filter score</th>
                <th>Use</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(([key, label, description, editableValues, category]) => {
                const cfg = handwrittenFactors[group][key] || {};
                const evalRow = evalRows[key] || {};
                const enabled = cfg.enabled !== false;
                const hasThreshold = editableValues.includes("threshold");
                const bandFields = editableValues.filter((field) => field !== "threshold");
                const score = evalRow.score;
                return (
                  <tr key={key} className={!enabled ? "filter-row-disabled" : ""}>
                    {group === "fundamental" && <td><span className="factor-group-pill">{category || "Other"}</span></td>}
                    <td className="filter-name-cell">
                      <strong>{label}</strong>
                      <small>{description}</small>
                    </td>
                    <td>
                      {hasThreshold ? (
                        <select
                          className="filter-compare-select"
                          value={cfg.comparator || ">"}
                          onChange={(e) => updateHandwrittenFactor(group, key, "comparator", e.target.value)}
                        >
                          <option value=">">&gt;</option>
                          <option value=">=">&gt;=</option>
                          <option value="<">&lt;</option>
                          <option value="<=">&lt;=</option>
                        </select>
                      ) : (
                        <span className="fixed-compare">{cfg.comparator || (evalRow.targetText ? "vs" : "—")}</span>
                      )}
                    </td>
                    <td>
                      {hasThreshold ? (
                        <input
                          className="filter-value-input"
                          type="number"
                          step="0.1"
                          value={cfg.threshold ?? 0}
                          onChange={(e) => updateHandwrittenFactor(group, key, "threshold", Number(e.target.value))}
                        />
                      ) : bandFields.length ? (
                        <div className="filter-band-values">
                          {bandFields.map((field) => (
                            <label key={field}>
                              <span>{field.toUpperCase()}</span>
                              <input
                                type="number"
                                step="0.1"
                                value={cfg[field] ?? 0}
                                onChange={(e) => updateHandwrittenFactor(group, key, field, Number(e.target.value))}
                              />
                            </label>
                          ))}
                        </div>
                      ) : (
                        <span className="filter-target-text">{evalRow.targetText != null ? (typeof evalRow.targetText === "number" ? formatFilterCurrent(key, evalRow.targetText) : String(evalRow.targetText)) : "Dynamic"}</span>
                      )}
                    </td>
                    <td className="filter-current-cell">{formatFilterCurrent(key, evalRow.currentValue)}</td>
                    <td>
                      <input
                        className="filter-weight-input"
                        type="number"
                        min="0"
                        step="1"
                        value={cfg.weight ?? 0}
                        onChange={(e) => updateHandwrittenFactor(group, key, "weight", Math.max(0, Number(e.target.value) || 0))}
                      />
                    </td>
                    <td>
                      <span className={`filter-score-badge ${score == null ? "is-na" : Number(score) > 0 ? "is-pass" : "is-fail"}`}>
                        {filterScoreText(score)}
                      </span>
                    </td>
                    <td>
                      <label className="compact-enable-toggle">
                        <input
                          type="checkbox"
                          checked={enabled}
                          onChange={(e) => updateHandwrittenFactor(group, key, "enabled", e.target.checked)}
                        />
                        <span>{enabled ? "On" : "Off"}</span>
                      </label>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {group === "fundamental" && (
          <div className="fundamental-score-strip">
            {Object.entries(factorEvaluationRows.fundamentalGroupScores || {}).map(([name, score]) => (
              <div key={name}><span>{name} score</span><strong>{filterScoreText(score)}</strong></div>
            ))}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="app">
      <header>
        <div>
          <h1>Stock Screener</h1>
          <p>US & Indian Market Dashboard</p>
        </div>

        <div className={`status ${dataStatus}`}>
          <span className="dot"></span>

          <div>
            <strong>
              {dataStatus === "fresh"
                ? "Data Fresh"
                : dataStatus === "cached"
                ? "Stored Data"
                : dataStatus === "stale"
                ? "Data Stale"
                : dataStatus === "loading"
                ? "Loading Data"
                : "Data Connected"}
            </strong>

            {lastUpdated && (
              <small>
                Last updated: {lastUpdated.toLocaleTimeString()}
              </small>
            )}
          </div>
        </div>
      </header>

      <main>
        <section className="controls">
          <select
            value={exchange}
            onChange={(e) => changeExchange(e.target.value)}
          >
            <option value="US">US Market</option>
            <option value="NSE">NSE India</option>
            <option value="BSE">BSE India (Limited)</option>
          </select>

          <div className="symbol-search" ref={symbolSearchRef}>
            <input
              value={symbolInput}
              onChange={(e) => searchCompanies(e.target.value)}
              onFocus={() => {
                if (suggestions.length) setShowSuggestions(true);
              }}
              placeholder="Search symbol or company"
            />

            {showSuggestions && suggestions.length > 0 && (
              <div className="suggestions">
                {suggestions.map((item) => (
                  <button
                    key={`${item.exchange}-${item.symbol}`}
                    type="button"
                    onClick={() => {
                      suggestionRequestRef.current += 1;
                      setSymbolInput(item.symbol);
                      setSymbol(item.symbol);
                      setSelectedCompany({ name: item.name || item.symbol, isin: item.isin || null });
                      setData([]);
                      setDashboard(null);
                      setFundamentals(null);
                      setFundamentalHistory(null);
                      setTechnicalSummary(null);
                      setIndicators(null);
                      setOwnershipDetails(null);
                      setIndiaShareholding(null);
                      setSecEdgar(null);
                      setShowSuggestions(false);
                      setSuggestions([]);
                    }}
                  >
                    <strong>{item.symbol}</strong>
                    <span>{item.name}</span>
                  </button>
                ))}
              </div>
            )}
          </div>

          <button
            onClick={async () => {
              const nextSymbol = symbolInput.trim().toUpperCase();
              if (!nextSymbol) {
                setMessage("Enter a stock symbol first.");
                return;
              }

              setShowSuggestions(false);
              setSuggestions([]);
              suggestionRequestRef.current += 1;

              if (nextSymbol !== symbol) {
                // Commit the typed symbol only when the user explicitly
                // searches/selects it. This prevents requests for partial
                // keystrokes such as I -> IN -> INF -> INFY from racing and
                // overwriting the final stock with stale data.
                setData([]);
                setDashboard(null);
                setFundamentals(null);
                setFundamentalHistory(null);
                setTechnicalSummary(null);
                setIndicators(null);
                setOwnershipDetails(null);
                setIndiaShareholding(null);
                setSecEdgar(null);
                setSelectedCompany({ name: nextSymbol, isin: null });
                setMessage("");
                setSymbol(nextSymbol);
                return;
              }

              // Re-load the currently selected symbol without forcing a full
              // historical provider refresh.
              await Promise.allSettled([
                loadChart(),
                loadIndicators(),
                loadBenchmark(),
                loadDashboard(),
                loadTechnicalSummary(),
                loadOwnershipDetails(),
                loadFundamentals(),
                loadFundamentalHistory(),
                exchange === "US" ? loadSecEdgar() : loadIndiaShareholding(),
              ]);
            }}
          >
            Search
          </button>

          <button className="refresh" onClick={refreshData}>
            Refresh Data
          </button>

          <button type="button" className="excel-live-top" onClick={downloadExcelLiveConnector}>
            Connect Excel Live
          </button>
        </section>

        <section className="timeframes">
          {["daily", "weekly", "monthly"].map((item) => (
            <button
              key={item}
              className={timeframe === item ? "active" : ""}
              onClick={() => setTimeframe(item)}
            >
              {item.charAt(0).toUpperCase() + item.slice(1)}
            </button>
          ))}
        </section>

        {message && (
          <div
            className={
              message.toLowerCase().includes("unavailable") ||
              message.toLowerCase().includes("failed") ||
              message.toLowerCase().includes("stale")
                ? "message error-message"
                : "message success-message"
            }
          >
            {message}
          </div>
        )}


        <section className="universe-screener-card">
          <div className="universe-screener-header">
            <div>
              <h2>Stock Universe Screener</h2>
              <p>Filter many stocks, choose the columns you need, then export the currently filtered list to Excel.</p>
            </div>
            <div className="universe-count-badge">
              <strong>{Number(universeMeta.total || 0).toLocaleString()}</strong>
              <span>Eligible stocks</span>
            </div>
          </div>

          <div className="universe-coverage-strip">
            <div><span>Price history</span><strong>{Number(universeMeta.coverage?.price_history_percent || 0).toFixed(1)}%</strong></div>
            <div><span>Fundamentals</span><strong>{Number(universeMeta.coverage?.fundamentals_percent || 0).toFixed(1)}%</strong></div>
            <div><span>Ownership</span><strong>{Number(universeMeta.coverage?.ownership_percent || 0).toFixed(1)}%</strong></div>
            <div><span>Sector / Industry</span><strong>{Number(universeMeta.coverage?.classification_percent || 0).toFixed(1)}%</strong></div>
            <small>Real provider data only • missing values are filled automatically in bounded background batches.</small>
          </div>

          <div className="universe-filter-title">
            <strong>Filters</strong>
            <span>{universeTab === "Fundamentals" ? "Client handwritten fundamental rules only — EPS / PAT / Sales / NPM / CFO / ROE / ROCE. Edit the exact rules below and apply them." : "Choose a filter group, set the values, then press Apply Filters."}</span>
          </div>

          <div className="universe-tabs">
            {["Popular", "Fundamentals", "Technicals", "Ownership", "Sector Analysis", "Relative Comparison"].map((tab) => (
              <button key={tab} type="button" className={universeTab === tab ? "active" : ""} onClick={() => setUniverseTab(tab)}>
                {tab}
              </button>
            ))}
          </div>

          <div className="universe-filter-grid">
            <label>
              <span>Stock Universe</span>
              <select value={universeFilters.market} onChange={(e) => setUniverseFilters((v) => ({ ...v, market: e.target.value, sector: "", industry: "" }))}>
                <option value="ALL">US + India</option>
                <option value="US">US Stocks</option>
                <option value="INDIA">Indian Stocks</option>
                <option value="NSE">NSE Only</option>
                <option value="BSE">BSE Only</option>
              </select>
            </label>
            <label>
              <span>Search</span>
              <input value={universeFilters.q} onChange={(e) => setUniverseFilters((v) => ({ ...v, q: e.target.value }))} placeholder="Symbol or company" />
            </label>
            <label>
              <span>Sector</span>
              <select value={universeFilters.sector} onChange={(e) => setUniverseFilters((v) => ({ ...v, sector: e.target.value }))}>
                <option value="">All sectors</option>
                {(universeMeta.facets?.sectors || []).map((item) => <option key={item} value={item}>{item}</option>)}
              </select>
            </label>
            <label>
              <span>Industry</span>
              <select value={universeFilters.industry} onChange={(e) => setUniverseFilters((v) => ({ ...v, industry: e.target.value }))}>
                <option value="">All industries</option>
                {(universeMeta.facets?.industries || []).map((item) => <option key={item} value={item}>{item}</option>)}
              </select>
            </label>

            {universeTab === "Popular" && (
              <>
                <label><span>Market Cap Min</span><input type="number" value={universeFilters.market_cap_min} onChange={(e) => setUniverseFilters((v) => ({ ...v, market_cap_min: e.target.value }))} placeholder="Any" /></label>
                <label><span>Near 52W High ≤ %</span><input type="number" value={universeFilters.distance_52w_high_max} onChange={(e) => setUniverseFilters((v) => ({ ...v, distance_52w_high_max: e.target.value }))} placeholder="e.g. 10" /></label>
                <label><span>Near 52W Low ≤ %</span><input type="number" value={universeFilters.distance_52w_low_max} onChange={(e) => setUniverseFilters((v) => ({ ...v, distance_52w_low_max: e.target.value }))} placeholder="e.g. 10" /></label>
                <label><span>Volume Shocker ≥ x</span><input type="number" step="0.1" value={universeFilters.volume_ratio_min} onChange={(e) => setUniverseFilters((v) => ({ ...v, volume_ratio_min: e.target.value }))} placeholder="e.g. 1.5" /></label>
              </>
            )}

            {universeTab === "Fundamentals" && (
              <div className="universe-client-factor-panel">
                <div className="universe-client-factor-head">
                  <div>
                    <strong>Client Fundamental Filters</strong>
                    <span>Exact handwritten groups: EPS, PAT, Sales, NPM, CFO and the confirmed ROE / ROCE rules. Generic Market Cap / EPS Min / Revenue Min filters have been removed from this tab.</span>
                  </div>
                  <span className="client-note-badge">Client notes</span>
                </div>
                {renderFilterTable("fundamental", "Fundamental Filters", "Quarterly + annual rules supplied by the client. Missing provider history stays N/A; nothing is fabricated.")}
                <div className="universe-client-factor-actions">
                  <button type="button" className="ranking-primary-button" onClick={() => {
                    localStorage.setItem("handwrittenFactors", JSON.stringify(handwrittenFactors));
                    loadDashboard();
                  }}>Apply Fundamental Rules</button>
                  <span>Settings are shared with the Milestone 2 ranking / qualification engine.</span>
                </div>
              </div>
            )}

            {universeTab === "Technicals" && (
              <>
                <label><span>LTP Min</span><input type="number" step="0.01" value={universeFilters.close_min} onChange={(e) => setUniverseFilters((v) => ({ ...v, close_min: e.target.value }))} placeholder="Any" /></label>
                <label><span>LTP Max</span><input type="number" step="0.01" value={universeFilters.close_max} onChange={(e) => setUniverseFilters((v) => ({ ...v, close_max: e.target.value }))} placeholder="Any" /></label>
                <label><span>Distance From 52W High ≤ %</span><input type="number" step="0.1" value={universeFilters.distance_52w_high_max} onChange={(e) => setUniverseFilters((v) => ({ ...v, distance_52w_high_max: e.target.value }))} placeholder="Any" /></label>
                <label><span>Distance From 52W Low ≤ %</span><input type="number" step="0.1" value={universeFilters.distance_52w_low_max} onChange={(e) => setUniverseFilters((v) => ({ ...v, distance_52w_low_max: e.target.value }))} placeholder="Any" /></label>
                <label><span>Volume / 52W Avg ≥ x</span><input type="number" step="0.1" value={universeFilters.volume_ratio_min} onChange={(e) => setUniverseFilters((v) => ({ ...v, volume_ratio_min: e.target.value }))} placeholder="Any" /></label>
              </>
            )}

            {universeTab === "Ownership" && (
              <>
                <label><span>Institutional Holding ≥ %</span><input type="number" step="0.1" value={universeFilters.institution_min} onChange={(e) => setUniverseFilters((v) => ({ ...v, institution_min: e.target.value }))} placeholder="Any" /></label>
                <label><span>Insider Holding ≥ %</span><input type="number" step="0.1" value={universeFilters.insider_min} onChange={(e) => setUniverseFilters((v) => ({ ...v, insider_min: e.target.value }))} placeholder="Any" /></label>
                <div className="universe-info-tile ownership-info-tile">
                  <strong>{universeFilters.market === "US" ? "US Ownership" : universeFilters.market === "ALL" ? "US + India Ownership" : "Indian Ownership"}</strong>
                  <span>{universeFilters.market === "US" ? "Institutional and insider provider holdings are filterable here. Public/retail is the residual where provider data allows it." : "Available provider ownership fields are filterable here. Promoter/FII/DII-MF historical rules remain in Advanced Ownership Filters and missing values stay N/A."}</span>
                </div>
                <button type="button" className="secondary-button ownership-advanced-button" onClick={() => document.getElementById("ranking-filters")?.scrollIntoView({ behavior: "smooth", block: "start" })}>Advanced Ownership Filters ↓</button>
              </>
            )}

            {universeTab === "Sector Analysis" && (
              <>
                <div className="universe-info-tile sector-info-tile">
                  <strong>Sector Analysis</strong>
                  <span>Select a sector above or leave All sectors to compare sectors. Current snapshot medians use real stored provider data; historical growth scores stay N/A until verified peer history exists.</span>
                </div>
                <button type="button" className="secondary-button sector-refresh-button" disabled={sectorAnalysisLoading} onClick={() => loadSectorAnalysis(universeFilters)}>{sectorAnalysisLoading ? "Loading…" : "Refresh Sector Analysis"}</button>
              </>
            )}

            {universeTab === "Relative Comparison" && (
              <>
                <label><span>Institutional Holding ≥ %</span><input type="number" step="0.1" value={universeFilters.institution_min} onChange={(e) => setUniverseFilters((v) => ({ ...v, institution_min: e.target.value }))} placeholder="Any" /></label>
                <label><span>Insider Holding ≥ %</span><input type="number" step="0.1" value={universeFilters.insider_min} onChange={(e) => setUniverseFilters((v) => ({ ...v, insider_min: e.target.value }))} placeholder="Any" /></label>
                <label><span>ROE ≥ %</span><input type="number" step="0.1" value={universeFilters.roe_min} onChange={(e) => setUniverseFilters((v) => ({ ...v, roe_min: e.target.value }))} placeholder="Any" /></label>
                <label><span>Near 52W High ≤ %</span><input type="number" step="0.1" value={universeFilters.distance_52w_high_max} onChange={(e) => setUniverseFilters((v) => ({ ...v, distance_52w_high_max: e.target.value }))} placeholder="Any" /></label>
              </>
            )}
          </div>

          <div className="universe-toolbar">
            <div className="universe-toolbar-left">
              {universeTab !== "Fundamentals" && (
                <button type="button" className="ranking-primary-button universe-apply-button" onClick={() => { setUniversePage(1); loadUniverseScreener(1); }}>Apply Filters</button>
              )}
              <button type="button" className="secondary-button button-muted" onClick={resetUniverseFilters}>Reset Filters</button>
              <button type="button" className="secondary-button button-columns" onClick={() => setShowUniverseColumns((v) => !v)}>{showUniverseColumns ? "Hide Columns" : "Add Columns"}</button>
              <button type="button" className="secondary-button button-factors" onClick={() => document.getElementById("ranking-filters")?.scrollIntoView({ behavior: "smooth", block: "start" })}>Ranking Filters ↓</button>
              <button type="button" className="secondary-button button-sync" disabled={universeSyncing} onClick={refreshUniverseMissingData}>{universeSyncing ? "Filling Data…" : "Fill Missing Data"}</button>
              <button type="button" className="secondary-button button-excel" onClick={downloadUniverseExcel}>Export Excel</button>
            </div>
            <div className="universe-toolbar-right">
              <label>Sort
                <select value={universeFilters.sort_by} onChange={(e) => setUniverseFilters((v) => ({ ...v, sort_by: e.target.value }))}>
                  <option value="data_coverage">Data Coverage</option><option value="symbol">Symbol</option><option value="market_cap">Market Cap</option><option value="close">LTP</option>
                  <option value="return_on_equity">ROE</option><option value="profit_margin">Profit Margin</option>
                  <option value="institution_percent">Institutional Holding</option><option value="distance_52w_high">Distance 52W High</option>
                  <option value="volume_ratio">Volume Ratio</option>
                </select>
              </label>
              <select aria-label="Sort direction" value={universeFilters.sort_dir} onChange={(e) => setUniverseFilters((v) => ({ ...v, sort_dir: e.target.value }))}>
                <option value="asc">Ascending</option><option value="desc">Descending</option>
              </select>
              <label>Page Size
                <select value={universePageSize} onChange={(e) => { const size = Number(e.target.value); setUniversePageSize(size); setUniversePage(1); loadUniverseScreener(1, universeFilters, size); }}>
                  {[25, 50, 100].map((size) => <option key={size} value={size}>{size}</option>)}
                </select>
              </label>
            </div>
          </div>

          {universeTab === "Ownership" && (
            <div className="ownership-universe-panel">
              <div className="ownership-universe-head">
                <div>
                  <h3>Ownership Filters</h3>
                  <p>Visible here exactly as a dedicated filter section. US uses Insider / Institutional / Retail-Public categories; Indian ranking rules use Promoter / FII / DII-MF / pledge / insider rules from the client notes.</p>
                </div>
                <span className="ownership-market-badge">{universeFilters.market === "ALL" ? "US + India" : universeFilters.market}</span>
              </div>
              {(universeFilters.market === "US" || universeFilters.market === "ALL") && renderUSOwnershipTable()}
              {(universeFilters.market !== "US") && renderFilterTable("ownership", "Ownership Ranking Filters", "Promoter / FII / DII-MF / pledge / insider rules from the handwritten client notes. Missing provider history remains N/A.")}
            </div>
          )}

          {universeTab === "Sector Analysis" && (
            <div className="sector-analysis-panel">
              <div className="sector-analysis-head">
                <div>
                  <h3>Sector Analysis</h3>
                  <p>{sectorAnalysis.formula || "EPS Growth RS 30% + PAT Growth RS 25% + Sales Growth RS 20% + Growth Acceleration RS 15% + Growth Breadth 5% + Acceleration Breadth 5%"}</p>
                </div>
                <span className="sector-method-badge">Median aggregation</span>
              </div>
              {sectorAnalysisError && <div className="message error-message universe-message">{sectorAnalysisError}</div>}
              <div className="sector-analysis-table-wrap">
                <table className="sector-analysis-table">
                  <thead><tr><th>Sector</th><th>Stocks</th><th>Median EPS</th><th>Median PAT</th><th>Median Sales</th><th>EPS Growth RS</th><th>PAT Growth RS</th><th>Sales Growth RS</th><th>Growth Accel RS</th><th>Growth Breadth</th><th>Accel Breadth</th><th>Sector RS</th><th>Status</th></tr></thead>
                  <tbody>
                    {sectorAnalysisLoading ? (
                      <tr><td colSpan="13" className="universe-empty">Loading sector analysis…</td></tr>
                    ) : sectorAnalysis.rows?.length ? sectorAnalysis.rows.map((row) => (
                      <tr key={row.sector}>
                        <td><strong>{row.sector}</strong></td>
                        <td>{Number(row.stock_count || 0).toLocaleString()}</td>
                        <td>{row.median_eps == null ? "N/A" : Number(row.median_eps).toFixed(2)}</td>
                        <td>{row.median_pat == null ? "N/A" : Number(row.median_pat).toLocaleString(undefined, { notation: "compact", maximumFractionDigits: 2 })}</td>
                        <td>{row.median_sales == null ? "N/A" : Number(row.median_sales).toLocaleString(undefined, { notation: "compact", maximumFractionDigits: 2 })}</td>
                        <td>{row.eps_growth_rs == null ? "N/A" : Number(row.eps_growth_rs).toFixed(2)}</td>
                        <td>{row.pat_growth_rs == null ? "N/A" : Number(row.pat_growth_rs).toFixed(2)}</td>
                        <td>{row.sales_growth_rs == null ? "N/A" : Number(row.sales_growth_rs).toFixed(2)}</td>
                        <td>{row.growth_acceleration_rs == null ? "N/A" : Number(row.growth_acceleration_rs).toFixed(2)}</td>
                        <td>{row.growth_breadth == null ? "N/A" : Number(row.growth_breadth).toFixed(2)}</td>
                        <td>{row.acceleration_breadth == null ? "N/A" : Number(row.acceleration_breadth).toFixed(2)}</td>
                        <td><strong>{row.sector_rs_score == null ? "N/A" : Number(row.sector_rs_score).toFixed(2)}</strong></td>
                        <td><span className={`sector-status ${row.sector_rs_score == null ? "is-pending" : "is-ready"}`}>{row.sector_rs_score == null ? row.history_status : "Ready"}</span></td>
                      </tr>
                    )) : <tr><td colSpan="13" className="universe-empty">No sector data is available for the selected universe.</td></tr>}
                  </tbody>
                </table>
              </div>
              <div className="sector-analysis-note">{sectorAnalysis.aggregation || "Use median stock growth for sector growth metrics rather than average."} {sectorAnalysis.data_rule}</div>
            </div>
          )}

          {showUniverseColumns && (
            <div className="universe-column-picker">
              {universeColumnOptions.map(([key, label]) => (
                <label key={key}>
                  <input type="checkbox" checked={universeColumns.includes(key)} onChange={(e) => {
                    setUniverseColumns((cols) => e.target.checked ? [...new Set([...cols, key])] : cols.filter((item) => item !== key || key === "symbol"));
                  }} />
                  <span>{label}</span>
                </label>
              ))}
            </div>
          )}

          {universeError && <div className="message error-message universe-message">{universeError}</div>}
          <div className="universe-table-wrap">
            <table className="universe-table">
              <thead>
                <tr>
                  {universeColumns.map((key) => <th key={key}>{universeColumnOptions.find(([item]) => item === key)?.[1] || key}</th>)}
                  <th>Open</th>
                </tr>
              </thead>
              <tbody>
                {universeLoading ? (
                  <tr><td colSpan={universeColumns.length + 1} className="universe-empty">Loading filtered stocks…</td></tr>
                ) : universeRows.length ? universeRows.map((row) => (
                  <tr key={`${row.exchange}-${row.symbol}`}>
                    {universeColumns.map((key) => (
                      <td key={key} className={key === "symbol" ? "universe-symbol-cell" : ""}>{formatUniverseCell(key, row[key], row)}</td>
                    ))}
                    <td><button type="button" className="universe-open-button" onClick={() => openUniverseStock(row)}>Open</button></td>
                  </tr>
                )) : (
                  <tr><td colSpan={universeColumns.length + 1} className="universe-empty">No stocks match the current filters.</td></tr>
                )}
              </tbody>
            </table>
          </div>

          <div className="universe-pagination">
            <span>Page {universePage} of {universeMeta.pages || 1}</span>
            <div>
              <button type="button" className="secondary-button" disabled={universePage <= 1 || universeLoading} onClick={() => { const p = Math.max(1, universePage - 1); setUniversePage(p); loadUniverseScreener(p); }}>Previous</button>
              <button type="button" className="secondary-button" disabled={universePage >= (universeMeta.pages || 1) || universeLoading} onClick={() => { const p = Math.min(universeMeta.pages || 1, universePage + 1); setUniversePage(p); loadUniverseScreener(p); }}>Next</button>
            </div>
          </div>
          <div className="universe-data-note">Only verified provider/database values are shown. Warrants, units, ETFs and obvious SPAC/acquisition securities are excluded from the normal US stock universe. Missing values remain N/A until the automatic enrichment process retrieves real data.</div>
        </section>

        <section className="cards">
          <div className="card">
            <span>Market</span>
            <strong>{exchange}</strong>
          </div>

          <div className="card company-identity-card">
            <span className="company-card-label">Company</span>
            <strong className="company-card-name">{selectedCompany?.name || dashboard?.name || symbol}</strong>
            <div className="company-card-meta">
              <span className="company-symbol-badge">{symbol}</span>
              <span className={`company-isin-badge ${(selectedCompany?.isin || dashboard?.isin) ? "has-value" : "is-missing"}`}>
                <span className="company-meta-label">ISIN</span>
                <b>{selectedCompany?.isin || dashboard?.isin || "N/A"}</b>
              </span>
            </div>
          </div>

          <div className="card">
            <span>Latest Close</span>
            <strong>
              {latest
                ? `${currency}${Number(latest.close).toFixed(2)}`
                : "-"}
            </strong>
          </div>

          <div className="card">
            <span>Volume</span>
            <strong>
              {latest ? Number(latest.volume).toLocaleString() : "-"}
            </strong>
          </div>
        </section>

        {dashboard && (
          <section className="dashboard-summary">
            <div className="summary-score">
              <span>Overall Score</span>
              <strong>{dashboardView?.score != null ? `${dashboardView.score}/100` : "N/A"}</strong>
              <small>{dashboardView?.score_coverage_percent ?? 0}% metric coverage</small>
            </div>
            <div className={`summary-signal signal-${dashboardView?.signal?.toLowerCase()}`}>
              <span>Rule-Based Signal</span>
              <strong>{dashboardView?.signal}</strong>
              <small>{dashboardView?.score == null ? `Ranking withheld: missing ${(dashboard.missing_required_score_categories || []).join(" + ") || (technicalSummary?.rs_available === false ? "verified relative-strength benchmark data" : "required data")}` : (technicalSummary?.rs_available === false ? "RS excluded because benchmark overlap is unavailable" : "Based on configured weighted data")}</small>
            </div>
            <div className="summary-item">
              <span>Sector</span>
              <strong>{dashboard.sector || "-"}</strong>
              <small>
                {dashboard.sector_rank?.available
                  ? `Rank: ${dashboard.sector_rank.rank}/${dashboard.sector_rank.total}`
                  : (dashboard.sector_rank?.note || "Insufficient peer data")}
              </small>
            </div>
            <div className="summary-item">
              <span>Industry</span>
              <strong>{dashboard.industry || "-"}</strong>
              <small>
                {dashboard.industry_rank?.available
                  ? `Rank: ${dashboard.industry_rank.rank}/${dashboard.industry_rank.total}`
                  : (dashboard.industry_rank?.note || "Insufficient peer data")}
              </small>
            </div>
          </section>
        )}

        {dashboard && (
            <section id="ranking-filters" className="fundamental-section score-weight-section ranking-settings-panel">
              <div className="ranking-settings-header">
                <div>
                  <h2>Milestone 2 Ranking Weight Settings ({exchange})</h2>
                  <p>Client composite: Fundamental 30% + Technical 25% + RS 25% + Ownership 15% + Sector 5%. Editable weights remain normalized automatically.</p>
                </div>
                <div className="ranking-total-badge">
                  <span>Entered total</span>
                  <strong>{Object.values(scoreWeights).reduce((sum, value) => sum + (Number(value) || 0), 0)}%</strong>
                  <small>Normalized automatically</small>
                </div>
              </div>

              <div className="ranking-category-grid">
                {[
                  ["technical", "Technical", "Trend, moving averages and RSI"],
                  ["fundamental", "Fundamental", "Earnings, margins and returns"],
                  ["relative_strength", "Relative Strength", `Performance vs ${exchange === "US" ? "S&P 500" : "NIFTY 500"}`],
                  ["ownership", "Ownership", exchange === "US" ? "Institutional and insider positioning" : "Promoter / FII / DII-MF positioning"],
                  ["sector", "Sector", "Sector growth ranking from EPS/PAT/Sales breadth and acceleration"],
                ].map(([key, label, description]) => {
                  const value = Number(scoreWeights[key]) || 0;
                  return (
                    <div className={`ranking-category-card ${value === 0 ? "is-disabled" : ""}`} key={key}>
                      <div className="ranking-category-copy">
                        <strong>{label}</strong>
                        <small>{description}</small>
                      </div>
                      <div className="weight-input-wrap">
                        <input
                          aria-label={`${label} weight`}
                          type="number"
                          min="0"
                          step="1"
                          value={scoreWeights[key]}
                          onChange={(e) => setScoreWeights((prev) => ({ ...prev, [key]: Math.max(0, Number(e.target.value) || 0) }))}
                        />
                        <span>%</span>
                      </div>
                    </div>
                  );
                })}
              </div>

              <div className="compact-ranking-result">
                <div className="compact-ranking-result-header">
                  <div>
                    <h3>Composite Ranking</h3>
                    <p>Arranged from the client note: component score × editable weight.</p>
                  </div>
                  <div className="composite-score-box">
                    <span>Final score</span>
                    <strong>{dashboardView?.score != null ? dashboardView.score.toFixed ? dashboardView.score.toFixed(0) : dashboardView.score : "N/A"}</strong>
                    <small>{dashboardView?.score_coverage_percent ?? 0}% data coverage</small>
                  </div>
                </div>
                <div className="compact-table-scroll">
                  <table className="component-score-table">
                    <thead><tr><th>Component</th><th>Score</th><th>Weight</th><th>Weighted contribution</th><th>Status</th></tr></thead>
                    <tbody>
                      {[
                        ["fundamental", "Fundamental"],
                        ["technical", "Technical"],
                        ["relative_strength", "RS"],
                        ["ownership", "Ownership"],
                        ["sector", "Sector"],
                      ].map(([key, label]) => {
                        const score = dashboardView?.score_components?.[key];
                        const weight = Number(scoreWeights[key]) || 0;
                        const totalWeight = Object.values(scoreWeights).reduce((sum, value) => sum + Math.max(0, Number(value) || 0), 0);
                        const normalizedWeight = totalWeight > 0 ? (weight / totalWeight) * 100 : 0;
                        const contribution = score == null ? null : (Number(score) * normalizedWeight) / 100;
                        return (
                          <tr key={key}>
                            <td><strong>{label}</strong></td>
                            <td>{score == null ? "N/A" : Number(score).toFixed(2)}</td>
                            <td>{weight}%</td>
                            <td>{contribution == null ? "N/A" : contribution.toFixed(2)}</td>
                            <td><span className={`component-status ${score == null ? "is-na" : "is-ready"}`}>{score == null ? "N/A" : "Ready"}</span></td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>

              <div className="ranking-actions">
                <button className="ranking-primary-button" onClick={() => {
                  localStorage.setItem("scoreWeights", JSON.stringify(scoreWeights));
                  localStorage.setItem("scoreWeightsVersion", SCORE_WEIGHTS_STORAGE_VERSION);
                  localStorage.setItem("handwrittenFactors", JSON.stringify(handwrittenFactors));
                  localStorage.setItem("rsWeights", JSON.stringify(rsWeights));
                  localStorage.setItem("rsWeightsVersion", RS_WEIGHTS_STORAGE_VERSION);
                  localStorage.setItem("rsVisibility", JSON.stringify(rsVisibility));
                  loadDashboard();
                  loadTechnicalSummary();
                }}>Apply Ranking</button>
                <button type="button" className="secondary-button ranking-secondary-button button-excel" onClick={downloadExcelLiveConnector}>Connect Excel Live</button>
                <button type="button" className="secondary-button ranking-secondary-button button-copy" onClick={copyExcelFeedUrl}>Copy Live Data URL</button>
                <button type="button" className="secondary-button ranking-secondary-button button-help" onClick={() => setShowExcelHelp((v) => !v)}>
                  {showExcelHelp ? "Hide Excel Steps" : "Excel Setup"}
                </button>
                <button type="button" className="secondary-button ranking-secondary-button" onClick={downloadExcelSnapshot}>Excel Snapshot</button>
                <button type="button" className="secondary-button ranking-secondary-button button-factors" onClick={() => setShowRankingDetails((v) => !v)}>
                  {showRankingDetails ? "Hide Factors" : "Show Factors"}
                </button>
                <button type="button" className="secondary-button ranking-secondary-button button-danger-soft" onClick={() => {
                  setScoreWeights({ ...defaultScoreWeights });
                  setHandwrittenFactors(JSON.parse(JSON.stringify(defaultHandwrittenFactors)));
                  localStorage.setItem("scoreWeights", JSON.stringify(defaultScoreWeights));
                  localStorage.setItem("scoreWeightsVersion", SCORE_WEIGHTS_STORAGE_VERSION);
                  localStorage.removeItem("handwrittenFactors");
                }}>Reset Defaults</button>
              </div>

              {(showExcelHelp || excelCopyMessage) && (
                <div className="excel-connect-panel">
                  {excelCopyMessage && <div className="excel-copy-message">{excelCopyMessage}</div>}
                  {showExcelHelp && (
                    <>
                      <strong>Live Excel connection — at least 4 years of indicator data</strong>
                      <ol>
                        <li>Click <b>Connect Excel Live</b>. This creates a small <b>.iqy</b> connection file, not a static data export.</li>
                        <li>Open the .iqy file in desktop Excel and allow the web connection when Excel asks.</li>
                        <li>Save the opened sheet as your normal <b>.xlsx</b> workbook. The external screener connection stays attached.</li>
                        <li>Later use <b>Data → Refresh All</b>; Excel requests the latest daily data from this screener automatically.</li>
                        <li>The live feed requests <b>5 years</b> of daily OHLCV, giving at least the required <b>4 years</b> for indicator creation when the provider has the history.</li>
                        <li>Keep your own indicator formulas on separate columns/sheets so a data refresh does not overwrite them.</li>
                      </ol>
                      <code>{excelLiveCsvUrl}</code>
                    </>
                  )}
                </div>
              )}

              <div className="ranking-help-note">
                <strong>How weighting works:</strong> the Milestone 2 default follows the latest handwritten composite formula: Fundamental 30%, Technical 25%, RS 25%, Ownership 15%, Sector 5%. Missing provider values remain N/A and are never invented. Ambiguous handwritten point allocations remain editable until confirmed.
              </div>

              {showRankingDetails && (
                <div className="compact-filter-stack">
                  {renderFilterTable("technical", "Technical Filters", `Client handwritten technical ranking filters • ${timeframe.charAt(0).toUpperCase() + timeframe.slice(1)} candles; period-based rules recalculate automatically`)}
                  {renderFilterTable("fundamental", "Fundamental Filters", "EPS / PAT / Sales / NPM / CFO and additional client filters")}
                  {exchange === "US" ? renderUSOwnershipTable() : renderFilterTable("ownership", "Ownership Filters", "Promoter / FII / DII-MF / pledge / insider filters")}

                  <div className="qualification-panel">
                    <div>
                      <h3>Fundamental Qualification</h3>
                      <p>Current selected stock against the enabled weighted fundamental filters. Missing provider values remain N/A.</p>
                    </div>
                    <div className={`qualification-status status-${selectedFundamentalQualification.status.toLowerCase().replaceAll(" ", "-")}`}>
                      <strong>{symbol}</strong>
                      <span>{selectedFundamentalQualification.status}</span>
                      <small>{selectedFundamentalQualification.passed}/{selectedFundamentalQualification.considered} passed{selectedFundamentalQualification.missing ? ` • ${selectedFundamentalQualification.missing} missing` : ""}</small>
                    </div>
                    <div className="qualification-note">
                      The universe-wide qualifying-stock list will use the same filter configuration as complete stored fundamental history becomes available for each company; the screener does not invent missing history to force qualification.
                    </div>
                  </div>
                </div>
              )}
            </section>
        )}

        {dashboard && (
          <section className="fundamental-section">
            <div className="ranking-settings-header">
              <div>
                <h2>Latest Client Ranking Formula</h2>
                <p>Captured from the newest handwritten Milestone 2 notes.</p>
              </div>
              <div className="formula-excel-actions">
                <button type="button" className="secondary-button button-excel" onClick={downloadExcelLiveConnector}>Connect Excel Live</button>
                <button type="button" className="secondary-button button-copy" onClick={copyExcelFeedUrl}>Copy Live URL</button>
              </div>
            </div>
            <div className="chart-note">
              Composite = Fundamental × 30% + Technical × 25% + RS × 25% + Ownership × 15% + Sector × 5%
            </div>
            <div className="chart-note" style={{ marginTop: 8 }}>
              Sector = EPS RS × 30% + PAT RS × 25% + Sales RS × 20% + Growth Acceleration RS × 15% + Growth Breadth × 5% + Acceleration Breadth × 5%
            </div>
            <div className="chart-note" style={{ marginTop: 8 }}>
              Sector Growth Breadth = (Sales breadth + PAT breadth + EPS breadth) / 3. Acceleration Breadth = 35% EPS + 35% PAT + 30% Sales. Sector growth aggregation uses the median stock growth from the client note.
            </div>
            {technicalSummary?.client_technical_filters && (
              <div className="ranking-detail-grid" style={{ marginTop: 16 }}>
                {[
                  ["Trend", technicalSummary.client_technical_filters.trend],
                  ["Strength", technicalSummary.client_technical_filters.strength],
                  ["Momentum", technicalSummary.client_technical_filters.momentum],
                  ["Participation", technicalSummary.client_technical_filters.participation],
                  ["Volatility", technicalSummary.client_technical_filters.volatility],
                  ["Base Formation", technicalSummary.client_technical_filters.base_formation],
                ].map(([title, values]) => (
                  <div className="ranking-detail-card" key={title}>
                    <div className="ranking-detail-card-header"><div><h3>{title}</h3></div></div>
                    <div className="ranking-parameter-list">
                      {Object.entries(values || {}).slice(0, 8).map(([key, value]) => (
                        <div className="ranking-parameter-row" key={key}>
                          <div className="ranking-parameter-copy">
                            <strong>{key.replaceAll("_", " ")}</strong>
                          </div>
                          <span>{formatClientFilterValue(key, value)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
            <div className="ranking-help-note" style={{ marginTop: 14 }}>
              Unclear handwritten point allocations are intentionally not guessed. They remain editable until the client confirms the exact values.
            </div>
          </section>
        )}

        <section className="chart-card">
          <div className="chart-header">
            <div>
              <h2>{symbol} Price</h2>
              <p>
                {exchange} • {timeframe} OHLCV data
              </p>
            </div>

            {loading && <span>Loading...</span>}
          </div>

          {chartInfo && !dataStale && (
            <div className="chart-note">
              {new Date(`${chartInfo.date}T00:00:00`).toLocaleDateString("en-US")} &nbsp;
              O {chartInfo.open.toFixed(2)} &nbsp; H {chartInfo.high.toFixed(2)} &nbsp;
              L {chartInfo.low.toFixed(2)} &nbsp; C {chartInfo.close.toFixed(2)}
            </div>
          )}

          {!dataStale && (
            <div className="indicator-settings chart-overlay-controls">
              {[
                ["ema", "EMA 20/30/50/100/150/200"],
                ["sma", "SMA 20/50"],
                ["bollinger", "Bollinger Bands"],
                ["volume", "Volume + 50P Avg"],
                ["eps", "Quarterly EPS"],
                ["rs", `RS vs ${benchmark?.name || "Benchmark"}`],
              ].map(([key, label]) => (
                <label key={key} className="overlay-toggle">
                  <input
                    type="checkbox"
                    checked={chartOverlays[key]}
                    onChange={(e) => setChartOverlays((prev) => ({ ...prev, [key]: e.target.checked }))}
                  />
                  {label}
                </label>
              ))}
            </div>
          )}

          {!dataStale && chartOverlays.ema && (
            <div className="ema-color-legend" aria-label="EMA color legend">
              {[
                [20, "#2563eb"],
                [30, "#f59e0b"],
                [50, "#7c3aed"],
                [100, "#0891b2"],
                [150, "#db2777"],
                [200, "#92400e"],
              ].map(([period, color]) => (
                <span key={period} className="ema-legend-item">
                  <span className="ema-legend-swatch" style={{ backgroundColor: color }} />
                  EMA {period}
                </span>
              ))}
              {chartOverlays.volume && (
                <span className="volume-legend-note">
                  Volume: <strong className="volume-up-text">green = up candle</strong>, <strong className="volume-down-text">red = down candle</strong>
                </span>
              )}
            </div>
          )}

          {loading ? (
            <div className="chart-loading-panel" role="status" aria-live="polite">
              <span className="chart-loading-spinner" aria-hidden="true" />
              <div>
                <strong>Loading market data…</strong>
                <small>Fetching the selected stock and recalculating indicators.</small>
              </div>
            </div>
          ) : !dataStale ? (
            <div
              ref={chartContainerRef}
              style={{
                width: "100%",
                height: "520px"
              }}
            />
          ) : (
            <div className="stale-panel">
              Historical data is unavailable or incomplete for this provider.
            </div>
          )}

          {benchmark?.warning && (
            <div className="provider-warning">{benchmark.warning}</div>
          )}
          {benchmark?.data?.length > 0 && (
            <div className="chart-note">
              Chart overlays: EMA 20/30/50/100/150/200, Bollinger Bands, volume + 50-period average volume, quarterly EPS, and Relative Strength = Stock Price / {benchmark.name}. The RS line is visually rebased only for overlay; its direction comes from the stock/index ratio.
            </div>
          )}

          {technicalSummary && (
            <div className="technical-metric-chart-block">
              <div className="technical-metric-value-grid">
                <div className="metric"><span>ADR % (20D)</span><strong>{technicalSummary.adr_percent != null ? `${technicalSummary.adr_percent}%` : "-"}</strong><small>Daily ADR reference</small></div>
                <div className="metric"><span>ATR % (14)</span><strong>{technicalSummary.atr_percent != null ? `${technicalSummary.atr_percent}%` : "-"}</strong></div>
                <div className="metric"><span>BB Width %</span><strong>{technicalSummary.bollinger_width_percent != null ? `${technicalSummary.bollinger_width_percent}%` : "-"}</strong><small>(Upper BB - Lower BB) × 100 / Lower BB</small></div>
                <div className="metric"><span>{`20-${timeframe === "daily" ? "Day" : timeframe === "weekly" ? "Week" : "Month"} Price Range`}</span><strong>{technicalSummary.range_20d_percent != null ? `${technicalSummary.range_20d_percent}%` : "-"}</strong></div>
              </div>
              {technicalSummary.technical_metric_series?.length > 1 && (
                <>
                  <h3>{`Technical Volatility Trends (${timeframe.charAt(0).toUpperCase() + timeframe.slice(1)})`}</h3>
                  <ResponsiveContainer width="100%" height={240}>
                    <LineChart data={technicalSummary.technical_metric_series}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="date" minTickGap={35} />
                      <YAxis unit="%" domain={["auto", "auto"]} />
                      <Tooltip formatter={(value, name) => [`${Number(value).toFixed(2)}%`, name]} />
                      <Line type="monotone" dataKey="adr_percent" name="ADR %" stroke="#2563eb" strokeWidth={2} dot={false} connectNulls />
                      <Line type="monotone" dataKey="atr_percent" name="ATR %" stroke="#f59e0b" strokeWidth={2} dot={false} connectNulls />
                      <Line type="monotone" dataKey="bollinger_width_percent" name="BB Width %" stroke="#7c3aed" strokeWidth={2} dot={false} connectNulls />
                      <Line type="monotone" dataKey="range_20d_percent" name="20-Day Range %" stroke="#0891b2" strokeWidth={2} dot={false} connectNulls />
                    </LineChart>
                  </ResponsiveContainer>
                </>
              )}
            </div>
          )}
        </section>

        <section className="fundamental-section relative-strength-section">
          <div className="rs-section-header">
            <div>
              <h2>Relative Strength vs {benchmark?.name || (exchange === "US" ? "S&P 500" : "NIFTY 500")}</h2>
              <p>Choose the periods to include and adjust their contribution to the final RS score.</p>
            </div>
            <div className="rs-weight-total" title="Sum of all RS weights">
              <span>Total weight</span>
              <strong>{Object.values(rsWeights).reduce((sum, value) => sum + (Number(value) || 0), 0)}%</strong>
            </div>
          </div>
          <div className="indicator-settings rs-weight-settings rs-horizon-settings">
            {["1w","2w","1m","2m","3m","6m","1y","sector"].map((key) => (
              <div key={key} className={`rs-horizon-control ${rsVisibility[key] === false ? "is-hidden" : ""}`}>
                <div className="rs-horizon-card-head">
                  <span className="rs-period-label">{key === "sector" ? "Sector RS" : key.toUpperCase()}</span>
                  <label className="rs-switch" title={rsVisibility[key] !== false ? "Included in display" : "Hidden from display"}>
                    <input
                      type="checkbox"
                      checked={rsVisibility[key] !== false}
                      onChange={(e) => setRsVisibility((prev) => ({ ...prev, [key]: e.target.checked }))}
                    />
                    <span className="rs-switch-track"><span className="rs-switch-thumb" /></span>
                    <span className="rs-switch-text">{rsVisibility[key] !== false ? "Shown" : "Hidden"}</span>
                  </label>
                </div>
                <label className="rs-weight-field">
                  <span>Weight</span>
                  <span className="rs-weight-input-wrap">
                    <input type="number" min="0" value={rsWeights[key]}
                      onChange={(e) => setRsWeights((prev) => ({ ...prev, [key]: Math.max(0, Number(e.target.value) || 0) }))} />
                    <span className="rs-percent-suffix">%</span>
                  </span>
                </label>
              </div>
            ))}
            <div className="rs-settings-actions">
              <span>Changes are applied to the RS calculation after saving.</span>
              <button onClick={() => {
                localStorage.setItem("rsWeights", JSON.stringify(rsWeights));
                localStorage.setItem("rsWeightsVersion", RS_WEIGHTS_STORAGE_VERSION);
                localStorage.setItem("rsVisibility", JSON.stringify(rsVisibility));
                loadTechnicalSummary();
                loadDashboard();
              }}>Apply RS Settings</button>
            </div>
          </div>
          <div className="rs-score-summary">
            <div className="metric rs-score-card">
              <span>{technicalSummary?.rs_universe?.complete ? "Final RS Score" : "RS Score (Provisional)"}</span>
              <strong>{technicalSummary?.rs_available ? Number(technicalSummary.rs_rating).toFixed(2) : "N/A"}</strong>
              <small>
                {technicalSummary?.rs_universe
                  ? `${Number(technicalSummary.rs_universe.scored_stocks_available || 0).toLocaleString()}/${Number(technicalSummary.rs_universe.target_size || (exchange === "US" ? 6000 : 5500)).toLocaleString()} scored stocks available`
                  : "Percentile-weighted score from the enabled RS periods"}
              </small>
            </div>
          </div>
          <div className="rs-period-grid">
            {["1w","2w","1m","2m","3m","6m","1y","sector"].filter((key) => rsVisibility[key] !== false).map((key) => {
              const item = technicalSummary?.rs_periods?.[key];
              if (key === "sector") {
                return (
                  <div className="metric rs-period-card" key={key}>
                    <span>Sector RS Score</span>
                    <strong>{item?.percentile != null ? Number(item.percentile).toFixed(2) : "-"}</strong>
                    <small>{item?.sector || dashboard?.sector || "Sector unavailable"} • Raw sector score {item?.score != null ? Number(item.score).toFixed(2) : "-"} • Weight {rsWeights[key]}%</small>
                  </div>
                );
              }
              return (
                <div className="metric rs-period-card" key={key}>
                  <span>{key.toUpperCase()} Relative Return</span>
                  <strong>{item?.relative_return_percent != null ? `${Number(item.relative_return_percent).toFixed(2)}%` : "-"}</strong>
                  <small>Percentile {item?.percentile != null ? Number(item.percentile).toFixed(2) : "-"} • Weight {rsWeights[key]}%</small>
                </div>
              );
            })}
          </div>

          {technicalSummary?.rs_comparison?.rows?.length > 0 && (
            <div className="table-card rs-comparison-table">
              <h3>Relative Strength Return Comparison</h3>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Relative Strength</th>
                      {(technicalSummary.rs_comparison.periods || []).map((period) => (
                        <th key={period}>{period.toUpperCase()}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {technicalSummary.rs_comparison.rows.map((row) => (
                      <tr key={row.key}>
                        <td>
                          <strong>{row.label}</strong>
                          {row.name ? <small style={{ display: "block" }}>{row.name}</small> : null}
                          {row.note ? <small style={{ display: "block" }}>{row.note}</small> : null}
                        </td>
                        {(technicalSummary.rs_comparison.periods || []).map((period) => (
                          <td key={period}>{formatPctChange(row.returns?.[period])}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="chart-note">{technicalSummary.rs_comparison.method}</div>
            </div>
          )}

          {technicalSummary?.rs_formula && (
            <div className="table-card rs-formula-audit">
              <h3>RS Formula Audit</h3>
              <div className="table-wrap">
                <table>
                  <tbody>
                    <tr><td><strong>Period Return</strong></td><td>{technicalSummary.rs_formula.period_return}</td></tr>
                    <tr><td><strong>Relative Return</strong></td><td>{technicalSummary.rs_formula.relative_return}</td></tr>
                    <tr><td><strong>Editable weights affect Relative Return?</strong></td><td>{technicalSummary.rs_formula.relative_return_uses_editable_weights ? "Yes" : "No"}</td></tr>
                    <tr><td><strong>Stock Percentile</strong></td><td>{technicalSummary.rs_formula.stock_percentile}</td></tr>
                    <tr><td><strong>Percentile Denominator</strong></td><td>{Number(technicalSummary.rs_formula.stock_percentile_denominator || (exchange === "US" ? 6000 : 5500)).toLocaleString()} stocks</td></tr>
                    <tr><td><strong>Final RS Score</strong></td><td>{technicalSummary.rs_formula.final_rs_score}</td></tr>
                  </tbody>
                </table>
              </div>
              <div className="chart-note">Changing RS weightage changes only the Final RS Score contribution. Raw stock return, benchmark return and Relative Return remain unchanged.</div>
              {technicalSummary?.rs_universe && !technicalSummary.rs_universe.complete && (
                <div className="provider-warning" style={{ marginTop: 10 }}>
                  RS universe coverage: {Number(technicalSummary.rs_universe.scored_stocks_available || 0).toLocaleString()} / {Number(technicalSummary.rs_universe.target_size || (exchange === "US" ? 6000 : 5500)).toLocaleString()} scored stocks.
                  The client-required percentile denominator remains fixed at {exchange === "US" ? "6,000 for US" : "5,500 for the Indian NSE/BSE universe"}, so the displayed RS score is provisional until the stored comparison universe is populated.
                </div>
              )}
            </div>
          )}

          <div className="chart-note">
            RS line = stock price / broad-market benchmark, rebased to 100 for charting only. Relative Return = Stock Return % - Benchmark Return % and is independent of the editable RS weights. The weights change only the Final RS Score. Each stock percentile uses the client-required market universe: {exchange === "US" ? "6,000 US stocks" : "5,500 Indian stocks (NSE + BSE)"}. Formula: [(stocks with lower relative return) + 0.5 × (stocks with equal relative return)] × 100 / {exchange === "US" ? "6000" : "5500"}. Final RS Score uses the enabled weighted percentile components. Default period weights remain 1W×0.30 + 1M×0.25 + 3M×0.20 + 6M×0.15 + 12M×0.10. 2W, 2M, and Sector RS are optional with default weight 0.
          </div>
          {technicalSummary?.rs_available && relativeStrengthChartData.length > 1 ? (
            <ResponsiveContainer width="100%" height={230}>
              <LineChart data={relativeStrengthChartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" minTickGap={35} />
                <YAxis domain={["auto", "auto"]} />
                <Tooltip formatter={(value) => [Number(value).toFixed(2), "RS"]} />
                <Line type="monotone" dataKey="rs" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="provider-warning">Relative Strength is unavailable because verified benchmark overlap is insufficient. RS is excluded from the ranking until benchmark data is available.</div>
          )}
        </section>

        {technicalSummary && (
          <section className="fundamental-section">
            <h2>Technical Screening Summary</h2>
            <div className="fundamental-grid">
              <div className="metric">
                <span>RS Rating vs {technicalSummary.rs_benchmark || "Benchmark"}</span>
                <strong>{technicalSummary.rs_available ? technicalSummary.rs_rating : "N/A"}</strong>
                <small>{["1w","2w","1m","2m","3m","6m","1y","sector"].filter((k) => rsVisibility[k] !== false).map((k) => `${k === "sector" ? "Sector RS" : k.toUpperCase()} ${rsWeights[k]}%`).join(" • ")}</small>
              </div>
              <div className="metric"><span>EMA Alignment</span><strong>{technicalSummary.ema_alignment}</strong></div>
              <div className="metric"><span>{timeframe === "daily" ? "20-Day Avg Volume" : "20-Period Avg Volume"}</span><strong>{technicalSummary.average_volume_20 != null ? Number(technicalSummary.average_volume_20).toLocaleString() : "-"}</strong></div>
              <div className="metric"><span>Volume Ratio</span><strong>{technicalSummary.volume_ratio ?? "-"}</strong></div>
              <div className="metric"><span>ADR (20D)</span><strong>{technicalSummary.adr_20 ?? "-"}</strong><small>20-session average of High - Low</small></div>
              <div className="metric"><span>ADR % (20D)</span><strong>{technicalSummary.adr_percent != null ? `${technicalSummary.adr_percent}%` : "-"}</strong><small>20-session avg of (High-Low)/Low</small></div>
              <div className="metric"><span>ATR (14)</span><strong>{technicalSummary.atr_14 ?? "-"}</strong></div>
              <div className="metric"><span>ATR %</span><strong>{technicalSummary.atr_percent != null ? `${technicalSummary.atr_percent}%` : "-"}</strong></div>
              <div className="metric"><span>BB Width</span><strong>{technicalSummary.bollinger_width_percent != null ? `${technicalSummary.bollinger_width_percent}%` : "-"}</strong></div>
              <div className="metric"><span>{timeframe === "daily" ? "20-Day Range" : "20-Period Range"}</span><strong>{technicalSummary.range_20d_percent != null ? `${technicalSummary.range_20d_percent}%` : "-"}</strong></div>
              <div className="metric"><span>Distance from 52W High</span><strong>{technicalSummary.distance_from_52w_high_percent != null ? `${technicalSummary.distance_from_52w_high_percent}%` : "-"}</strong></div>
              <div className="metric"><span>Pivot</span><strong>{technicalSummary.pivot ?? "-"}</strong></div>
              <div className="metric"><span>Breakout Status</span><strong>{technicalSummary.breakout_status}</strong></div>
              <div className="metric"><span>Breakout Strength</span><strong>{technicalSummary.breakout_strength != null ? `${technicalSummary.breakout_strength}/100` : "-"}</strong></div>
              <div className="metric"><span>Gap</span><strong>{technicalSummary.gap_percent != null ? `${technicalSummary.gap_percent}%` : "-"}</strong><small>{technicalSummary.gap_classification}</small></div>
              <div className="metric"><span>VCP Stage</span><strong>{technicalSummary.vcp_stage}</strong></div>
              <div className="metric"><span>Std. Deviation Contraction</span><strong>{technicalSummary.vcp_standard_deviation_contraction == null ? "-" : technicalSummary.vcp_standard_deviation_contraction ? "Yes" : "No"}</strong></div>
              <div className="metric"><span>Volume Contraction</span><strong>{technicalSummary.vcp_volume_contraction == null ? "-" : technicalSummary.vcp_volume_contraction ? "Yes" : "No"}</strong></div>
              <div className="metric"><span>Pattern</span><strong>{technicalSummary.pattern}</strong></div>
            </div>

            {technicalSummary.vcp_contractions?.length > 0 && (
              <>
                <h3>VCP Contraction Detail</h3>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr><th>Contraction</th><th>Price Depth</th><th>ATR %</th><th>Std Dev %</th><th>Avg Volume</th></tr>
                    </thead>
                    <tbody>
                      {technicalSummary.vcp_contractions.map((item, index) => (
                        <tr key={index}>
                          <td>{index + 1}</td>
                          <td>{item.depth_percent != null ? `${Number(item.depth_percent).toFixed(2)}%` : "-"}</td>
                          <td>{item.atr_percent != null ? `${Number(item.atr_percent).toFixed(2)}%` : "-"}</td>
                          <td>{item.standard_deviation_percent != null ? `${Number(item.standard_deviation_percent).toFixed(2)}%` : "-"}</td>
                          <td>{item.average_volume != null ? Number(item.average_volume).toLocaleString() : "-"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}

            <h3>Volume Delivery %</h3>
            {technicalSummary.volume_delivery?.available ? (
              <div className="fundamental-grid">
                {[
                  ["Day", technicalSummary.volume_delivery.day],
                  ["Weekly", technicalSummary.volume_delivery.weekly],
                  ["Monthly", technicalSummary.volume_delivery.monthly],
                ].map(([label, item]) => (
                  <div className="metric" key={label}>
                    <span>{label}</span>
                    <strong>{item?.percent != null ? `${Number(item.percent).toFixed(2)}%` : "-"}</strong>
                    <small>Delivered {item?.delivered_quantity != null ? Number(item.delivered_quantity).toLocaleString() : "-"} / Traded {item?.traded_quantity != null ? Number(item.traded_quantity).toLocaleString() : "-"}</small>
                  </div>
                ))}
              </div>
            ) : (
              <div className="provider-warning">{technicalSummary.volume_delivery?.note || "Delivery percentage is unavailable from the current exchange provider."}</div>
            )}

            <h3>EMA Alignment Values</h3>
            <div className="fundamental-grid">
              {[20, 30, 50, 100, 150, 200].map((period) => (
                <div className="metric" key={period}>
                  <span>EMA {period}</span>
                  <strong>{technicalSummary.ema?.[String(period)] ?? "-"}</strong>
                </div>
              ))}
            </div>
            <div className="chart-note">{technicalSummary.criteria_note}</div>
            <div className="chart-note">{technicalSummary.rs_note}</div>
          </section>
        )}

        {indicators && (
          <section className="fundamental-section">
            <h2>Technical Indicators</h2>

            <div className="indicator-settings">
              <div>
                <label>SMA Short</label>
                <input
                  type="number"
                  min="2"
                  value={smaShort}
                  onChange={(e) => setSmaShort(Number(e.target.value))}
                />
              </div>

              <div>
                <label>SMA Long</label>
                <input
                  type="number"
                  min="2"
                  value={smaLong}
                  onChange={(e) => setSmaLong(Number(e.target.value))}
                />
              </div>

              <div>
                <label>RSI Period</label>
                <input
                  type="number"
                  min="2"
                  value={rsiPeriod}
                  onChange={(e) => setRsiPeriod(Number(e.target.value))}
                />
              </div>

              <button onClick={loadIndicators}>
                Apply Indicators
              </button>
            </div>

            <div className="fundamental-grid">
              <div className="metric">
                <span>SMA {indicators.settings?.sma_short ?? smaShort}</span>
                <strong>{indicators.sma_short ?? "-"}</strong>
              </div>

              <div className="metric">
                <span>SMA {indicators.settings?.sma_long ?? smaLong}</span>
                <strong>{indicators.sma_long ?? "-"}</strong>
              </div>

              <div className="metric">
                <span>EMA {indicators.settings?.sma_short ?? smaShort}</span>
                <strong>{indicators.ema_short ?? "-"}</strong>
              </div>

              <div className="metric">
                <span>EMA {indicators.settings?.sma_long ?? smaLong}</span>
                <strong>{indicators.ema_long ?? "-"}</strong>
              </div>

              <div className="metric">
                <span>EMA 150</span>
                <strong>{indicators.ema_150 ?? "-"}</strong>
              </div>

              <div className="metric">
                <span>EMA 200</span>
                <strong>{indicators.ema_200 ?? "-"}</strong>
              </div>

              <div className="metric">
                <span>RSI {indicators.settings?.rsi_period ?? rsiPeriod}</span>
                <strong>{indicators.rsi ?? "-"}</strong>
              </div>
            </div>
          </section>
        )}

        {fundamentals?.fundamentals && (
          <section className="fundamental-section">
            <h2>{exchange === "US" ? "Fundamentals & Ownership" : "Fundamentals"}</h2>
            <div className="chart-note">
              {exchange === "US"
                ? "US fundamentals are refreshed automatically from the configured provider, with SEC EDGAR shown separately when available."
                : `Indian fundamentals for ${exchange} are refreshed automatically from the configured provider. The same fundamental ranking filters are applied to Indian and US stocks; unavailable fields remain N/A.`}
            </div>

            <div className="fundamental-grid">
              <div className="metric">
                <span>Market Cap</span>
                <strong>
                  {formatMarketMoney(fundamentals.fundamentals.market_cap, exchange)}
                </strong>
              </div>

              <div className="metric">
                <span>EPS</span>
                <strong>
                  {fundamentals.fundamentals.trailing_eps ?? "-"}
                </strong>
              </div>

              <div className="metric">
                <span>Forward EPS</span>
                <strong>
                  {fundamentals.fundamentals.forward_eps ?? "-"}
                </strong>
              </div>

              <div className="metric">
                <span>Revenue</span>
                <strong>
                  {formatMarketMoney(fundamentals.fundamentals.revenue, exchange)}
                </strong>
              </div>

              <div className="metric">
                <span>Net Income</span>
                <strong>
                  {formatMarketMoney(fundamentals.fundamentals.net_income, exchange)}
                </strong>
              </div>

              <div className="metric">
                <span>Profit Margin</span>
                <strong>
                  {fundamentals.fundamentals.profit_margin != null
                    ? `${(fundamentals.fundamentals.profit_margin * 100).toFixed(2)}%`
                    : "-"}
                </strong>
              </div>

              <div className="metric">
                <span>ROE</span>
                <strong>
                  {fundamentalHistory?.annual?.[0]?.roe != null
                    ? `${fundamentalHistory.annual[0].roe}%`
                    : fundamentals.fundamentals.return_on_equity != null
                    ? `${(fundamentals.fundamentals.return_on_equity * 100).toFixed(2)}%`
                    : "-"}
                </strong>
              </div>

              <div className="metric">
                <span>ROA</span>
                <strong>
                  {fundamentalHistory?.annual?.[0]?.roa != null
                    ? `${fundamentalHistory.annual[0].roa}%`
                    : fundamentals.fundamentals.return_on_assets != null
                    ? `${(fundamentals.fundamentals.return_on_assets * 100).toFixed(2)}%`
                    : "-"}
                </strong>
              </div>

              <div className="metric">
                <span>ROCE</span>
                <strong>
                  {fundamentalHistory?.annual?.[0]?.roce != null
                    ? `${fundamentalHistory.annual[0].roce}%`
                    : "-"}
                </strong>
              </div>

              {exchange === "US" && <>
              <div className="metric">
                <span>Insider Ownership</span>
                <strong>
                  {fundamentals.ownership.insider_percent != null
                    ? `${(fundamentals.ownership.insider_percent * 100).toFixed(2)}%`
                    : "-"}
                </strong>
              </div>

              <div className="metric">
                <span>Institution Ownership</span>
                <strong>
                  {fundamentals.ownership.institution_percent != null
                    ? `${(fundamentals.ownership.institution_percent * 100).toFixed(2)}%`
                    : "-"}
                </strong>
              </div>

              <div className="metric">
                <span>Shares Outstanding</span>
                <strong>
                  {fundamentals.ownership.shares_outstanding != null
                    ? `${(fundamentals.ownership.shares_outstanding / 1e9).toFixed(2)}B`
                    : "-"}
                </strong>
              </div>

              <div className="metric">
                <span>Float Shares</span>
                <strong>
                  {fundamentals.ownership.float_shares != null
                    ? `${(fundamentals.ownership.float_shares / 1e9).toFixed(2)}B`
                    : "-"}
                </strong>
              </div>
              </>}
            </div>
          </section>
        )}

        
        {exchange !== "US" && (
          <section className="fundamental-section">
            <h2>Indian Shareholding History</h2>
            {indiaShareholding ? (
              <>
                <div className="chart-note">{indiaShareholding.provider_note}</div>
                {indiaShareholding.latest && (
                  <div className="metrics-grid" style={{ marginTop: "14px" }}>
                    {[
                      ["Promoter", "promoter"],
                      ["FII", "fii"],
                      ["DII", "dii"],
                      ["Mutual Funds", "mutual_funds"],
                      ["Public", "public"],
                    ].map(([label, key]) => (
                      <div className="metric" key={key}>
                        <span>{label}</span>
                        <strong>{indiaShareholding.latest[key] != null ? `${Number(indiaShareholding.latest[key]).toFixed(2)}%` : "Unavailable"}</strong>
                        <small>{indiaShareholding.latest[`${key}_change`] != null ? `QoQ change ${formatPctChange(indiaShareholding.latest[`${key}_change`])}` : "No separate change value"}</small>
                      </div>
                    ))}
                  </div>
                )}

                <h3>Quarterly Ownership Details</h3>
                <div className="history-table-wrapper">
                  <table className="history-table ownership-matrix-table">
                    <thead>
                      <tr>
                        <th>Holder</th>
                        {(indiaShareholding.history || []).slice(0, 4).reverse().map((row, index) => (
                          <th key={`${row.period}-${index}`}>{row.period}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {[
                        ["FII", "fii"],
                        ["DII", "dii"],
                        ["MF", "mutual_funds"],
                        ["Promoter", "promoter"],
                        ["Others / Public", "public"],
                      ].map(([label, key]) => (
                        <tr key={key}>
                          <td><strong>{label}</strong></td>
                          {(indiaShareholding.history || []).slice(0, 4).reverse().map((row, index) => (
                            <td key={`${key}-${row.period}-${index}`}>
                              {row[key] != null ? `${Number(row[key]).toFixed(2)}%` : "-"}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <h3>Quarterly Ownership Changes</h3>
                <div className="history-table-wrapper">
                  <table className="history-table">
                    <thead>
                      <tr>
                        <th>Quarter</th><th>Promoter</th><th>QoQ pp Change</th><th>FII</th><th>QoQ pp Change</th><th>DII</th><th>QoQ pp Change</th><th>MF</th><th>QoQ pp Change</th><th>Public</th><th>QoQ pp Change</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(indiaShareholding.history || []).map((row, index) => (
                        <tr key={index}>
                          <td>{row.period}</td>
                          <td>{row.promoter != null ? `${Number(row.promoter).toFixed(2)}%` : "-"}</td>
                          <td>{formatPctChange(row.promoter_change)}</td>
                          <td>{row.fii != null ? `${Number(row.fii).toFixed(2)}%` : "-"}</td>
                          <td>{formatPctChange(row.fii_change)}</td>
                          <td>{row.dii != null ? `${Number(row.dii).toFixed(2)}%` : "-"}</td>
                          <td>{formatPctChange(row.dii_change)}</td>
                          <td>{row.mutual_funds != null ? `${Number(row.mutual_funds).toFixed(2)}%` : "-"}</td>
                          <td>{formatPctChange(row.mutual_funds_change)}</td>
                          <td>{row.public != null ? `${Number(row.public).toFixed(2)}%` : "-"}</td>
                          <td>{formatPctChange(row.public_change)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="chart-note" style={{ marginTop: "10px" }}>Source: {indiaShareholding.source}. The first table follows the client reference layout with report dates across columns. Values come from the live public provider; example handwritten percentages are not hard-coded. Change columns below are quarter-over-quarter percentage-point changes.</div>
              </>
            ) : (
              <div className="provider-warning">Indian shareholding history could not be loaded from the public provider right now. Technical and price data remain available.</div>
            )}
          </section>
        )}

{exchange === "US" && ownershipDetails && (() => {
          const summary = ownershipDetails.current_summary || {};
          const institutionCurrent = summary.institutional_percent != null
            ? Number(summary.institutional_percent)
            : (fundamentals?.ownership?.institution_percent != null ? Number(fundamentals.ownership.institution_percent) * 100 : null);
          const insiderCurrent = summary.insider_percent != null
            ? Number(summary.insider_percent)
            : (fundamentals?.ownership?.insider_percent != null ? Number(fundamentals.ownership.insider_percent) * 100 : null);
          const retailCurrent = summary.retail_public_percent != null
            ? Number(summary.retail_public_percent)
            : (institutionCurrent != null && insiderCurrent != null ? Math.max(0, 100 - institutionCurrent - insiderCurrent) : null);

          const ownershipRows = [
            { label: "Institutional Ownership", current: institutionCurrent, source: "Yahoo aggregate ownership" },
            { label: "Insider Ownership", current: insiderCurrent, source: "Yahoo aggregate ownership" },
            { label: "Retail / Public Investors", current: retailCurrent, source: "Derived remainder: 100% - institutional - insider" },
          ];

          return (
            <section className="fundamental-section">
              <h2>Ownership Detail</h2>
              <div className="chart-note">
                US ownership uses US-market categories. Promoter, FII and DII headings are not used for US stocks.
                Retail/Public is shown only as the transparent remainder when both aggregate Institutional and Insider ownership are available.
              </div>

              {ownershipDetails.provider_note && (
                <div className="provider-warning">{ownershipDetails.provider_note}</div>
              )}

              <h3>Current US Ownership</h3>
              <div className="history-table-wrapper">
                <table className="history-table ownership-matrix-table">
                  <thead>
                    <tr><th>Ownership Type</th><th>Current</th><th>Source / Method</th></tr>
                  </thead>
                  <tbody>
                    {ownershipRows.map((row) => (
                      <tr key={row.label}>
                        <td><strong>{row.label}</strong></td>
                        <td>{row.current != null && Number.isFinite(row.current) ? `${row.current.toFixed(2)}%` : "N/A"}</td>
                        <td>{row.source}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="chart-note">
                Historical Yahoo top-holder rows are not treated as total-market ownership history. This avoids presenting a sum of a few reported holders as the full institutional/public market percentage.
              </div>
            </section>
          );
        })()}

        {exchange === "US" && secEdgar && (
          <section className="fundamental-section">
            <h2>SEC EDGAR — Official US Filings</h2>
            <div className="chart-note">
              {secEdgar.note || "Official SEC EDGAR filing metadata and XBRL company facts."}
            </div>
            {Array.isArray(secEdgar.warnings) && secEdgar.warnings.length > 0 && (
              <div className="provider-warning">
                {secEdgar.warnings.join(" ")}
              </div>
            )}
            <div className="fundamental-grid">
              <div className="metric"><span>Company</span><strong>{secEdgar.company_name || symbol}</strong></div>
              <div className="metric"><span>CIK</span><strong>{secEdgar.cik || "-"}</strong></div>
              <div className="metric"><span>Filings Source</span><strong>{secEdgar.source || "SEC EDGAR"}</strong></div>
              <div className="metric"><span>Fundamentals Source</span><strong>{secEdgar.companyfacts_source || "-"}</strong></div>
            </div>

            <h3>Recent SEC Filings</h3>
            <div className="history-table-wrapper">
              <table className="history-table">
                <thead>
                  <tr><th>Form</th><th>Filing Date</th><th>Report Date</th><th>Description</th><th>EDGAR</th></tr>
                </thead>
                <tbody>
                  {(secEdgar.filings || []).map((filing, index) => (
                    <tr key={`${filing.accession_number || filing.form}-${index}`}>
                      <td><strong>{filing.form || "-"}</strong></td>
                      <td>{filing.filing_date || "-"}</td>
                      <td>{filing.report_date || "-"}</td>
                      <td>{filing.description || filing.primary_document || "-"}</td>
                      <td>{filing.url ? <a href={filing.url} target="_blank" rel="noreferrer">Open filing</a> : "-"}</td>
                    </tr>
                  ))}
                  {!(secEdgar.filings || []).length && (
                    <tr><td colSpan="5">No recent supported SEC filing types were returned.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
            <div className="chart-note">SEC EDGAR is used for official US filing/XBRL data. It does not replace OHLCV price data, and unavailable ownership classifications are not fabricated.</div>
          </section>
        )}

        {exchange === "US" && !secEdgar && secEdgarError && (
          <section className="fundamental-section">
            <h2>SEC EDGAR — Official US Filings</h2>
            <div className="provider-warning">{secEdgarError}</div>
            <div className="chart-note">
              SEC EDGAR requires a backend SEC_USER_AGENT containing the application name and a real contact email. No SEC values are substituted when the official source is unavailable.
            </div>
          </section>
        )}

        {fundamentalHistory && (
          <section className="fundamental-section">
            <h2>Fundamental History ({exchange})</h2>
            {exchange !== "US" && (
              <div className="chart-note">
                The same quarterly and annual fundamental fields/filters used for US stocks are enabled for Indian stocks. Values come from the configured provider and missing values are not estimated.
              </div>
            )}

            <h3>Quarterly History ({Math.min(fundamentalHistory.quarterly?.length || 0, 12)}/12 available)</h3>
            <div className="history-table-wrapper">
              <table className="history-table">
                <thead>
                  <tr>
                    <th>Period</th>
                    <th>Sales</th>
                    <th>Sales QoQ</th>
                    <th>Sales YoY</th>
                    <th>PAT</th>
                    <th>PAT QoQ</th>
                    <th>PAT YoY</th>
                    <th>EPS</th>
                    <th>EPS QoQ</th>
                    <th>EPS YoY</th>
                    <th>EBIT</th>
                    <th>OPM</th>
                    <th>NPM</th>
                  </tr>
                </thead>

                <tbody>
                  {fundamentalHistory.quarterly?.slice(0, 12).map((row) => (
                    <tr key={row.period}>
                      <td>{row.period}</td>
                      <td>
                        {row.sales != null
                          ? formatMarketMoney(row.sales, exchange)
                          : "-"}
                      </td>
                      <td>
                        {row.qoq_sales != null ? `${row.qoq_sales}%` : "-"}
                      </td>
                      <td>{row.yoy_sales != null ? `${row.yoy_sales}%` : "-"}</td>
                      <td>
                        {row.pat != null
                          ? formatMarketMoney(row.pat, exchange)
                          : "-"}
                      </td>
                      <td>
                        {row.qoq_pat != null ? `${row.qoq_pat}%` : "-"}
                      </td>
                      <td>{row.yoy_pat != null ? `${row.yoy_pat}%` : "-"}</td>
                      <td>{row.eps ?? "-"}</td>
                      <td>
                        {row.qoq_eps != null ? `${row.qoq_eps}%` : "-"}
                      </td>
                      <td>{row.yoy_eps != null ? `${row.yoy_eps}%` : "-"}</td>
                      <td>
                        {row.ebit != null
                          ? formatMarketMoney(row.ebit, exchange)
                          : "-"}
                      </td>
                      <td>
                        {row.opm != null ? `${row.opm}%` : "-"}
                      </td>
                      <td>
                        {row.npm != null ? `${row.npm}%` : "-"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <h3>Quarterly Result Trends</h3>
            <div className="fundamental-chart-grid">
              <div className="fundamental-chart-card">
                <h4>Quarterly Sales</h4>
                <ResponsiveContainer width="100%" height={220}>
                  <LineChart data={[...(fundamentalHistory.quarterly || [])].slice(0, 12).reverse()}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="period" />
                    <YAxis tickFormatter={(value) => formatMarketMoney(value, exchange)} />
                    <Tooltip formatter={(value) => value != null ? formatMarketMoney(value, exchange) : "-"} />
                    <Line type="monotone" dataKey="sales" strokeWidth={2} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
              <div className="fundamental-chart-card">
                <h4>Quarterly EPS</h4>
                <ResponsiveContainer width="100%" height={220}>
                  <LineChart data={[...(fundamentalHistory.quarterly || [])].slice(0, 12).reverse()}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="period" />
                    <YAxis />
                    <Tooltip />
                    <Line type="monotone" dataKey="eps" strokeWidth={2} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
              <div className="fundamental-chart-card">
                <h4>Quarterly PAT</h4>
                <ResponsiveContainer width="100%" height={220}>
                  <LineChart data={[...(fundamentalHistory.quarterly || [])].slice(0, 12).reverse()}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="period" />
                    <YAxis tickFormatter={(value) => formatMarketMoney(value, exchange)} />
                    <Tooltip formatter={(value) => value != null ? formatMarketMoney(value, exchange) : "-"} />
                    <Line type="monotone" dataKey="pat" strokeWidth={2} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
                    <div className="fundamental-chart-card">
                <h4>Quarterly EBIT</h4>
                <ResponsiveContainer width="100%" height={220}>
                  <LineChart data={[...(fundamentalHistory.quarterly || [])].slice(0, 12).reverse()}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="period" />
                    <YAxis tickFormatter={(value) => formatMarketMoney(value, exchange)} />
                    <Tooltip formatter={(value) => value != null ? formatMarketMoney(value, exchange) : "-"} />
                    <Line type="monotone" dataKey="ebit" strokeWidth={2} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
              <div className="fundamental-chart-card">
                <h4>Quarterly OPM</h4>
                <ResponsiveContainer width="100%" height={220}>
                  <LineChart data={[...(fundamentalHistory.quarterly || [])].slice(0, 12).reverse()}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="period" />
                    <YAxis tickFormatter={(value) => `${value}%`} />
                    <Tooltip formatter={(value) => value != null ? `${value}%` : "-"} />
                    <Line type="monotone" dataKey="opm" strokeWidth={2} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
              <div className="fundamental-chart-card">
                <h4>Quarterly NPM</h4>
                <ResponsiveContainer width="100%" height={220}>
                  <LineChart data={[...(fundamentalHistory.quarterly || [])].slice(0, 12).reverse()}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="period" />
                    <YAxis tickFormatter={(value) => `${value}%`} />
                    <Tooltip formatter={(value) => value != null ? `${value}%` : "-"} />
                    <Line type="monotone" dataKey="npm" strokeWidth={2} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>

            <h3>Previous 7 Years ({Math.min(fundamentalHistory.annual?.filter((row) => row.sales != null || row.pat != null || row.eps != null).length || 0, 7)}/7 available)</h3>
            <div className="history-table-wrapper">
              <table className="history-table">
                <thead>
                  <tr>
                    <th>Period</th>
                    <th>Sales</th>
                    <th>Sales YoY</th>
                    <th>PAT</th>
                    <th>PAT YoY</th>
                    <th>EPS</th>
                    <th>EPS YoY</th>
                    <th>EBIT</th>
                    <th>OPM</th>
                    <th>NPM</th>
                    <th>Debt/Equity</th>
                    <th>Operating Cash Flow</th>
                    <th>Free Cash Flow</th>
                    <th>ROE</th>
                    <th>ROA</th>
                    <th>ROCE</th>
                    <th>Cash Flow/Share</th>
                  </tr>
                </thead>

                <tbody>
                  {fundamentalHistory.annual?.slice(0, 7).map((row) => (
                    <tr key={row.period}>
                      <td>{row.period}</td>
                      <td>
                        {row.sales != null
                          ? formatMarketMoney(row.sales, exchange)
                          : "-"}
                      </td>
                      <td>{row.yoy_sales != null ? `${row.yoy_sales}%` : "-"}</td>
                      <td>
                        {row.pat != null
                          ? formatMarketMoney(row.pat, exchange)
                          : "-"}
                      </td>
                      <td>{row.yoy_pat != null ? `${row.yoy_pat}%` : "-"}</td>
                      <td>{row.eps ?? "-"}</td>
                      <td>{row.yoy_eps != null ? `${row.yoy_eps}%` : "-"}</td>
                      <td>
                        {row.ebit != null
                          ? formatMarketMoney(row.ebit, exchange)
                          : "-"}
                      </td>
                      <td>
                        {row.opm != null ? `${row.opm}%` : "-"}
                      </td>
                      <td>
                        {row.npm != null ? `${row.npm}%` : "-"}
                      </td>
                      <td>
                        {row.debt_to_equity != null
                          ? row.debt_to_equity
                          : "-"}
                      </td>

                      <td>
                        {row.operating_cash_flow != null
                          ? formatMarketMoney(row.operating_cash_flow, exchange)
                          : "-"}
                      </td>
                      <td>
                        {row.free_cash_flow != null
                          ? formatMarketMoney(row.free_cash_flow, exchange)
                          : "-"}
                      </td>
                      <td>
                        {row.roe != null ? `${row.roe}%` : "-"}
                      </td>
                      <td>
                        {row.roa != null ? `${row.roa}%` : "-"}
                      </td>
                      <td>
                        {row.roce != null ? `${row.roce}%` : "-"}
                      </td>

                      <td>
                        {row.cash_flow_per_share != null
                          ? formatMarketMoney(row.cash_flow_per_share, exchange)
                          : "-"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <h3>3-Year CAGR</h3>

            <div className="fundamental-grid">
              <div className="metric">
                <span>Sales CAGR</span>
                <strong>
                  {fundamentalHistory.cagr_3y?.sales != null
                    ? `${fundamentalHistory.cagr_3y.sales}%`
                    : "-"}
                </strong>
              </div>

              <div className="metric">
                <span>PAT CAGR</span>
                <strong>
                  {fundamentalHistory.cagr_3y?.pat != null
                    ? `${fundamentalHistory.cagr_3y.pat}%`
                    : "-"}
                </strong>
              </div>

              <div className="metric">
                <span>EPS CAGR</span>
                <strong>
                  {fundamentalHistory.cagr_3y?.eps != null
                    ? `${fundamentalHistory.cagr_3y.eps}%`
                    : "-"}
                </strong>
              </div>
            </div>

            <h3>5-Year CAGR</h3>
            <div className="fundamental-grid">
              <div className="metric"><span>Sales CAGR</span><strong>{fundamentalHistory.cagr_5y?.sales != null ? `${fundamentalHistory.cagr_5y.sales}%` : "Unavailable"}</strong></div>
              <div className="metric"><span>PAT CAGR</span><strong>{fundamentalHistory.cagr_5y?.pat != null ? `${fundamentalHistory.cagr_5y.pat}%` : "Unavailable"}</strong></div>
              <div className="metric"><span>EPS CAGR</span><strong>{fundamentalHistory.cagr_5y?.eps != null ? `${fundamentalHistory.cagr_5y.eps}%` : "Unavailable"}</strong></div>
            </div>
            {(fundamentalHistory.cagr_5y?.sales == null || fundamentalHistory.cagr_5y?.pat == null || fundamentalHistory.cagr_5y?.eps == null) && (
              <div className="provider-warning">
                5-year CAGR requires six valid annual endpoints. The configured provider currently returns insufficient usable annual history for this stock, so unavailable values are not estimated.
              </div>
            )}

            {fundamentalHistory.source && (
              <div className="provider-note">
                Fundamental history source: {fundamentalHistory.source}. ROE = net income / period-end equity; ROA = net income / period-end assets; ROCE = EBIT / (assets - current liabilities).
              </div>
            )}

            <h3>Fundamental Trends</h3>

            <div className="fundamental-chart-grid">
              <div className="fundamental-chart-card">
                <h4>Sales Trend</h4>
                <ResponsiveContainer width="100%" height={250}>
                  <LineChart
                    data={[...(fundamentalHistory.annual || [])].reverse()}
                  >
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="period" />
                    <YAxis
                      tickFormatter={(value) => `${(value / 1e9).toFixed(0)}B`}
                    />
                    <Tooltip
                      formatter={(value) =>
                        value != null ? `$${(value / 1e9).toFixed(2)}B` : "-"
                      }
                    />
                    <Line
                      type="monotone"
                      dataKey="sales"
                      strokeWidth={2}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>

              <div className="fundamental-chart-card">
                <h4>EPS Trend</h4>
                <ResponsiveContainer width="100%" height={250}>
                  <LineChart
                    data={[...(fundamentalHistory.annual || [])].reverse()}
                  >
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="period" />
                    <YAxis />
                    <Tooltip />
                    <Line
                      type="monotone"
                      dataKey="eps"
                      strokeWidth={2}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>

              <div className="fundamental-chart-card">
                <h4>PAT Trend</h4>
                <ResponsiveContainer width="100%" height={250}>
                  <LineChart
                    data={[...(fundamentalHistory.annual || [])].reverse()}
                  >
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="period" />
                    <YAxis
                      tickFormatter={(value) => `${(value / 1e9).toFixed(0)}B`}
                    />
                    <Tooltip
                      formatter={(value) =>
                        value != null ? `$${(value / 1e9).toFixed(2)}B` : "-"
                      }
                    />
                    <Line
                      type="monotone"
                      dataKey="pat"
                      strokeWidth={2}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          </section>
        )}

        <section className="table-card">
          <h2>Recent Market Data</h2>

          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Open</th>
                  <th>High</th>
                  <th>Low</th>
                  <th>Close</th>
                  <th>Volume</th>
                </tr>
              </thead>

              <tbody>
                {!dataStale &&
                  [...data].reverse().slice(0, 10).map((row) => (
                    <tr key={row.date}>
                      <td>{new Date(`${String(row.date).slice(0, 10)}T00:00:00`).toLocaleDateString("en-US")}</td>
                      <td>{Number(row.open).toFixed(2)}</td>
                      <td>{Number(row.high).toFixed(2)}</td>
                      <td>{Number(row.low).toFixed(2)}</td>
                      <td>{Number(row.close).toFixed(2)}</td>
                      <td>{Number(row.volume).toLocaleString()}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </section>
      </main>
    </div>
  );
}

export default App;