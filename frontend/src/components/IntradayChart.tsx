import {
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ReferenceDot,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ACTIVE_FACTOR_KEYS, FACTOR_LABELS } from "../types";
import type { MinutePoint, RealtimePayload } from "../types";

interface Props {
  data: RealtimePayload | null;
  loading?: boolean;
}

interface ChartPoint {
  time: string;
  price: number | null;
  vwap: number | null;
  factors?: Record<string, number>;
  factor_status?: Record<string, string>;
  signal?: string;
  reasons?: string[];
  markerSignal?: "BUY" | "SELL";
  markerPrice?: number;
  markerReason?: string;
}

type MarkerPoint = ChartPoint & { markerSignal: "BUY" | "SELL"; price: number };

const FULL_TRADING_TIMES = buildTradingTimes();
const X_TICKS = ["09:30:00", "10:30:00", "11:30:00", "14:00:00", "15:00:00"];

function buildTradingTimes(): string[] {
  return [
    ...buildTimeRange("09:30:00", "11:30:00"),
    ...buildTimeRange("13:00:00", "15:00:00"),
  ];
}

function buildTimeRange(start: string, end: string): string[] {
  const out: string[] = [];
  const startSec = timeToSec(start);
  const endSec = timeToSec(end);
  for (let sec = startSec; sec <= endSec; sec += 60) {
    out.push(secToTime(sec));
  }
  return out;
}

function secToTime(total: number): string {
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  return [h, m, s].map((n) => String(n).padStart(2, "0")).join(":");
}

function normTime(t: string): string {
  const s = String(t).trim();
  const part = s.includes(" ") ? s.split(" ").pop()! : s;
  if (part.length >= 8) return part.slice(0, 8);
  if (part.length === 5) return `${part}:00`;
  return part;
}

function timeToSec(t: string): number {
  const [h, m, sec] = normTime(t).split(":").map(Number);
  return (h || 0) * 3600 + (m || 0) * 60 + (sec || 0);
}

function formatXAxisTick(t: string): string {
  const time = normTime(t).slice(0, 5);
  return time === "11:30" ? "11:30/13:00" : time;
}

function findClosestIndex(points: { time: string }[], markTime: string): number {
  const target = timeToSec(markTime);
  let best = 0;
  let bestDiff = Infinity;
  points.forEach((p, i) => {
    const diff = Math.abs(timeToSec(p.time) - target);
    if (diff < bestDiff) {
      bestDiff = diff;
      best = i;
    }
  });
  return best;
}

function BuyDot(props: { cx?: number; cy?: number; title?: string }) {
  const { cx, cy, title } = props;
  if (typeof cx !== "number" || typeof cy !== "number" || Number.isNaN(cx) || Number.isNaN(cy)) {
    return null;
  }
  const y = cy + 16;
  return (
    <g>
      {title ? <title>{title}</title> : null}
      <polygon
        points={`${cx},${y - 8} ${cx - 8},${y + 7} ${cx + 8},${y + 7}`}
        fill="#22c55e"
        stroke="#fff"
        strokeWidth={1.5}
      />
      <text x={cx} y={y + 20} textAnchor="middle" fill="#22c55e" fontSize={10} fontWeight={700}>
        买
      </text>
    </g>
  );
}

function SellDot(props: { cx?: number; cy?: number; title?: string }) {
  const { cx, cy, title } = props;
  if (typeof cx !== "number" || typeof cy !== "number" || Number.isNaN(cx) || Number.isNaN(cy)) {
    return null;
  }
  const y = cy + 16;
  return (
    <g>
      {title ? <title>{title}</title> : null}
      <polygon
        points={`${cx},${y + 8} ${cx - 8},${y - 7} ${cx + 8},${y - 7}`}
        fill="#ef4444"
        stroke="#fff"
        strokeWidth={1.5}
      />
      <text x={cx} y={y + 22} textAnchor="middle" fill="#ef4444" fontSize={10} fontWeight={700}>
        卖
      </text>
    </g>
  );
}

function BuyReferenceShape(props: { cx?: number; cy?: number; marker?: MarkerPoint }) {
  const marker = props.marker;
  return (
    <BuyDot
      cx={props.cx}
      cy={props.cy}
      title={marker ? markerTitle(marker) : undefined}
    />
  );
}

function SellReferenceShape(props: { cx?: number; cy?: number; marker?: MarkerPoint }) {
  const marker = props.marker;
  return (
    <SellDot
      cx={props.cx}
      cy={props.cy}
      title={marker ? markerTitle(marker) : undefined}
    />
  );
}

