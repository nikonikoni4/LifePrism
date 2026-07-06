.PHONY: check lint format type test clean help frontend-check frontend-fix frontend-lint frontend-format frontend-type frontend-test frontend-clean all

PKG := lifeprism
TESTS := test

help:
	@echo "Targets:"
	@echo "  make check           - run lint + type + test (local CI)"
	@echo "  make lint            - ruff check + format check"
	@echo "  make format          - ruff format + ruff --fix (auto-fix)"
	@echo "  make type            - mypy type check"
	@echo "  make test            - pytest"
	@echo "  make clean           - remove caches"
	@echo ""
	@echo "  make frontend-check  - run format + lint + type + test (local CI)"
	@echo "  make frontend-fix    - auto-fix format + lint"
	@echo "  make frontend-lint   - eslint check"
	@echo "  make frontend-format - prettier auto-fix"
	@echo "  make frontend-type   - typescript type check"
	@echo "  make frontend-test   - vitest"
	@echo "  make frontend-clean  - remove frontend caches"
	@echo ""
	@echo "  make all             - run backend + frontend checks"

check:
	@echo ">>> ruff check" && ruff check $(PKG) && \
	  echo ">>> ruff format check" && ruff format --check $(PKG) && \
	  echo ">>> mypy" && mypy && \
	  echo ">>> pytest" && pytest $(TESTS)

lint:
	ruff check $(PKG)
	ruff format --check $(PKG)

format:
	ruff format $(PKG)
	ruff check --fix $(PKG)

type:
	mypy

test:
	pytest $(TESTS)

clean:
	rm -rf .mypy_cache .pytest_cache .ruff_cache .coverage
	find . -type d -name __pycache__ -exec rm -rf {} +

# ==================== Frontend ====================

frontend-check:
	cd frontend && npm run format && npm run lint && npm run type-check && npm run test -- --run

frontend-fix:
	cd frontend && npm run format && npm run lint:fix

frontend-lint:
	cd frontend && npm run lint

frontend-format:
	cd frontend && npm run format

frontend-type:
	cd frontend && npm run type-check

frontend-test:
	cd frontend && npm run test -- --run

frontend-clean:
	rm -rf frontend/node_modules/.vite frontend/dist frontend/coverage

# ==================== All ====================

all: check frontend-check
