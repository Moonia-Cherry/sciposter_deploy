# SciPoster Deploy

SciPoster Deploy 是面向 Windows x64 的自包含 FastClaw 部署包。它携带固定版本的 FastClaw、Python 3.12、Node.js、PptxGenJS、sharp 与四个论文上传 skill，用于部署海报、幻灯片、公众号文章和小红书内容生成能力。

## 快速开始

1. 解压发布包到普通本地目录。
2. 以 PowerShell 运行 `deploy.ps1`。首次运行会生成 `config/deploy.local.json` 并提示填写管理员、模型供应商与验证配置。
3. 填写配置后再次运行 `deploy.ps1`，完成 FastClaw 启动、5 个 agent 对账、skill 安装、API Key 创建和验证。
4. 日常使用 `start.ps1`、`stop.ps1`、`status.ps1` 和 `verify.ps1`。

完整步骤、agent 映射、前后端接入、升级及故障排查见 [部署文档](docs/deployment.md)。

## 安全边界

- FastClaw 仅监听 `127.0.0.1:18954`，不得直接暴露到公网。
- `FASTCLAW_SANDBOX_ENABLED=false`：skill 延续原部署架构，在 FastClaw 主机 workspace 中运行，不使用 Docker sandbox。
- 浏览器只访问业务 backend/middleware；middleware 使用受限 API Key 调用四个生产 agent。
- 演示 agent `poster-fastclaw-upload-agent` 不包含在 middleware API Key 权限范围内。
- `config/deploy.local.json` 和 `state/`、`data/`、`logs/` 不进入版本控制或发布包。

## 开发与发布

Skill 源码位于 `skill-src/`，部署 ZIP 位于 `skills/`。运行 `scripts\Build-Skills.ps1 -CheckReproducible` 可重建 ZIP 并校验可复现性；`skill-src/` 不进入最终部署包。
