#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="v0.1"
PLATFORM="${PLATFORM:-linux/amd64}"
PLATFORM_TAG="${PLATFORM//\//-}"
RELEASE_DIR="${ROOT_DIR}/release/${VERSION}"

if [ -f "${ROOT_DIR}/frontend/.env" ]; then
    set -a
    # shellcheck disable=SC1091
    . "${ROOT_DIR}/frontend/.env"
    set +a
fi

PIP_INDEX_URL="${PIP_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}"
PIP_TRUSTED_HOST="${PIP_TRUSTED_HOST:-pypi.tuna.tsinghua.edu.cn}"
NODEJS_DIST_MIRROR="${NODEJS_DIST_MIRROR:-https://mirrors.tuna.tsinghua.edu.cn/nodejs-release/}"
VITE_AMAP_JS_API_KEY="${VITE_AMAP_JS_API_KEY:-${VITE_AMAP_API_KEY:-}}"
VITE_AMAP_SECURITY_CODE="${VITE_AMAP_SECURITY_CODE:-}"

if [ -z "${VITE_AMAP_JS_API_KEY}" ] || [ -z "${VITE_AMAP_SECURITY_CODE}" ]; then
    echo "Warning: VITE_AMAP_JS_API_KEY or VITE_AMAP_SECURITY_CODE is empty. Frontend map may fail to load." >&2
fi

BACKEND_IMAGE="zjjz-backend:${VERSION}"
FRONTEND_IMAGE="zjjz-frontend:${VERSION}"
REDIS_SOURCE_IMAGE="redis:7.2-alpine"
REDIS_IMAGE="zjjz-redis:${VERSION}"
BACKEND_TAR="${RELEASE_DIR}/zjjz-backend-${VERSION}-${PLATFORM_TAG}.tar"
FRONTEND_TAR="${RELEASE_DIR}/zjjz-frontend-${VERSION}-${PLATFORM_TAG}.tar"
REDIS_TAR="${RELEASE_DIR}/zjjz-redis-${VERSION}-${PLATFORM_TAG}.tar"

mkdir -p "${RELEASE_DIR}"

echo "[1/5] Building ${BACKEND_IMAGE} for ${PLATFORM}"
docker build \
    --platform "${PLATFORM}" \
    --provenance=false \
    --build-arg "PIP_INDEX_URL=${PIP_INDEX_URL}" \
    --build-arg "PIP_TRUSTED_HOST=${PIP_TRUSTED_HOST}" \
    -t "${BACKEND_IMAGE}" \
    "${ROOT_DIR}/backend"

echo "[2/5] Building ${FRONTEND_IMAGE} for ${PLATFORM}"
docker build \
    --platform "${PLATFORM}" \
    --provenance=false \
    --build-arg "NODEJS_DIST_MIRROR=${NODEJS_DIST_MIRROR}" \
    --build-arg "VITE_AMAP_JS_API_KEY=${VITE_AMAP_JS_API_KEY}" \
    --build-arg "VITE_AMAP_SECURITY_CODE=${VITE_AMAP_SECURITY_CODE}" \
    -t "${FRONTEND_IMAGE}" \
    "${ROOT_DIR}/frontend"

echo "[3/5] Pulling ${REDIS_SOURCE_IMAGE} for ${PLATFORM} and tagging it as ${REDIS_IMAGE}"
docker pull --platform "${PLATFORM}" "${REDIS_SOURCE_IMAGE}"
docker tag "${REDIS_SOURCE_IMAGE}" "${REDIS_IMAGE}"

echo "[4/5] Saving image tar files to ${RELEASE_DIR}"
docker save --platform "${PLATFORM}" -o "${BACKEND_TAR}" "${BACKEND_IMAGE}"
docker save --platform "${PLATFORM}" -o "${FRONTEND_TAR}" "${FRONTEND_IMAGE}"
docker save --platform "${PLATFORM}" -o "${REDIS_TAR}" "${REDIS_IMAGE}"

echo "[5/5] Copying deployment files"
cp "${ROOT_DIR}/deploy/docker-compose.v0.1.yml" "${RELEASE_DIR}/docker-compose.yml"
cp "${ROOT_DIR}/deploy/backend.v0.1.env" "${RELEASE_DIR}/backend.v0.1.env"
cp "${ROOT_DIR}/deploy/DEPLOY.v0.1.md" "${RELEASE_DIR}/DEPLOY.v0.1.md"

if command -v shasum >/dev/null 2>&1; then
    (
        cd "${RELEASE_DIR}"
        shasum -a 256 ./*.tar > SHA256SUMS
    )
fi

echo "Release files are ready in ${RELEASE_DIR}"
