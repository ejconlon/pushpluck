PYTHON_PREFIX := $(shell pyenv prefix 3.8.3)
PYTHON := $(PYTHON_PREFIX)/bin/python

.PHONY: error
error:
	exit 1

.PHONY: pipready
pipready:
	$(PYTHON) -m pip install pip-tools

.PHONY: pipclean
pipclean:
	rm -f dev-requirements.txt
	rm -f requirements.txt

.PHONY: pipcompile
pipcompile:
	$(PYTHON) -m piptools compile requirements.in
	$(PYTHON) -m piptools compile dev-requirements.in

.PHONY: newvenv
newvenv:
	rm -rf .venv
	$(PYTHON) -m venv .venv

.PHONY: revenv
revenv:
	mkdir -p .pipcache
	.venv/bin/pip install --cache-dir .pipcache -r dev-requirements.txt

.PHONY: venv
venv: newvenv revenv

.PHONY: repl
repl:
	.venv/bin/ipython --no-confirm-exit --logappend .ipython

.PHONY: lint
lint:
	.venv/bin/flake8 pushpluck

.PHONY: typecheck
typecheck:
	.venv/bin/mypy -p pushpluck

.PHONY: test-lint
test-lint:
	.venv/bin/flake8 tests

.PHONY: test-typecheck
test-typecheck:
	.venv/bin/mypy -p tests

.PHONY: unit
unit:
	.venv/bin/python -Werror -m pytest -v tests/unit

.PHONY: test
test: lint typecheck test-lint test-typecheck unit

.PHONY: isort
isort:
	.venv/bin/isort pushpluck

.PHONY: test-isort
test-isort:
	.venv/bin/isort tests

.PHONY: run
run:
	./run.sh
