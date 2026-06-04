# v0.1 Docker Tar 部署说明

## 1. 本地构建镜像 tar

```bash
bash scripts/build_release_tars.sh
```

默认会在构建阶段使用清华镜像：

- Python 包：`https://pypi.tuna.tsinghua.edu.cn/simple`
- Node 发行文件：`https://mirrors.tuna.tsinghua.edu.cn/nodejs-release/`

如需临时覆盖，可在执行时传环境变量：

```bash
PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
PIP_TRUSTED_HOST=pypi.tuna.tsinghua.edu.cn \
NODEJS_DIST_MIRROR=https://mirrors.tuna.tsinghua.edu.cn/nodejs-release/ \
bash scripts/build_release_tars.sh
```

产物会输出到 `release/v0.1/`：

- `zjjz-backend-v0.1-linux-amd64.tar`
- `zjjz-frontend-v0.1-linux-amd64.tar`
- `zjjz-redis-v0.1-linux-amd64.tar`
- `docker-compose.yml`
- `backend.v0.1.env`

## 2. 传到服务器

把 `release/v0.1/` 目录下的文件传到 `47.93.141.103`，例如：

```bash
ssh root@47.93.141.103 "mkdir -p /opt/zjjz-v0.1"
scp release/v0.1/* root@47.93.141.103:/opt/zjjz-v0.1/
```

## 3. 服务器加载镜像

```bash
cd /opt/zjjz-v0.1
docker load -i zjjz-backend-v0.1-linux-amd64.tar
docker load -i zjjz-frontend-v0.1-linux-amd64.tar
docker load -i zjjz-redis-v0.1-linux-amd64.tar
```

## 4. 编辑环境变量

至少检查这些值：

- `SECRET_KEY`
- `ALLOWED_HOSTS`
- `DB_HOST`
- `DB_PASSWORD`
- `REDIS_URL`
- `AMAP_WEB_SERVICE_KEY`
- `BIGMODEL_API_KEY`

## 5. 启动

```bash
docker compose -f docker-compose.yml up -d
```

默认对外暴露：

- 前端 `80`
- 后端仅容器内暴露 `8000`，由前端容器里的 `nginx` 反代 `/api`、`/ws`、`/sensor`
- Redis 仅容器内暴露 `6379`

## 6. 更新到 v0.1

重新构建 tar、上传、执行：

```bash
docker compose -f docker-compose.yml down
docker load -i zjjz-backend-v0.1-linux-amd64.tar
docker load -i zjjz-frontend-v0.1-linux-amd64.tar
docker load -i zjjz-redis-v0.1-linux-amd64.tar
docker compose -f docker-compose.yml up -d
```

## 说明

- 这个方案默认启动 `frontend + backend + redis + worker + beat`。
- `backend` 使用 ASGI + `daphne`，支持 `/ws/realtime/` WebSocket。
- `worker` 与 `beat` 复用 `zjjz-backend:v0.1` 镜像，通过不同命令启动 Celery。
- 如果服务器的 `80` 端口已经被宿主机 `nginx` 或其他服务占用，请先改 `docker-compose.yml` 里的端口映射。
- `zjjz-redis:v0.1` 来自官方 `redis:7.2-alpine`，在本地构建脚本里拉取后重新打 tag 并导出 tar。
