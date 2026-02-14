.PHONY: test lint

lint:
	ruff check .

test: lint
	pytest
