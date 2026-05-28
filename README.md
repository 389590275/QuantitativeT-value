# A股 T0 量化助手 MVP

基于需求文档实现的最小可用版本：1 只股票、10 个核心因子、实时 WebSocket 推送、买卖信号、Windows 桌面通知、企业微信 Webhook。

## 项目结构

```text
QuantitativeT-value/
├── backend/          # Python FastAPI 后端
├── frontend/         # React + Electron 桌面端
├── .env.example      # 配置模板
└── data/             # SQLite（运行后自动生成）
```

## 环境要求

- Python 3.9+
- Node.js 18+

## 快速开始

### 1. 配置

```bash
copy .env.example .env
```

编辑 `.env`：

- `SYMBOL`：监控股票代码（如 `600519`）
- `SECTOR_ETF`：行业 ETF（因子9，默认 `512880`）
- `WECOM_WEBHOOK`：企业微信机器人地址（可选）

### 2. 启动后端

```powershell
cd e:\WorkSpace\QuantitativeT-value
.\venv\Scripts\activate
pip install -r backend\requirements.txt
cd backend
python main.py
```

后端默认：`http://127.0.0.1:10002`  
WebSocket：`ws://127.0.0.1:10002/ws/realtime`

> 若 `10002` 仍被占用，可在 `.env` 中修改 `API_PORT`，并同步改 `frontend/vite.config.ts` 中的代理端口。

### 3. 启动前端（浏览器开发模式）

```powershell
cd frontend
npm install
npm run dev
```

浏览器打开：http://127.0.0.1:5173

### 4. 启动 Electron 桌面端

先确保后端已运行，再执行：

```powershell
cd frontend
npx tsc -p tsconfig.electron.json
npm run electron:dev
```

## 功能说明

| 模块 | 说明 |
|------|------|
| 行情 | AkShare + 东方财富实时行情，约 1 秒轮询 |
| 因子 | 10 个因子独立模块，统一 `BaseFactor` 接口 |
| 信号 | BUY / SELL / WATCH / HOLD，评分 0–100 |
| 通知 | 信号首次出现时：桌面通知 + 企微（去重） |
| 存储 | SQLite 记录 `signals`、`ticks` |

## API

- `GET /api/health` — 健康检查
- `GET /api/status` — 当前状态
- `POST /api/symbol` — 切换股票 `{"symbol":"600519"}`
- `POST /api/start` / `POST /api/stop` — 引擎控制
- `WS /ws/realtime` — 实时推送

## 注意事项

- **交易时段**外行情可能为空或延迟，属数据源限制。
- 本系统**不执行自动交易**，仅供因子与信号验证。
- 首次拉取全市场 spot 较慢，请耐心等待几秒。

## MVP 验收

1. 交易时段内价格约 1 秒刷新
2. 因子面板 10 项实时更新
3. 满足规则时出现 BUY/SELL 并推送通知

$body = @{
  msgtype = "markdown"
  markdown = @{
    content = "### T0 测试`n买卖点通知通道正常"
  }
} | ConvertTo-Json -Depth 3

Invoke-RestMethod -Uri "https://work.weixin.qq.com/wework_admin/common/openBotProfile/24e5d2aecdb2f20851b8c7da81dd6e0461" -Method Post -Body $body -ContentType "application/json; charset=utf-8"