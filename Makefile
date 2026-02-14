.PHONY: test lint d-test

lint:
	ruff check .

test: lint
	pytest

# Docker前提のテスト（Docker内で lint+pytest を回す）
d-test:
	docker build -t usagi-dev .
	docker run --rm usagi-dev make test
