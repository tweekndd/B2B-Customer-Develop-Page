#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI Trade Customer Analyzer - 数据同步工具
一键导入/导出客户数据，替代 sync_data.cmd（Windows 不允许执行 cmd 时的备选方案）

用法:
    python sync_data.py export         导出客户数据到 JSON
    python sync_data.py import         从 JSON 导入客户数据
    python sync_data.py backup         备份数据库文件 (.db)
    python sync_data.py restore        从备份恢复数据库
    python sync_data.py status         查看数据状态
    python sync_data.py watch          监听导出目录自动导入（双机同步）

高级:
    python sync_data.py export <路径>   导出到指定目录
    python sync_data.py import <路径>   从指定目录导入

环境变量:
    API_BASE=http://127.0.0.1:8000/api   (默认 http://127.0.0.1:8000/api)
    SYNC_DIR=路径                         (默认 ~/Desktop/TradeDataSync)
"""

import sys
import json
import os
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path

# ─── 配置 ───
API_BASE = os.environ.get("API_BASE", "http://127.0.0.1:8000/api")
DEFAULT_SYNC_DIR = os.path.join(os.path.expanduser("~"), "Desktop", "TradeDataSync")
SYNC_DIR = os.environ.get("SYNC_DIR", DEFAULT_SYNC_DIR)
EXPORT_FILE = "trade_data_export.json"
DB_PATH = Path("app") / "customers.db"
PROJECT_ROOT = Path.cwd()

# ─── 颜色输出 ───
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
BOLD = "\033[1m"
NORMAL = "\033[0m"

def info(msg):
    print(f"  {msg}")

def ok(msg):
    print(f"  {GREEN}✔{NORMAL} {msg}")

def warn(msg):
    print(f"  {YELLOW}⚠{NORMAL} {msg}")

def err(msg):
    print(f"  {RED}✘{NORMAL} {msg}")

def heading(title):
    width = 50
    print(f"\n  {CYAN}{'─' * width}{NORMAL}")
    print(f"  {BOLD}{title}{NORMAL}")
    print(f"  {CYAN}{'─' * width}{NORMAL}")

def bold(s):
    return f"{BOLD}{s}{NORMAL}"

def fmt_size(size_bytes):
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / 1024 / 1024:.1f} MB"
    elif size_bytes >= 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes} 字节"


# ═══════════════════════════════════════════════════════════════
# 导出（via API → JSON）
# ═══════════════════════════════════════════════════════════════
def cmd_export(target_dir=None):
    target_dir = Path(target_dir or SYNC_DIR)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / EXPORT_FILE

    heading("📤 导出客户数据")
    info(f"源:    {API_BASE}/sync/export")
    info(f"目标:  {target_file}")
    print()

    data = _api_get("/sync/export")
    if data is None:
        err("导出失败！请确认程序已启动 (http://localhost:8000)")
        return False

    stats = data.get("stats", {})
    info(f"客户: {stats.get('customers', 0)} 个 | "
         f"搜索任务: {stats.get('search_tasks', 0)} 个 | "
         f"缓存: {stats.get('search_cache', 0)} + {stats.get('website_cache', 0)} 条")

    target_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    file_size = target_file.stat().st_size
    ok(f"导出成功！{fmt_size(file_size)}")
    info(f"文件: {target_file}")
    print()
    info("提示: 将此文件拷贝到另一台电脑，用 import 命令导入即可。")
    return True


# ═══════════════════════════════════════════════════════════════
# 导入（via API ← JSON）
# ═══════════════════════════════════════════════════════════════
def cmd_import(target_dir=None):
    target_dir = Path(target_dir or SYNC_DIR)
    target_file = target_dir / EXPORT_FILE

    heading("📥 导入客户数据")
    info(f"目标: {API_BASE}/sync/import")

    if not target_file.exists():
        err(f"未找到导入文件: {target_file}")
        print()
        info("请先执行 export 导出数据，或指定正确的目录:")
        info(f"  python sync_data.py import D:\\你的目录")
        return False

    file_size = target_file.stat().st_size
    info(f"文件: {target_file} ({fmt_size(file_size)})")

    # 读取并显示摘要
    try:
        data = json.loads(target_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        err("文件格式错误，不是有效的 JSON 文件")
        return False

    stats = data.get("stats", {})
    print()
    info(f"  客户: {stats.get('customers', 0)} 个")
    info(f"  搜索任务: {stats.get('search_tasks', 0)} 个")
    info(f"  搜索缓存: {stats.get('search_cache', 0)} 条")
    info(f"  网页缓存: {stats.get('website_cache', 0)} 条")
    info(f"  分析缓存: {stats.get('analysis_cache', 0)} 条")
    if data.get("exported_at"):
        info(f"  导出时间: {data['exported_at'][:19]}")
    print()

    info("正在导入...（需要服务端处理，大文件可能较慢）")
    result = _api_post("/sync/import", data)
    if result is None:
        err("导入失败！请确认程序已启动 (http://localhost:8000)")
        return False

    imp = result.get("imported", {})
    print()
    ok(f"{result.get('message', '导入完成')}")
    info(f"  新导入客户: {imp.get('customers', 0)} 个")
    info(f"  跳过重复:   {imp.get('customers_skipped', 0)} 个")
    info(f"  导入任务:   {imp.get('search_tasks', 0)} 个")
    info(f"  导入缓存:   {imp.get('search_cache', 0)} + {imp.get('website_cache', 0)} + {imp.get('analysis_cache', 0)} 条")
    return True


# ═══════════════════════════════════════════════════════════════
# 备份数据库（直接拷贝 .db）
# ═══════════════════════════════════════════════════════════════
def cmd_backup(target_dir=None):
    target_dir = Path(target_dir or SYNC_DIR)
    target_dir.mkdir(parents=True, exist_ok=True)

    heading("💾 备份数据库")

    if not DB_PATH.exists():
        err(f"未找到数据库文件: {DB_PATH}")
        info("请确认在项目根目录下运行（与 app/ 同级）")
        return False

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = target_dir / f"backup_{timestamp}.db"
    src_size = DB_PATH.stat().st_size
    info(f"数据库: {DB_PATH} ({fmt_size(src_size)})")
    info(f"备份到: {backup_file}")

    # 带重试
    for attempt in range(3):
        try:
            shutil.copy2(DB_PATH, backup_file)
            break
        except PermissionError:
            if attempt < 2:
                warn(f"文件被占用，1 秒后重试...")
                time.sleep(1)
            else:
                err("备份失败！数据库文件被占用。请先关闭程序。")
                return False

    dst_size = backup_file.stat().st_size
    ok(f"备份完成！{fmt_size(dst_size)}")
    return True


# ═══════════════════════════════════════════════════════════════
# 恢复数据库
# ═══════════════════════════════════════════════════════════════
def cmd_restore(target_dir=None):
    target_dir = Path(target_dir or SYNC_DIR)

    heading("🔄 恢复数据库")
    info(f"目标: {DB_PATH}")
    info(f"来源: {target_dir}")

    # 查找最新备份
    backups = sorted(target_dir.glob("backup_*.db"), key=os.path.getmtime, reverse=True)
    if not backups:
        err(f"未在 {target_dir} 中找到任何备份文件 (backup_*.db)")
        return False

    backup_file = backups[0]
    file_size = backup_file.stat().st_size
    print()
    info(f"找到最新备份: {backup_file.name} ({fmt_size(file_size)})")
    print()
    warn("恢复操作将覆盖当前数据库！")
    warn("建议先执行 backup 保留当前数据。")
    print()

    confirm = input(f"  确认恢复？(y/N): ").strip().lower()
    if confirm != "y":
        info("操作已取消。")
        return False

    # 自动备份当前数据库
    backup_before = DB_PATH.with_suffix(DB_PATH.suffix + ".before_restore.bak")
    try:
        shutil.copy2(DB_PATH, backup_before)
        ok(f"当前数据库已备份到: {backup_before}")
    except Exception:
        warn("当前数据库自动备份失败，继续恢复...")

    # 恢复
    try:
        shutil.copy2(backup_file, DB_PATH)
    except PermissionError:
        err("恢复失败！数据库文件被占用，请先关闭程序。")
        return False

    ok("恢复成功！请重启程序使数据生效。")
    print()
    info("如需回退，将以下文件复制为 app/customers.db 即可：")
    info(f"  {backup_before}")
    return True


# ═══════════════════════════════════════════════════════════════
# 状态查看
# ═══════════════════════════════════════════════════════════════
def cmd_status():
    heading("📊 数据状态")

    # 本地数据库
    print(f"  {BOLD}[本地数据库]{NORMAL}")
    if DB_PATH.exists():
        size = DB_PATH.stat().st_size
        mtime = datetime.fromtimestamp(DB_PATH.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        info(f"数据库: {DB_PATH}")
        info(f"大小:   {fmt_size(size)}")
        info(f"修改:   {mtime}")
    else:
        err(f"未找到: {DB_PATH}")
    print()

    # API 在线统计
    print(f"  {BOLD}[API 在线统计]{NORMAL}")
    data = _api_get("/stats")
    if data:
        info(f"客户总数: {data.get('total', '?')}")
        info(f"已分析:   {data.get('analyzed', '?')}")
        pd = data.get("priority_distribution", {})
        info(f"A 级: {pd.get('A', 0)}  |  B 级: {pd.get('B', 0)}  |  C 级: {pd.get('C', 0)}  |  D 级: {pd.get('D', 0)}")
        sd = data.get("status_distribution", {})
        if sd:
            info(f"待联系: {sd.get('待联系', 0)}  |  已发邮件: {sd.get('已发邮件', 0)}")
    else:
        warn("服务未运行或无法访问")
        info("请先启动程序: http://localhost:8000")
        info(f"API 地址: {API_BASE}")
    print()

    # 同步文件
    print(f"  {BOLD}[同步文件]{NORMAL}")
    sync_file = Path(SYNC_DIR) / EXPORT_FILE
    if sync_file.exists():
        size = sync_file.stat().st_size
        mtime = datetime.fromtimestamp(sync_file.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        info(f"文件: {sync_file}")
        info(f"大小: {fmt_size(size)} ({mtime})")
        try:
            data = json.loads(sync_file.read_text(encoding="utf-8"))
            stats = data.get("stats", {})
            print()
            info(f"  客户: {stats.get('customers', 0)} 个 | "
                 f"任务: {stats.get('search_tasks', 0)} 个 | "
                 f"缓存: {stats.get('search_cache', 0)} 条")
            if data.get("exported_at"):
                info(f"  导出时间: {data['exported_at'][:19]}")
        except Exception:
            pass
    else:
        info("暂无同步文件")
        info("执行 python sync_data.py export 生成")
    print()

    # 备份文件
    print(f"  {BOLD}[数据库备份]{NORMAL}")
    backups = sorted(Path(SYNC_DIR).glob("backup_*.db"), key=os.path.getmtime, reverse=True)
    if backups:
        info(f"共 {len(backups)} 个备份")
        for b in backups[:3]:
            size = b.stat().st_size
            mtime = datetime.fromtimestamp(b.stat().st_mtime).strftime("%m-%d %H:%M")
            info(f"  {b.name}  ({fmt_size(size)}, {mtime})")
        if len(backups) > 3:
            info(f"  ... 还有 {len(backups) - 3} 个")
    else:
        info("暂无数据库备份")
        info("执行 python sync_data.py backup 创建")

    return True


# ═══════════════════════════════════════════════════════════════
# Watch 模式 - 监听导出目录，自动导入（双机同步）
# ═══════════════════════════════════════════════════════════════
def cmd_watch(target_dir=None):
    target_dir = Path(target_dir or SYNC_DIR)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / EXPORT_FILE

    heading("👀 同步监听模式")
    info(f"监听目录: {target_dir}")
    info(f"检测到 {EXPORT_FILE} 更新后自动导入")
    info("按 Ctrl+C 停止")
    print()

    last_mtime = target_file.stat().st_mtime if target_file.exists() else 0

    try:
        while True:
            if target_file.exists():
                current_mtime = target_file.stat().st_mtime
                if current_mtime > last_mtime:
                    info(f"{datetime.now().strftime('%H:%M:%S')} 检测到文件更新，正在导入...")
                    cmd_import(target_dir)
                    last_mtime = current_mtime
                    print()
            time.sleep(5)
    except KeyboardInterrupt:
        info("监听已停止。")
    return True


# ═══════════════════════════════════════════════════════════════
# API 辅助函数
# ═══════════════════════════════════════════════════════════════
def _api_get(path):
    """调用 API GET 请求"""
    try:
        import httpx
        resp = httpx.get(f"{API_BASE}{path}", timeout=30)
        resp.raise_for_status()
        return resp.json()
    except ImportError:
        # fallback: 使用 urllib
        import urllib.request
        try:
            with urllib.request.urlopen(f"{API_BASE}{path}", timeout=30) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            err(f"请求失败: {e}")
            return None
    except Exception as e:
        err(f"请求失败: {e}")
        return None


def _api_post(path, data):
    """调用 API POST 请求"""
    try:
        import httpx
        resp = httpx.post(f"{API_BASE}{path}", json=data, timeout=120)
        resp.raise_for_status()
        return resp.json()
    except ImportError:
        import urllib.request
        try:
            body = json.dumps(data).encode("utf-8")
            req = urllib.request.Request(
                f"{API_BASE}{path}",
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            err(f"导入请求失败: {e}")
            return None
    except Exception as e:
        err(f"导入请求失败: {e}")
        return None


# ═══════════════════════════════════════════════════════════════
# 使用说明
# ═══════════════════════════════════════════════════════════════
def print_usage():
    print(f"""
  {BOLD}AI Trade Customer Analyzer - 数据同步工具{NORMAL}
  {'═' * 50}

  {bold('用法:')}
    python sync_data.py export [目录]     导出客户数据
    python sync_data.py import [目录]     导入客户数据（自动去重）
    python sync_data.py backup [目录]     备份数据库
    python sync_data.py restore [目录]    恢复数据库
    python sync_data.py status            查看状态
    python sync_data.py watch [目录]      监听模式，自动同步

  {bold('目录路径（可选，默认为桌面 TradeDataSync）:')}
     可指定到网盘目录实现多设备同步

  {bold('环境变量:')}
     API_BASE=http://127.0.0.1:8000/api  (API 地址)
     SYNC_DIR=D:\\MyCloud\\TradeData    (同步目录)

  {bold('示例:')}
    python sync_data.py export
    python sync_data.py export D:\\我的网盘\\TradeData
    python sync_data.py import D:\\我的网盘\\TradeData
    python sync_data.py backup
    python sync_data.py restore
    python sync_data.py status
    python sync_data.py watch

  {bold('完整流程（多设备同步）:')}
    设备A: python sync_data.py export
      → 将 trade_data_export.json 上传到网盘
    设备B: 下载到目录 → python sync_data.py import D:\\网盘目录

  {bold('双机自动同步:')}
    设备B: python sync_data.py watch D:\\网盘目录
      → 设备A 再次 export 后，设备B 自动 import
""")


# ═══════════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════════
def main():
    args = sys.argv[1:]
    cmd = args[0].lower() if args else ""
    target = args[1] if len(args) > 1 else None

    if cmd == "export":
        success = cmd_export(target)
    elif cmd == "import":
        success = cmd_import(target)
    elif cmd == "backup":
        success = cmd_backup(target)
    elif cmd == "restore":
        success = cmd_restore(target)
    elif cmd == "status":
        success = cmd_status()
    elif cmd == "watch":
        success = cmd_watch(target)
    else:
        print_usage()
        success = True

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
