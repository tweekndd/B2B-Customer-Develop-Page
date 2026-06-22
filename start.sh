#!/bin/bash
# AI Trade Customer Analyzer - macOS 启动脚本
# 使用前先在终端设置 API Key:
#   export DEEPSEEK_API_KEY=sk-your-key
#   export SERPAPI_API_KEY=your-key
# 或写入本文件 export 行（注意不要提交到 git）

cd "$(dirname "$0")"
venv/bin/python3 main.py
