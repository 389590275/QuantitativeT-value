import { useCallback, useEffect, useRef, useState } from "react";
import type { RealtimePayload } from "../types";

const API_HOST = typeof __API_HOST__ !== "undefined" ? __API_HOST__ : "127.0.0.1";
const API_PORT = typeof __API_PORT__ !== "undefined" ? __API_PORT__ : "10002";

function wsUrl(): string {
  return `ws://${API_HOST}:${API_PORT}/ws/realtime`;
}

export function useRealtime() {
  const [data, setData] = useState<RealtimePayload | null>(null);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const unmountedRef = useRef(false);

  const connect = useCallback(() => {
    if (unmountedRef.current) return;

    const existing = wsRef.current;
    if (
      existing &&
      (existing.readyState === WebSocket.OPEN ||
        existing.readyState === WebSocket.CONNECTING)
    ) {
      return;
    }

    if (existing) {
      existing.onclose = null;
      existing.onerror = null;
      existing.close();
    }

    const ws = new WebSocket(wsUrl());
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);

    ws.onerror = () => {
      setConnected(false);
    };

    ws.onclose = () => {
      setConnected(false);
      wsRef.current = null;
      if (!unmountedRef.current) {
        reconnectRef.current = setTimeout(connect, 3000);
      }
    };

    ws.onmessage = (ev) => {
      try {
        const parsed = JSON.parse(ev.data);
        if (parsed.type === "ping") return;
        setData(parsed as RealtimePayload);
      } catch {
        /* ignore */
      }
    };
  }, []);

  useEffect(() => {
    unmountedRef.current = false;
    connect();
    return () => {
      unmountedRef.current = true;
      if (reconnectRef.current) {
        clearTimeout(reconnectRef.current);
        reconnectRef.current = null;
      }
      const ws = wsRef.current;
      if (ws) {
        ws.onclose = null;
        ws.onerror = null;
        ws.close();
        wsRef.current = null;
      }
    };
  }, [connect]);

  return { data, connected };
}

export async function apiSetSymbol(symbol: string) {
  const res = await fetch("/api/symbol", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ symbol }),
  });
  return res.json();
}

export async function apiSetTradeDate(tradeDate: string) {
  const res = await fetch("/api/trade-date", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ trade_date: tradeDate }),
  });
  return res.json();
}

export async function apiShiftTradeDate(offset: number, tradeDate: string) {
  const res = await fetch("/api/trade-date/shift", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ offset, trade_date: tradeDate }),
  });
  return res.json();
}

export async function apiStart() {
  await fetch("/api/start", { method: "POST" });
}

export async function apiClearRecalculate(tradeDate: string) {
  const res = await fetch("/api/clear-recalculate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ trade_date: tradeDate }),
  });
  return res.json();
}

export async function apiRefreshCache(tradeDate: string) {
  const res = await fetch("/api/refresh-cache", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ trade_date: tradeDate }),
  });
  return res.json();
}
