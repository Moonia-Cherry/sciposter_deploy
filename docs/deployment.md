# SciPoster Deploy 1.1.3 部署指引

## 1. 架构与前提

部署目标为 Windows x64。发布包自带 FastClaw、自定义构建二进制、Python 3.12、Node.js、PptxGenJS、sharp 和全部 Python 依赖，不要求系统安装 Python、Node 或 Docker。

FastClaw 固定绑定 `127.0.0.1:18954`，并保持 `FASTCLAW_SANDBOX_ENABLED=false`。四个生产 skill 在主机上的 FastClaw workspace 内运行，统一使用发布包内 runtime。浏览器不得直接调用 FastClaw；所有外部请求均应先进入 backend/middleware，再由 middleware 使用受限 API Key 调用本机 FastClaw。

部署前确认：

- 64 位 Windows；
- PowerShell 可运行本地脚本；
- `127.0.0.1:18954` 未被其他程序占用；
- Windows 已安装 Microsoft YaHei、SimSun 或 SimHei 中文字体之一；
- 模型供应商 API 地址、API Key 和模型 ID 可用。

## 2. 首次部署

1. 将发布 ZIP 解压到最终目录。部署后不要移动其中的 `runtime/`、`bin/` 或 `skills/`。
2. 在部署目录运行：

   ```powershell
   .\deploy.ps1
   ```

3. 首次运行会创建 `config\deploy.local.json` 并停止。填写管理员密码、供应商 API、模型和验证配置；不要修改 FastClaw host 为非 loopback 地址。
4. 再次运行 `.\deploy.ps1`。脚本会校验 manifest/runtime，启动 FastClaw，对账 agent、prompt 和 skill，创建或更新 middleware API Key，并执行验证。

`deploy.ps1` 是首次部署及配置变更后的对账入口。它是幂等的，可以重复运行；重复运行不会重复创建 agent。

## 3. 日常运维入口

```powershell
.\start.ps1
.\status.ps1
.\verify.ps1
.\verify.ps1 -Smoke
.\stop.ps1
```

- `start.ps1`：启动本部署目录所属的 FastClaw。
- `status.ps1`：显示端口、进程和健康状态。
- `verify.ps1`：校验部署、agent、prompt、skill 和 API Key 范围。
- `verify.ps1 -Smoke`：额外执行模型/agent smoke test。
- `stop.ps1`：仅停止本部署目录所属的 FastClaw，不处理占用同一端口的外部进程。

## 4. Agent 与 skill 映射

`config/agents.json` 是映射的唯一事实来源。

| Agent key | Skill | Middleware | 用途 |
| --- | --- | --- | --- |
| `poster-agent` | `academic-poster-fastclaw-upload` | 是 | 生产海报生成 |
| `poster-fastclaw-upload-agent` | `academic-poster-fastclaw-upload` | 否 | 实验/演示 |
| `slides-agent` | `slides-fastclaw-upload` | 是 | 组会幻灯片 |
| `popular-article-agent` | `popular-article-fastclaw-upload` | 是 | 公众号文章 |
| `xiaohongshu-agent` | `xhs-fastclaw-upload` | 是 | 小红书图文 |

`middlewareAccess` 缺省为 `true`。演示 agent 显式设置为 `false`；部署和验证会确保生产 API Key 精确包含其余四个 agent。

## 5. Backend 与前端接入

部署完成后，`config/deploy.local.json` 中的 `fastclawClientApiKey` 是 middleware 专用凭据。Backend 应在服务器端读取该值，并按 OpenAI 兼容接口调用：

```text
POST http://127.0.0.1:18954/v1/chat/completions
Authorization: Bearer <fastclawClientApiKey>
```

请求中的 agent ID 应从 `state/deploy-state.json` 的 agent 映射取得，不要在前端写死。Backend 负责用户认证、业务授权、上传大小和类型限制、超时及错误转换。前端仅调用 backend 的业务 API；不能持有 FastClaw API Key，也不能直接访问用户机器上的 `127.0.0.1`。

## 6. Skill 产物与输入

四个 skill 支持 TXT、DOCX 和 PDF；旧 `.doc` 输入只作尽力解析，推荐转换成 DOCX 或 PDF。未上传论文时，流水线会生成 `missing-upload-report.json`，不会报告成功。

- 海报：PPTX、PNG、SVG、HTML、JSON 等。
- 幻灯片：可编辑 PPTX、逐页 PNG、预览 HTML 和 JSON。
- 公众号文章：Markdown、DOCX、真实 PDF、头图 PNG/PPTX、预览和 JSON；不再生成伪 `.doc`。
- 小红书：DOCX、卡片 PNG、预览 HTML、Markdown 和 JSON。

## 7. 验证与升级

发布包内 `manifest.json` 由构建工具生成，覆盖 FastClaw 自定义构建、二进制、普通 payload 文件及完整 Python/Node runtime tree。部署时会校验路径安全、重复项、大小、SHA-256 和 runtime tree；不要手工编辑 manifest。

升级流程：

1. 备份 `config/deploy.local.json`、`data/` 和 `state/`。
2. 停止旧版本：`.\stop.ps1`。
3. 解压新发布包到新目录，将本地配置迁入新目录。
4. 运行 `.\deploy.ps1` 重新对账，再运行 `.\verify.ps1 -Smoke`。
5. 确认业务 backend 使用新目录中的 API Key 和 agent 映射后再移除旧目录。

开发者修改 `skill-src/` 后运行：

```powershell
.\scripts\Build-Skills.ps1 -CheckReproducible
```

构建脚本按排序后的 POSIX 路径写入固定元数据的 ZIP，并排除 `vendor/`、`node_modules/`、缓存、字节码和临时文件。最终 release payload 包含本文档但不包含 `skill-src/`、`dist/`、`vendor/` 或 `node_modules/`。

## 8. 故障排查

- **端口被占用**：运行 `.\status.ps1`；部署脚本不会停止不属于当前部署目录的进程。
- **缺少 Node/Python 依赖**：确认发布包完整解压并通过 manifest 校验，不要让 skill 改用系统解释器。
- **中文乱码或字体错误**：安装 Microsoft YaHei、SimSun 或 SimHei 后重新运行部署；skill 不会静默回退到不支持中文的默认字体。
- **未发现上传论文**：检查文件是否位于当前 agent workspace，并查看 `output/missing-upload-report.json`。
- **API Key 无权访问 agent**：重新运行 `.\deploy.ps1`；脚本会把 middleware API Key 对账为四个生产 agent。
- **重复 agent 或 skill 未更新**：连续运行两次 `.\deploy.ps1`，再用 `.\verify.ps1` 检查幂等状态。
- **完整性校验失败**：重新下载并解压官方 release；不要绕过 manifest 校验或手工替换 runtime 文件。
