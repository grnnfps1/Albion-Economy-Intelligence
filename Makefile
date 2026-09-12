.PHONY: help up down logs ps test test-backend test-frontend lint migrate revision import-items collect collector-up collector-logs shell-db shell-redis clean

help:
	@grep -E '^[a-z-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-16s %s\n", $$1, $$2}'

up:              ## Sobe toda a stack
	docker compose up -d --build
down:            ## Derruba a stack (mantém os volumes)
	docker compose down
logs:            ## Acompanha os logs
	docker compose logs -f
ps:              ## Estado dos serviços
	docker compose ps
test: test-backend test-frontend  ## Roda todos os testes
test-backend:    ## Testes do backend
	docker compose exec backend pytest -q
test-frontend:   ## Testes do frontend
	docker compose exec frontend npm run test
lint:            ## Lint do backend
	docker compose exec backend ruff check .
migrate:         ## Aplica as migrations (FASE 2 em diante)
	docker compose exec backend alembic upgrade head
revision:        ## make revision m="mensagem"
	docker compose exec backend alembic revision --autogenerate -m "$(m)"
import-items:    ## Importa o catálogo de itens do ao-bin-dumps (~40 MB de download)
	docker compose exec backend python -m app.cli.import_items
collect:         ## Roda uma coleta de preços agora (make collect s=west)
	docker compose exec backend python -m app.cli.collect_market --server $(or $(s),west)
collector-up:    ## Sobe o worker de coleta contínua
	docker compose --profile collector up -d worker-market
collector-logs:  ## Logs do worker de coleta
	docker compose --profile collector logs -f worker-market
shell-db:        ## psql no banco
	docker compose exec postgres psql -U albion -d albion
shell-redis:     ## redis-cli
	docker compose exec redis redis-cli
clean:           ## Derruba a stack E apaga os volumes (perde os dados)
	docker compose down -v
