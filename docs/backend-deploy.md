# SciPoster 后端部署说明

## 目录

- 后端目录：`D:\SciPoster\backend`

## 环境变量模板

复制：

```powershell
Copy-Item D:\SciPoster\backend\.env.example D:\SciPoster\backend\.env
```

## 必填项

- `PORT=8787`
- `POSTER_PROVIDER=fastclaw`
- `SLIDES_PROVIDER=fastclaw`
- `ARTICLE_PROVIDER=fastclaw`
- `SOCIAL_PROVIDER=fastclaw`
- `FASTCLAW_BASE_URL=http://127.0.0.1:18954`
- `FASTCLAW_API_KEY=<FastClaw middleware key>`
- `FASTCLAW_END_USER=sciposter-local-user`
- `FASTCLAW_MODEL=fastclaw-router`
- `FASTCLAW_TIMEOUT_MS=120000`
- `FASTCLAW_POSTER_AGENT_ID`
- `FASTCLAW_SLIDES_AGENT_ID`
- `FASTCLAW_POPULAR_ARTICLE_AGENT_ID`
- `FASTCLAW_XIAOHONGSHU_AGENT_ID`

## 构建与启动

```powershell
cd D:\SciPoster\backend
npm install
npm run build
node dist/index.js
```

## 说明

- 当前 backend 默认 workspace 根目录读取自 `backend/src/config.ts`
- 默认值是 `D:/SciPoster/fastclaw-home-fixed/workspaces`
- 如果部署机器目录不同，需通过环境变量覆盖
