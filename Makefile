.PHONY: help up down logs ps clean test lint format

help:
	@echo "Available commands:"
	@echo "  make up        - Start the full stack via Docker Compose"
	@echo "  make down      - Stop and remove all containers"
	@echo "  make logs      - Tail logs from all running services"
	@echo "  make ps        - Show running services"
	@echo "  make clean     - Remove containers, volumes, and generated data"
	@echo "  make test      - Run pytest tests"
	@echo "  make lint      - Lint Python code with ruff"
	@echo "  make format    - Format Python code with ruff"

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

ps:
	docker compose ps

clean:
	docker compose down -v
	rm -rf data/ output/

test:
	pytest data_generator/tests/ -v

lint:
	ruff check .

format:
	ruff format .
