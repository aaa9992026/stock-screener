import { useEffect, useState } from "react";
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

const API =
  import.meta.env.VITE_API_URL ||
  "http://127.0.0.1:8000";

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

  const [suggestions, setSuggestions] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);

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

      const detail =
        err.response?.data?.detail ||
        "Market data could not be loaded.";

      setMessage(detail);

    } finally {
      setLoading(false);
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

    if (exchange === "US") {
      loadFundamentals();
    } else {
      setFundamentals(null);
    }
  }, [timeframe, exchange]);

  const latest = !dataStale && data.length
    ? data[data.length - 1]
    : null;
  const currency = exchange === "US" ? "$" : "₹";

  const changeExchange = (value) => {
    setExchange(value);
    setData([]);
    setMessage("");

    if (value === "US") {
      setSymbol("AAPL");
    } else if (value === "NSE") {
      setSymbol("RELIANCE");
    } else {
      setSymbol("500325");
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
            <option value="BSE">BSE India</option>
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
            onClick={() => {
              loadChart();
              loadFundamentals();
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
            <ResponsiveContainer width="100%" height={420}>
              <LineChart data={data}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis
                  dataKey="date"
                  minTickGap={35}
                  tickFormatter={(value) =>
                    new Date(value).toLocaleDateString()
                  }
                />
                <YAxis domain={["auto", "auto"]} />
                <Tooltip />
                <Line
                  type="monotone"
                  dataKey="close"
                  strokeWidth={2}
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="stale-panel">
              Historical data is unavailable or incomplete for this provider.
            </div>
          )}
        </section>

        {exchange === "US" && fundamentals && (
          <section className="fundamental-section">
            <h2>Fundamentals & Ownership</h2>

            <div className="fundamental-grid">
              <div className="metric">
                <span>Market Cap</span>
                <strong>
                  ${(fundamentals.fundamentals.market_cap / 1e9).toFixed(2)}B
                </strong>
              </div>

              <div className="metric">
                <span>EPS</span>
                <strong>
                  {fundamentals.fundamentals.trailing_eps ?? "-"}
                </strong>
              </div>

              <div className="metric">
                <span>Revenue</span>
                <strong>
                  ${(fundamentals.fundamentals.revenue / 1e9).toFixed(2)}B
                </strong>
              </div>

              <div className="metric">
                <span>Net Income</span>
                <strong>
                  ${(fundamentals.fundamentals.net_income / 1e9).toFixed(2)}B
                </strong>
              </div>

              <div className="metric">
                <span>Profit Margin</span>
                <strong>
                  {(fundamentals.fundamentals.profit_margin * 100).toFixed(2)}%
                </strong>
              </div>

              <div className="metric">
                <span>ROE</span>
                <strong>
                  {(fundamentals.fundamentals.return_on_equity * 100).toFixed(2)}%
                </strong>
              </div>

              <div className="metric">
                <span>Insider Ownership</span>
                <strong>
                  {(fundamentals.ownership.insider_percent * 100).toFixed(2)}%
                </strong>
              </div>

              <div className="metric">
                <span>Institution Ownership</span>
                <strong>
                  {(fundamentals.ownership.institution_percent * 100).toFixed(2)}%
                </strong>
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