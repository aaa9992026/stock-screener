import { useEffect, useRef, useState } from "react";
import {
  createChart,
  CandlestickSeries,
  LineSeries,
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
  const [suggestions, setSuggestions] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [benchmark, setBenchmark] = useState(null);
  const [dashboard, setDashboard] = useState(null);
  const [technicalSummary, setTechnicalSummary] = useState(null);
  const [ownershipDetails, setOwnershipDetails] = useState(null);

  const loadDashboard = async () => {
    try {
      const res = await axios.get(
        `${API}/market/dashboard/${symbol}?exchange=${exchange}`
      );
      setDashboard(res.data);
    } catch {
      setDashboard(null);
    }
  };

  const loadTechnicalSummary = async () => {
    try {
      const res = await axios.get(
        `${API}/market/technical-summary/${symbol}?exchange=${exchange}`
      );
      setTechnicalSummary(res.data);
    } catch {
      setTechnicalSummary(null);
    }
  };

  const loadOwnershipDetails = async () => {
    try {
      const res = await axios.get(
        `${API}/market/ownership-details/${symbol}?exchange=${exchange}`
      );
      setOwnershipDetails(res.data);
    } catch {
      setOwnershipDetails(null);
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
      const res = await axios.get(
        `${API}/market/fundamentals/${symbol}?exchange=US`
      );

      setFundamentals(res.data);

    } catch {
      try {
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
        `${API}/market/chart/${symbol}?exchange=${exchange}&timeframe=${timeframe}&limit=100`
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
        `${API}/market/benchmark/${exchange}?limit=100`
      );

      setBenchmark(res.data);
    } catch {
      setBenchmark(null);
    }
  };

  const refreshData = async () => {
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
      height: 420,
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
      },
      timeScale: {
        borderColor: "#cbd5e1",
        timeVisible: true,
      },
    });

    const candleSeries = chart.addSeries(CandlestickSeries, {});

    const candleData = data.map((row) => ({
      time: String(row.date).slice(0, 10),
      open: Number(row.open),
      high: Number(row.high),
      low: Number(row.low),
      close: Number(row.close),
    }));

    candleSeries.setData(candleData);

    if (benchmark?.data?.length && candleData.length) {
      const benchmarkSeries = chart.addSeries(LineSeries, {
        lineWidth: 2,
        priceScaleId: "right",
      });

      let rawBenchmark = benchmark.data.map((row) => ({
        time: String(row.date).slice(0, 10),
        value: Number(row.close),
      }));

      if (timeframe === "weekly") {
        const grouped = {};

        rawBenchmark.forEach((row) => {
          const d = new Date(row.time);

          const day = d.getUTCDay();
          const diff =
            d.getUTCDate() - day + (day === 0 ? -6 : 1);

          const monday = new Date(
            Date.UTC(
              d.getUTCFullYear(),
              d.getUTCMonth(),
              diff
            )
          );

          const key = monday.toISOString().slice(0, 10);

          grouped[key] = {
            time: key,
            value: row.value,
          };
        });

        rawBenchmark = Object.values(grouped);
      }

      if (timeframe === "monthly") {
        const grouped = {};

        rawBenchmark.forEach((row) => {
          const d = new Date(row.time);

          const year = d.getUTCFullYear();
          const month = String(
            d.getUTCMonth() + 1
          ).padStart(2, "0");

          const key = `${year}-${month}-01`;

          grouped[key] = {
            time: key,
            value: row.value,
          };
        });

        rawBenchmark = Object.values(grouped);
      }

      // Rebase the benchmark to the stock's first visible close. This keeps the
      // candlesticks on their real price scale while making the benchmark line
      // represent relative performance instead of an unrelated index price.
      const firstBenchmark = rawBenchmark[0]?.value;
      const firstStock = candleData[0]?.close;

      if (firstBenchmark && firstStock) {
        benchmarkSeries.setData(
          rawBenchmark.map((row) => ({
            time: row.time,
            value: (row.value / firstBenchmark) * firstStock,
          }))
        );
      }
    }

    chart.timeScale().fitContent();

    const handleResize = () => {
      if (chartContainerRef.current) {
        chart.applyOptions({
          width: chartContainerRef.current.clientWidth,
        });
      }
    };

    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
    };
  }, [data, benchmark, timeframe]);

  const latest = !dataStale && data.length
    ? data[data.length - 1]
    : null;
  const currency = exchange === "US" ? "$" : "₹";

  const changeExchange = (value) => {
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

          <div className="symbol-search">
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
              try {
                setLoading(true);

                // First try to load existing stored data
                const res = await axios.get(
                  `${API}/market/chart/${symbol}?exchange=${exchange}&timeframe=${timeframe}&limit=100`
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
              <strong>{dashboard.score}/100</strong>
              <small>{dashboard.score_coverage_percent}% metric coverage</small>
            </div>
            <div className={`summary-signal signal-${dashboard.signal?.toLowerCase()}`}>
              <span>Rule-Based Signal</span>
              <strong>{dashboard.signal}</strong>
              <small>Based on available technical + fundamental data</small>
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

          {!dataStale ? (
            <div
              ref={chartContainerRef}
              style={{
                width: "100%",
                height: "420px"
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
              {benchmark.name} line is rebased to the stock price at the first overlapping date so relative performance can be compared on the same chart.
            </div>
          )}
        </section>

        {technicalSummary && (
          <section className="fundamental-section">
            <h2>Technical Screening Summary</h2>
            <div className="fundamental-grid">
              <div className="metric">
                <span>RS Rating</span>
                <strong>{technicalSummary.rs_rating ?? "Unavailable"}</strong>
                <small>
                  {technicalSummary.rs_rating != null
                    ? `Stored universe: ${technicalSummary.rs_universe_size}`
                    : `Insufficient universe: ${technicalSummary.rs_universe_size ?? 0}/${technicalSummary.rs_minimum_universe ?? 20}`}
                </small>
              </div>
              <div className="metric"><span>EMA Alignment</span><strong>{technicalSummary.ema_alignment}</strong></div>
              <div className="metric"><span>20-Day Avg Volume</span><strong>{technicalSummary.average_volume_20 != null ? Number(technicalSummary.average_volume_20).toLocaleString() : "-"}</strong></div>
              <div className="metric"><span>Volume Ratio</span><strong>{technicalSummary.volume_ratio ?? "-"}</strong></div>
              <div className="metric"><span>ADR (20D)</span><strong>{technicalSummary.adr_percent != null ? `${technicalSummary.adr_percent}%` : "-"}</strong></div>
              <div className="metric"><span>Breakout Status</span><strong>{technicalSummary.breakout_status}</strong></div>
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
                  {fundamentals.fundamentals.return_on_equity != null
                    ? `${(fundamentals.fundamentals.return_on_equity * 100).toFixed(2)}%`
                    : "-"}
                </strong>
              </div>

              <div className="metric">
                <span>ROA</span>
                <strong>
                  {fundamentals.fundamentals.return_on_assets != null
                    ? `${(fundamentals.fundamentals.return_on_assets * 100).toFixed(2)}%`
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

        {ownershipDetails && (
          <section className="fundamental-section">
            <h2>Ownership Detail</h2>
            {ownershipDetails.provider_note && (
              <div className="provider-warning">{ownershipDetails.provider_note}</div>
            )}

            <h3>Top Institutional Holders</h3>
            <div className="history-table-wrapper">
              <table className="history-table">
                <thead><tr><th>Holder</th><th>Shares</th><th>Value</th><th>% Held</th></tr></thead>
                <tbody>
                  {(ownershipDetails.institutional_holders || []).slice(0, 5).map((row, index) => (
                    <tr key={index}>
                      <td>{row.Holder || row.holder || "-"}</td>
                      <td>{row.Shares != null ? Number(row.Shares).toLocaleString() : "-"}</td>
                      <td>{row.Value != null ? Number(row.Value).toLocaleString() : "-"}</td>
                      <td>{row.pctHeld != null ? `${(Number(row.pctHeld) * 100).toFixed(2)}%` : (row["% Out"] ?? "-")}</td>
                    </tr>
                  ))}
                  {(!ownershipDetails.institutional_holders || ownershipDetails.institutional_holders.length === 0) && (
                    <tr><td colSpan="4">No institutional-holder rows returned by the configured provider.</td></tr>
                  )}
                </tbody>
              </table>
            </div>

            <h3>Top Mutual Fund Holders</h3>
            <div className="history-table-wrapper">
              <table className="history-table">
                <thead><tr><th>Holder</th><th>Shares</th><th>Value</th><th>% Held</th></tr></thead>
                <tbody>
                  {(ownershipDetails.mutual_fund_holders || []).slice(0, 5).map((row, index) => (
                    <tr key={index}>
                      <td>{row.Holder || row.holder || "-"}</td>
                      <td>{row.Shares != null ? Number(row.Shares).toLocaleString() : "-"}</td>
                      <td>{row.Value != null ? Number(row.Value).toLocaleString() : "-"}</td>
                      <td>{row.pctHeld != null ? `${(Number(row.pctHeld) * 100).toFixed(2)}%` : (row["% Out"] ?? "-")}</td>
                    </tr>
                  ))}
                  {(!ownershipDetails.mutual_fund_holders || ownershipDetails.mutual_fund_holders.length === 0) && (
                    <tr><td colSpan="4">No mutual-fund holder rows returned by the configured provider.</td></tr>
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

            <h3>Last 4 Quarters</h3>
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
                  {fundamentalHistory.quarterly?.slice(0, 4).map((row) => (
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

            <h3>Previous 3 Years</h3>
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
                  {fundamentalHistory.annual?.slice(0, 3).map((row) => (
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
                      <td>{new Date(row.date).toLocaleDateString()}</td>
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