function formatNumber(value: number | undefined, digits = 4): string {
  if (typeof value !== "number" || Number.isNaN(value)) return "—";
  return value.toFixed(digits);
}

function formatVwapBias(price: number | null | undefined, vwap: number | null | undefined): string {
  if (
    typeof price !== "number" ||
    Number.isNaN(price) ||
    typeof vwap !== "number" ||
    Number.isNaN(vwap) ||
    vwap <= 0
  ) {
    return "—";
  }
  const bias = ((price - vwap) / vwap) * 100;
  return `${bias >= 0 ? "+" : ""}${bias.toFixed(2)}%`;
}

function macdDif(point: Pick<ChartPoint, "factors">): number | undefined {
  const value = point.factors?.macd_fs;
  return typeof value === "number" && !Number.isNaN(value) ? value : undefined;
}

function markerTitle(marker: MarkerPoint): string {
  const title = [
    `${marker.markerSignal === "BUY" ? "买点" : "卖点"} ${marker.time}`,
    `价格: ${formatNumber(marker.markerPrice ?? marker.price ?? undefined, 2)}`,
    `分时均线: ${formatNumber(marker.vwap ?? undefined, 2)}`,
    `距分时均线: ${formatVwapBias(marker.markerPrice ?? marker.price, marker.vwap)}`,
    `1分MACD DIF: ${formatNumber(macdDif(marker), 4)}`,
    `原因: ${marker.markerReason ?? "—"}`,
  ];

  const factorRows = Object.entries(marker.factors ?? {}).filter(([key]) =>
    ACTIVE_FACTOR_KEYS.has(key)
  );
  if (factorRows.length > 0) {
    title.push("因子快照:");
    factorRows.forEach(([key, value]) => {
      title.push(
        `${FACTOR_LABELS[key] ?? key}: ${formatNumber(value)} (${marker.factor_status?.[key] ?? "中性"})`
      );
    });
  } else {
    title.push("因子快照: 暂无");
  }

  return title.join("\n");
}

function FactorTooltip(props: { active?: boolean; payload?: Array<{ payload: ChartPoint }> }) {
  const point =
    props.payload?.find((item) => item.payload?.markerSignal)?.payload ??
    props.payload?.[0]?.payload;
  if (!props.active || !point) return null;

  const factorRows = Object.entries(point.factors ?? {}).filter(([key]) =>
    ACTIVE_FACTOR_KEYS.has(key)
  );
  const isMarker = Boolean(point.markerSignal);

  return (
    <div className="chart-tooltip">
      <div className="tooltip-title">
        {point.time}
        {isMarker ? ` · ${point.markerSignal === "BUY" ? "买点" : "卖点"}` : ""}
      </div>
      <div className="tooltip-row">
        <span>价格</span>
        <b>{formatNumber(point.price ?? undefined, 2)}</b>
      </div>
      {isMarker ? (
        <>
          <div className="tooltip-row">
            <span>成交标记</span>
            <b>{point.markerSignal === "BUY" ? "买点" : "卖点"}</b>
          </div>
          <div className="tooltip-row">
            <span>标记价格</span>
            <b>{formatNumber(point.markerPrice ?? point.price ?? undefined, 2)}</b>
          </div>
          {point.markerReason ? (
            <div className="tooltip-row">
              <span>原因</span>
              <b>{point.markerReason}</b>
            </div>
          ) : null}
        </>
      ) : null}
      <div className="tooltip-row">
        <span>分时均线</span>
        <b>{formatNumber(point.vwap ?? undefined, 2)}</b>
      </div>
      <div className="tooltip-row">
        <span>距分时均线</span>
        <b>{formatVwapBias(point.price, point.vwap)}</b>
      </div>
      <div className="tooltip-row">
        <span>1分MACD DIF</span>
        <b>{formatNumber(macdDif(point), 4)}</b>
      </div>
      {point.signal ? (
        <div className="tooltip-row">
          <span>信号</span>
          <b>{point.signal}</b>
        </div>
      ) : null}
      {factorRows.length > 0 ? (
        <div className="tooltip-factors">
          {factorRows.map(([key, value]) => (
            <div className="tooltip-row factor" key={key}>
              <span>{FACTOR_LABELS[key] ?? key}</span>
              <b>
                {formatNumber(value)}
                <em>
                  {point.factor_status?.[key] ?? "中性"}
                </em>
              </b>
            </div>
          ))}
        </div>
      ) : (
        <div className="tooltip-empty">该历史点暂无因子快照</div>
      )}
    </div>
  );
}

