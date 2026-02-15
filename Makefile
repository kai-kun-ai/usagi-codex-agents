.PHONY: test lint d-test

lint:
	ruff check .

test: lint
	pytest

# Docker前提のテスト（Docker内で lint+pytest を回す）
d-test:
	docker build -t usagi-dev .
	docker run --rm usagi-dev make test

# Dockerコンテナに入って公式CLIでログイン等を行う
d-shell:
	docker build -t usagi-dev .
	docker run --rm -it \
	  -v "$$PWD":/app \
	  usagi-dev bash
