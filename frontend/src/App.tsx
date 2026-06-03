import { useEffect, useState } from "react";
import { FactorPanel } from "./components/FactorPanel";
import { IntradayChart } from "./components/IntradayChart";
import { TradeList } from "./components/TradeList";
import type { RealtimePayload } from "./types";
import {
  apiClearRecalculate,
  apiRefreshCache,
  apiSetSymbol,
  apiSetTradeDate,
  apiShiftTradeDate,
  useRealtime,
} from "./hooks/useRealtime";
import "./App.css";

function signalClass(signal: string) {
  if (signal === "BUY") return "signal-buy";
  if (signal === "SELL") return "signal-sell";
  if (signal === "WATCH") return "signal-watch";
  return "signal-hold";
}

function todayString() {
  return new Date().toISOString().slice(0, 10);
}

export default function App() {
  const { data, connected } = useRealtime();
  const [symbolInput, setSymbolInput] = useState("600519");
  const [tradeDate, setTradeDate] = useState(todayString());
  const [loading, setLoading] = useState(false);
  const [dateLoading, setDateLoading] = useState(false);
  const [clearing, setClearing] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [stableChartData, setStableChartData] = useState<RealtimePayload | null>(null);
  const isPreparingData = loading || dateLoading || clearing || refreshing;
  const isDataLoading = data?.data_status === "loading";
  const isSyntheticData = data?.data_status === "synthetic";

  useEffect(() => {
    if ((data?.minute_points?.length ?? 0) > 0) {
      setStableChartData(data);
    }
  }, [data]);

  const chartData = isDataLoading ? data : isPreparingData && stableChartData ? stableChartData : data;

  const handleSetSymbol = async () => {
    setLoading(true);
    try {
      await apiSetSymbol(symbolInput.trim());
    } finally {
      setLoading(false);
    }
  };

  const handleClearRecalculate = async () => {
    if (!window.confirm(`确定清空当前股票 ${tradeDate} 的数据并重新计算吗？`)) {
      return;
    }
    setClearing(true);
    try {
      await apiClearRecalculate(tradeDate);
    } finally {
      setClearing(false);
    }
  };

  const handleSetTradeDate = async (nextTradeDate = tradeDate) => {
    if (!nextTradeDate) return;
    setDateLoading(true);
    try {
      await apiSetTradeDate(nextTradeDate);
    } finally {
      setDateLoading(false);
    }
  };

  const handleAdjustTradeDate = async (days: number) => {
    if (!tradeDate || dateLoading) return;
    setDateLoading(true);
    try {
      const result = await apiShiftTradeDate(days, tradeDate);
      if (result?.trade_date) {
        setTradeDate(result.trade_date);
      }
    } finally {
      setDateLoading(false);
    }
  };

  const handleRefreshCache = async () => {
    if (!window.confirm(`确定刷新当前股票 ${tradeDate} 的行情缓存并重新计算吗？`)) {
      return;
    }
    setRefreshing(true);
    try {
      await apiRefreshCache(tradeDate);
    } finally {
      setRefreshing(false);
    }
  };

  return (
    <div className="app">
      <header className="header">
        <h1>T0 量化助手</h1>
        <span className={`conn ${connected ? "on" : "off"}`}>
          {connected ? "已连接" : "重连中…"}
        </span>
      </header>

      <section className="toolbar">
        <input
          value={symbolInput}
          onChange={(e) => setSymbolInput(e.target.value)}
          placeholder="股票代码，如 600519"
          maxLength={6}
        />
        <button onClick={handleSetSymbol} disabled={loading}>
          {loading ? "切换中…" : "监控此股"}
        </button>
        <input
          className="date-input"
          type="date"
          value={tradeDate}
          onChange={(e) => setTradeDate(e.target.value)}
        />
        <button
          className="secondary date-step"
          onClick={() => handleAdjustTradeDate(-1)}
          disabled={dateLoading || !tradeDate}
        >
          前一天
        </button>
        <button
          className="secondary date-step"
          onClick={() => handleAdjustTradeDate(1)}
          disabled={dateLoading || !tradeDate}
        >
          后一天
        </button>
        <button
          className="secondary"
          onClick={() => handleSetTradeDate()}
          disabled={dateLoading || !tradeDate}
        >
          {dateLoading ? "加载中…" : "切换交易日"}
        </button>
        <button
          className="secondary"
          onClick={handleClearRecalculate}
          disabled={clearing || refreshing || !tradeDate}
        >
          {clearing ? "清空中…" : "清空重新计算"}
        </button>
        <button
          className="secondary"
          onClick={handleRefreshCache}
          disabled={refreshing || clearing || !tradeDate}
        >
          {refreshing ? "刷新中…" : "刷新行情缓存"}
        </button>
      </section>

      <section className="hero">
        <div className="stock-info">
          <h2>
            {data?.name || "—"} <span className="code">{data?.symbol || symbolInput}</span>
          </h2>
          <p className="trade-date">交易日：{data?.trade_date || tradeDate}</p>
          <div className="price-row">
            <span className="price">{isDataLoading ? "加载中" : data?.price?.toFixed(2) ?? "—"}</span>
            <span
              className={
                (data?.change_pct ?? 0) >= 0 ? "change up" : "change down"
              }
            >
              {!isDataLoading && data?.change_pct != null
                ? `${data.change_pct >= 0 ? "+" : ""}${data.change_pct.toFixed(2)}%`
                : "—"}
            </span>
          </div>
          <p className="vwap">
            VWAP: {isDataLoading ? "行情加载中" : data?.vwap?.toFixed(2) ?? "—"}
            {isSyntheticData ? " · 分钟行情不可用，仅展示日线估算" : ""}
          </p>
          <p className="t0-pair">
            已完成 T0：买 {data?.buy_count ?? 0} / 卖 {data?.sell_count ?? 0} ✓ 数量相等
            {data?.pending_buy ? ` · 待卖出买点 ${data.pending_buy.price.toFixed(2)}` : ""}
          </p>
        </div>
        <div className={`signal-card ${signalClass(data?.signal ?? "HOLD")}`}>
          <div className="signal-label">当前信号</div>
          <div className="signal-value">{isDataLoading ? "LOADING" : data?.signal ?? "HOLD"}</div>
          <div className="signal-score">强度 {data?.score?.toFixed(0) ?? "—"}</div>
          <ul className="reasons">
            {(data?.reasons ?? []).map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        </div>
      </section>

      <main className="grid">
        <IntradayChart data={chartData} loading={isPreparingData && Boolean(stableChartData)} />
        <div className="side-column">
          <TradeList data={data} />
          <FactorPanel data={data} />
        </div>
      </main>

      <footer className="footer">
        数据来源：AkShare / 东方财富 · 仅供研究，不构成投资建议
      </footer>
    </div>
  );
}
