# SYS-00 共享基础服务池 · 阶段一交付报告

> 实施日期：2026-11-16
> 依据：`docs/SYS-00-共享基础服务池-单体版-修正稿.md`、`docs/实施交接说明.md`
> 形态：单机 Docker Compose（Docker Desktop 29.6.1，12GB / 10 CPU）

## 一、变更清单

| 文件 | 动作 | 原因 |
|---|---|---|
| `sys-00-infra/.env` | 新建（不入库） | 由 `.env.example` 复制并填入随机密钥；额外含 `CREDIT_SYS01..13_PASSWORD`、`CREDIT_SYS01..13_S3_AK/SK`、`S3_ADMIN_AK/SK`、`FERRETDB_PASSWORD`、`RAGFLOW_DB_PASSWORD` |
| `sys-00-infra/docker-compose.yml` | 修改 | ① PG18 数据卷改为 `/var/lib/postgresql`（18+ 官方镜像新布局）；② SeaweedFS 固定 digest `sha256:a35a9224…` 并挂载 S3 身份配置；③ 新增 `ferretdb-pg`（`ghcr.io/ferretdb/postgres-documentdb:17`）专供 FerretDB 2.7.0；④ FerretDB 指向新后端并开发期 `--no-auth`；⑤ 为 etcd/Prometheus/Grafana/SeaweedFS 补 healthcheck |
| `sys-00-infra/scripts/init-databases.sh` | 新建 | T-00-02 建 13 个业务库（credit_sys01..13）与一库一账号，撤销 PUBLIC 连接权限 |
| `sys-00-infra/scripts/init-opensearch.sh` | 新建 | T-00-03 安装 analysis-ik 3.9.0 并写索引模板 |
| `sys-00-infra/opensearch/credit_docs_template.json` | 新建 | 修正稿 5.2 索引模板（shards 1 / replicas 0 / ik_max_word） |
| `sys-00-infra/scripts/gen-seaweedfs-config.sh` | 新建 | 由 `.env` 生成每系统一 AccessKey、桶级权限的 `s3.json` |
| `sys-00-infra/secrets/seaweedfs-s3.json` | 生成（chmod 600，不入库） | SeaweedFS S3 身份配置 |
| `sys-00-infra/scripts/init-mysql.sh` | 新建 | T-00-08 建 RAGFlow 库与 `ragflow@172.%` 账号 |
| `sys-00-infra/grafana/provisioning/datasources/prometheus.yml` | 新建 | T-00-07 Grafana 数据源指向 Prometheus |
| `sys-00-infra/evidence/*.log` | 新建 | 验证原始输出留证 |

## 二、执行日志（关键命令）

```bash
# 环境
docker context use desktop-linux        # OrbStack VM 异常，改用 Docker Desktop
# Docker Desktop 内存 8192 → 12288 MiB（用户确认）
docker stop sungraph-pg                 # 释放 5432（用户确认）

# 启动
cd sys-00-infra && cp .env.example .env # 写入随机密钥
docker pull docker.1panel.live/opensearchproject/opensearch:3.9.0
docker tag  docker.1panel.live/opensearchproject/opensearch:3.9.0 opensearchproject/opensearch:3.9.0
docker compose up -d
./scripts/init-databases.sh
./scripts/gen-seaweedfs-config.sh
./scripts/init-opensearch.sh
./scripts/init-mysql.sh
```

## 三、验证结果表

| 编号 | 命令 | 预期 | 实际 | 结论 |
|---|---|---|---|---|
| V-00-01 | `docker compose ps` | 全部 Up/healthy | 11 个容器全部 `Up (healthy)` | 通过 |
| V-00-02 | `pg_isready -h 127.0.0.1 -p 5432` | accepting connections | `127.0.0.1:5432 - accepting connections` | 通过 |
| V-00-03 | `mysql ... -e "select 1"` | 返回 1 | 返回 `1` | 通过 |
| V-00-04 | `valkey-cli -p 6379 ping` | PONG | `PONG` | 通过 |
| V-00-05 | `valkey-cli -p 6380 info persistence` | aof_enabled:1 | `aof_enabled:1` | 通过 |
| V-00-06 | `curl localhost:9200/_cluster/health` | green / 1 node | `"status":"green","number_of_nodes":1` | 通过 |
| V-00-07 | `etcdctl put smoke ok && get smoke` | ok | `OK` / `smoke` / `ok` | 通过 |
| V-00-08 | SeaweedFS healthz + `mc ls` | 正常响应 | healthz HTTP 200；admin 列出 13 桶；sys01 读本桶成功、读 sys02 返回 `Access Denied` | 通过 |
| V-00-09 | `curl localhost:9090/-/healthy` | Healthy | `Prometheus Server is Healthy.` | 通过 |
| V-00-10 | `curl localhost:3000/api/health` | database ok | `{"database":"ok","version":"13.3.1"}` | 通过 |

