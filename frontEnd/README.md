# OpenClaw Chat Viewer

聊天记录管理后台，读取 OpenClaw session JSONL 文件，清洗后展示历史聊天记录。

## 快速开始

```bash
npm install
node scripts/sync.js   # 清洗数据
npm run build           # 构建前端
npm start               # 启动服务 http://localhost:3001
```

## 开发

```bash
npm start &             # 后端 3001
npm run dev             # 前端 5173（自动代理 API）
```

## API

- `GET /api/sessions` — 会话列表
- `GET /api/sessions/:id` — 会话消息
- `POST /api/sync` — 重新清洗数据
