# 构建阶段
FROM node:20-alpine AS builder
WORKDIR /app

# 设置npm镜像源
RUN npm config set registry https://registry.npmmirror.com

# 先复制依赖清单并安装（利用层缓存）
COPY package.json package-lock.json ./
RUN npm ci

# 复制源代码并执行docker构建命令
COPY . .
RUN npm run build:docker

# 运行阶段：非root nginx，统一监听8080
FROM nginxinc/nginx-unprivileged:1.27-alpine
WORKDIR /usr/share/nginx/html

# 复制构建产物
COPY --from=builder /app/dist .

# 复制nginx配置（listen 8080；compose 场景由挂载的变体配置覆盖）
COPY bin/nginx.docker.conf /etc/nginx/conf.d/default.conf

# 暴露端口
EXPOSE 8080

# 启动nginx
CMD ["nginx", "-g", "daemon off;"]