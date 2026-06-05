export interface VwapThresholdsInfo {
  avg_amplitude_5d: number;
  buy_zone_pct: number;
  extreme_down_pct: number;
  extreme_up_pct: number;
  full_deviation_pct: number;
  bias_status_pct: number;
  early_session_active?: boolean;
}

export interface RealtimePayload {
  symbol: string;
  name: string;
  trade_date?: string;
  quote_time?: string;
  price: number;
  prev_close?: number;
  change_pct: number | null;
  signal: string;
  reasons: string[];
  factors: Record<string, number>;
  factor_status: Record<string, string>;
  vwap: number;
  minute_points: MinutePoint[];
  signal_marks: { time: string; signal: string; price: number; reason?: string }[];
  pending_buy?: { time: string; signal: string; price: number; reason?: string } | null;
  t0_position?: "flat" | "long";
  buy_count?: number;
  sell_count?: number;
  data_status?: "ok" | "loading" | "synthetic";
  vwap_thresholds?: VwapThresholdsInfo;
}

export interface MinutePoint {
  time: string;
  price: number;
  vwap: number;
  factors?: Record<string, number>;
  factor_status?: Record<string, string>;
  signal?: string;
  reasons?: string[];
}

export const FACTOR_LABELS: Record<string, string> = {
  vwap_bias: "分时均线偏离",
  kdj_5m: "5分钟KDJ",
  macd_fs: "1分MACD",
};

export const ACTIVE_FACTOR_KEYS = new Set([
  "vwap_bias",
  "kdj_5m",
  "macd_fs",
]);
