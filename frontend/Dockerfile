# Build stage
FROM node:24-bookworm-slim AS build

WORKDIR /app

RUN npm install -g pnpm@12.3.4

COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY . .
RUN pnpm build

# Production stage
FROM node:24-bookworm-slim

WORKDIR /app

RUN npm install -g serve@14.2.5

COPY --from=build /app/dist ./dist

EXPOSE 3000

CMD ["serve", "-s", "dist", "-l", "tcp://0.0.0.0:3000"]