FROM node:20-alpine

WORKDIR /app

RUN npm install -g pnpm

COPY package.json pnpm-lock.yaml* ./

# Slow/flaky-network resilience: retry failed tarball fetches with a long ceiling
# instead of aborting the whole install on the first timeout.
RUN pnpm config set fetch-retries 15 \
    && pnpm config set fetch-retry-mintimeout 20000 \
    && pnpm config set fetch-retry-maxtimeout 300000 \
    && pnpm config set network-concurrency 4

RUN pnpm install --frozen-lockfile 2>/dev/null || echo "No lockfile yet"

COPY . .

CMD ["pnpm", "dev"]
