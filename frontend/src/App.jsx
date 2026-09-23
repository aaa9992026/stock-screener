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

const chartLimitForTimeframe = (timeframe) => timeframe === "daily" ? 1040 : timeframe === "weekly" ? 260 : 240;

const formatPctChange = (value) => {
  if (value === null || value === undefined || value === "") return "-";
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "-";
  const prefix = numeric > 0 ? "+" : "";
  return `${prefix}${numeric.toFixed(2)}%`;
};

const defaultScoreWeights = { technical: 35, fundamental: 35, relative_strength: 15, ownership: 10 };
const defaultRsWeights = { "1w": 10, "2w": 0, "1m": 30, "2m": 20, "3m": 15, "6m": 15, "1y": 10 };
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
    bb_width: { weight: 10, threshold: 10 },
    atr5_lt20: { weight: 10 },
    atr10_lt20: { weight: 5 },
    rsi14: { weight: 0, enabled: false, lower: 30, preferred: 50, upper: 70 },
    volume10_lt20: { weight: 10 },
    volume20_lt40: { weight: 5 },
    distance52: { weight: 10, t1: 10, t2: 17, t3: 20, p1: 10, p2: 8, p3: 6, p4: 3 },
    ema20_gt50: { weight: 8 },
    ema50_gt150: { weight: 4 },
  },
  fundamental: {
    q_eps_yoy: { weight: 10, threshold: 30 },
    q_eps_rising: { weight: 4 },
    q_eps_yoy_rising: { weight: 6 },
    q_pat_yoy: { weight: 6, threshold: 30 },
    q_pat_rising: { weight: 4 },
    q_pat_yoy_rising: { weight: 6 },
    q_npm_yoy: { weight: 4, threshold: 20 },
    q_sales_yoy: { weight: 7, threshold: 30 },
    q_sales_rising: { weight: 4 },
    a_eps_yoy: { weight: 6, threshold: 20 },
    a_eps_rising: { weight: 4 },
    a_pat_yoy: { weight: 5, threshold: 20 },
    a_pat_rising: { weight: 4 },
    a_sales_yoy: { weight: 5, threshold: 20 },
    a_sales_rising: { weight: 4 },
    a_ocf_yoy: { weight: 4, threshold: 10 },
    a_npm_rising: { weight: 3 },
  },
  ownership: {
    promoter_qoq: { weight: 10, threshold: 0.3 },
    promoter_above: { weight: 8, threshold: 50 },
    promoter_rising: { weight: 5 },
    pledge: { weight: 5, t1: 5, t2: 10, t3: 15, t4: 20 },
    fii_qoq: { weight: 10, threshold: 0.3 },
    fii_rising: { weight: 10 },
    dii_mf_qoq: { weight: 10, threshold: 0.1 },
    dii_mf_rising: { weight: 10 },
    insider_activity: { weight: 10 },
  },
};

