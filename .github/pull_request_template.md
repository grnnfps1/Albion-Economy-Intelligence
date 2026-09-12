## O que muda

<!-- Uma frase. Qual fase, qual comportamento novo. -->

## Por quê

<!-- Que problema isso resolve. Se corrige um bug, qual era o sintoma. -->

## Checklist

- [ ] `ruff check .` limpo
- [ ] `pytest -q -rs` verde, sem teste pulado por acidente
- [ ] `npm run typecheck && npm run test` verdes
- [ ] Mudança de schema tem migration, e `alembic downgrade base && upgrade head` funciona
- [ ] Nenhum número inventado: valor não verificado ficou `NULL` com `source = 'UNKNOWN'`
- [ ] Ausência de dado continua sendo `NULL`, nunca `0`
- [ ] Nenhuma regra de negócio nova em `frontend/`
- [ ] README atualizado se o comando de rodar mudou

## Como testei

<!-- Comandos reais e o que eles mostraram. -->
