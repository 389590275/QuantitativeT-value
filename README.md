# A股 T0 量化助手 MVP

基于需求文档实现的最小可用版本：1 只股票、3 个核心因子、实时 WebSocket 推送、买卖信号、Windows 桌面通知、企业微信 Webhook。

## 项目结构

```text
QuantitativeT-value/
├── backend/          # Python FastAPI 后端
├── frontend/         # React + Electron 桌面端
├── .env.example      # 配置模板
└── data/             # 本地 SQLite（运行后自动生成；生产见 DB_PATH）
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

- `SYMBOL`：监控股票代码（如 `600938`）
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
| 因子 | 分时偏离、5分钟KDJ、1分MACD |
| 买点 | 低于分时均线固定 0.5% 且（1分MACD DIF<-0.07 且金叉；或 MACD未预热） |
| 卖点 | 距买点涨幅≥2%；或 1分MACD死叉 |
| 通知 | 信号首次出现时：桌面通知 + 企微（去重） |
| 存储 | SQLite（`DB_PATH`）；生产默认 `/data/save/t0.db` |

## API

- `GET /api/health` — 健康检查
- `GET /api/status` — 当前状态
- `POST /api/symbol` — 切换股票 `{"symbol":"600938"}`
- `POST /api/start` / `POST /api/stop` — 引擎控制
- `WS /ws/realtime` — 实时推送

## CentOS 生产部署

| 路径 | 用途 |
|------|------|
| `/data/app` | 程序代码（打包解压目录） |
| `/data/save` | SQLite 与持久化数据（`.env` 中 `DB_PATH=/data/save/t0.db`） |
| `/data/app/logs` | 运行日志 |

```bash
# 打包（Windows）
powershell -ExecutionPolicy Bypass -File scripts\package.ps1

# 服务器解压后
cd /data/app
bash scripts/init_prod_dirs.sh   # 创建 /data/save 等目录
bash scripts/install_deps.sh
bash scripts/start.sh
```

若此前数据库在 `/data/app/data/t0.db`，迁移示例：

```bash
mkdir -p /data/save
cp -a /data/app/data/t0.db /data/save/t0.db
```

## 注意事项

- **交易时段**外行情可能为空或延迟，属数据源限制。
- 本系统**不执行自动交易**，仅供因子与信号验证。
- 首次拉取全市场 spot 较慢，请耐心等待几秒。

## MVP 验收

1. 交易时段内价格约 1 秒刷新
2. 因子面板 3 项实时更新
3. 满足规则时出现 BUY/SELL 并推送通知

$body = @{
  msgtype = "markdown"
  markdown = @{
    content = "### T0 测试`n买卖点通知通道正常"
  }
} | ConvertTo-Json -Depth 3

Invoke-RestMethod -Uri "https://work.weixin.qq.com/wework_admin/common/openBotProfile/24e5d2aecdb2f20851b8c7da81dd6e0461" -Method Post -Body $body -ContentType "application/json; charset=utf-8"