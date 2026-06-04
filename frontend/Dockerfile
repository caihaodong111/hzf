FROM node:20-alpine AS build

ARG NODEJS_DIST_MIRROR=https://mirrors.tuna.tsinghua.edu.cn/nodejs-release/
ARG VITE_AMAP_JS_API_KEY=
ARG VITE_AMAP_SECURITY_CODE=

ENV npm_config_disturl=${NODEJS_DIST_MIRROR} \
    VITE_AMAP_JS_API_KEY=${VITE_AMAP_JS_API_KEY} \
    VITE_AMAP_SECURITY_CODE=${VITE_AMAP_SECURITY_CODE}

WORKDIR /app

COPY package.json package-lock.json /app/
RUN npm ci

COPY . /app
RUN npm run build

FROM nginx:1.27-alpine

COPY nginx/default.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
