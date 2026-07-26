#!/usr/bin/env bash

set -e


# =====================================================
# 自动定位项目目录
# =====================================================

PROJECT_DIR="$(
    cd "$(dirname "${BASH_SOURCE[0]}")"
    pwd
)"

CONDA_ENV_NAME="${CONDA_ENV_NAME:-knowledge-agent}"

API_HOST="${API_HOST:-0.0.0.0}"
API_PORT="${API_PORT:-6006}"

FRONTEND_HOST="${FRONTEND_HOST:-0.0.0.0}"
FRONTEND_PORT="${FRONTEND_PORT:-6008}"

LOG_DIR="${PROJECT_DIR}/logs"


# =====================================================
# 停止服务
# =====================================================

cleanup() {
    echo ""
    echo "正在停止Knowledge Agent服务……"

    if [ -n "${API_PID:-}" ]; then
        kill "${API_PID}" 2>/dev/null || true
    fi

    if [ -n "${FRONTEND_PID:-}" ]; then
        kill "${FRONTEND_PID}" 2>/dev/null || true
    fi

    wait 2>/dev/null || true

    echo "Knowledge Agent服务已停止"
}


trap cleanup EXIT INT TERM


# =====================================================
# 进入项目并创建日志目录
# =====================================================

cd "${PROJECT_DIR}"

mkdir -p "${LOG_DIR}"


# =====================================================
# 查找并初始化Conda
# =====================================================

if command -v conda >/dev/null 2>&1; then
    CONDA_BASE="$(conda info --base)"

elif [ -f "${HOME}/miniconda3/etc/profile.d/conda.sh" ]; then
    CONDA_BASE="${HOME}/miniconda3"

elif [ -f "${HOME}/anaconda3/etc/profile.d/conda.sh" ]; then
    CONDA_BASE="${HOME}/anaconda3"

else
    echo "错误：没有找到Conda"
    echo "请先安装Miniconda或Anaconda"
    exit 1
fi


CONDA_SCRIPT="${CONDA_BASE}/etc/profile.d/conda.sh"


if [ ! -f "${CONDA_SCRIPT}" ]; then
    echo "错误：没有找到Conda初始化脚本"
    echo "查找路径：${CONDA_SCRIPT}"
    exit 1
fi


source "${CONDA_SCRIPT}"


if ! conda env list | awk '{print $1}' | grep -qx "${CONDA_ENV_NAME}"; then
    echo "错误：Conda环境不存在：${CONDA_ENV_NAME}"
    echo ""
    echo "请先创建环境，例如："
    echo "conda create -n ${CONDA_ENV_NAME} python=3.11"
    exit 1
fi


conda activate "${CONDA_ENV_NAME}"


# =====================================================
# 启动服务
# =====================================================

echo "正在启动Knowledge Agent……"
echo "项目目录：${PROJECT_DIR}"
echo "Conda环境：${CONDA_ENV_NAME}"


uvicorn app.api.main:app \
    --host "${API_HOST}" \
    --port "${API_PORT}" \
    > "${LOG_DIR}/api.log" 2>&1 &

API_PID=$!


streamlit run frontend.py \
    --server.address "${FRONTEND_HOST}" \
    --server.port "${FRONTEND_PORT}" \
    > "${LOG_DIR}/frontend.log" 2>&1 &

FRONTEND_PID=$!


# =====================================================
# 检查服务是否成功启动
# =====================================================

sleep 3


if ! kill -0 "${API_PID}" 2>/dev/null; then
    echo "错误：FastAPI启动失败"
    echo "后端日志："
    tail -n 30 "${LOG_DIR}/api.log"
    exit 1
fi


if ! kill -0 "${FRONTEND_PID}" 2>/dev/null; then
    echo "错误：Streamlit启动失败"
    echo "前端日志："
    tail -n 30 "${LOG_DIR}/frontend.log"
    exit 1
fi


# =====================================================
# 输出运行信息
# =====================================================

echo ""
echo "Knowledge Agent启动成功"
echo ""
echo "FastAPI进程ID：${API_PID}"
echo "Streamlit进程ID：${FRONTEND_PID}"
echo ""
echo "FastAPI接口文档：http://localhost:${API_PORT}/docs"
echo "Streamlit前端：http://localhost:${FRONTEND_PORT}"
echo ""
echo "后端日志：${LOG_DIR}/api.log"
echo "前端日志：${LOG_DIR}/frontend.log"
echo ""
echo "按Ctrl+C停止全部服务"


wait