FROM docker.io/node:24-bookworm-slim

WORKDIR /app

# The Elm compiler fetches its packages over HTTPS with the system's certificates, which the slim image lacks
# (Node and pnpm bring their own).
RUN apt-get update && apt-get install --no-install-recommends -y ca-certificates \
  && rm -rf /var/lib/apt/lists/*

ENV COREPACK_ENABLE_DOWNLOAD_PROMPT=0
RUN corepack enable

COPY ./package.json ./pnpm-lock.yaml ./pnpm-workspace.yaml ./elm-tooling.json /app/

RUN pnpm install --frozen-lockfile

ENV PATH=./node_modules/.bin/:$PATH
