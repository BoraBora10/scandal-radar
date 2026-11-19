PYTHON ?= python3
.PHONY: run setup build

setup:
	@if [ ! -x .venv/bin/python ]; then if command -v uv >/dev/null; then uv venv --python 3.12 .venv; else $(PYTHON) -m venv .venv; fi; fi
	@.venv/bin/python -c 'import sys; assert sys.version_info >= (3,11), "Python 3.11+ is required; set PYTHON=/path/to/python3.12"'
	@if command -v uv >/dev/null; then uv pip install --python .venv/bin/python -r requirements.txt; else .venv/bin/python -m pip install -r requirements.txt; fi
	npm ci

build:
	.venv/bin/python -m ingestion.build_demo
	npm run build

run: setup build
	.venv/bin/python -m api.run
