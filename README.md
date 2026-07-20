# SciPoster FastClaw Deployment Package

本目录用于给 `Moonia-Cherry/sciposter_deploy` 仓库提交部署交付内容，目标是让部署同学可以按现有项目真实结构完成 FastClaw、后端、前端的部署配置整理。

这个部署包只整理 SciPoster 当前项目所需的部署材料，不修改主项目业务逻辑，不改 FastClaw 源码，不改前端样式。

## 1. 当前项目的真实运行结构

- 前端目录：`D:\SciPoster\app`
- 后端目录：`D:\SciPoster\backend`
- FastClaw 源码/二进制目录：`D:\State_Key_Lab_Media_Convergence_Communication\poster\fastclaw-dev\fastclaw-dev`
- FastClaw HOME：`D:\SciPoster\fastclaw-home-fixed`
- FastClaw workspace 根目录：`D:\SciPoster\fastclaw-home-fixed\workspaces`
- FastClaw 网关地址：`http://127.0.0.1:18954`
- 后端 API 地址：`http://127.0.0.1:8787`

当前链路是：

1. 前端调用 `SciPoster backend`
2. backend 按 jobType 路由到对应 FastClaw agent
3. FastClaw agent 调用各自挂载的 upload-oriented skill
4. skill 在 agent workspace 中写出本地产物和预览文件

## 2. config 路径怎么配

首次部署时复制：

```powershell
Copy-Item .\config\deploy.example.json .\config\deploy.local.json
```

`config/deploy.local.json` 至少要确认这些字段：

- `fastclaw.host`: 固定为 `127.0.0.1`
- `fastclaw.port`: 固定为 `18954`
- `fastclaw.apiKeyName`: 建议保持 `sciposter-middleware`
- `administrator.*`: FastClaw 管理员账号
- `provider.*`: 上游模型配置
- `paths.projectRoot`: `D:/SciPoster`
- `paths.fastclawRoot`: `D:/State_Key_Lab_Media_Convergence_Communication/poster/fastclaw-dev/fastclaw-dev`
- `paths.fastclawHome`: `D:/SciPoster/fastclaw-home-fixed`
- `paths.fastclawWorkspaceRoot`: `D:/SciPoster/fastclaw-home-fixed/workspaces`
- `paths.backendRoot`: `D:/SciPoster/backend`
- `paths.frontendRoot`: `D:/SciPoster/app`

说明：

- `paths` 字段主要用于部署文档对齐和人工核对，当前 `bootstrap.py` 不直接消费这些路径。
- 真正启动 FastClaw 仍以主项目里的 `scripts/start-fastclaw.ps1` 为准。

## 3. FastClaw 初始化参数怎么写

以主项目真实脚本 `D:\SciPoster\scripts\start-fastclaw.ps1` 为准，当前实际参数是：

```powershell
$env:FASTCLAW_HOME = "D:\SciPoster\fastclaw-home-fixed"
$env:FASTCLAW_PORT = "18954"
$env:FASTCLAW_BIND = "loopback"
$env:FASTCLAW_SANDBOX_ENABLED = "true"
$env:FASTCLAW_SANDBOX_BACKEND = "docker"
$env:FASTCLAW_SANDBOX_IMAGE = "thinkany/fastclaw-sandbox:latest"
$env:NO_PROXY = "127.0.0.1,localhost"
$env:no_proxy = "127.0.0.1,localhost"
```

并清理这些代理变量：

- `HTTP_PROXY`
- `HTTPS_PROXY`
- `ALL_PROXY`
- `http_proxy`
- `https_proxy`
- `all_proxy`

启动命令：

```powershell
cd D:\SciPoster
.\scripts\start-fastclaw.ps1
```

## 4. 每个 agent 挂哪些 skill

当前项目推荐按“单 agent 单主 skill”挂载，避免通用 skill 叠加导致规划轮次增多和超时风险上升。

- `poster-agent` -> `academic-poster-fastclaw-upload`
- `poster-fastclaw-upload-agent` -> `academic-poster-fastclaw-upload`
- `slides-agent` -> `slides-fastclaw-upload`
- `popular-article-agent` -> `popular-article-fastclaw-upload`
- `xiaohongshu-agent` -> `xhs-fastclaw-upload`

其中：

- `poster-agent` 是给后端正式路由使用的学术海报 agent
- `poster-fastclaw-upload-agent` 是独立演示/联调用 agent

## 5. 部署同学需要执行哪些脚本

建议顺序如下。

### 5.1 启动 FastClaw

```powershell
cd D:\SciPoster
.\scripts\start-fastclaw.ps1
```

### 5.2 初始化 agent

