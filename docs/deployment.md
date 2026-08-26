# 部署手册（Windows GPU 服务器）

## 硬件建议
| 组件 | 最低 | 推荐 |
|---|---|---|
| GPU | RTX 3060 12GB | RTX 4090 24GB（SDXL+ControlNet 约 10~14GB 显存） |
| 内存 | 32GB | 64GB |
| 磁盘 | 100GB NVMe | 2TB NVMe（模型 + 图片库增长快） |

## 步骤

### 0. 显卡驱动要求（重要，避免踩坑）
| ComfyUI 便携包内置 | torch CUDA 版本 | 需要 Windows 驱动 |
|---|---|---|
| 2026 新包 | cu130（CUDA 13） | **580+** |
| 已降级修复（本项目当前状态） | cu126（CUDA 12.6） | 527+（12.x 系列均兼容） |

本项目机器驱动为 556.12（CUDA 12.5），新包 cu130 启动即崩溃（access violation）。
已用 `scripts/download_wheels.sh`（阿里云镜像并行分片）+ pip 本地安装把 torch 降为
**2.7.1+cu126**，实测稳定。若更换新便携包后无法启动，先看驱动版本（`nvidia-smi`），
再决定升级驱动或降级 torch。

8GB 显存（如 RTX 3070）必须加 `--lowvram` 启动，单张 1024×768 约 15~25 秒。

### 1. 初始化 ComfyUI + 主模型
```powershell
cd E:\RealVisXL-App
powershell -ExecutionPolicy Bypass -File scripts\setup_comfyui.ps1
```
脚本会：下载 ComfyUI 便携包（若已有则跳过）→ 把根目录的
`realvisxlV50_v50LightningBakedvae.safetensors` 硬链接到
`ComfyUI_windows_portable\ComfyUI\models\checkpoints\`。

### 2. 下载 ControlNet 模型
```powershell
powershell -ExecutionPolicy Bypass -File scripts\download_models.ps1
# 国内网络慢可先设镜像：
$env:HF_ENDPOINT="https://hf-mirror.com"
```
下载 4 个 xinsir SDXL ControlNet（lineart/scribble/canny/depth，各约 2.5GB）。

### 3. 启动 ComfyUI
```powershell
cd E:\RealVisXL-App\ComfyUI_windows_portable
# 8GB 显存（3070/4060 等）
.\python_embeded\python.exe -s ComfyUI\main.py --lowvram --port 8188
# 12GB+ 显存可直接用 run_nvidia_gpu.bat（不带 --lowvram）
```
实测参考（RTX 3070 Laptop, lowvram, Lightning 8 步）：文生图首次 ~50s（含模型加载），
后续 ~20s；图生图/局部重绘 ~20s。

### 4. 启动业务后端
```powershell
cd E:\RealVisXL-App\server
copy .env.example .env        # 按需修改（ComfyUI 地址、密钥等）
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --port 8000 --host 0.0.0.0
```
首次启动自动建库并写入 admin/admin123 与 8 套内置风格模板。

### 5. 前端
```powershell
cd E:\RealVisXL-App\web
npm install
npm run build                 # 产物 web/dist，由后端 8000 端口托管
```
设计师浏览器访问 `http://<服务器IP>:8000` 即可（建议内网）。

### 6. 验证
- 后端健康：`GET http://127.0.0.1:8000/api/health`
- ComfyUI 连通：登录后 `GET /api/tasks/meta/health` → `{"mode":"comfyui","healthy":true}`
- 无 GPU 联调：`.env` 设 `MOCK_COMFYUI=true`，或运行 `python test_e2e.py`

## 日常运维
- 数据备份：`server/realvisxl.db` + `data/` 目录
- 日志：uvicorn 控制台（可加 `--log-file`）；ComfyUI 有独立控制台
- 修改端口：`.env` 的 `COMFYUI_URL` 指向远端 GPU 机器即可，前后端无需改动
- 常见问题：
  - 提交任务报"提交 ComfyUI 失败" → 检查 ComfyUI 是否启动、地址是否正确
  - 图生图报"control_net_name"校验失败 → ControlNet 文件名与前端选项不一致，
    以 `ComfyUI\models\controlnet\` 实际文件名为准调整
  - 显存不足 → 减小尺寸/张数，或在 ComfyUI 启动参数加 `--lowvram`

## 安全
- 生产务必修改 `.env` 的 `SECRET_KEY` 与 admin 密码
- 仅内网开放 8000/8188 端口；如需外网访问建议加反向代理与 HTTPS
