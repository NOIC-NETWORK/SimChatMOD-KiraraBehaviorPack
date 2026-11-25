#!/bin/bash
set -e

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PROJECT_DIR=$(dirname "$SCRIPT_DIR")
MODEL_DIR="$PROJECT_DIR/models"
GGUF_FILE="$MODEL_DIR/llama-3.1-8b-instruct-reasoner-1o1_v0.3-q4_k_m.gguf"
MODEL_FILE="$SCRIPT_DIR/modelfile.txt"
TEMP_MODEL_FILE="$SCRIPT_DIR/modelfile-temp.txt"

echo "========================================"
echo "   Kirara (JRVS) 一键部署脚本"
echo "========================================"
echo ""

echo "[1/5] 检查环境..."

if ! command -v ollama &> /dev/null; then
    echo "ERROR: 未找到 Ollama，请先安装 Ollama"
    echo "下载地址: https://ollama.com/download"
    echo "安装命令: curl -fsSL https://ollama.com/install.sh | sh"
    exit 1
fi
echo "OK: Ollama 已安装"

echo ""
echo "[2/5] 检查模型文件..."

if [ ! -f "$GGUF_FILE" ]; then
    echo "ERROR: 未找到模型文件:"
    echo "        $GGUF_FILE"
    echo ""
    echo "请将 llama-3.1-8b-instruct-reasoner-1o1_v0.3-q4_k_m.gguf 放入 models 目录"
    exit 1
fi
echo "OK: 模型文件已找到"

echo ""
echo "[3/5] 检查 Ollama 服务状态..."

if ! ollama list &> /dev/null; then
    echo "INFO: Ollama 服务未运行，需要启动服务"
    echo "请在另一个终端中运行: ollama serve"
    echo "然后重新运行此脚本"
    exit 1
fi
echo "OK: Ollama 服务已运行"

echo ""
echo "[4/5] 生成临时 modelfile (绝对路径)..."

cp "$MODEL_FILE" "$TEMP_MODEL_FILE"
sed -i.bak "s|^FROM .*$|FROM \"$GGUF_FILE\"|" "$TEMP_MODEL_FILE"
rm -f "$TEMP_MODEL_FILE.bak"
echo "OK: 临时 modelfile 已生成"

echo ""
echo "[5/5] 创建 Kirara 模型..."

cd "$SCRIPT_DIR"
if ! ollama create kirara -f "$TEMP_MODEL_FILE"; then
    echo "ERROR: 创建模型失败"
    rm -f "$TEMP_MODEL_FILE"
    exit 1
fi
rm -f "$TEMP_MODEL_FILE"
echo "OK: Kirara 模型创建成功"

echo ""
echo "========================================"
echo "   部署完成！"
echo "========================================"
echo ""
echo "使用方法:"
echo "  对话:     ollama run kirara"
echo "  或在 Kirara 应用中选择 \"kirara\" 模型"
echo ""