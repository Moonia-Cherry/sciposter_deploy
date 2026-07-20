# SciPoster 部署检查清单

## 部署前

- 确认主项目根目录为 `D:\SciPoster`
- 确认 FastClaw 根目录为 `D:\State_Key_Lab_Media_Convergence_Communication\poster\fastclaw-dev\fastclaw-dev`
- 确认 `D:\SciPoster\fastclaw-home-fixed` 已存在
- 确认 Docker Desktop 可正常运行
- 确认上游模型 API Key 已准备

## FastClaw

- 执行 `D:\SciPoster\scripts\start-fastclaw.ps1`
- 确认 `http://127.0.0.1:18954/healthz` 可访问
- 执行 `D:\SciPoster\scripts\init-fastclaw-agents.ps1`
- 执行 `D:\SciPoster\scripts\sync-fastclaw-agent-files.ps1`

## Agent 与 Skill

- `poster-agent` 已挂载 `academic-poster-fastclaw-upload`
- `poster-fastclaw-upload-agent` 已挂载 `academic-poster-fastclaw-upload`
- `slides-agent` 已挂载 `slides-fastclaw-upload`
- `popular-article-agent` 已挂载 `popular-article-fastclaw-upload`
- `xiaohongshu-agent` 已挂载 `xhs-fastclaw-upload`

## 后端

- `backend/.env` 已从 `.env.example` 复制
- 四类 provider 已切到 `fastclaw`
- `FASTCLAW_BASE_URL` 为 `http://127.0.0.1:18954`
- 四个后端使用的 agent id 已填写
- `npm run build` 成功
- `node dist/index.js` 成功启动

## 前端

- `app` 目录依赖已安装
- `npm run build` 成功
- 已确认 `src/shared/api.ts` 中的 backend/FastClaw 地址是否符合部署环境

## 提交 PR 前

- `manifest.json` 已更新
- `config/agents.json` 与 skill 包一致
- `README.md`、`docs/` 与实际执行步骤一致
- skill zip 已随仓库一并提交
