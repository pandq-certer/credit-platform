#!/usr/bin/env bash
# 由 .env 生成 SeaweedFS S3 身份配置（每系统一桶一 AccessKey，越权访问应 403）
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; . ./.env; set +a
mkdir -p secrets
out=secrets/seaweedfs-s3.json

{
  echo '{'
  echo '  "identities": ['
  echo "    {\"name\": \"admin\", \"credentials\": [{\"accessKey\": \"${S3_ADMIN_AK}\", \"secretKey\": \"${S3_ADMIN_SK}\"}], \"actions\": [\"Admin\", \"Read\", \"Write\", \"List\", \"Tagging\"]},"
  for n in $(seq -w 1 12); do
    ak="CREDIT_SYS${n}_S3_AK"; sk="CREDIT_SYS${n}_S3_SK"
    echo "    {\"name\": \"credit-sys${n}\", \"credentials\": [{\"accessKey\": \"${!ak}\", \"secretKey\": \"${!sk}\"}], \"actions\": [\"Read:credit-sys${n}\", \"Write:credit-sys${n}\", \"List:credit-sys${n}\", \"Tagging:credit-sys${n}\", \"Admin:credit-sys${n}\"]},"
  done
  n=13
  ak="CREDIT_SYS${n}_S3_AK"; sk="CREDIT_SYS${n}_S3_SK"
  echo "    {\"name\": \"credit-sys${n}\", \"credentials\": [{\"accessKey\": \"${!ak}\", \"secretKey\": \"${!sk}\"}], \"actions\": [\"Read:credit-sys${n}\", \"Write:credit-sys${n}\", \"List:credit-sys${n}\", \"Tagging:credit-sys${n}\", \"Admin:credit-sys${n}\"]}"
  echo '  ]'
  echo '}'
} > "$out"
chmod 600 "$out"
echo "wrote $out"
