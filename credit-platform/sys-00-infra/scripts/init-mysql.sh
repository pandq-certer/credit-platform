#!/usr/bin/env bash
# T-00-08 MySQL：RAGFlow 库与业务账号（限 Docker 网段 172.%）
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; . ./.env; set +a

docker compose exec -T -e MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql mysql -uroot <<SQL
CREATE DATABASE IF NOT EXISTS ragflow DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'ragflow'@'172.%' IDENTIFIED BY '${RAGFLOW_DB_PASSWORD}';
ALTER USER 'ragflow'@'172.%' IDENTIFIED BY '${RAGFLOW_DB_PASSWORD}';
GRANT ALL PRIVILEGES ON ragflow.* TO 'ragflow'@'172.%';
FLUSH PRIVILEGES;
SQL
echo "OK ragflow"
