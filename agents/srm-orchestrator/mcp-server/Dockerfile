FROM node:22-alpine AS ui
WORKDIR /build
COPY ui/package*.json ./
RUN npm ci
COPY ui/index.html ui/app.ts ui/build.mjs ui/tsconfig.json ./
RUN npm run build

FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY server.py dashboard.py ./
COPY --from=ui /dist/dashboard.html ./dist/dashboard.html
RUN useradd --uid 10001 --create-home srm
USER srm
EXPOSE 8000
CMD ["python", "server.py"]
