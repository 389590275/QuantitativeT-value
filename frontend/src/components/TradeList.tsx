import { useState } from "react";
import type { RealtimePayload } from "../types";

interface Props {
  data: RealtimePayload | null;
}

type TradeMark = RealtimePayload["signal_marks"][number];

function formatPrice(value: number | undefined): string {
  return typeof value === "number" && !Number.isNaN(value) ? value.toFixed(2) : "—";
}

function formatChangePct(price: number | undefined, prevClose: number | undefined): string {
  if (
    typeof price !== "number" ||
    Number.isNaN(price) ||
    typeof prevClose !== "number" ||
    Number.isNaN(prevClose) ||
    prevClose <= 0
  ) {
    return "—";
  }
  const pct = (price / prevClose - 1) * 100;
  return `${pct >= 0 ? "+" : ""}${pct.toFixed(2)}%`;
}

function formatPct(value: number | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) return "—";
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function formatNumber(value: number | undefined, digits = 4): string {
  return typeof value === "number" && !Number.isNaN(value) ? value.toFixed(digits) : "—";
}

function normTime(time: string | undefined): string {
  const raw = String(time ?? "").trim();
  const part = raw.includes(" ") ? raw.split(" ").pop() ?? "" : raw;
  if (part.length >= 8) return part.slice(0, 8);
  if (part.length === 5) return `${part}:00`;
  return part;
}

function vwapBias(price: number | undefined, vwap: number | undefined): number | undefined {
  if (
    typeof price !== "number" ||
    Number.isNaN(price) ||
    typeof vwap !== "number" ||
    Number.isNaN(vwap) ||
    vwap <= 0
  ) {
    return undefined;
  }
  return ((price - vwap) / vwap) * 100;
}

export function TradeList({ data }: Props) {
  const rows = data?.signal_marks ?? [];
  const pendingBuy = data?.pending_buy;
  const [selected, setSelected] = useState<TradeMark | null>(null);
  const selectedMark = selected
    ? rows.find(
        (row) =>
          row.time === selected.time &&
          row.signal === selected.signal &&
          row.price === selected.price
      ) ?? null
    : null;
  const selectedPoint = selectedMark
    ? data?.minute_points?.find((point) => normTime(point.time) === normTime(selectedMark.time))
    : null;
  const selectedVwapBias = selectedMark
    ? vwapBias(selectedMark.price, selectedPoint?.vwap)
    : undefined;
  const buyThreshold = data?.vwap_thresholds?.buy_zone_pct;
  const macdDif = selectedPoint?.factors?.macd_fs;
  const macdStatus = selectedPoint?.factor_status?.macd_fs ?? "—";
  const kdjJ = selectedPoint?.factors?.kdj_5m;
  const kdjStatus = selectedPoint?.factor_status?.kdj_5m ?? "—";

  return (
    <div className="panel trade-list">
      <div className="trade-list-header">
        <h3>今日买卖点</h3>
        <span>
          买 {data?.buy_count ?? 0} / 卖 {data?.sell_count ?? 0}
        </span>
      </div>

      {pendingBuy ? (
        <div className="pending-trade">
          待卖出：{pendingBuy.time} 买入 {formatPrice(pendingBuy.price)}
        </div>
      ) : null}

      {rows.length === 0 ? (
        <p className="muted trade-empty">暂无已完成买卖点</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>时间</th>
              <th>方向</th>
              <th>价格</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, idx) => (
              <tr
                key={`${row.signal}-${row.time}-${idx}`}
                className={`trade-${row.signal} ${selectedMark === row ? "selected" : ""}`}
                onClick={() => setSelected(row)}
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    setSelected(row);
                  }
                }}
              >
                <td>{row.time}</td>
                <td>{row.signal === "BUY" ? "买" : "卖"}</td>
                <td>{formatPrice(row.price)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {selectedMark ? (
        <div className="trade-detail">
          <div className="trade-detail-title">
            {selectedMark.signal === "BUY" ? "买点详情" : "卖点详情"}
          </div>
          <div className="trade-detail-row">
            <span>股票</span>
            <b>{data?.name || "—"} ({data?.symbol || "—"})</b>
          </div>
          <div className="trade-detail-row">
            <span>信号</span>
            <b>{selectedMark.signal}</b>
          </div>
          <div className="trade-detail-row">
            <span>价格</span>
            <b>
              {formatPrice(selectedMark.price)} / {formatChangePct(selectedMark.price, data?.prev_close)}
            </b>
          </div>
          <div className="trade-detail-row">
            <span>今日</span>
            <b>买{data?.buy_count ?? 0} / 卖{data?.sell_count ?? 0}</b>
          </div>
          <div className="trade-detail-row">
            <span>距分时均线</span>
            <b>
              {formatPct(selectedVwapBias)}
              {typeof buyThreshold === "number" ? ` / 买点阈值 -${buyThreshold.toFixed(2)}%` : ""}
            </b>
          </div>
          <div className="trade-detail-row">
            <span>1分MACD DIF</span>
            <b>{formatNumber(macdDif, 4)}（{macdStatus}）</b>
          </div>
          <div className="trade-detail-row">
            <span>5分钟KDJ J</span>
            <b>{formatNumber(kdjJ, 2)}（{kdjStatus}）</b>
          </div>
          <div className="trade-detail-row">
            <span>原因</span>
            <b>{selectedMark.reason || "—"}</b>
          </div>
        </div>
      ) : null}
    </div>
  );
}
