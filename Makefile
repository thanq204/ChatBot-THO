.PHONY: install dev dev-backend dev-frontend build run test lint format typecheck check clean

install:
	pip install -r requirements.txt
	cd frontend && npm install

# Two processes in development: Vite owns the UI on :5173 and proxies /api to :8000.
dev-backend:
	uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000

dev-frontend:
	cd frontend && npm run dev

build:
	cd frontend && npm run build

# Single process: FastAPI serves the built SPA and the API on one origin.
run: build
	uvicorn backend.main:app --host 0.0.0.0 --port 8000

test:
	pytest tests/ -v

lint:
	ruff check backend/ tests/

format:
	ruff format backend/ tests/

typecheck:
	mypy backend/

check: lint format test

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name .ruff_cache -exec rm -rf {} +
	rm -rf frontend/dist
