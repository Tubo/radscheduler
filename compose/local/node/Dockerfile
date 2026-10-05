FROM docker.io/node:24-bookworm-slim

WORKDIR /app

ENV COREPACK_ENABLE_DOWNLOAD_PROMPT=0
RUN corepack enable

COPY ./package.json ./pnpm-lock.yaml ./pnpm-workspace.yaml /app/

RUN pnpm install --frozen-lockfile

ENV PATH=./node_modules/.bin/:$PATH
