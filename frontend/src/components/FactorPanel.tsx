import { ACTIVE_FACTOR_KEYS, FACTOR_LABELS } from "../types";
import type { RealtimePayload } from "../types";

interface Props {
  data: RealtimePayload | null;
}

export function FactorPanel({ data }: Props) {
  if (!data) {
    return <div className="panel">等待行情数据…</div>;
  }

  const rows = Object.entries(data.factors).map(([key, value]) => ({
    key,
    label: FACTOR_LABELS[key] ?? key,
    value,
    status: data.factor_status[key] ?? "中性",
    score: data.factor_scores?.[key] ?? 0,
    active: ACTIVE_FACTOR_KEYS.has(key),
  }));

  return (
    <div className="panel factor-panel">
      <h3>因子面板</h3>
      <table>
        <thead>
          <tr>
            <th>因子</th>
            <th>当前值</th>
            <th>状态</th>
            <th>打分</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr
              key={r.key}
              className={`${r.active ? `status-${r.status}` : "factor-disabled"}`}
            >
              <td>{r.label}</td>
              <td>{typeof r.value === "number" ? r.value.toFixed(4) : r.value}</td>
              <td>{r.active ? r.status : "停用"}</td>
              <td>{r.active ? (r.score > 0 ? `+${r.score.toFixed(1)}` : r.score.toFixed(1)) : "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
