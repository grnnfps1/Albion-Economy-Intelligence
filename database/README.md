# database/

Seeds e scripts de dados.

- `seeds/` — dados fixos (servidores, cidades, categorias). Entram na FASE 2 via
  migration de dados do Alembic, não via script solto: assim o estado do banco é
  sempre reprodutível a partir de `alembic upgrade head`.

O schema em si vive em `backend/alembic/versions/`. Nunca usar `create_all()`
para criar tabelas fora de teste (requisito 45).
