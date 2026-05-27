import type { RealtimePayload } from "../types";

interface Props {
  data: RealtimePayload | null;
}

function formatPrice(value: number | undefined): string {
  return typeof value === "number" && !Number.isNaN(value) ? value.toFixed(2) : "—";
}

function formatScore(value: number | undefined): string {
  return typeof value === "number" && !Number.isNaN(value) ? value.toFixed(0) : "—";
}

export function TradeList({ data }: Props) {
  const rows = data?.signal_marks ?? [];
  const pendingBuy = data?.pending_buy;

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
          待卖出：{pendingBuy.time} 买入 {formatPrice(pendingBuy.price)}，
          强度 {formatScore(pendingBuy.score)}
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
              <th>评分</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, idx) => (
              <tr key={`${row.signal}-${row.time}-${idx}`} className={`trade-${row.signal}`}>
                <td>{row.time}</td>
                <td>{row.signal === "BUY" ? "买" : "卖"}</td>
                <td>{formatPrice(row.price)}</td>
                <td>{formatScore(row.score)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
