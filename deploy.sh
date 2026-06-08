#!/bin/bash
# ============================================
# 部署脚本 — 将已验证的代码更新到生产环境
# 用法：
#   ./deploy.sh             部署全栈（后端+前端）
#   ./deploy.sh backend     仅部署后端
#   ./deploy.sh frontend    仅部署前端
# ============================================
set -e

TARGET=${1:-all}

echo "╔══════════════════════════════════════╗"
echo "║    indicator-dispatch 部署工具      ║"
echo "╚══════════════════════════════════════╝"
echo ""

deploy_backend() {
    echo "📦 [1/3] 构建生产镜像..."
    docker compose build backend

    echo "🔄 [2/3] 切换服务（预计中断 < 5 秒）..."
    docker compose up -d --no-deps --force-recreate backend

    echo "⏳ [3/3] 等待健康检查..."
    sleep 3

    if docker ps --filter "name=indicator-backend" --filter "status=running" --format "{{.Names}}" | grep -q indicator-backend; then
        echo ""
        echo "✅ 后端部署成功！"
        echo "   内网: http://localhost:8000"
    else
        echo ""
        echo "❌ 后端部署失败！请检查日志："
        docker compose logs backend --tail 20
        exit 1
    fi
}

deploy_frontend() {
    echo "📦 构建前端..."
    docker compose build frontend

    echo "🔄 更新前端容器..."
    docker compose up -d --no-deps --force-recreate frontend

    echo "⏳ 等待启动..."
    sleep 2

    if docker ps --filter "name=indicator-frontend" --filter "status=running" --format "{{.Names}}" | grep -q indicator-frontend; then
        echo ""
        echo "✅ 前端部署成功！"
        echo "   内网: http://localhost:3000"
    else
        echo ""
        echo "❌ 前端部署失败！请检查日志："
        docker compose logs frontend --tail 20
        exit 1
    fi
}

case "$TARGET" in
    backend)
        deploy_backend
        ;;
    frontend)
        deploy_frontend
        ;;
    all)
        deploy_backend
        echo ""
        deploy_frontend
        echo ""
        echo "════════════════════════════════════════"
        echo "  🎉 全栈部署完成！"
        echo "  前端: http://localhost:3000"
        echo "  后端: http://localhost:8000"
        echo "  API文档: http://localhost:8000/docs"
        echo "════════════════════════════════════════"
        ;;
    *)
        echo "用法: ./deploy.sh [backend|frontend|all]"
        exit 1
        ;;
esac
