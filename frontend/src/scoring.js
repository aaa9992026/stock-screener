// Pure calculation helpers shared by the UI and independent Node regressions.
import { compositePoints } from "./scoreRounding.js";
export function alignFiscalSlots(input, kind) {
  if (!Array.isArray(input) || !input.length) return [];
  const rows = [...input].sort((a, b) => String(b.period || "").localeCompare(String(a.period || "")));
  const stamp = (row) => Date.parse(String(row?.period || "").slice(0, 10));
  const latest = stamp(rows[0]);
  if (!Number.isFinite(latest)) return rows;
  const step = kind === "annual" ? 365 : 91;
  const tolerance = kind === "annual" ? 30 : 25;
  return Array.from({length: rows.length}, (_, i) => {
    const match = rows.map(row => ({row, gap: Math.abs((latest-stamp(row))/86400000-step*i)}))
      .filter(item => Number.isFinite(item.gap) && item.gap <= tolerance).sort((a,b) => a.gap-b.gap)[0];
    return match?.row || {};
  });
}

export function ruleCoverage(settings, rows) {
  const enabled = Object.entries(settings).filter(([, cfg]) => cfg.enabled !== false && Number(cfg.weight) > 0);
  const available = enabled.filter(([key]) => rows[key]?.score != null && Number.isFinite(Number(rows[key].score)));
  return {required: enabled.length, available: available.length, complete: enabled.length > 0 && available.length === enabled.length,
    required_weight: enabled.reduce((sum,[,cfg]) => sum+Number(cfg.weight),0),
    available_weight: available.reduce((sum,[,cfg]) => sum+Number(cfg.weight),0),
    missing: enabled.filter(([key]) => !available.some(([name]) => name===key)).map(([key])=>key)};
}

export function reconcileComposite(components, weights) {
  const total = Object.values(weights).reduce((sum,w) => sum+Math.max(0, Number(w)||0),0);
  const normalized = Object.fromEntries(Object.entries(weights).map(([key,w]) => [key,total>0?Math.max(0,Number(w)||0)/total*100:0]));
  const available = Object.entries(components).filter(([key,v]) => normalized[key]>0 && v!=null && v!=="" && Number.isFinite(Number(v)));
  const contributions = Object.fromEntries(available.map(([key,v]) => [key, Number(v)*normalized[key]/100]));
  const provisional = compositePoints(available, normalized);
  return {provisional, normalized, contributions, coverage: available.reduce((sum,[key])=>sum+normalized[key],0),
    missing: Object.keys(components).filter(key=>normalized[key]>0 && !available.some(([name])=>name===key))};
}

export const compareNumeric = (left, comparator, right) => {
  if (left == null || right == null || left === "" || right === "") return null;
  const a = Number(left);
  const b = Number(right);
  if (!Number.isFinite(a) || !Number.isFinite(b)) return null;
  if (comparator === ">=") return a >= b;
  if (comparator === "<=") return a <= b;
  if (comparator === "<") return a < b;
  return a > b;
};