补充验证：

| 项 | 结果 |
|---|---|
| T-00-02 13 库可连接 | `credit_sys01..13` 均存在；`credit_sys01` 登录本库成功 |
| T-00-02 跨库被拒 | `credit_sys01` 连 `credit_sys02`：`FATAL: permission denied for database`，结论通过 |
| T-00-03 IK 插件 | `analysis-ik 3.9.0` 已安装；`cn_text` 分词输出 `['智能','信贷','文档','处理系统','处理','系统']` |
| T-00-03 索引模板 | `_index_template/credit_docs` 可查，settings 为 shards=1 / replicas=0 |
| T-00-04 桶与隔离 | 13 桶 `credit-sys01..13`；sys01 跨桶访问 403 |
| T-00-05 FerretDB CRUD | insert/read/update/delete 全部成功，count 一致 |
| T-00-06 etcd | 读写一致（同 V-00-07） |
| T-00-07 Grafana 数据源 | `Prometheus` 数据源 health=OK，`up` 指标可查 |
| T-00-08 MySQL 业务账号 | `ragflow@172.%` 可连接 `ragflow` 库 |

## 四、待确认清单

1. **Docker 运行环境变更（已获确认）**：OrbStack VM 异常（docker.sock EOF），改用 Docker Desktop；内存由 8GB 上调至 12GB；停止非本项目容器 `sungraph-pg` 释放 5432；退出 OrbStack 释放 3306/6379。
2. **镜像拉取通道**：`registry-1.docker.io` 本机不可达，OpenSearch 3.9.0 经 `docker.1panel.live`、`postgres-documentdb:17` 经 `ghcr.nju.edu.cn` 拉取；已校验 `postgres-documentdb` 的 index digest 与 ghcr 官方一致（`sha256:2386795e…`）。tag 未变，不涉及版本替换。
3. **FerretDB 2.7.0 架构补充（已获确认）**：官方要求 PostgreSQL + DocumentDB 扩展，原 compose 的普通 `postgres:18.7` 不满足。新增专用 `sys00-ferretdb-pg`（`ghcr.io/ferretdb/postgres-documentdb:17`，PG 17.6 + documentdb 0.107），业务 PG 18.7 不受影响。该服务为清单外新增中间件。
4. **FerretDB 认证**：开发期 `--no-auth`（单机简化，与 OpenSearch `plugins.security.disabled=true` 口径一致）；二期启用认证并建用户。
5. **PostgreSQL 18 数据卷路径**：官方镜像要求挂载 `/var/lib/postgresql`，已按官方建议调整，非版本/端口变更。
6. **OpenSearch 索引模板 API**：3.x legacy `_template` 不接受 `template` 包裹（落成空模板），改用等价的 `_index_template/credit_docs`，模板体与修正稿 5.2 完全一致。
7. **数据库命名**：修正稿“13 个库命名 credit_sys00…credit_sys13”与“13 个库”自相矛盾；按 13 个业务系统（SYS-01..SYS-13）建 `credit_sys01..credit_sys13`，SYS-01 使用 `credit_sys01`。
8. **IK 插件**：`https://get.infini.cloud/opensearch/analysis-ik/3.9.0` 存在且与 OpenSearch 3.9.0 精确匹配，**未降级**。
9. **SeaweedFS**：镜像固定 digest `sha256:a35a92243aefd043b974ec3ebcc0e9511efb49894339f6c1ece087b44eb52b3b`；S3 身份配置含 13 个桶级身份 + admin。
10. **Grafana 版本**：13.3.1（修正稿修正值），健康检查返回 version 13.3.1。
