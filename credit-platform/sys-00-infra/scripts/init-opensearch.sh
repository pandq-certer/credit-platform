#!/usr/bin/env bash
# T-00-03 安装 IK 分词插件并写入索引模板（单节点 shards=1 / replicas=0）
# IK 插件版本与 OpenSearch 3.9.0 精确匹配：https://get.infini.cloud/opensearch/analysis-ik/3.9.0
set -euo pipefail
cd "$(dirname "$0")/.."

IK_URL="https://get.infini.cloud/opensearch/analysis-ik/3.9.0"
IK_ZIP="/tmp/analysis-ik-3.9.0.zip"

if ! docker compose exec -T opensearch test -d /usr/share/opensearch/plugins/analysis-ik; then
  curl -fsSL "$IK_URL" -o "$IK_ZIP"
  docker cp "$IK_ZIP" sys00-opensearch:/tmp/analysis-ik-3.9.0.zip
  docker compose exec -T opensearch bin/opensearch-plugin install -b file:///tmp/analysis-ik-3.9.0.zip
  docker compose restart opensearch
  until curl -sf localhost:9200 >/dev/null; do sleep 3; done
fi

# OpenSearch 3.x 的 legacy _template 不接受 template 包裹（会落成空模板），
# 使用等价的 composable 索引模板 API，模板体与修正稿 5.2 一致。
curl -fsS -XPUT localhost:9200/_index_template/credit_docs \
  -H 'Content-Type: application/json' \
  --data-binary @opensearch/credit_docs_template.json
echo
