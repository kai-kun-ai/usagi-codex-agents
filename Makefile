.PHONY: test d-test d-shell

test:
	ruff check .
	pytest -q

# Dockerが正: ローカルpipはデバッグ用途
d-test:
	docker build -t usagi-dev .
	docker run --rm usagi-dev make test

# Dockerコンテナに入って公式CLIでログイン等を行う
d-shell:
	docker build -t usagi-dev .
	docker run --rm -it \
	  -v "$$PWD":/app \
	  usagi-dev bash
