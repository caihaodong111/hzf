#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="${ROOT_DIR}/backend"
FRONTEND_DIR="${ROOT_DIR}/frontend"
RUNTIME_DIR="${ROOT_DIR}/output/dev-runtime"
LOG_DIR="${RUNTIME_DIR}/logs"
PID_DIR="${RUNTIME_DIR}/pids"

CONDA_ENV_NAME="hzf"
BACKEND_PORT=8000
FRONTEND_PORT=5173

STARTED_PIDS=()

info() {
    printf '[INFO] %s\n' "$1"
}

error() {
    printf '[ERROR] %s\n' "$1" >&2
}

cleanup_started_services() {
    local pid=""
    for pid in "${STARTED_PIDS[@]:-}"; do
        if ps -p "${pid}" >/dev/null 2>&1; then
            kill "${pid}" >/dev/null 2>&1 || true
        fi
    done
}

check_required_path() {
    local path="$1"
    local name="$2"

    if [[ ! -e "${path}" ]]; then
        error "缺少 ${name}: ${path}"
        exit 1
    fi
}

check_port_available() {
    local port="$1"
    local service_name="$2"
    local lsof_output=""

    if lsof_output="$(lsof -nP -iTCP:"${port}" -sTCP:LISTEN 2>/dev/null)"; then
        error "${service_name} 需要的端口 ${port} 已被占用，请先释放后再启动。"
        printf '%s\n' "${lsof_output}" >&2
        exit 1
    fi
}

check_process_absent() {
    local pattern="$1"
    local service_name="$2"
    local process_output=""

    process_output="$(ps -ax -o pid= -o command= | grep -F "${pattern}" | grep -v grep || true)"
    if [[ -n "${process_output}" ]]; then
        error "${service_name} 已经在运行，请先停止旧进程。"
        printf '%s\n' "${process_output}" >&2
        exit 1
    fi
}

ensure_command() {
    local command_name="$1"

    if ! command -v "${command_name}" >/dev/null 2>&1; then
        error "未找到命令: ${command_name}"
        cleanup_started_services
        exit 1
    fi
}

activate_hzf_env() {
    if [[ "${CONDA_DEFAULT_ENV:-}" == "${CONDA_ENV_NAME}" ]]; then
        info "当前已经在 conda 环境 ${CONDA_ENV_NAME} 中。"
        return
    fi

    ensure_command conda

    # shellcheck disable=SC1090
    eval "$(conda shell.bash hook)"

    if ! conda env list | awk '{print $1}' | grep -qx "${CONDA_ENV_NAME}"; then
        error "未找到 conda 环境 ${CONDA_ENV_NAME}。"
        exit 1
    fi

    conda activate "${CONDA_ENV_NAME}"

    if [[ "${CONDA_DEFAULT_ENV:-}" != "${CONDA_ENV_NAME}" ]]; then
        error "conda 环境 ${CONDA_ENV_NAME} 激活失败。"
        exit 1
    fi

    info "已激活 conda 环境 ${CONDA_ENV_NAME}。"
}

wait_for_port() {
    local pid="$1"
    local port="$2"
    local service_name="$3"
    local log_file="$4"
    local attempt=0

    for attempt in {1..15}; do
        if lsof -nP -iTCP:"${port}" -sTCP:LISTEN >/dev/null 2>&1; then
            return 0
        fi

        if ! ps -p "${pid}" >/dev/null 2>&1; then
            break
        fi

        sleep 1
    done

    error "${service_name} 启动失败，请查看日志：${log_file}"
    sed -n '1,120p' "${log_file}" >&2 || true
    cleanup_started_services
    exit 1
}

launch_service() {
    local service_name="$1"
    local workdir="$2"
    local log_file="$3"
    shift 3

    info "启动 ${service_name}..."

    (
        cd "${workdir}"
        nohup "$@" >"${log_file}" 2>&1 &
        echo $! >"${PID_DIR}/${service_name}.pid"
    )

    sleep 1

    local pid=""
    pid="$(cat "${PID_DIR}/${service_name}.pid")"

    if ! ps -p "${pid}" >/dev/null 2>&1; then
        error "${service_name} 启动失败，请查看日志：${log_file}"
        sed -n '1,120p' "${log_file}" >&2 || true
        cleanup_started_services
        exit 1
    fi

    STARTED_PIDS+=("${pid}")
    info "${service_name} 已启动，PID=${pid}。"
}

main() {
    check_required_path "${BACKEND_DIR}/manage.py" "后端入口"
    check_required_path "${FRONTEND_DIR}/package.json" "前端入口"

    mkdir -p "${LOG_DIR}" "${PID_DIR}"

    ensure_command lsof
    ensure_command ps

    info "检查端口占用情况..."
    check_port_available "${BACKEND_PORT}" "Django 后端"
    check_port_available "${FRONTEND_PORT}" "Vite 前端"
    check_process_absent "celery -A aquaculture worker -l info" "Celery Worker"
    check_process_absent "celery -A aquaculture beat -l info" "Celery Beat"

    activate_hzf_env

    ensure_command python
    ensure_command celery
    ensure_command npm

    launch_service "backend" "${BACKEND_DIR}" "${LOG_DIR}/backend.log" \
        python manage.py runserver 0.0.0.0:"${BACKEND_PORT}"
    wait_for_port "$(cat "${PID_DIR}/backend.pid")" "${BACKEND_PORT}" "Django 后端" "${LOG_DIR}/backend.log"

    launch_service "frontend" "${FRONTEND_DIR}" "${LOG_DIR}/frontend.log" \
        npm run dev -- --host 0.0.0.0 --port "${FRONTEND_PORT}"
    wait_for_port "$(cat "${PID_DIR}/frontend.pid")" "${FRONTEND_PORT}" "Vite 前端" "${LOG_DIR}/frontend.log"

    launch_service "celery_worker" "${BACKEND_DIR}" "${LOG_DIR}/celery_worker.log" \
        celery -A aquaculture worker -l info
    launch_service "celery_beat" "${BACKEND_DIR}" "${LOG_DIR}/celery_beat.log" \
        celery -A aquaculture beat -l info

    printf '\n'
    info "全部服务启动完成。"
    printf '后端地址: http://127.0.0.1:%s\n' "${BACKEND_PORT}"
    printf '前端地址: http://127.0.0.1:%s\n' "${FRONTEND_PORT}"
    printf '日志目录: %s\n' "${LOG_DIR}"
    printf 'PID 目录: %s\n' "${PID_DIR}"
    printf '注意: Celery 依赖 backend/.env 中配置的 Redis 服务，请确认 Redis 已启动。\n'
}

main "$@"
