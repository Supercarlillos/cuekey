PYTHON ?= python3.13
VENV := .venv

.PHONY: install dev test coverage clean

install:
	pipx install .

dev:
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/pip install --upgrade pip
	$(VENV)/bin/pip install -e ".[dev]"

test:
	$(VENV)/bin/pytest

coverage:
	$(VENV)/bin/pytest --cov --cov-report=term-missing

clean:
	rm -rf $(VENV) dist build .pytest_cache .coverage *.egg-info
