# SciPoster Agent 与 Skill 对应表

## 推荐挂载

- `poster-agent` -> `academic-poster-fastclaw-upload`
- `poster-fastclaw-upload-agent` -> `academic-poster-fastclaw-upload`
- `slides-agent` -> `slides-fastclaw-upload`
- `popular-article-agent` -> `popular-article-fastclaw-upload`
- `xiaohongshu-agent` -> `xhs-fastclaw-upload`

## 设计原则

- 采用单 agent 单主 skill 挂载
- 优先走 upload-oriented 本地 happy path
- 避免把 `paper-intake`、`translation`、`web-search`、`code-runner` 这类通用 skill 叠加到正式成功路径
- 减少 agent 规划轮次，降低模型超时和不稳定性

## 当前后端实际使用

- backend 的学术海报入口使用 `poster-agent`
- `poster-fastclaw-upload-agent` 主要用于独立演示和联调
- backend 当前没有单独的 `poster-fastclaw-upload-agent` 环境变量
