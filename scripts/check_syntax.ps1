# 语法自检：验证两个部署脚本可被 PowerShell 正确解析
foreach ($f in @("setup_comfyui.ps1", "download_models.ps1")) {
    $path = Join-Path $PSScriptRoot $f
    $errs = $null
    [System.Management.Automation.Language.Parser]::ParseFile($path, [ref]$null, [ref]$errs) | Out-Null
    if ($errs.Count -eq 0) {
        Write-Host "$f : OK" -ForegroundColor Green
    } else {
        Write-Host "$f : $($errs.Count) 个错误" -ForegroundColor Red
        $errs | ForEach-Object { Write-Host ("  line {0}: {1}" -f $_.Extent.StartLineNumber, $_.Message) }
        exit 1
    }
}
