# 提交到 sciposter_deploy 的 PR 交接说明

## 建议 PR 标题

`Align sciposter_deploy with current 5-agent FastClaw upload workflow`

## 建议 PR 描述

本次变更将部署仓库从旧版 4-agent 通用 skill 模板，整理为与当前 SciPoster 项目一致的 5-agent upload-oriented 部署结构，便于部署同学直接编写和执行部署文件。

主要内容：

- 端口从 `18953` 对齐到 `18954`
- `config/agents.json` 对齐为 5 个 agent
- 每个 agent 改为单主 skill 挂载
- 新增 `poster-fastclaw-upload-agent`
- 新增后端、前端、部署检查、agent-skill 映射文档
- 补充当前项目实际脚本执行顺序说明

## 交接时需要口头说明的点

- 正式后端仍走 `poster-agent`，不是 `poster-fastclaw-upload-agent`
- `poster-fastclaw-upload-agent` 是演示/联调独立链路
- 当前前端接口地址在源码里写死，部署说明必须单独强调
- 这次不改主项目业务逻辑，只补齐部署仓库材料
