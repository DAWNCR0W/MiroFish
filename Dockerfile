FROM python:3.11

# Node.js(>=18 충족)와 필요한 도구를 설치합니다
RUN apt-get update \
  && apt-get install -y --no-install-recommends nodejs npm \
  && rm -rf /var/lib/apt/lists/*

# uv 공식 이미지에서 uv를 복사합니다
COPY --from=ghcr.io/astral-sh/uv:0.9.26 /uv /uvx /bin/

WORKDIR /app

# 캐시를 활용하기 위해 의존성 설명 파일을 먼저 복사합니다
COPY package.json package-lock.json ./
COPY frontend/package.json frontend/package-lock.json ./frontend/
COPY backend/pyproject.toml backend/uv.lock ./backend/

# 의존성을 설치합니다(Node + Python)
RUN npm ci \
  && npm ci --prefix frontend \
  && cd backend && uv sync --frozen

# 프로젝트 소스를 복사합니다
COPY . .

EXPOSE 3000 5001

# 프런트엔드와 백엔드를 함께 시작합니다(개발 모드)
CMD ["npm", "run", "dev"]
