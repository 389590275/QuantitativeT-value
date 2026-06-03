export interface RealtimePayload {
  symbol: string;
  name: string;
  trade_date?: string;
  quote_time?: string;
  price: number;
  change_pct: number | null;
  signal: string;
  score: number;
  reasons: string[];
  factors: Record<string, number>;
  factor_status: Record<string, string>;
  factor_scores: Record<string, number>;
  vwap: number;
  minute_points: MinutePoint[];
  signal_marks: { time: string; signal: string; price: number; score?: number; reason?: string }[];
  pending_buy?: { time: string; signal: string; price: number; score?: number; reason?: string } | null;
  t0_position?: "flat" | "long";
  buy_count?: number;
  sell_count?: number;
  data_status?: "ok" | "loading" | "synthetic";
}

export interface MinutePoint {
  time: string;
  price: number;
  vwap: number;
  factors?: Record<string, number>;
  factor_status?: Record<string, string>;
  factor_scores?: Record<string, number>;
  signal?: string;
  score?: number;
  reasons?: string[];
}

export const FACTOR_LABELS: Record<string, string> = {
  vwap_bias: "分时均线偏离",
  kdj_5m: "5分钟KDJ",
  macd_fs: "MACD快慢线差",
};

export const ACTIVE_FACTOR_KEYS = new Set([
  "vwap_bias",
  "kdj_5m",
  "macd_fs",
]);
