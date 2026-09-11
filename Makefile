.PHONY: help setup demo preset edgecases test eval docker-build docker-demo docker-interactive docker-test

help:
	@echo "========================================================================"
	@echo "            @AppleSupport AI Support Agent — Makefile"
	@echo "========================================================================"
	@echo "Quick Start Commands:"
	@echo "  make demo               Launch interactive agent demo (all menus)"
	@echo "  make preset             Run 5 standard customer intent scenarios"
	@echo "  make edgecases          Run 5 production edge cases & security defenses"
	@echo "  make test               Run unit test suite (pytest)"
	@echo "  make eval               Run evaluation pipeline on golden set (30 cases)"
	@echo ""
	@echo "Docker Commands (Zero Local Python Setup):"
	@echo "  make docker-build       Build container image"
	@echo "  make docker-demo        Run preset support demonstration in Docker"
	@echo "  make docker-interactive Run interactive CLI demo inside Docker"
	@echo "  make docker-test        Run test suite inside Docker"
	@echo "========================================================================"

setup:
	python3 -m venv venv && . venv/bin/activate && pip install --upgrade pip && pip install -r requirements.txt
	@if [ ! -f .env ]; then cp .env.example .env; echo "Created .env from .env.example. Please add your GROQ_API_KEY."; fi

demo:
	python demo.py

preset:
	python demo.py --preset

edgecases:
	python demo.py --edgecases

test:
	pytest tests/test_agent.py -v

eval:
	python evaluation/eval_metrics.py --limit 30

docker-build:
	docker compose build

docker-demo:
	docker compose run --rm agent

docker-interactive:
	docker compose run --rm interactive

docker-test:
	docker compose run --rm test
