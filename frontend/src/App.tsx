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
  const [symbolInput, setSymbolInput] = useState("600938");
  const [tradeDate, setTradeDate] = useState(todayString());
  const [loading, setLoading] = useState(false);
  const [dateLoading, setDateLoading] = useState(false);
  const [clearing, setClearing] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [previewData, setPreviewData] = useState<RealtimePayload | null>(null);
  const [stableChartData, setStableChartData] = useState<RealtimePayload | null>(null);
  const isPreparingData = loading || dateLoading || clearing || refreshing;
  const isViewingToday = tradeDate === todayString();
  const liveData = data?.trade_date === todayString() ? data : null;
  const isLiveDataLoading = liveData?.data_status === "loading";
  const liveDisplayData = isLiveDataLoading && stableChartData ? stableChartData : liveData ?? stableChartData;
  const displayData = isViewingToday ? liveDisplayData : previewData;
  const isDisplayDataLoading = displayData?.data_status === "loading";
  const isSyntheticData = displayData?.data_status === "synthetic";

  useEffect(() => {
    if (data?.trade_date === todayString() && (data?.minute_points?.length ?? 0) > 0) {
      setStableChartData(data);
    }
  }, [data]);

  const chartData = isPreparingData && isViewingToday && stableChartData ? stableChartData : displayData;

  const handleSetSymbol = async () => {
    setLoading(true);
    try {
      await apiSetSymbol(symbolInput.trim());
      if (!isViewingToday) {
        const result = await apiSetTradeDate(tradeDate);
        setPreviewData(result?.latest ?? null);
      } else {
        setPreviewData(null);
      }
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
      const result = await apiSetTradeDate(nextTradeDate);
      if (nextTradeDate === todayString()) {
        setPreviewData(null);
      } else {
        setPreviewData(result?.latest ?? null);
      }
    } finally {
      setDateLoading(false);
    }
  };

  const handleToday = async () => {
    const today = todayString();
    setTradeDate(today);
    setPreviewData(null);
    setDateLoading(true);
    try {
      await apiSetTradeDate(today);
    } finally {
      setDateLoading(false);
    }
  };

  const handleRefreshCache = async () => {
    if (!window.confirm(`确定拉取当前股票 ${tradeDate} 的行情并重新计算吗？`)) {
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
          placeholder="股票代码，如 600938"
          maxLength={6}
        />
        <button onClick={handleSetSymbol} disabled={loading}>
          {loading ? "切换中…" : "监控此股"}
        </button>
        <input
          className="date-input"
          type="date"
          value={tradeDate}
          onChange={(e) => {
            setTradeDate(e.target.value);
            setPreviewData(null);
          }}
        />
        <button
          className="secondary"
          onClick={() => handleSetTradeDate()}
          disabled={dateLoading || !tradeDate}
        >
          {dateLoading ? "加载中…" : "切换交易日"}
        </button>
        <button
          className="secondary date-step"
          onClick={handleToday}
          disabled={dateLoading}
        >
          今日
        </button>
        <button
          className="secondary"
          onClick={handleClearRecalculate}
          disabled={clearing || refreshing || !tradeDate}
        >
          {clearing ? "清空中…" : "重新计算"}
        </button>
        <button
          className="secondary"
          onClick={handleRefreshCache}
          disabled={refreshing || clearing || !tradeDate}
        >
          {refreshing ? "拉取中…" : "拉取行情"}
        </button>
      </section>

      <section className="hero">
        <div className="stock-info">
          <h2>
            {displayData?.name || "—"} <span className="code">{displayData?.symbol || symbolInput}</span>
          </h2>
          <p className="trade-date">交易日：{displayData?.trade_date || tradeDate}</p>
          <p className="quote-time">行情时间：{displayData?.quote_time || "—"}</p>
          <div className="price-row">
            <span className="price">{isDisplayDataLoading ? "—" : displayData?.price?.toFixed(2) ?? "—"}</span>
            <span
              className={
                (displayData?.change_pct ?? 0) >= 0 ? "change up" : "change down"
              }
            >
              {!isDisplayDataLoading && displayData?.change_pct != null
                ? `${displayData.change_pct >= 0 ? "+" : ""}${displayData.change_pct.toFixed(2)}%`
                : "—"}
            </span>
          </div>
          <p className="vwap">
            VWAP: {isDisplayDataLoading ? "—" : displayData?.vwap?.toFixed(2) ?? "—"}
            {isSyntheticData ? " · 分钟行情不可用，仅展示日线估算" : ""}
          </p>
          {displayData?.vwap_thresholds && (
            <p className="signal-thresholds">
              买点条件① 低于分时均线{" "}
              {displayData.vwap_thresholds.buy_zone_pct.toFixed(2)}%
              （固定阈值）
              {" · "}
              且（1分MACD DIF&lt;-0.07且金叉/即将金叉，或MACD未预热，或5分钟KDJ J&lt;20）
              {" · "}
              卖点：涨1% / 死叉 / 涨0.8%且1分MACD即将死叉
            </p>
          )}
          <p className="t0-pair">
            已完成 T0：买 {displayData?.buy_count ?? 0} / 卖 {displayData?.sell_count ?? 0} ✓ 数量相等
            {displayData?.pending_buy ? ` · 待卖出买点 ${displayData.pending_buy.price.toFixed(2)}` : ""}
          </p>
        </div>
        <div className={`signal-card ${signalClass(displayData?.signal ?? "HOLD")}`}>
          <div className="signal-label">当前信号</div>
          <div className="signal-value">{displayData?.signal ?? "HOLD"}</div>
          <ul className="reasons">
            {(displayData?.reasons ?? []).map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        </div>
      </section>

      <main className="grid">
        <IntradayChart data={chartData} loading={isPreparingData && Boolean(stableChartData)} />
        <div className="side-column">
          <TradeList data={displayData} />
          <FactorPanel data={displayData} />
        </div>
      </main>

      <footer className="footer">
        数据来源：AkShare / 东方财富 · 仅供研究，不构成投资建议
      </footer>
    </div>
  );
}
