.PHONY: lint format install install-dev serve test coverage

install-dev:
	uv pip install -e ".[dev]"

install:
	uv pip install -e .

format:
	uv run black .

lint:
	uv run black --check .

serve:
	uv run server.py --reload

help:
	uv run server.py --help

test:
	uv run pytest tests/

coverage:
	uv run pytest --cov=src tests/ --cov-report=term-missing --cov-report=xml
