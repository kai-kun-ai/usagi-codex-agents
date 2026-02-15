.PHONY: test go-test d-test d-shell

go-test:
	go test ./...

test: go-test

# Docker前提のテスト
d-test:
	docker build -t usagi-corp-dev .
	docker run --rm usagi-corp-dev version

# Dockerコンテナに入る（codex/claude login等）
d-shell:
	docker build -t usagi-corp-dev .
	docker run --rm -it -v "$$PWD":/app usagi-corp-dev bash
