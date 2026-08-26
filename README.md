# RealVisXL 装修效果图系统

面向装修设计公司的 AI 效果图工作台：设计师上传 CAD 线稿/手绘草图/现场照片，
基于 **RealVisXL V5.0 Lightning**（SDXL）秒级生成照片级效果图。

## 功能
- **文生图**：文字描述 → 效果图（风格探索）
- **图生图**：线稿/草图/照片 + ControlNet 保户型结构 → 效果图
- **局部重绘 + 软装快速替换**：涂抹区域换沙发/地板/墙色（29 个软装预设）
- **平面图渲染**：户型平面线稿 → 俯视彩色平面布置图
- **户型图分房生成**：上传户型图自动识别房间（OCR 标注 + 「X房X厅X卫」摘要解析）→ 按风格批量生成每个房间的透视效果图 / 分房彩色平面图
- **CAD 转施工图**：DXF 图层规范化 + 图框标题栏 → 黑白施工图 PDF（确定性出图，非 AI）
- 中文提示词自动翻译（在线 + 装修词典兜底）、非装修领域内容拦截
- 内置 8 套装修风格模板 + 4 套平面图模板，项目化管理与历史追溯

## 技术栈
React18 + AntD5 + Konva │ FastAPI + SQLite │ ComfyUI（GPU 推理）│ RapidOCR（离线户型识别）│ ezdxf（施工图）│ SSE 进度推送

## 快速开始

### 一键启动（Windows GPU 机器，推荐）
```bat
start.bat
```
也可直接双击根目录的 `start.bat`。脚本会自动：

1. 首次运行时从 `.env.example` 创建 `server\.env`
2. 新窗口启动 ComfyUI 推理服务（端口 8188，`--lowvram` 适配 8GB 显存）
3. 新窗口启动 FastAPI 后端（端口 8000，同时托管已构建的前端页面）
4. 后端就绪后自动打开浏览器 http://127.0.0.1:8000 （账号 admin / admin123）

停止服务：关闭 `ComfyUI` 与 `RealVisXL-Server` 两个窗口即可。
前提：系统 Python 已安装 `server/requirements.txt`；前端有改动时先 `cd web && npm run build`（启动的是 `web/dist` 构建产物）。

### 无 GPU 也能跑（Mock 模式，验证全流程）
```powershell
cd server
python -m pip install -r requirements.txt
$env:MOCK_COMFYUI="true"; python -m uvicorn app.main:app --port 8000
# 另一个终端构建前端
cd ..\web ; npm install ; npm run build
# 浏览器打开 http://127.0.0.1:8000  账号 admin / admin123
```

### 正式部署（GPU 服务器）
见 **docs/deployment.md**（三步：setup_comfyui.ps1 → download_models.ps1 → 启动服务）；本机/单机 GPU 环境直接运行根目录 `start.bat` 一键启动。

架构与设计说明见 **docs/architecture.md**，模型清单见 **docs/models.md**。

## 目录
```
server/   FastAPI 后端（api / services / comfy / workflows / e2e测试）
web/      React 前端（工作台 / 项目历史 / 模板管理 / 掩码画布）
scripts/  ComfyUI 初始化与 ControlNet 下载脚本（PowerShell）
docs/     架构、部署、模型文档
data/     运行时数据（数据库 / 上传图 / 生成产物，不入库）
```
