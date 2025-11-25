#!/bin/bash
# Lambda Layer用のパッケージをビルドするスクリプト

set -e

echo "=========================================="
echo "Building Lambda Layer for slack-markdown-parser"
echo "=========================================="

# クリーンアップ
echo "Cleaning up old builds..."
rm -rf python/ slack-markdown-parser-layer.zip

# pythonディレクトリを作成
echo "Creating python directory..."
mkdir -p python

# パッケージをインストール
echo "Installing package..."
pip install . -t python/ --no-deps

# 不要なファイルを削除
echo "Removing unnecessary files..."
find python/ -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find python/ -type d -name "*.dist-info" -exec rm -rf {} + 2>/dev/null || true
find python/ -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true
find python/ -type f -name "*.pyc" -delete 2>/dev/null || true

# ZIPファイルを作成
echo "Creating ZIP file..."
zip -r slack-markdown-parser-layer.zip python/ -q

# ファイルサイズを表示
FILE_SIZE=$(du -h slack-markdown-parser-layer.zip | cut -f1)
echo "=========================================="
echo "✅ Lambda Layer created successfully!"
echo "   File: slack-markdown-parser-layer.zip"
echo "   Size: $FILE_SIZE"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Upload to AWS Lambda Layer:"
echo "   aws lambda publish-layer-version \\"
echo "       --layer-name slack-markdown-parser \\"
echo "       --zip-file fileb://slack-markdown-parser-layer.zip \\"
echo "       --compatible-runtimes python3.8 python3.9 python3.10 python3.11"
echo ""
echo "2. Attach to your Lambda function:"
echo "   aws lambda update-function-configuration \\"
echo "       --function-name YOUR_FUNCTION_NAME \\"
echo "       --layers arn:aws:lambda:REGION:ACCOUNT_ID:layer:slack-markdown-parser:VERSION"
echo "=========================================="
