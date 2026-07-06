#!/usr/bin/env bash
# =============================================================================
# B2B Customer Develop Platform — VPS 一键部署脚本
# 适用于 Ubuntu 22.04 / Debian 12 / CentOS 7+
# 使用方法:
#   bash deploy.sh            # 首次部署
#   bash deploy.sh update     # 更新代码后重新构建
#   bash deploy.sh logs       # 查看日志
#   bash deploy.sh db-backup  # 备份数据库
# =============================================================================
set -euo pipefail

# ─── 颜色 ─────────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'
NC='\033[0m' # No Color

info()  { echo -e "${CYAN}[INFO]${NC}  $1"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
err()   { echo -e "${RED}[ERROR]${NC} $1"; }

# ─── 前置检查 ─────────────────────────────────────────────────────────────────
check_prerequisites() {
    info "检查前置依赖..."

    # Docker
    if ! command -v docker &>/dev/null; then
        warn "Docker 未安装，正在安装..."
        curl -fsSL https://get.docker.com | bash
        sudo usermod -aG docker "$USER"
        ok "Docker 安装完成（可能需要重新登录生效）"
    else
        ok "Docker $(docker --version | cut -d' ' -f3 | tr -d ',')"
    fi

    # Docker Compose
    if ! docker compose version &>/dev/null; then
        if ! command -v docker-compose &>/dev/null; then
            err "Docker Compose 未安装，请手动安装"
            exit 1
        fi
    fi
    ok "Docker Compose $(docker compose version --short 2>/dev/null || docker-compose --version 2>/dev/null | cut -d' ' -f4)"

    # .env 文件
    if [ ! -f .env ]; then
        if [ -f .env.example ]; then
            err ".env 文件不存在！请复制 .env.example 为 .env 并填写配置："
            echo "  cp .env.example .env"
            echo "  nano .env"
            exit 1
        else
            err ".env 和 .env.example 都不存在，请确认在项目根目录执行"
            exit 1
        fi
    fi
    ok ".env 文件已存在"
}

# ─── 创建必要目录 ─────────────────────────────────────────────────────────────
prepare_dirs() {
    mkdir -p searxng
    ok "目录准备完成"
}

# ─── 首次部署 ─────────────────────────────────────────────────────────────────
deploy() {
    echo ""
    echo "=========================================="
    echo "   B2B 客户发现平台 — VPS 部署"
    echo "=========================================="
    echo ""

    check_prerequisites
    prepare_dirs

    # 停止旧容器（如果有）
    docker compose down --remove-orphans 2>/dev/null || true

    # 构建并启动
    info "正在构建 Docker 镜像..."
    docker compose build --pull

    info "正在启动服务..."
    docker compose up -d

    # 等待就绪
    info "等待服务启动..."
    for i in $(seq 1 30); do
        if curl -sf http://127.0.0.1:8000/login > /dev/null 2>&1; then
            ok "服务已就绪！"
            break
        fi
        if [ "$i" -eq 30 ]; then
            warn "服务启动可能较慢，请稍后用以下命令检查状态："
            echo "  docker compose ps"
            echo "  docker compose logs app"
        fi
        sleep 2
    done

    # 输出访问信息
    echo ""
    echo "=========================================="
    echo -e "${GREEN}   部署完成！${NC}"
    echo "=========================================="
    echo ""
    echo "  访问地址: http://$(curl -s ifconfig.me):8000"
    echo "  或:       http://服务器公网IP:8000"
    echo ""
    echo "  管理指令:"
    echo "    docker compose ps          查看状态"
    echo "    docker compose logs -f app  查看应用日志"
    echo "    docker compose logs -f searxng  查看搜索引擎日志"
    echo "    bash deploy.sh update      更新代码后重新部署"
    echo "    bash deploy.sh db-backup   备份数据库"
    echo ""
}

# ─── 更新部署（拉取代码后重新构建） ───────────────────────────────────────────
update() {
    echo ""
    info "正在更新部署..."
    check_prerequisites

    # 拉取最新代码（如果是 git 仓库）
    if [ -d .git ]; then
        info "拉取最新代码..."
        git pull
    fi

    # 重新构建并重启
    docker compose build --pull
    docker compose up -d --force-recreate

    # 清理旧镜像
    docker image prune -f

    echo ""
    ok "更新完成！"
    docker compose ps
}

# ─── 查看日志 ─────────────────────────────────────────────────────────────────
logs() {
    docker compose logs -f --tail=100 "${2:-app}"
}

# ─── 数据库备份 ───────────────────────────────────────────────────────────────
db_backup() {
    local backup_dir="${BACKUP_DIR:-./backups}"
    local timestamp
    timestamp=$(date +%Y%m%d_%H%M%S)

    mkdir -p "$backup_dir"

    info "正在备份 SQLite 数据库..."

    # 复制 SQLite 数据库文件（从 Docker 卷复制到宿主机）
    if docker ps --format '{{.Names}}' | grep -q '^b2b-app$'; then
        docker cp b2b-app:/app/app/customers.db "${backup_dir}/customers_${timestamp}.db"
        # 也导出为 JSON
        # docker exec b2b-app python -c "
        # from app.database import SessionLocal, Customer
        # import json
        # db = SessionLocal()
        # customers = db.query(Customer).all()
        # print(json.dumps([{'id':c.id,'company_name':c.company_name,'website':c.website} for c in customers], ensure_ascii=False))
        # db.close()
        # " > "${backup_dir}/customers_${timestamp}.json" 2>/dev/null || true
        ok "备份完成: ${backup_dir}/customers_${timestamp}.db"
    else
        warn "应用容器未运行，跳过备份"
    fi

    # 保留最近 30 天备份，删除旧备份
    find "$backup_dir" -name 'customers_*.db' -mtime +30 -delete 2>/dev/null || true
}

# ─── 主入口 ───────────────────────────────────────────────────────────────────
case "${1:-deploy}" in
    deploy)
        deploy
        ;;
    update)
        update
        ;;
    logs)
        logs "$@"
        ;;
    db-backup|backup)
        db_backup
        ;;
    *)
        echo "用法: bash deploy.sh [命令]"
        echo ""
        echo "命令:"
        echo "  deploy        首次部署（默认）"
        echo "  update        更新代码后重新构建"
        echo "  logs [服务]   查看日志（默认 app）"
        echo "  db-backup     备份 SQLite 数据库"
        echo ""
        ;;
esac
