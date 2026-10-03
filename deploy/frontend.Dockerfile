# Next.js website. Build from the repository root:
#   docker build -f deploy/frontend.Dockerfile \
#     --build-arg NEXT_PUBLIC_CCS_API_URL=https://api.example.org \
#     -t ccs-screen-web .
#
# NEXT_PUBLIC_CCS_API_URL is inlined at BUILD time: build one image per backend
# URL. NEXT_PUBLIC_CCS_REPO_URL is optional; when empty no repository link is
# rendered.
FROM node:22-slim AS build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend ./
ARG NEXT_PUBLIC_CCS_API_URL
ARG NEXT_PUBLIC_CCS_REPO_URL=
ARG NEXT_PUBLIC_CCS_BASE_PATH=
RUN test -n "$NEXT_PUBLIC_CCS_API_URL" || (echo "NEXT_PUBLIC_CCS_API_URL build arg is required" && exit 1)
ENV NEXT_PUBLIC_CCS_API_URL=$NEXT_PUBLIC_CCS_API_URL \
    NEXT_PUBLIC_CCS_REPO_URL=$NEXT_PUBLIC_CCS_REPO_URL \
    NEXT_PUBLIC_CCS_BASE_PATH=$NEXT_PUBLIC_CCS_BASE_PATH \
    NEXT_TELEMETRY_DISABLED=1
RUN npm run build && npm prune --omit=dev

FROM node:22-slim
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1
COPY --from=build /app/package.json ./
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/.next ./.next
COPY --from=build /app/next.config.mjs ./
USER node
EXPOSE 3000
CMD ["npx", "next", "start", "-p", "3000"]
