#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# 数据同步脚本 - 通过网盘在多设备间同步客户数据
# ═══════════════════════════════════════════════════════════════
#
# 使用方式：
#
#   # 1. 从本机导出数据到网盘
#   ./sync.sh export ~/Library/Mobile\ Documents/com~apple~CloudDocs/TradeAnalyzer
#
#   # 2. 从网盘导入数据到本机
#   ./sync.sh import ~/Library/Mobile\ Documents/com~apple~CloudDocs/TradeAnalyzer
#
#   网盘路径示例：
#   - iCloud:    ~/Library/Mobile Documents/com~apple~CloudDocs/TradeAnalyzer
#   - Dropbox:   ~/Dropbox/TradeAnalyzer
#   - Google Drive: ~/Library/CloudStorage/GoogleDrive-user/TradeAnalyzer
#   - 任意路径:  /Volumes/USB/TradeAnalyzer
#
# ═══════════════════════════════════════════════════════════════

set -e

CMD=$1
SYNC_DIR=${2:-"$HOME/Desktop/TradeAnalyzerSync"}
API_BASE=${API_BASE:-"http://127.0.0.1:8000/api"}
EXPORT_FILE="trade_data_export.json"

mkdir -p "$SYNC_DIR"

case "$CMD" in
  export)
    echo "📤 导出数据... (从 $API_BASE/sync/export)"
    curl -s "$API_BASE/sync/export" -o "$SYNC_DIR/$EXPORT_FILE"
    echo "   导出完成: $(python3 -c "import json; d=json.load(open('$SYNC_DIR/$EXPORT_FILE')); print(f'{d[\"stats\"][\"customers\"]} 个客户, {d[\"stats\"][\"search_cache\"]} 条搜索缓存')")"
    echo "   文件: $SYNC_DIR/$EXPORT_FILE"
    echo "   大小: $(du -h "$SYNC_DIR/$EXPORT_FILE" | cut -f1)"
    ;;

  import)
    if [ ! -f "$SYNC_DIR/$EXPORT_FILE" ]; then
        echo "❌ 未找到同步文件: $SYNC_DIR/$EXPORT_FILE"
        echo "   请先在另一台设备上执行 export，或将文件放入: $SYNC_DIR/"
        exit 1
    fi
    echo "📥 导入数据... (POST $API_BASE/sync/import)"
    IMPORT_FILE_SIZE=$(du -h "$SYNC_DIR/$EXPORT_FILE" | cut -f1)
    echo "   文件大小: $IMPORT_FILE_SIZE"
    RESPONSE=$(curl -s -X POST "$API_BASE/sync/import" \
        -H "Content-Type: application/json" \
        -d @"$SYNC_DIR/$EXPORT_FILE")
    echo "   导入结果: $RESPONSE"
    ;;

  status)
    echo "📊 本地数据状态:"
    curl -s "$API_BASE/stats" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(f'   客户总数: {d[\"total\"]}')
print(f'   已分析: {d[\"analyzed\"]}')
print(f'   A级客户: {d[\"priority_distribution\"][\"A\"]}')
print(f'   B级客户: {d[\"priority_distribution\"][\"B\"]}')
"
    if [ -f "$SYNC_DIR/$EXPORT_FILE" ]; then
        echo ""
        echo "📋 同步文件状态:"
        python3 -c "
import json
d = json.load(open('$SYNC_DIR/$EXPORT_FILE'))
print(f'   导出时间: {d.get(\"exported_at\", \"未知\")[:19]}')
print(f'   文件中的客户: {d[\"stats\"][\"customers\"]}')
print(f'   文件中的缓存: {d[\"stats\"][\"search_cache\"]}条')
"
    fi
    ;;

  *)
    echo "用法: ./sync.sh <export|import|status> [目录路径]"
    echo ""
    echo "   export   将本机数据导出到指定目录（生成 trade_data_export.json）"
    echo "   import   从指定目录导入数据到本机（自动去重合并）"
    echo "   status   查看本机和同步文件状态"
    echo ""
    echo "   目录路径（可选，默认为 ~/Desktop/TradeAnalyzerSync）:"
    echo "     导出后手动上传到 Google Drive 网页版即可跨设备同步"
    echo ""
    echo "     常用路径:"
    echo "       ~/Desktop/TradeDataSync       桌面（推荐）"
    echo "       /Volumes/USB/TradeData         USB 设备"
    echo "       ~/Library/Mobile Documents/    iCloud 同步目录"
    echo ""
    echo "   环境变量 API_BASE（可选，默认 http://127.0.0.1:8000/api）:"
    echo "     export API_BASE=http://192.168.1.100:8000/api  # 从局域网另一台设备导入"
    echo ""
    echo "   完整流程:"
    echo "     设备A: ./sync.sh export ~/Desktop/TradeDataSync"
    echo "       → 将 trade_data_export.json 上传到 Google Drive 网页版"
    echo "     设备B: 从 Google Drive 下载文件到目录"
    echo "       → ./sync.sh import ~/Downloads/TradeDataSync"
    echo ""
    echo "示例:"
    echo "   ./sync.sh export                              # 导出到桌面"
    echo "   ./sync.sh import ~/Downloads/TradeDataSync    # 从 Downloads 导入"
    echo "   ./sync.sh status                              # 查看数据状态"
    echo "   API_BASE=http://10.0.0.2:8000/api ./sync.sh import  # 远程导入"
    ;;
esac
