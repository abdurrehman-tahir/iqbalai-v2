FROM node:20-alpine

WORKDIR /app

RUN npm install -g pnpm

COPY package.json pnpm-lock.yaml* ./

RUN pnpm install --frozen-lockfile 2>/dev/null || echo "No lockfile yet"

COPY . .

CMD ["pnpm", "dev"]
