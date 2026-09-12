-- Banco separado para os testes de integração.
-- Roda uma única vez, na primeira criação do volume do Postgres.
SELECT 'CREATE DATABASE albion_test'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'albion_test')\gexec
