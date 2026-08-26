# 下载 ControlNet 模型（国内魔搭 ModelScope 源，实测 3MB/s+）
# 用法：powershell -ExecutionPolicy Bypass -File scripts\download_models.ps1

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$CnDir = Join-Path $ProjectRoot "ComfyUI_windows_portable\ComfyUI\models\controlnet"

New-Item -ItemType Directory -Force -Path $CnDir | Out-Null

# 模型清单：源地址 -> 本地文件名（与前端选项、工作流模板对应）
$Models = @(
    @{
        url = "https://modelscope.cn/models/TheMisto.ai/MistoLine/resolve/master/mistoLine_fp16.safetensors"
        file = "mistoline_sdxl_fp16.safetensors"
        note = "MistoLine SDXL 线稿 ControlNet（CAD/手绘/草图，核心必装）"
    }
)

foreach ($m in $Models) {
    $dst = Join-Path $CnDir $m.file
    if (Test-Path $dst) {
        Write-Host "已存在，跳过：$($m.file)" -ForegroundColor Green
        continue
    }
    Write-Host "下载 $($m.note)" -ForegroundColor Cyan
    Write-Host "  $($m.url)"
    curl.exe -L -C - --retry 5 -o $dst $m.url
    if ($LASTEXITCODE -ne 0) {
        Remove-Item $dst -ErrorAction SilentlyContinue
        throw "下载失败：$($m.file)"
    }
}

Write-Host ""
Write-Host "完成。当前 ControlNet：" -ForegroundColor Green
Get-ChildItem $CnDir -Filter *.safetensors | ForEach-Object {
    Write-Host ("  {0}  {1:N1} GB" -f $_.Name, ($_.Length / 1GB))
}

# 可选扩展（照片保透视等场景）：xinsir union promax，一个文件覆盖线稿/边缘/深度等
#   https://modelscope.cn/models/AI-ModelScope/controlnet-union-sdxl-1.0/resolve/master/diffusion_pytorch_model_promax.safetensors
#   下载后重命名为 sdxl_union_promax_xinsir.safetensors，并在前端 ControlNet 选项中启用
