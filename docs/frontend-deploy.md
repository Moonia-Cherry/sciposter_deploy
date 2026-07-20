# SciPoster 前端部署说明

## 目录

- 前端目录：`D:\SciPoster\app`

## 启动与构建

```powershell
cd D:\SciPoster\app
npm install
npm run build
```

开发联调：

```powershell
npm run dev
```

## 当前接口地址

文件：`D:\SciPoster\app\src\shared\api.ts`

当前写死：

- backend: `http://localhost:8787`
- fastclaw: `http://localhost:18954`

## 部署说明必须写清楚的点

- 如果前端与 backend/FastClaw 在同一台机器，本机地址可直接复用
- 如果前端单独部署到其他主机，需要调整接口地址或增加反向代理
- 本次交付不改前端样式，不改前端页面结构，只整理部署所需说明