export const buildClientFundamentalRows = ({ fundamentalHistory, fundamentals, dashboard, factors }) => {
  const finite = (value) => {
    if (value === null || value === undefined || value === "") return null;
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
  };
  const growth = (current, previous) => {
    const c = finite(current);
    const p = finite(previous);
    if (c == null || p == null || p === 0) return null;
    return ((c - p) / Math.abs(p)) * 100;
  };
  const delta = (left, right) => {
    const a = finite(left);
    const b = finite(right);
    return a == null || b == null ? null : a - b;
  };
  const avg2 = (a, b) => {
    const x = finite(a);
    const y = finite(b);
    return x == null || y == null ? null : (x + y) / 2;
  };
  const avg = (values) => {
    const valid = values.map(finite).filter((v) => v != null);
    return valid.length === values.length && valid.length ? valid.reduce((sum, v) => sum + v, 0) / valid.length : null;
  };
  const row = (key, currentValue, targetText = null, forcedScore = undefined) => {
    const cfg = factors?.[key] || {};
    let score = forcedScore;
    if (score === undefined) {
      const result = compareNumeric(currentValue, cfg.comparator || ">", cfg.threshold);
      score = result == null ? null : (result ? 100 : 0);
    }
    return { currentValue, score, targetText };
  };

  const q = alignFiscalSlots(fundamentalHistory?.quarterly, "quarterly");
  const a = alignFiscalSlots(fundamentalHistory?.annual, "annual");
  const rows = {};

  const addMetric = (metric) => {
    const yoy = [0, 1, 2].map((i) => finite(q[i]?.[`yoy_${metric}`]));
    const qoq = [0, 1, 2].map((i) => finite(q[i]?.[`qoq_${metric}`]));
    const annualYoy = [0, 1, 2].map((i) => finite(a[i]?.[`yoy_${metric}`]));

    rows[`q_${metric}_yoy_latest`] = row(`q_${metric}_yoy_latest`, yoy[0]);
    rows[`q_${metric}_yoy_delta_latest_prior`] = row(`q_${metric}_yoy_delta_latest_prior`, delta(yoy[0], yoy[1]), yoy[1] == null ? "Prior Q YoY unavailable" : `Prior Q YoY ${yoy[1].toFixed(2)}%`);
    rows[`q_${metric}_yoy_delta_prior_second`] = row(`q_${metric}_yoy_delta_prior_second`, delta(yoy[1], yoy[2]), yoy[2] == null ? "Second-prior Q YoY unavailable" : `Second-prior Q YoY ${yoy[2].toFixed(2)}%`);
    rows[`q_${metric}_yoy_accel_vs_avg`] = row(
      `q_${metric}_yoy_accel_vs_avg`,
      avg2(yoy[1], yoy[2]) == null || yoy[0] == null ? null : yoy[0] - avg2(yoy[1], yoy[2]),
      avg2(yoy[1], yoy[2]) == null ? "Prior-two YoY average unavailable" : `Prior-two YoY avg ${avg2(yoy[1], yoy[2]).toFixed(2)}%`
    );

    rows[`q_${metric}_qoq_latest`] = row(`q_${metric}_qoq_latest`, qoq[0]);
    rows[`q_${metric}_qoq_prior`] = row(`q_${metric}_qoq_prior`, qoq[1]);
    rows[`q_${metric}_qoq_second`] = row(`q_${metric}_qoq_second`, qoq[2]);
    rows[`q_${metric}_qoq_accel_vs_avg`] = row(
      `q_${metric}_qoq_accel_vs_avg`,
      avg2(qoq[1], qoq[2]) == null || qoq[0] == null ? null : qoq[0] - avg2(qoq[1], qoq[2]),
      avg2(qoq[1], qoq[2]) == null ? "Prior-two QoQ average unavailable" : `Prior-two QoQ avg ${avg2(qoq[1], qoq[2]).toFixed(2)}%`
    );

    rows[`a_${metric}_yoy_latest`] = row(`a_${metric}_yoy_latest`, annualYoy[0]);
    rows[`a_${metric}_yoy_delta_latest_prior`] = row(
      `a_${metric}_yoy_delta_latest_prior`,
      delta(annualYoy[0], annualYoy[1]),
      annualYoy[1] == null ? "Prior annual YoY unavailable" : `Prior annual YoY ${annualYoy[1].toFixed(2)}%`
    );
    rows[`a_${metric}_yoy_accel_vs_avg`] = row(
      `a_${metric}_yoy_accel_vs_avg`,
      avg2(annualYoy[1], annualYoy[2]) == null || annualYoy[0] == null ? null : annualYoy[0] - avg2(annualYoy[1], annualYoy[2]),
      avg2(annualYoy[1], annualYoy[2]) == null ? "Prior-two annual YoY average unavailable" : `Prior-two annual YoY avg ${avg2(annualYoy[1], annualYoy[2]).toFixed(2)}%`
    );
  };

  addMetric("eps");
  addMetric("pat");
  addMetric("sales");

  const latestQNpm = finite(q[0]?.npm);
  const qNpmYoy0 = q.length >= 5 ? growth(q[0]?.npm, q[4]?.npm) : null;
  const qNpmYoy1 = q.length >= 6 ? growth(q[1]?.npm, q[5]?.npm) : null;
  const qNpmQoq = q.length >= 2 ? growth(q[0]?.npm, q[1]?.npm) : null;
  const annualNpmYoy = a.length >= 2 ? growth(a[0]?.npm, a[1]?.npm) : null;
  const npm3yAverage = a.length >= 3 ? avg([a[0]?.npm, a[1]?.npm, a[2]?.npm]) : null;
  const currentNpm = latestQNpm ?? finite(a[0]?.npm);
  const npmExpansion = currentNpm == null || npm3yAverage == null || npm3yAverage === 0
    ? null
    : ((currentNpm - npm3yAverage) / Math.abs(npm3yAverage)) * 100;
  const industryMedianNpm = finite(dashboard?.industry_median_npm);
  const industryScore = currentNpm == null || industryMedianNpm == null
    ? null
    : (currentNpm > industryMedianNpm ? 100 : 50);

  rows.npm_q_yoy_growth = row("npm_q_yoy_growth", qNpmYoy0);
  rows.npm_q_qoq_growth = row("npm_q_qoq_growth", qNpmQoq);
  rows.npm_a_yoy_growth = row("npm_a_yoy_growth", annualNpmYoy);
  rows.npm_expansion_3y = row(
    "npm_expansion_3y",
    npmExpansion,
    npm3yAverage == null ? "3-year average NPM unavailable" : `3-year average NPM ${npm3yAverage.toFixed(2)}%`
  );
  rows.npm_industry_compare = row(
    "npm_industry_compare",
    currentNpm,
    industryMedianNpm == null ? "Industry median NPM unavailable" : `Industry median NPM ${industryMedianNpm.toFixed(2)}%`,
    industryScore
  );
  rows.npm_q_yoy_delta = row(
    "npm_q_yoy_delta",
    delta(qNpmYoy0, qNpmYoy1),
    qNpmYoy1 == null ? "Prior Q NPM YoY unavailable" : `Prior Q NPM YoY ${qNpmYoy1.toFixed(2)}%`
  );

  const qCfoYoy0 = q.length >= 5 ? growth(q[0]?.operating_cash_flow, q[4]?.operating_cash_flow) : null;
  const qCfoYoy1 = q.length >= 6 ? growth(q[1]?.operating_cash_flow, q[5]?.operating_cash_flow) : null;
  const qCfoQoq = q.length >= 2 ? growth(q[0]?.operating_cash_flow, q[1]?.operating_cash_flow) : null;
  const annualOcfGrowth = a.length >= 2 ? growth(a[0]?.operating_cash_flow, a[1]?.operating_cash_flow) : null;
  const latestQuarterCfo = finite(q[0]?.operating_cash_flow);
  const latestAnnualCfo = finite(a[0]?.operating_cash_flow);
  const currentCfo = latestQuarterCfo ?? latestAnnualCfo;
  const cfo3yAverage = a.length >= 3 ? avg([a[0]?.operating_cash_flow, a[1]?.operating_cash_flow, a[2]?.operating_cash_flow]) : null;
  const cfoExpansion = currentCfo == null || cfo3yAverage == null || cfo3yAverage === 0
    ? null
    : ((currentCfo - cfo3yAverage) / Math.abs(cfo3yAverage)) * 100;
  const industryMedianCfo = finite(dashboard?.industry_median_cfo) ?? finite(dashboard?.industry_median_operating_cash_flow);
  const cfoIndustryScore = currentCfo == null || industryMedianCfo == null
    ? null
    : (currentCfo > industryMedianCfo ? 100 : 50);

  const roeValue = finite(a[0]?.roe) ?? (finite(fundamentals?.fundamentals?.return_on_equity) != null ? Number(fundamentals.fundamentals.return_on_equity) * 100 : null);
  const roceValue = finite(a[0]?.roce);
  const sharesOutstanding = finite(fundamentals?.ownership?.shares_outstanding);
  const floatShares = finite(fundamentals?.ownership?.float_shares);
  const latestOcf = latestAnnualCfo;
  const cashflowPerShare = latestOcf != null && sharesOutstanding != null && sharesOutstanding !== 0 ? latestOcf / sharesOutstanding : null;

  rows.cfo_q_yoy_growth = row("cfo_q_yoy_growth", qCfoYoy0);
  rows.cfo_q_qoq_growth = row("cfo_q_qoq_growth", qCfoQoq);
  rows.cfo_a_yoy_growth = row("cfo_a_yoy_growth", annualOcfGrowth);
  rows.cfo_expansion_3y = row(
    "cfo_expansion_3y",
    cfoExpansion,
    cfo3yAverage == null ? "3-year average CFO unavailable" : `3-year average CFO ${cfo3yAverage.toFixed(2)}`
  );
  rows.cfo_industry_compare = row(
    "cfo_industry_compare",
    currentCfo,
    industryMedianCfo == null ? "Industry median CFO unavailable" : `Industry median CFO ${industryMedianCfo.toFixed(2)}`,
    cfoIndustryScore
  );
  rows.cfo_q_yoy_delta = row(
    "cfo_q_yoy_delta",
    delta(qCfoYoy0, qCfoYoy1),
    qCfoYoy1 == null ? "Prior Q CFO YoY unavailable" : `Prior Q CFO YoY ${qCfoYoy1.toFixed(2)}%`
  );
  rows.cashflow_per_share = row("cashflow_per_share", cashflowPerShare);
  rows.roe_above = row("roe_above", roeValue);
  rows.roce_above = row("roce_above", roceValue);
  rows.shares_outstanding = factors?.shares_outstanding?.enabled === false
    ? { currentValue: sharesOutstanding, score: null, targetText: "Disabled until exact point rule is confirmed" }
    : row("shares_outstanding", sharesOutstanding);
  rows.float_shares = factors?.float_shares?.enabled === false
    ? { currentValue: floatShares, score: null, targetText: "Disabled until exact point rule is confirmed" }
    : row("float_shares", floatShares);

  return rows;
};