export function IntradayChart({ data, loading = false }: Props) {
  const points = data?.minute_points ?? [];
  const marks = data?.signal_marks ?? [];
  const isLoadingData = data?.data_status === "loading";

  if (isLoadingData || points.length === 0) {
    return (
      <div className="panel chart-panel">
        <h3>分时图</h3>
        <p className="muted">
          {isLoadingData ? "行情加载中，暂不计算买卖点" : "暂无分时数据（非交易时段或行情加载中）"}
        </p>
      </div>
    );
  }

  const actualData: ChartPoint[] = points.map((p: MinutePoint, i) => ({
    time: normTime(p.time || String(i)),
    price: p.price,
    vwap: p.vwap,
    factors: p.factors,
    factor_status: p.factor_status,
    signal: p.signal,
    reasons: p.reasons,
  }));
  const pointByTime = new Map(actualData.map((p) => [p.time, p]));
  const chartData: ChartPoint[] = FULL_TRADING_TIMES.map((time) => (
    pointByTime.get(time) ?? { time, price: null, vwap: null }
  ));

  const markerData: MarkerPoint[] = [];
  marks
    .filter((m) => m.signal === "BUY" || m.signal === "SELL")
    .forEach((m) => {
      const idx = findClosestIndex(actualData, m.time);
      const base = actualData[idx];
      if (!base || typeof base.price !== "number" || Number.isNaN(base.price)) {
        return;
      }
      markerData.push({
        ...base,
        // 用分时价格线定位，三角形自身再向下偏移，避免遮挡价格线。
        price: base.price,
        markerSignal: m.signal as "BUY" | "SELL",
        markerPrice: m.price,
        markerReason: m.reason,
      });
    });

  const buyMarkData = markerData.filter((p) => p.markerSignal === "BUY");
  const sellMarkData = markerData.filter((p) => p.markerSignal === "SELL");

  const buyN = data?.buy_count ?? marks.filter((m) => m.signal === "BUY").length;
  const sellN = data?.sell_count ?? marks.filter((m) => m.signal === "SELL").length;
  const balanced = buyN === sellN;
  const pendingBuy = data?.pending_buy;

  return (
    <div className="panel chart-panel">
      <div className="chart-header">
        <h3>分时图 · 买卖点</h3>
        <div className="chart-badges">
          {loading ? (
            <span className="t0-stats pending">数据准备中，保留上一版图形</span>
          ) : null}
          {data?.data_status === "synthetic" ? (
            <span className="t0-stats pending">分钟行情不可用，仅展示日线估算，不计算买卖点</span>
          ) : null}
          <span className={`t0-stats ${balanced ? "balanced" : "open"}`}>
            已完成 买 {buyN} / 卖 {sellN}
            {balanced ? " · 数量相等" : ""}
          </span>
          {pendingBuy ? (
            <span className="t0-stats pending">
              待卖出买点 {pendingBuy.price.toFixed(2)}
            </span>
          ) : null}
        </div>
      </div>
      <ResponsiveContainer width="100%" height={320}>
        <ComposedChart data={chartData} margin={{ top: 20, right: 12, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
          <XAxis
            dataKey="time"
            tick={{ fontSize: 10 }}
            ticks={X_TICKS}
            tickFormatter={formatXAxisTick}
            interval={0}
          />
          <YAxis domain={["auto", "auto"]} tick={{ fontSize: 11 }} />
          <Tooltip content={<FactorTooltip />} />
          <Legend />
          <Line type="monotone" dataKey="price" stroke="#4ade80" dot={false} name="价格" />
          <Line type="monotone" dataKey="vwap" stroke="#60a5fa" dot={false} name="VWAP" />
          {buyMarkData.map((p, idx) => (
            <ReferenceDot
              key={`buy-${p.time}-${idx}`}
              x={p.time}
              y={p.price}
              r={0}
              ifOverflow="visible"
              shape={<BuyReferenceShape marker={p} />}
            />
          ))}
          {sellMarkData.map((p, idx) => (
            <ReferenceDot
              key={`sell-${p.time}-${idx}`}
              x={p.time}
              y={p.price}
              r={0}
              ifOverflow="visible"
              shape={<SellReferenceShape marker={p} />}
            />
          ))}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
