# 文件路径：frontend/Dockerfile
# 用途：前端开发容器
# MVP 范围：开发热重载

FROM node:20-slim

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install

COPY . .

EXPOSE 3000

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "3000"]