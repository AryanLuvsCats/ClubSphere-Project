# ==============================================================================
# Stage 1: Build the Vite React Frontend Application
# ==============================================================================
FROM node:20-alpine AS build

WORKDIR /app

# Cache dependencies
COPY package.json package-lock.json ./
RUN npm ci

# Copy project files
COPY . .

# Optional build-time argument for API Base URL
ARG VITE_API_BASE_URL
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

# Compile TypeScript and bundle with Vite
RUN npm run build

# ==============================================================================
# Stage 2: Production Nginx Static Server & Reverse Proxy
# ==============================================================================
FROM nginx:1.27-alpine

# Remove default static files
RUN rm -rf /usr/share/nginx/html/*

# Copy built SPA artifacts
COPY --from=build /app/dist /usr/share/nginx/html

# Copy the Nginx config template. The official nginx entrypoint renders it at
# container start using BACKEND_SCHEME / BACKEND_HOST from the environment.
# Defaults suit local Docker Compose (backend service on port 8000); Render
# overrides them with its public backend URL.
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
ENV BACKEND_SCHEME=http \
    BACKEND_HOST=backend:8000

# Expose HTTP port
EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget -q --spider http://127.0.0.1/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
