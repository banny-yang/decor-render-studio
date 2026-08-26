# 系统架构

## 总览

```
┌─────────────────────────────────────────────────────────────┐
│ 前端 React + Ant Design（web/，构建产物由后端托管）            │
│ 生图工作台（文生图/图生图/局部重绘）│ 项目历史 │ 风格模板库    │
└──────────────────┬──────────────────────────────────────────┘
                   │ REST（X-Auth-Token）+ SSE（?token=）
┌──────────────────▼──────────────────────────────────────────┐
│ 业务后端 FastAPI（server/，端口 8000）                        │
│ ├─ api/        auth / assets / tasks(含SSE) / projects /     │
│               templates                                     │
│ ├─ services/   task_service（任务编排+归档+Mock）             │
│               workflow_builder（JSON模板参数注入）            │
│ ├─ comfy/      client（/prompt /upload /history /view）      │
│               listener（WebSocket 进度 → 状态机 → SSE）      │
│ └─ 存储 SQLite（realvisxl.db）+ 磁盘图片库（data/）            │
└──────────────────┬──────────────────────────────────────────┘
                   │ HTTP /prompt + WS /ws（ComfyUI 原生 API）
┌──────────────────▼──────────────────────────────────────────┐
│ ComfyUI 推理服务（GPU 服务器，端口 8188）                      │
│ 主模型 realvisxlV50_v50LightningBakedvae.safetensors          │
│ ControlNet: lineart / scribble / canny / depth（SDXL）        │
└─────────────────────────────────────────────────────────────┘
```

## 关键设计

### 为什么不让前端直连 ComfyUI
ComfyUI 面向单实例调试：无任务持久化、无按客户归档、无模板管理、无鉴权。
业务后端承担这些职责后，ComfyUI 可独立升级/重启，不影响业务数据。

### 任务状态机
```
pending → queued → running → done
                ↘ error（提交失败/执行异常，error 字段存原因）
```
- 提交：POST /api/tasks 落库后立即返回，后台协程上传输入图并提交 ComfyUI
- 进度：listener 监听 ComfyUI `/ws`（progress 事件）更新任务，EventBus 广播
- 归档：execution_success 后从 /history 拉产物，存 `data/assets/task{id}/`，建 Asset 记录
- 推送：前端 EventSource 订阅 `GET /api/tasks/{id}/events`，先收快照再收增量

### 三种生图模式 → 三套工作流模板
`server/workflows/` 下 JSON 为 ComfyUI API 格式，参数由
`workflow_builder.py` 按**固定节点编号**注入（见该文件头部注释）：

| 模式 | 模板文件 | 结构控制 | 典型 denoise |
|---|---|---|---|
| 文生图 | t2i.json | 无 | 1.0 |
| 图生图 | img2img_controlnet.json | ControlNet（线稿/涂鸦/边缘/深度） | 0.7~0.9 |
| 局部重绘 | inpaint.json | 掩码（前端 Konva 涂抹→PNG alpha 通道） | 1.0 |

### Lightning 模型要点
realvisxlV50_v50LightningBakedvae 是 SDXL Lightning 蒸馏版（自带 VAE）：
- 步数 4~8（默认 6），**CFG 1~2**（默认 1.5，过高会爆色）
- 采样 euler + 调度 sgm_uniform
- 单张 1024×768 约 1~3 秒（4090），批量 4 张几乎无排队压力
- 全部默认值已写入 8 套内置风格模板的 params 中

### 认证
- PBKDF2 口令哈希 + HMAC 签名 token（uid.过期时间.签名，base64）
- Header `X-Auth-Token`；SSE 与 `<img>` 走 `?token=` 查询参数（deps.py 两者都接受）
- 前端用 zustand 存内存 + localStorage 兜底（内嵌 webview 存储被禁时仍可用）

### Mock 模式
`MOCK_COMFYUI=true` 时不连 ComfyUI：后台协程模拟分步进度并用 Pillow 生成
渐变占位图，全链路（提交/SSE/归档/画廊）可无 GPU 联调。

## 目录结构
```
RealVisXL-App/
├── realvisxlV50_v50LightningBakedvae.safetensors   # 主模型（挂载到 ComfyUI）
├── server/           # FastAPI 业务后端
│   ├── app/          # api/ services/ comfy/ + 配置、ORM、种子
│   ├── workflows/    # 三套 ComfyUI 工作流模板
│   └── test_e2e.py   # 端到端测试（Mock 模式）
├── web/              # React 前端（Vite + TS + antd5 + Konva）
├── scripts/          # setup_comfyui.ps1 / download_models.ps1
├── docs/             # 本文档 + 部署手册 + 模型清单
└── data/             # 运行时数据：SQLite/上传图/产物（gitignore）
```
