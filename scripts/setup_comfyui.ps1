# ComfyUI 初始化脚本（Windows GPU 服务器）
# 用法：powershell -ExecutionPolicy Bypass -File scripts\setup_comfyui.ps1
# 作用：下载 ComfyUI 便携包（若未安装）并把工程根目录的 RealVisXL 主模型挂载到 checkpoints/

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$ComfyRoot = Join-Path $ProjectRoot "ComfyUI_windows_portable"
$CheckpointDir = Join-Path $ComfyRoot "ComfyUI\models\checkpoints"
$MainModel = Join-Path $ProjectRoot "realvisxlV50_v50LightningBakedvae.safetensors"

# 1. 下载 ComfyUI 便携包（nvidia 版，需 CUDA 显卡）
if (-not (Test-Path $ComfyRoot)) {
    Write-Host "[1/3] 未检测到 ComfyUI，开始下载便携包（约 1.7GB）..." -ForegroundColor Cyan
    $zip = Join-Path $ProjectRoot "comfyui_portable.7z"
    curl.exe -L -C - -o $zip "https://github.com/comfyanonymous/ComfyUI/releases/latest/download/ComfyUI_windows_portable_nvidia.7z"
    if ($LASTEXITCODE -ne 0) { throw "下载失败，请检查网络或手动下载后解压到 $ComfyRoot" }
    Write-Host "解压中..."
    $sevenZip = "7z"
    if (-not (Get-Command $sevenZip -ErrorAction SilentlyContinue)) {
        # 常见安装位置兜底
        $cand = @("$env:ProgramFiles\7-Zip\7z.exe", "${env:ProgramFiles(x86)}\7-Zip\7z.exe") | Where-Object { Test-Path $_ }
        if (-not $cand) { throw "未找到 7-Zip，请安装后重试：https://www.7-zip.org/" }
        $sevenZip = $cand[0]
    }
    & $sevenZip x $zip -o"$ProjectRoot" -y | Out-Null
    Remove-Item $zip
} else {
    Write-Host "[1/3] 已存在 ComfyUI：$ComfyRoot" -ForegroundColor Green
}

# 2. 挂载主模型（同盘硬链接，不占额外空间；失败则复制）
Write-Host "[2/3] 挂载主模型到 checkpoints/..." -ForegroundColor Cyan
New-Item -ItemType Directory -Force -Path $CheckpointDir | Out-Null
$Target = Join-Path $CheckpointDir (Split-Path -Leaf $MainModel)
if (-not (Test-Path $Target)) {
    if (Test-Path $MainModel) {
        try {
            New-Item -ItemType HardLink -Path $Target -Target $MainModel | Out-Null
            Write-Host "  已创建硬链接：$Target" -ForegroundColor Green
        } catch {
            Write-Host "  硬链接失败，改为复制（约 7GB）..." -ForegroundColor Yellow
            Copy-Item $MainModel $Target
        }
    } else {
        Write-Warning "  主模型不在工程根目录：$MainModel"
        Write-Warning "  请手动放置后重新运行本脚本"
    }
} else {
    Write-Host "  已存在：$Target" -ForegroundColor Green
}

# 3. 启动提示
Write-Host "[3/3] 完成。启动 ComfyUI：" -ForegroundColor Cyan
Write-Host "  cd $ComfyRoot"
Write-Host "  .\run_nvidia_gpu.bat        （默认监听 8188 端口）"
Write-Host ""
Write-Host "再运行 ControlNet 模型下载："
Write-Host "  powershell -ExecutionPolicy Bypass -File scripts\download_models.ps1"
