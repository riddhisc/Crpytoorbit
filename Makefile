.PHONY: dev test lint demo

dev:
	uvicorn app.main:app --reload --port 8000

test:
	pytest -q --cov=app --cov-fail-under=85
	cd web && npm test && npm run typecheck

lint:
	ruff check app tests
	ruff format --check app tests
	mypy app
	cd web && npm run lint && npx tsc --noEmit

demo:
	python -m app.cli import sample-data/wazirx_trades.csv sample-data/binance_trades.csv sample-data/wallet_transfers.json