```powershell
cd D:\SciPoster
.\scripts\init-fastclaw-agents.ps1
```

该脚本会初始化以下 5 个 agent：

- `poster-agent`
- `poster-fastclaw-upload-agent`
- `slides-agent`
- `popular-article-agent`
- `xiaohongshu-agent`

### 5.3 同步 agent 的 SOUL/IDENTITY 文件

```powershell
cd D:\SciPoster
.\scripts\sync-fastclaw-agent-files.ps1
```

### 5.4 构建或核对 skill zip

如果要从主项目重新打包 skill：

```powershell
cd D:\SciPoster
.\scripts\build-fastclaw-skill-zips.ps1
```

如果部署仓库已经收到了 `skills/*.zip`，部署同学通常不需要再本地打包。

### 5.5 后端启动

```powershell
cd D:\SciPoster\backend
Copy-Item .\.env.example .\.env
npm install
npm run build
node dist/index.js
```

后端 `.env` 里正式联调建议改成：

- `POSTER_PROVIDER=fastclaw`
- `SLIDES_PROVIDER=fastclaw`
- `ARTICLE_PROVIDER=fastclaw`
- `SOCIAL_PROVIDER=fastclaw`
- `FASTCLAW_BASE_URL=http://127.0.0.1:18954`

### 5.6 前端启动

```powershell
cd D:\SciPoster\app
npm install
npm run dev
```

## 6. 前端部署时要交哪些文件和配置

部署同学至少需要知道以下内容。

### 6.1 前端目录

- `D:\SciPoster\app`

### 6.2 前端构建命令

```powershell
npm install
npm run build
```

### 6.3 前端当前写死的联调地址

文件：`D:\SciPoster\app\src\shared\api.ts`

当前写死：

- backend `http://localhost:8787`
- fastclaw `http://localhost:18954`

因此部署说明里必须明确：

1. 如果前端与 backend/FastClaw 不在同一机器，需要调整这里的地址。
2. 如果只是本机演示环境，可以保持当前地址不变。
3. 这次交付不改前端样式，也不改前端接口设计，只做部署说明整理。

### 6.4 前端需要交付给部署同学的内容

- 前端源码目录说明
- 构建命令
- 接口基地址说明
- 如需反向代理时的目标地址说明

## 7. 后端部署时要交哪些配置

文件模板：`D:\SciPoster\backend\.env.example`

重点配置项：

- `PORT=8787`
- `FASTCLAW_BASE_URL=http://127.0.0.1:18954`
- `FASTCLAW_API_KEY=`
- `FASTCLAW_END_USER=sciposter-local-user`
- `FASTCLAW_MODEL=fastclaw-router`
- `FASTCLAW_TIMEOUT_MS=120000`
- `FASTCLAW_POSTER_AGENT_ID`
- `FASTCLAW_SLIDES_AGENT_ID`
- `FASTCLAW_POPULAR_ARTICLE_AGENT_ID`
- `FASTCLAW_XIAOHONGSHU_AGENT_ID`

说明：

- 当前 backend 没有单独使用 `poster-fastclaw-upload-agent` 的环境变量。
- 正式后端路由仍使用 `poster-agent`。
- `FASTCLAW_WORKSPACE_ROOT` 默认值见 `backend/src/config.ts`，当前默认是 `D:/SciPoster/fastclaw-home-fixed/workspaces`。

## 8. 建议给 PR 新增哪些目录和文档

建议在 `sciposter_deploy` 仓库里保留：

- `config/`
- `skills/`
- `agents/prompts/`
- `docs/`

建议新增文档：

- `docs/deploy-checklist.md`
- `docs/fastclaw-agent-skill-mapping.md`
- `docs/backend-deploy.md`
- `docs/frontend-deploy.md`
- `docs/pr-handoff.md`

## 9. 这次部署包和旧模板的主要区别

- FastClaw 端口从 `18953` 对齐为当前项目实际使用的 `18954`
- agent 从旧版 4 个扩展为当前真实使用的 5 个
- 旧版“通用 skill 组合挂载”改为“单 agent 单主 skill”
- 增补了 `poster-fastclaw-upload-agent`
- README 增加了后端、前端、脚本执行和 PR 交接说明

## 10. 提交到 GitHub 前要注意

如果本地目录只是压缩包解压结果，没有 `.git` 历史，就不能直接在这里发起真正的 GitHub PR。

正确做法是：

1. 把本目录内容同步到真正 clone 下来的 `Moonia-Cherry/sciposter_deploy`
2. 在真实 git 仓库里提交 commit
3. 再发起 PR

本次交付已经按“可提 PR 内容”整理部署仓库内容，但是否能直接 push，取决于你本地是否使用了真实 clone 仓库。
