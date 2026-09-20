"""Tira do rastreio os itens sem nome em nenhum idioma.

Revision ID: 0014_destrava_itens_sem_nome
Revises: 0013_taxas_medidas
Create Date: 2026-09-20

Medido em 20/09/2026: dos 455 itens rastreados, 45 nunca tiveram cotação
alguma. Trinta deles não têm `display_name` em português **nem** em inglês —
são os `CRYSTALLEAGUE_*_TEMPLATE` e o `QUESTITEM_TOKEN_ARENA_CRYSTAL`, que
existem no dump como peça de configuração de conteúdo e não como coisa que
alguém compra. Perguntado ao AODP direto: as 35 linhas de cada um voltam com
todos os preços zerados.

Eram 6,6% de cada varredura completa — 30 de 455 itens, a 1 req/s sustentado —
gastos em item que não tem mercado.

**O critério é a ausência de nome, não a ausência de cotação.** Os outros 15
sem cotação continuam rastreados: cinco são montarias raras (`Lobinho-fantasma`,
`Gamo do Mestre`) e dez são rédeas e elixires de montaria. Todos têm nome, são
itens de verdade, e só não tiveram ordem observada ainda. **Ausência de mercado
observado não é ausência de mercado** — e foi por confundir as duas que a
primeira versão desta limpeza ia tirar 40 em vez de 30.

O importador aplica a mesma regra em `normalize`, com teste. Esta migration
existe porque `is_tracked` não é sobrescrito na reimportação (é decisão
operacional), então o banco de quem já importou não se corrigiria sozinho.
"""

from alembic import op

revision = "0014_destrava_itens_sem_nome"
down_revision = "0013_taxas_medidas"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE items
           SET is_tracked = false
         WHERE is_tracked = true
           AND display_name_pt IS NULL
           AND display_name_en IS NULL
        """
    )


def downgrade() -> None:
    # Devolve o rastreio a quem o tinha. Não dá para distinguir, na volta, quem
    # já estava fora antes — e por isso o critério é repetido aqui em vez de se
    # guardar uma lista: ele é determinístico.
    op.execute(
        """
        UPDATE items
           SET is_tracked = true
         WHERE display_name_pt IS NULL
           AND display_name_en IS NULL
           AND subcategory_code IN ('tokens')
        """
    )
