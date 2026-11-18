#!/usr/bin/env bash
# T-00-02 建 PostgreSQL 库与账号（单机版）
# 13 个业务系统库 credit_sys01..credit_sys13，一库一账号，账号仅拥有本库。
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; . ./.env; set +a

for n in $(seq -w 1 13); do
  db="credit_sys${n}"
  role="credit_sys${n}"
  pwvar="CREDIT_SYS${n}_PASSWORD"
  pw="${!pwvar:?missing ${pwvar} in .env}"
  docker compose exec -T postgres psql -U postgres -v ON_ERROR_STOP=1 \
    -v db="$db" -v role="$role" -v pw="$pw" <<'SQL'
SELECT 'CREATE ROLE ' || quote_ident(:'role') || ' LOGIN PASSWORD ' || quote_literal(:'pw')
 WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'role')\gexec
SELECT 'CREATE DATABASE ' || quote_ident(:'db') || ' OWNER ' || quote_ident(:'role')
 WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'db')\gexec
SELECT 'REVOKE ALL ON DATABASE ' || quote_ident(:'db') || ' FROM PUBLIC'\gexec
SELECT 'GRANT CONNECT, TEMPORARY ON DATABASE ' || quote_ident(:'db') || ' TO ' || quote_ident(:'role')\gexec
SQL
  echo "OK ${db}"
done

# FerretDB 后端库（compose 中 --postgresql-url 指向 /ferretdb）
docker compose exec -T postgres psql -U postgres -v ON_ERROR_STOP=1 <<'SQL'
SELECT 'CREATE DATABASE ferretdb OWNER postgres'
 WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'ferretdb')\gexec
SQL
echo "OK ferretdb"
