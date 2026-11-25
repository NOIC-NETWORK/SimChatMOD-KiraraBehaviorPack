$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectDir = Join-Path $scriptDir ".."
$modelDir = Join-Path $projectDir "models"
$ggufFile = Join-Path $modelDir "llama-3.1-8b-instruct-reasoner-1o1_v0.3-q4_k_m.gguf"
$modelFile = Join-Path $scriptDir "modelfile.txt"
$tempModelFile = Join-Path $scriptDir "modelfile-temp.txt"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   Kirara (JRVS) 一键部署脚本" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "[1/5] 检查环境..." -ForegroundColor Yellow

$ollamaPath = Get-Command ollama -ErrorAction SilentlyContinue
if (-not $ollamaPath) {
    Write-Host "ERROR: 未找到 Ollama，请先安装 Ollama" -ForegroundColor Red
    Write-Host "下载地址: https://ollama.com/download" -ForegroundColor Red
    Read-Host "按回车键退出"
    exit 1
}
Write-Host "OK: Ollama 已安装 - $($ollamaPath.Source)" -ForegroundColor Green

Write-Host ""
Write-Host "[2/5] 检查模型文件..." -ForegroundColor Yellow

if (-not (Test-Path $ggufFile)) {
    Write-Host "ERROR: 未找到模型文件:" -ForegroundColor Red
    Write-Host "        $ggufFile" -ForegroundColor Red
    Write-Host ""
    Write-Host "请将 llama-3.1-8b-instruct-reasoner-1o1_v0.3-q4_k_m.gguf 放入 models 目录" -ForegroundColor Red
    Read-Host "按回车键退出"
    exit 1
}
Write-Host "OK: 模型文件已找到" -ForegroundColor Green

Write-Host ""
Write-Host "[3/5] 检查 Ollama 服务状态..." -ForegroundColor Yellow

try {
    $null = & ollama list 2>&1
    Write-Host "OK: Ollama 服务已运行" -ForegroundColor Green
} catch {
    Write-Host "INFO: Ollama 服务未运行，需要启动服务" -ForegroundColor Yellow
    Write-Host "请在另一个终端中运行: ollama serve" -ForegroundColor Yellow
    Write-Host "然后重新运行此脚本" -ForegroundColor Yellow
    Read-Host "按回车键退出"
    exit 1
}

Write-Host ""
Write-Host "[4/5] 生成临时 modelfile (绝对路径)..." -ForegroundColor Yellow

Copy-Item -Path $modelFile -Destination $tempModelFile -Force
$content = Get-Content $tempModelFile -Raw
$content = $content -replace '^FROM .*$', "FROM `"$ggufFile`""
Set-Content -Path $tempModelFile -Value $content -NoNewline
Write-Host "OK: 临时 modelfile 已生成" -ForegroundColor Green

Write-Host ""
Write-Host "[5/5] 创建 Kirara 模型..." -ForegroundColor Yellow

Set-Location $scriptDir
try {
    & ollama create kirara -f $tempModelFile
    if ($LASTEXITCODE -ne 0) {
        throw "创建模型失败，退出码: $LASTEXITCODE"
    }
    Write-Host "OK: Kirara 模型创建成功" -ForegroundColor Green
} catch {
    Write-Host "ERROR: 创建模型失败 - $_" -ForegroundColor Red
    if (Test-Path $tempModelFile) { Remove-Item $tempModelFile -Force }
    Read-Host "按回车键退出"
    exit 1
}

if (Test-Path $tempModelFile) { Remove-Item $tempModelFile -Force }

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   部署完成！" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "使用方法:" -ForegroundColor White
Write-Host "  对话:     ollama run kirara" -ForegroundColor Gray
Write-Host "  或在 Kirara 应用中选择 ""kirara"" 模型" -ForegroundColor Gray
Write-Host ""
Read-Host "按回车键退出"