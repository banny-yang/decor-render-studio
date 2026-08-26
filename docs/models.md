# 模型清单

## 主模型（已包含在工程根目录）
| 文件 | 说明 |
|---|---|
| realvisxlV50_v50LightningBakedvae.safetensors（6.94GB） | RealVisXL V5.0 Lightning 蒸馏版，SDXL 架构，自带 VAE。照片级写实效果，**4~8 步出图** |

### Lightning 参数要点（已内置为系统默认值）
- 步数：4~8（默认 6），不要用标准版的 25~30
- CFG：**1~2**（默认 1.5）。Lightning 蒸馏模型 CFG 超过 3 会严重爆色
- 采样器：euler / euler_ancestral；调度器：sgm_uniform
- 图生图 denoise 建议 0.7~0.9；局部重绘 1.0

## ControlNet（由 scripts/download_models.ps1 从魔搭 ModelScope 下载，实测 3MB/s+）
放置目录：`ComfyUI_windows_portable\ComfyUI\models\controlnet\`

| 文件名 | 来源 | 用途 | 前端选项 |
|---|---|---|---|
| mistoline_sdxl_fp16.safetensors（2.4GB） | 魔搭 TheMisto.ai/MistoLine | 任意线稿输入保户型（CAD 线稿/手绘草图均适用） | 线稿（CAD/手绘/草图，MistoLine） |

可选扩展：魔搭 `AI-ModelScope/controlnet-union-sdxl-1.0` 的 promax 版
（约 2.4GB，一个文件覆盖线稿/边缘/深度/涂鸦等 12 种控制，适合照片改风格场景），
下载方法见 download_models.ps1 末尾注释。

> 说明：原方案的 xinsir 单项 ControlNet 走 HuggingFace/hf-mirror，国内实测不可达，
> 已替换为魔搭源的 MistoLine（同为 SDXL 线稿控制，质量口碑良好）。

## 主模型挂载位置
`ComfyUI_windows_portable\ComfyUI\models\checkpoints\realvisxlV50_v50LightningBakedvae.safetensors`
（setup_comfyui.ps1 用硬链接挂载，不重复占磁盘）

## 可选扩展（当前未启用）
| 模型 | 用途 | 接入方式 |
|---|---|---|
| 4x-UltraSharp / ESRGAN | 结果图放大 | ComfyUI 加 Upscale 节点 |
| SUPIR | 高保真超分 | ComfyUI 自定义节点 |
| IP-Adapter SDXL | 参考图风格迁移 | workflow 加节点，后端参数注入 |
| 控制网权重微调 | 公司专属风格 | 用自有效果图 LoRA 训练后挂 checkpoints |