const handwrittenFactorMeta = {
  technical: [
    ["bb_width", "Upper BB - Lower BB", "BB width ≤ editable threshold", ["threshold"]],
    ["atr5_lt20", "5-day ATR% average < 20-day ATR% average", "ATR contraction", []],
    ["atr10_lt20", "10-day ATR% average < 20-day ATR% average", "ATR contraction", []],
    ["rsi14", "RSI (14)", "Handwritten RSI bands; exact point allocation is not fully legible in the supplied photo, so this factor is disabled by default until confirmed", ["lower", "preferred", "upper"]],
    ["volume10_lt20", "10-day volume average < 20-day volume average", "Volume contraction", []],
    ["volume20_lt40", "20-day volume average < 40-day volume average", "Longer-volume comparison", []],
    ["distance52", "Distance from 52-week high", "Handwritten 10 / 17 / 20% distance bands", ["t1", "t2", "t3"]],
    ["ema20_gt50", "20 EMA > 50 EMA", "EMA trend factor", []],
    ["ema50_gt150", "50 EMA > 150 EMA", "EMA trend factor", []],
  ],
  fundamental: [
    ["q_eps_yoy", "Latest quarter EPS (YoY)", "Latest quarterly EPS YoY growth", ["threshold"]],
    ["q_eps_rising", "Quarterly EPS rising", "Latest EPS > prior EPS > second-prior EPS", []],
    ["q_eps_yoy_rising", "Quarterly EPS YoY trend rising", "Latest YoY > prior YoY > second-prior YoY", []],
    ["q_pat_yoy", "Latest quarter PAT (YoY)", "Latest quarterly PAT YoY growth", ["threshold"]],
    ["q_pat_rising", "Quarterly PAT rising", "Latest PAT > prior PAT > second-prior PAT", []],
    ["q_pat_yoy_rising", "Quarterly PAT YoY trend rising", "Latest YoY > prior YoY > second-prior YoY", []],
    ["q_npm_yoy", "Quarterly Net Profit Margin growth (YoY)", "Latest NPM vs year-ago quarter", ["threshold"]],
    ["q_sales_yoy", "Latest quarter Sales (YoY)", "Latest quarterly sales YoY growth", ["threshold"]],
    ["q_sales_rising", "Quarterly Sales trend rising", "Latest sales > prior sales > second-prior sales", []],
    ["a_eps_yoy", "Latest year EPS (YoY)", "Latest annual EPS growth", ["threshold"]],
    ["a_eps_rising", "Annual EPS trend rising", "Latest EPS > prior year > second-prior year", []],
    ["a_pat_yoy", "Latest year PAT (YoY)", "Latest annual PAT growth", ["threshold"]],
    ["a_pat_rising", "Annual PAT trend rising", "Latest PAT > prior year > second-prior year", []],
    ["a_sales_yoy", "Latest year Sales (YoY)", "Latest annual sales growth", ["threshold"]],
    ["a_sales_rising", "Annual Sales trend rising", "Latest sales > prior year > second-prior year", []],
    ["a_ocf_yoy", "Cash flow from operating activities (YoY)", "Latest annual operating cash flow growth > editable value", ["threshold"]],
    ["a_npm_rising", "Annual Net Profit Margin rising", "Latest year net profit margin > prior year net profit margin", []],
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
  const [smaShort, setSmaShort] = useState(20);
  const [smaLong, setSmaLong] = useState(50);
  const [rsiPeriod, setRsiPeriod] = useState(14);
  const chartContainerRef = useRef(null);
  const symbolSearchRef = useRef(null);
  const [suggestions, setSuggestions] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [benchmark, setBenchmark] = useState(null);
  const [dashboard, setDashboard] = useState(null);
  const [technicalSummary, setTechnicalSummary] = useState(null);
  const [ownershipDetails, setOwnershipDetails] = useState(null);
  const [indiaShareholding, setIndiaShareholding] = useState(null);
  const [chartInfo, setChartInfo] = useState(null);
  const [scoreWeights, setScoreWeights] = useState(() => {
    try {
      const saved = JSON.parse(localStorage.getItem("scoreWeights")) || {};
      return {
        technical: Number(saved.technical ?? defaultScoreWeights.technical),
        fundamental: Number(saved.fundamental ?? defaultScoreWeights.fundamental),
        relative_strength: Number(saved.relative_strength ?? defaultScoreWeights.relative_strength),
        ownership: Number(saved.ownership ?? defaultScoreWeights.ownership),
      };
    } catch {
      return { ...defaultScoreWeights };
    }
  });
  const [rsWeights, setRsWeights] = useState(() => readLocalObject("rsWeights", defaultRsWeights));
  const [rsVisibility, setRsVisibility] = useState(() => readLocalObject("rsVisibility", { "1w": true, "2w": true, "1m": true, "2m": true, "3m": true, "6m": true, "1y": true }));
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
  const [chartOverlays, setChartOverlays] = useState({
    ema: true, sma: true, bollinger: true, volume: true, eps: true, rs: true
  });

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

  const loadDashboard = async () => {
    try {
      const params = new URLSearchParams({
        exchange,
        technical_weight: scoreWeights.technical,
        fundamental_weight: scoreWeights.fundamental,
        relative_strength_weight: scoreWeights.relative_strength,
        ownership_weight: scoreWeights.ownership,
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
      });
      const res = await axios.get(`${API}/market/dashboard/${symbol}?${params.toString()}`);
      setDashboard(res.data);
    } catch {
      setDashboard(null);
    }
  };

  const loadTechnicalSummary = async () => {
    try {
      const res = await axios.get(
        `${API}/market/technical-summary/${symbol}?exchange=${exchange}&timeframe=${timeframe}` +
        `&rs_1w_weight=${rsWeights["1w"]}&rs_2w_weight=${rsWeights["2w"]}&rs_1m_weight=${rsWeights["1m"]}&rs_2m_weight=${rsWeights["2m"]}` +
        `&rs_3m_weight=${rsWeights["3m"]}&rs_6m_weight=${rsWeights["6m"]}&rs_1y_weight=${rsWeights["1y"]}`
      );
      setTechnicalSummary(res.data);
    } catch {
      setTechnicalSummary(null);
    }
  };

  const loadOwnershipDetails = async () => {
    if (exchange !== "US") {
      setOwnershipDetails(null);
      return;
    }
    try {
      const res = await axios.get(
        `${API}/market/ownership-details/${symbol}?exchange=${exchange}`
      );
      setOwnershipDetails(res.data);
    } catch {
      setOwnershipDetails(null);
    }
  };

  const loadIndiaShareholding = async () => {
    if (exchange === "US") {
      setIndiaShareholding(null);
      return;
    }
    try {
      const res = await axios.get(
        `${API}/market/india-shareholding/${symbol}?exchange=${exchange}&limit=8`
      );
      setIndiaShareholding(res.data);
    } catch {
      setIndiaShareholding(null);
    }
  };

  const loadIndicators = async () => {
    try {
      const res = await axios.get(
        `${API}/market/indicators/${symbol}?exchange=${exchange}&timeframe=${timeframe}&sma_short=${smaShort}&sma_long=${smaLong}&rsi_period=${rsiPeriod}`
      );

      setIndicators(res.data);
    } catch {
      setIndicators(null);
    }
  };

  const searchCompanies = async (value) => {
    setSymbol(value.toUpperCase());

    if (value.trim().length < 2) {
      setSuggestions([]);
      setShowSuggestions(false);
      return;
    }

    try {
      const res = await axios.get(
        `${API}/companies/search?q=${encodeURIComponent(value)}&exchange=${exchange}&limit=10`
      );

      setSuggestions(res.data);
      setShowSuggestions(true);
    } catch {
      setSuggestions([]);
      setShowSuggestions(false);
    }
  };

  const loadFundamentals = async () => {
    if (exchange !== "US") {
      setFundamentals(null);
      return;
    }

    try {
      // Refresh first so an older empty DB row (for example BA) does not keep
      // rendering dashes after provider data has become available.
      const res = await axios.post(
        `${API}/market/fundamentals/${symbol}?exchange=US`
      );

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
    } catch {
      try {
        const res = await axios.get(
          `${API}/market/fundamentals/${symbol}?exchange=US`
        );
        setFundamentals(res.data);
      } catch {
        setFundamentals(null);
      }
    }
  };

  const loadFundamentalHistory = async () => {
    try {
      const res = await axios.get(
        `${API}/market/fundamentals-history/${symbol}?exchange=${exchange}`
      );

      setFundamentalHistory(res.data);
    } catch {
      setFundamentalHistory(null);
    }
  };

  const loadChart = async () => {
    try {
      setLoading(true);

      const res = await axios.get(
        `${API}/market/chart/${symbol}?exchange=${exchange}&timeframe=${timeframe}&limit=${chartLimitForTimeframe(timeframe)}`
      );

      const rows = res.data.data || [];

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

      setData([]);
      setDataStale(true);
      setDataStatus("stale");

      setMessage(
        err.response?.data?.detail ||
        "Market data could not be loaded."
      );
    } finally {
      setLoading(false);
    }
  };

  const loadBenchmark = async () => {
    try {
      const res = await axios.get(
        `${API}/market/benchmark/${exchange}?limit=1400`
      );

      setBenchmark(res.data);
    } catch {
      setBenchmark(null);
    }
  };

  const refreshData = async () => {
    setShowSuggestions(false);
    setSuggestions([]);
    setLoading(true);

    try {
      const res = await axios.post(
        `${API}/market/refresh/${symbol}?exchange=${exchange}`
      );

      setDataStale(false);

      setDataStatus("fresh");
      setLastUpdated(new Date());

      setMessage(
        `Updated successfully: ${res.data.added} added, ${res.data.updated} updated`
      );

      await loadChart();
      await loadIndicators();
      await loadDashboard();
      await loadTechnicalSummary();

    } catch (err) {
      console.error("Refresh error:", err);

      const detail =
        err.response?.data?.detail ??
        "Refresh failed. Data may be unavailable or stale.";

      setDataStale(true);
      setDataStatus("stale");
      setMessage(detail);

    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadChart();
    loadIndicators();
    loadBenchmark();
    loadDashboard();
    loadTechnicalSummary();
    loadOwnershipDetails();
    loadIndiaShareholding();

    if (exchange === "US") {
      loadFundamentals();
      loadFundamentalHistory();
    } else {
      setFundamentals(null);
      setFundamentalHistory(null);
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
    // The handwritten RSI thresholds are visible, but the exact point allocation
    // is not fully legible in the supplied photo.  Do not invent it.
    const rsiScore = null;
    const technicalComponent = factorScore("technical", {
      bb_width: finite(technicalSummary?.bollinger_width_percent) == null ? null : (Number(technicalSummary.bollinger_width_percent) <= Number(tech.bb_width.threshold) ? 100 : 0),
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
    const fundamentalComponent = factorScore("fundamental", {
      q_eps_yoy: finite(q[0]?.yoy_eps) == null ? null : (Number(q[0].yoy_eps) > Number(fcfg.q_eps_yoy.threshold) ? 100 : 0),
      q_eps_rising: q.length < 3 ? null : (isRising3(q[0]?.eps, q[1]?.eps, q[2]?.eps) ? 100 : 0),
      q_eps_yoy_rising: comparable("yoy_eps").length < 3 ? null : (isRising3(...comparable("yoy_eps")) ? 100 : 0),
      q_pat_yoy: finite(q[0]?.yoy_pat) == null ? null : (Number(q[0].yoy_pat) > Number(fcfg.q_pat_yoy.threshold) ? 100 : 0),
      q_pat_rising: q.length < 3 ? null : (isRising3(q[0]?.pat, q[1]?.pat, q[2]?.pat) ? 100 : 0),
      q_pat_yoy_rising: comparable("yoy_pat").length < 3 ? null : (isRising3(...comparable("yoy_pat")) ? 100 : 0),
      q_npm_yoy: qNpmGrowth == null ? null : (qNpmGrowth > Number(fcfg.q_npm_yoy.threshold) ? 100 : 0),
      q_sales_yoy: finite(q[0]?.yoy_sales) == null ? null : (Number(q[0].yoy_sales) > Number(fcfg.q_sales_yoy.threshold) ? 100 : 0),
      q_sales_rising: q.length < 3 ? null : (isRising3(q[0]?.sales, q[1]?.sales, q[2]?.sales) ? 100 : 0),
      a_eps_yoy: finite(a[0]?.yoy_eps) == null ? null : (Number(a[0].yoy_eps) > Number(fcfg.a_eps_yoy.threshold) ? 100 : 0),
      a_eps_rising: a.length < 3 ? null : (isRising3(a[0]?.eps, a[1]?.eps, a[2]?.eps) ? 100 : 0),
      a_pat_yoy: finite(a[0]?.yoy_pat) == null ? null : (Number(a[0].yoy_pat) > Number(fcfg.a_pat_yoy.threshold) ? 100 : 0),
      a_pat_rising: a.length < 3 ? null : (isRising3(a[0]?.pat, a[1]?.pat, a[2]?.pat) ? 100 : 0),
      a_sales_yoy: finite(a[0]?.yoy_sales) == null ? null : (Number(a[0].yoy_sales) > Number(fcfg.a_sales_yoy.threshold) ? 100 : 0),
      a_sales_rising: a.length < 3 ? null : (isRising3(a[0]?.sales, a[1]?.sales, a[2]?.sales) ? 100 : 0),
      a_ocf_yoy: annualOcfGrowth == null ? null : (annualOcfGrowth > Number(fcfg.a_ocf_yoy.threshold) ? 100 : 0),
      a_npm_rising: a.length < 2 || finite(a[0]?.npm) == null || finite(a[1]?.npm) == null ? null : (Number(a[0].npm) > Number(a[1].npm) ? 100 : 0),
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
        promoter_qoq: finite(latestH.promoter_change) == null ? null : (Number(latestH.promoter_change) > Number(ocfg.promoter_qoq.threshold) ? 100 : 0),
        promoter_above: finite(latestH.promoter) == null ? null : (Number(latestH.promoter) > Number(ocfg.promoter_above.threshold) ? 100 : 0),
        promoter_rising: finite(latestH.promoter) == null || finite(previousYearH.promoter) == null ? null : (Number(latestH.promoter) > Number(previousYearH.promoter) ? 100 : 0),
        pledge: null,
        fii_qoq: finite(latestH.fii_change) == null ? null : (Number(latestH.fii_change) > Number(ocfg.fii_qoq.threshold) ? 100 : 0),
        fii_rising:
          finite(latestH.fii) == null || finite(previousYearH.fii) == null ||
          finite(priorQuarterH.fii) == null || finite(secondPriorQuarterH.fii) == null
            ? null
            : (Number(latestH.fii) > Number(previousYearH.fii) && Number(priorQuarterH.fii) > Number(secondPriorQuarterH.fii) ? 100 : 0),
        dii_mf_qoq: changeSum == null ? null : (changeSum > Number(ocfg.dii_mf_qoq.threshold) ? 100 : 0),
        dii_mf_rising: priorDiiMf == null || secondPriorDiiMf == null ? null : (priorDiiMf > secondPriorDiiMf ? 100 : 0),
        insider_activity: null,
      });
    } else if (exchange === "US") {
      // The handwritten Ownership sheet specifically uses Promoter/FII/DII-MF/
      // pledge/history factors. Yahoo's US holder tables are not equivalent to
      // those categories, so the ownership score is intentionally unavailable
      // instead of mapping unlike data.
      ownershipComponent = null;
    }

    const components = {
      technical: technicalComponent,
      fundamental: fundamentalComponent,
      relative_strength: technicalSummary?.rs_available === false ? null : finite(technicalSummary?.rs_rating),
      ownership: ownershipComponent,
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
    const score = missingIndianFundamental || availableWeight <= 0 ? null : Math.max(0, Math.min(100, Math.round(points / availableWeight)));
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

    if (value === "US") {
      setSymbol("AAPL");
    } else if (value === "NSE") {
      setSymbol("RELIANCE");
    } else {
      setSymbol("INFY");
    }
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
                : dataStatus === "stale"
                ? "Data Stale"
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
              value={symbol}
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
                      setSymbol(item.symbol);
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
              setShowSuggestions(false);
              setSuggestions([]);

              try {
                setLoading(true);

                // First try to load existing stored data
                const res = await axios.get(
                  `${API}/market/chart/${symbol}?exchange=${exchange}&timeframe=${timeframe}&limit=${chartLimitForTimeframe(timeframe)}`
                );

                const rows = res.data.data || [];

                if (rows.length > 0) {
                  setData(rows);
                  setDataStale(false);
                  setDataStatus("fresh");
                  setMessage("");

                  await loadIndicators();

                  if (exchange === "US") {
                    await loadFundamentals();
                  }

                  return;
                }

                // If no stored data exists, fetch it automatically
                await axios.post(
                  `${API}/market/refresh/${symbol}?exchange=${exchange}`
                );

                await loadChart();
                await loadIndicators();

                if (exchange === "US") {
                  await loadFundamentals();
                }

              } catch (err) {
                console.error("Search error:", err);

                const detail =
                  err.response?.data?.detail ||
                  "Unable to load data for this symbol.";

                setDataStale(true);
                setDataStatus("stale");
                setMessage(detail);

              } finally {
                setLoading(false);
              }
            }}
          >
            Search
          </button>

          <button className="refresh" onClick={refreshData}>
            Refresh Data
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

        <section className="cards">
          <div className="card">
            <span>Market</span>
            <strong>{exchange}</strong>
          </div>

          <div className="card">
            <span>Symbol</span>
            <strong>{symbol}</strong>
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
          exchange === "US" ? (
            <section className="fundamental-section score-weight-section ranking-settings-panel">
              <div className="ranking-settings-header">
                <div>
                  <h2>Ranking Weight Settings (US)</h2>
                  <p>Customize the broad ranking categories, then use only the client's handwritten factors below.</p>
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
                  ["relative_strength", "Relative Strength", "Performance vs S&P 500"],
                  ["ownership", "Ownership", "Institutional and insider positioning"],
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

              <div className="ranking-actions">
                <button className="ranking-primary-button" onClick={() => {
                  localStorage.setItem("scoreWeights", JSON.stringify(scoreWeights));
                  localStorage.setItem("handwrittenFactors", JSON.stringify(handwrittenFactors));
                  localStorage.setItem("rsWeights", JSON.stringify(rsWeights));
                  localStorage.setItem("rsVisibility", JSON.stringify(rsVisibility));
                  loadDashboard();
                  loadTechnicalSummary();
                }}>Apply Ranking</button>
                <button type="button" className="secondary-button ranking-secondary-button" onClick={() => setShowRankingDetails((v) => !v)}>
                  {showRankingDetails ? "Hide Factors" : "Show Factors"}
                </button>
                <button type="button" className="secondary-button ranking-secondary-button" onClick={() => {
                  setScoreWeights({ ...defaultScoreWeights });
                  setHandwrittenFactors(JSON.parse(JSON.stringify(defaultHandwrittenFactors)));
                  localStorage.removeItem("scoreWeights");
                  localStorage.removeItem("handwrittenFactors");
                }}>Reset Defaults</button>
              </div>

              <div className="ranking-help-note">
                <strong>How weighting works:</strong> only the factors from the client's handwritten sheets are used here. Category and factor weightages are customizable and normalized automatically. Use the Enabled/Disabled switch beside each factor to include or exclude it. Weightage and editable values remain customizable. Breakout/VCP remains analysis-only and is not a final-ranking category.
              </div>

              {showRankingDetails && (
                <div className="ranking-detail-grid handwritten-factor-grid">
                  {[
                    ["technical", "Technical factors", "Only the technical factors from the handwritten sheet"],
                    ["fundamental", "Fundamental factors", "Quarterly and annual growth factors from the handwritten sheet"],
                    ["ownership", "Ownership factors", "Promoter / FII / DII-MF / pledge / insider factors from the handwritten sheet"],
                  ].map(([group, title, subtitle]) => (
                    <div className="ranking-detail-card" key={group}>
                      <div className="ranking-detail-card-header">
                        <div>
                          <h3>{title}</h3>
                          <p>{subtitle}</p>
                        </div>
                        <span>{Object.values(handwrittenFactors[group]).reduce((sum, item) => sum + (item.enabled === false ? 0 : (Number(item.weight) || 0)), 0)} active weight</span>
                      </div>
                      <div className="ranking-parameter-list">
                        {handwrittenFactorMeta[group].map(([key, label, description, editableValues]) => {
                          const factor = handwrittenFactors[group][key];
                          const factorWeight = Number(factor?.weight) || 0;
                          const factorEnabled = factor?.enabled !== false;
                          return (
                            <div className={`ranking-parameter-row handwritten-factor-row ${!factorEnabled ? "is-disabled" : ""}`} key={key}>
                              <div className="ranking-parameter-copy">
                                <strong>{label}</strong>
                                <small>{description}</small>
                                {editableValues.length > 0 && (
                                  <div className="factor-value-grid">
                                    {editableValues.map((valueKey) => (
                                      <label key={valueKey}>
                                        <span>{valueKey === "threshold" ? "Value" : valueKey.toUpperCase()}</span>
                                        <input
                                          aria-label={`${label} ${valueKey}`}
                                          type="number"
                                          step="0.1"
                                          value={factor[valueKey]}
                                          onChange={(e) => setHandwrittenFactors((prev) => ({
                                            ...prev,
                                            [group]: {
                                              ...prev[group],
                                              [key]: { ...prev[group][key], [valueKey]: Number(e.target.value) },
                                            },
                                          }))}
                                        />
                                      </label>
                                    ))}
                                  </div>
                                )}
                              </div>
                              <div className="factor-controls">
                                <label className="factor-enable-toggle">
                                  <input
                                    type="checkbox"
                                    checked={factorEnabled}
                                    onChange={(e) => setHandwrittenFactors((prev) => ({
                                      ...prev,
                                      [group]: {
                                        ...prev[group],
                                        [key]: { ...prev[group][key], enabled: e.target.checked },
                                      },
                                    }))}
                                  />
                                  <span>{factorEnabled ? "Enabled" : "Disabled"}</span>
                                </label>
                                <div className="weight-input-wrap parameter-weight-input">
                                <input
                                  aria-label={`${label} weight`}
                                  type="number"
                                  min="0"
                                  step="1"
                                  value={factor.weight}
                                  onChange={(e) => setHandwrittenFactors((prev) => ({
                                    ...prev,
                                    [group]: {
                                      ...prev[group],
                                      [key]: { ...prev[group][key], weight: Math.max(0, Number(e.target.value) || 0) },
                                    },
                                  }))}
                                />
                                <span>w</span>
                                </div>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>
          ) : (
            <section className="fundamental-section score-weight-section">
              <h2>Indian Market Ranking</h2>
              <div
                style={{
                  padding: "18px",
                  border: "1px solid #f0c36d",
                  borderRadius: "10px",
                  background: "#fffaf0",
                }}
              >
                <strong>Ranking unavailable</strong>
                <p style={{ margin: "8px 0 0" }}>
                  Fundamental and ownership data are required before an Indian-market ranking can be calculated. Technical analysis and RS vs NIFTY 500 remain available.
                </p>
              </div>
            </section>
          )
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

          {!dataStale ? (
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
        </section>

        <section className="fundamental-section relative-strength-section">
          <h2>Relative Strength vs {benchmark?.name || (exchange === "US" ? "S&P 500" : "NIFTY 500")}</h2>
          <div className="indicator-settings rs-weight-settings rs-horizon-settings">
            {["1w","2w","1m","2m","3m","6m","1y"].map((key) => (
              <div key={key} className={`rs-horizon-control ${rsVisibility[key] === false ? "is-hidden" : ""}`}>
                <label>{key.toUpperCase()} %</label>
                <input type="number" min="0" value={rsWeights[key]}
                  onChange={(e) => setRsWeights((prev) => ({ ...prev, [key]: Math.max(0, Number(e.target.value) || 0) }))} />
                <label className="rs-visibility-toggle">
                  <input
                    type="checkbox"
                    checked={rsVisibility[key] !== false}
                    onChange={(e) => setRsVisibility((prev) => ({ ...prev, [key]: e.target.checked }))}
                  />
                  Show
                </label>
              </div>
            ))}
            <button onClick={() => {
              localStorage.setItem("rsWeights", JSON.stringify(rsWeights));
              localStorage.setItem("rsVisibility", JSON.stringify(rsVisibility));
              loadTechnicalSummary();
              loadDashboard();
            }}>Apply RS Settings</button>
          </div>
          <div className="rs-period-grid">
            {["1w","2w","1m","2m","3m","6m","1y"].filter((key) => rsVisibility[key] !== false).map((key) => {
              const item = technicalSummary?.rs_periods?.[key];
              return (
                <div className="metric rs-period-card" key={key}>
                  <span>{key.toUpperCase()} Relative Return</span>
                  <strong>{item?.relative_return_percent != null ? `${Number(item.relative_return_percent).toFixed(2)}%` : "-"}</strong>
                  <small>Weight {rsWeights[key]}%</small>
                </div>
              );
            })}
          </div>
          <div className="chart-note">
            RS line = stock price / broad-market benchmark, rebased to 100 at the first overlapping point. Rising means the stock is outperforming the benchmark; falling means underperforming. The rating uses the customizable 1W/2W/1M/2M/3M/6M/1Y horizon weights above. Show/hide controls affect the horizon cards only; scoring continues to use the entered weights, and a weight of 0 disables a horizon.
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
                <small>{["1w","2w","1m","2m","3m","6m","1y"].filter((k) => rsVisibility[k] !== false).map((k) => `${k.toUpperCase()} ${rsWeights[k]}%`).join(" • ")}</small>
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
              <div className="metric"><span>Pattern</span><strong>{technicalSummary.pattern}</strong></div>
            </div>
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
                <span>RSI {indicators.settings?.rsi_period ?? rsiPeriod}</span>
                <strong>{indicators.rsi ?? "-"}</strong>
              </div>
            </div>
          </section>
        )}

        {exchange === "US" &&
          fundamentals?.fundamentals &&
          fundamentals?.ownership && (
          <section className="fundamental-section">
            <h2>Fundamentals & Ownership</h2>

            <div className="fundamental-grid">
              <div className="metric">
                <span>Market Cap</span>
                <strong>
                  {fundamentals.fundamentals.market_cap != null
                    ? `$${(fundamentals.fundamentals.market_cap / 1e9).toFixed(2)}B`
                    : "-"}
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
                  {fundamentals.fundamentals.revenue != null
                    ? `$${(fundamentals.fundamentals.revenue / 1e9).toFixed(2)}B`
                    : "-"}
                </strong>
              </div>

              <div className="metric">
                <span>Net Income</span>
                <strong>
                  {fundamentals.fundamentals.net_income != null
                    ? `$${(fundamentals.fundamentals.net_income / 1e9).toFixed(2)}B`
                    : "-"}
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

                <h3>Quarterly Ownership Pattern & Changes</h3>
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
                <div className="chart-note" style={{ marginTop: "10px" }}>Source: {indiaShareholding.source}. Change columns are quarter-over-quarter percentage-point changes. Missing categories are shown as unavailable rather than estimated.</div>
              </>
            ) : (
              <div className="provider-warning">Indian shareholding history could not be loaded from the public provider right now. Technical and price data remain available.</div>
            )}
          </section>
        )}

{exchange === "US" && ownershipDetails && (
          <section className="fundamental-section">
            <h2>Ownership Detail</h2>
            <div className="chart-note">Holder tables show the provider's latest reported date and provider-reported position change when available. For Yahoo holder tables, Change means proportional change in the holder's share position; it is not a quarter-over-quarter change in ownership percentage points. Unavailable history is not estimated.</div>
            {ownershipDetails.provider_note && (
              <div className="provider-warning">{ownershipDetails.provider_note}</div>
            )}

            <h3>Top Institutional Holders</h3>
            <div className="history-table-wrapper">
              <table className="history-table">
                <thead><tr><th>Holder</th><th>Report Date</th><th>Shares</th><th>Value</th><th>% Held</th><th>Provider Change</th></tr></thead>
                <tbody>
                  {(ownershipDetails.institutional_holders || []).slice(0, 5).map((row, index) => (
                    <tr key={index}>
                      <td>{row.Holder || row.holder || "-"}</td>
                      <td>{row["Date Reported"] ? String(row["Date Reported"]).slice(0, 10) : (row.dateReported ? String(row.dateReported).slice(0, 10) : "-")}</td>
                      <td>{row.Shares != null ? Number(row.Shares).toLocaleString() : "-"}</td>
                      <td>{row.Value != null ? Number(row.Value).toLocaleString() : "-"}</td>
                      <td>{row.pctHeld != null ? `${(Number(row.pctHeld) * 100).toFixed(2)}%` : (row["% Out"] ?? "-")}</td>
                      <td>{row.pctChange != null ? `${(Number(row.pctChange) * 100).toFixed(2)}%` : (row["% Change"] ?? "-")}</td>
                    </tr>
                  ))}
                  {(!ownershipDetails.institutional_holders || ownershipDetails.institutional_holders.length === 0) && (
                    <tr><td colSpan="6">No institutional-holder rows returned by the configured provider.</td></tr>
                  )}
                </tbody>
              </table>
            </div>

            <h3>Top Mutual Fund Holders</h3>
            <div className="history-table-wrapper">
              <table className="history-table">
                <thead><tr><th>Holder</th><th>Report Date</th><th>Shares</th><th>Value</th><th>% Held</th><th>Provider Change</th></tr></thead>
                <tbody>
                  {(ownershipDetails.mutual_fund_holders || []).slice(0, 5).map((row, index) => (
                    <tr key={index}>
                      <td>{row.Holder || row.holder || "-"}</td>
                      <td>{row["Date Reported"] ? String(row["Date Reported"]).slice(0, 10) : (row.dateReported ? String(row.dateReported).slice(0, 10) : "-")}</td>
                      <td>{row.Shares != null ? Number(row.Shares).toLocaleString() : "-"}</td>
                      <td>{row.Value != null ? Number(row.Value).toLocaleString() : "-"}</td>
                      <td>{row.pctHeld != null ? `${(Number(row.pctHeld) * 100).toFixed(2)}%` : (row["% Out"] ?? "-")}</td>
                      <td>{row.pctChange != null ? `${(Number(row.pctChange) * 100).toFixed(2)}%` : (row["% Change"] ?? "-")}</td>
                    </tr>
                  ))}
                  {(!ownershipDetails.mutual_fund_holders || ownershipDetails.mutual_fund_holders.length === 0) && (
                    <tr><td colSpan="6">No mutual-fund holder rows returned by the configured provider.</td></tr>
                  )}
                </tbody>
              </table>
            </div>

            <h3>Recent Insider Transactions</h3>
            <div className="history-table-wrapper">
              <table className="history-table">
                <thead><tr><th>Insider</th><th>Position</th><th>Transaction</th><th>Shares</th></tr></thead>
                <tbody>
                  {(ownershipDetails.insider_transactions || []).slice(0, 5).map((row, index) => (
                    <tr key={index}>
                      <td>{row.Insider || row.insider || row.Name || "-"}</td>
                      <td>{row.Position || row.position || "-"}</td>
                      <td>{row.Transaction || row.transaction || row.Text || "-"}</td>
                      <td>{row.Shares != null ? Number(row.Shares).toLocaleString() : "-"}</td>
                    </tr>
                  ))}
                  {(!ownershipDetails.insider_transactions || ownershipDetails.insider_transactions.length === 0) && (
                    <tr><td colSpan="4">No insider transaction rows returned by the configured provider.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </section>
        )}

        {exchange === "US" && fundamentalHistory && (
          <section className="fundamental-section">
            <h2>Fundamental History</h2>

            <h3>Quarterly History ({Math.min(fundamentalHistory.quarterly?.length || 0, 8)}/8 available)</h3>
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
                  {fundamentalHistory.quarterly?.slice(0, 8).map((row) => (
                    <tr key={row.period}>
                      <td>{row.period}</td>
                      <td>
                        {row.sales != null
                          ? `$${(row.sales / 1e9).toFixed(2)}B`
                          : "-"}
                      </td>
                      <td>
                        {row.qoq_sales != null ? `${row.qoq_sales}%` : "-"}
                      </td>
                      <td>{row.yoy_sales != null ? `${row.yoy_sales}%` : "-"}</td>
                      <td>
                        {row.pat != null
                          ? `$${(row.pat / 1e9).toFixed(2)}B`
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
                          ? `$${(row.ebit / 1e9).toFixed(2)}B`
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
                  <LineChart data={[...(fundamentalHistory.quarterly || [])].slice(0, 8).reverse()}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="period" />
                    <YAxis tickFormatter={(value) => `${(value / 1e9).toFixed(0)}B`} />
                    <Tooltip formatter={(value) => value != null ? `$${(value / 1e9).toFixed(2)}B` : "-"} />
                    <Line type="monotone" dataKey="sales" strokeWidth={2} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
              <div className="fundamental-chart-card">
                <h4>Quarterly EPS</h4>
                <ResponsiveContainer width="100%" height={220}>
                  <LineChart data={[...(fundamentalHistory.quarterly || [])].slice(0, 8).reverse()}>
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
                  <LineChart data={[...(fundamentalHistory.quarterly || [])].slice(0, 8).reverse()}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="period" />
                    <YAxis tickFormatter={(value) => `${(value / 1e9).toFixed(0)}B`} />
                    <Tooltip formatter={(value) => value != null ? `$${(value / 1e9).toFixed(2)}B` : "-"} />
                    <Line type="monotone" dataKey="pat" strokeWidth={2} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>

            <h3>Previous 5 Years ({Math.min(fundamentalHistory.annual?.filter((row) => row.sales != null || row.pat != null || row.eps != null).length || 0, 5)}/5 available)</h3>
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
                  {fundamentalHistory.annual?.slice(0, 5).map((row) => (
                    <tr key={row.period}>
                      <td>{row.period}</td>
                      <td>
                        {row.sales != null
                          ? `$${(row.sales / 1e9).toFixed(2)}B`
                          : "-"}
                      </td>
                      <td>{row.yoy_sales != null ? `${row.yoy_sales}%` : "-"}</td>
                      <td>
                        {row.pat != null
                          ? `$${(row.pat / 1e9).toFixed(2)}B`
                          : "-"}
                      </td>
                      <td>{row.yoy_pat != null ? `${row.yoy_pat}%` : "-"}</td>
                      <td>{row.eps ?? "-"}</td>
                      <td>{row.yoy_eps != null ? `${row.yoy_eps}%` : "-"}</td>
                      <td>
                        {row.ebit != null
                          ? `$${(row.ebit / 1e9).toFixed(2)}B`
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
                          ? `$${(row.operating_cash_flow / 1e9).toFixed(2)}B`
                          : "-"}
                      </td>
                      <td>
                        {row.free_cash_flow != null
                          ? `$${(row.free_cash_flow / 1e9).toFixed(2)}B`
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
                          ? `$${row.cash_flow_per_share.toFixed(2)}`
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