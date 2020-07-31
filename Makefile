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

.PHONY: newvenv
newvenv:
	rm -rf .venv
	$(PYTHON) -m venv .venv

.PHONY: revenv
revenv:
	mkdir -p .pipcache
	.venv/bin/pip install --cache-dir .pipcache -r requirements.txt

.PHONY: venv
venv: newvenv revenv

.PHONY: repl
repl:
	.venv/bin/ipython --no-confirm-exit --logappend .ipython

.PHONY: lint
lint:
	.venv/bin/flake8 *.py

.PHONY: typecheck
typecheck:
	.venv/bin/mypy *.py

.PHONY: test
test: lint typecheck

.PHONY: isort
isort:
	.venv/bin/isort *.py

.PHONY: test-isort
test-isort:
	.venv/bin/isort tests
