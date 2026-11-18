# SYS-00 共享基础服务池 · 单体版修正稿

> 版本：V2.0-单机版（2026-11-16）
> 依据：`智能信贷标准系统集成设计_SYS-00_共享基础服务池.docx` 修正而成
> 变更原则：全部服务单体部署、单机 Docker Compose 编排，面向单台开发/实施机

## 一、相对原 docx 的修正点

| # | 原文档问题 | 本稿修正 |
|---|---|---|
| 1 | MySQL 部署形态矛盾（部署表 1 主 1 备 vs 任务卡单实例） | 统一为**单实例**（用户决策：先单体） |
| 2 | etcd 列为组件但无部署任务卡、无验证项 | 新增 **T-00-07 部署 etcd**、**V-00-07 验证**（SYS-10 APISIX 依赖它） |
| 3 | T-00-06 SeaweedFS 前置 T-00-04 Valkey（假依赖） | 改为前置：无 |
| 4 | 验证命令全 localhost 但拓扑为主备/三节点 | 单机后 localhost 口径成立（V-00-08 补充容器状态检查） |
| 5 | Grafana 12.4.15 版本不存在 | 修正为 **13.3.1**（2026-11-10 发布，endoflife.date 核实） |
| 6 | PostgreSQL/MySQL/Valkey/OpenSearch/Prometheus/etcd 版本存疑 | **全部核实无误**（见版本表，核实于 2026-11-16） |
| 7 | OpenSearch 3 节点 + IK 插件版本未锁定 | 单节点部署；IK 插件需选与 3.9.0 精确匹配版本，见 4.2 注意事项 |
| 8 | pg_partman 归档、流复制、备份目录挂载等生产项 | 单机开发阶段简化：`archive_mode=off`，分区与备份列为二期项 |

## 二、组件版本表（已核实 2026-11-16）

| 组件 | 版本 | 许可 | 核实结果 | 核实来源 |
|---|---|---|---|---|
| PostgreSQL | 18.7 | PostgreSQL License | ✅ 2026-11-09 发布 | endoflife.date/api/postgresql |
| MySQL | 8.4.13 | GPL-2.0 | ✅ 2026-09-30 发布（8.4 LTS 分支） | endoflife.date/api/mysql |
| FerretDB | 2.7.0 | Apache-2.0 | ✅ v2.7.0（2025-11-10） | GitHub Releases |
| Valkey | 9.0.7 | BSD-3-Clause | ✅ 2026-10-26（另有 9.1.3，本稿保持 9.0.7） | endoflife.date/api/valkey |
| OpenSearch | 3.9.0 | Apache-2.0 | ✅ 2026-09-29 发布 | endoflife.date/api/opensearch |
| SeaweedFS | 无版本化标签 | Apache-2.0 | ✅ 维持原结论，实施时固定镜像 digest | Docker Hub |
| etcd | v3.7.3 | Apache-2.0 | ✅ 2026-10-22 | endoflife.date/api/etcd |
| Prometheus | v3.16.0 | Apache-2.0 | ✅ 2026-11-05 | endoflife.date/api/prometheus |
| Grafana | **13.3.1** | AGPL-3.0 | ⚠️ 原 12.4.15 未核实到，改为当前稳定版 13.3.1（2026-11-10） | endoflife.date/api/grafana |

版本核实命令（在实施机上重跑一遍再开工）：

```bash
curl -s https://endoflife.date/api/postgresql.json | python3 -m json.tool | head -30
curl -s https://pypi.org/pypi/docling/json | python3 -c "import json,sys;print(json.load(sys.stdin)['info']['version'])"
```

## 三、部署单元表（全部单体）

| 单元 | 镜像 | 容器端口 | 数据卷 | 说明 |
|---|---|---|---|---|
| PostgreSQL | library/postgres:18.7 | 5432 | vol-sys00-pg | 13 个业务系统分库 |
| MySQL | library/mysql:8.4.13 | 3306 | vol-sys00-mysql | 仅 RAGFlow 元数据 |
| FerretDB | ferretdb/ferretdb:2.7.0 | 27017 | 无（落 PG） | 后端 PostgreSQL |
| Valkey 缓存 | valkey/valkey:9.0.7 | 6379 | 无 | 不持久化，LRU 逐出 |
| Valkey 队列 | valkey/valkey:9.0.7 | 6380 | vol-sys00-valkey-q | AOF everysec |
| OpenSearch | opensearchproject/opensearch:3.9.0 | 9200/9300 | vol-sys00-os | 单节点，IK 插件 |
| SeaweedFS | chrislusf/seaweedfs（固定 digest） | 9333/8333 | vol-sys00-seaweed | server 模式一体（master+volume+filer+S3） |
| etcd | quay.io/coreos/etcd:v3.7.3 | 2379/2380 | vol-sys00-etcd | SYS-10 APISIX 配置存储 |
| Prometheus | prom/prometheus:v3.16.0 | 9090 | vol-sys00-prom | 本地保留 15 天 |
| Grafana | grafana/grafana:13.3.1 | 3000 | vol-sys00-grafana | 仅内网/本机访问 |

内存预算（单体）：PG ~1G + MySQL ~0.8G + OpenSearch ~2G + Valkey×2 ~0.2G + SeaweedFS ~0.5G + etcd ~0.2G + Prometheus ~1G + Grafana ~0.5G ≈ **6.5GB**。16GB 开发机可承受（SYS-01 另计约 4-6GB）。

## 四、实施步骤（Compose 化）

- **T-00-01 启动基础服务栈**。输入：`sys-00-infra/docker-compose.yml`、`.env`。动作：`docker compose up -d`，等待全部 healthy。完成标志：`docker compose ps` 全部 Up/healthy。
- **T-00-02 建 PostgreSQL 库与账号**。动作：逐系统建库建账号，账号仅授权本库；执行建库 SQL 模板。完成标志：13 个库可连接，跨库访问被拒。
- **T-00-03 安装 OpenSearch IK 插件并写模板**。动作：`opensearch-plugin install` 对应版本 analysis-ik → 重启 → 写索引模板（单节点：shards 1 / replicas 0）。完成标志：模板可查、中文分词生效。
- **T-00-04 初始化 SeaweedFS 桶与配额**。动作：s3cmd/mc 建每系统一桶、独立 AccessKey。完成标志：越权访问 403。
- **T-00-05 初始化 FerretDB**。动作：建库、CRUD 验证。完成标志：写读一致。
- **T-00-06 初始化 etcd**。动作：写入/读取冒烟键值。完成标志：etcdctl 读写一致。
- **T-00-07 部署监控配置**。动作：prometheus.yml 挂载生效、Grafana 数据源指向 Prometheus。完成标志：核心指标可见。
- **T-00-08 MySQL 业务账号**。动作：初始化 root 口令、建 RAGFlow 库与账号、限本机网段。完成标志：RAGFlow 连接规范账号可用。

前置依赖：T-00-01 → 全部其余；其余之间无强依赖。

## 五、配置落盘

配置与编排统一放 `credit-platform/sys-00-infra/`（见同目录 `docker-compose.yml`、`prometheus/prometheus.yml`、`.env.example`），密钥一律走 `.env` 注入，不入库不入 git。

### 5.1 PostgreSQL（单机简化版，覆盖 compose 内 command）

```yaml
# 由 compose environment/command 注入，或挂载 /etc/credit/sys-00/postgresql.conf
listen_addresses = '*'
port = 5432
max_connections = 300
shared_buffers = 1GB
effective_cache_size = 4GB
wal_level = replica        # 二期上备库时改 replica；单机开发可 保持默认
archive_mode = off         # 单机开发关闭；二期改 on 并接独立备份卷
log_min_duration_statement = 1000
log_checkpoints = on
```

### 5.2 OpenSearch 索引模板（单节点版）

```json
PUT _template/credit_docs
{
  "index_patterns": ["credit_*"],
  "template": {
    "settings": {
      "number_of_shards": 1,
      "number_of_replicas": 0,
      "analysis": {
        "analyzer": {
          "cn_text": { "type": "custom", "tokenizer": "ik_max_word", "filter": ["lowercase"] }
        }
      }
    },
    "mappings": {
      "properties": {
        "title":   { "type": "text", "analyzer": "cn_text" },
        "content": { "type": "text", "analyzer": "cn_text" },
        "tenant":  { "type": "keyword" },
        "scene":   { "type": "keyword" }
      }
    }
  }
}
```

### 5.3 Valkey 双实例差异项（与原文档一致）

- 缓存实例：`maxmemory 2gb`（单机下调）、`allkeys-lru`、`save ""`、`appendonly no`
- 队列实例：`appendonly yes`、`appendfsync everysec`、`noeviction`、`save ""`

## 六、初始化注意事项

1. **IK 插件匹配**：INFINI analysis-ik 按 OpenSearch 版本发 tag，必须装与 3.9.0 精确一致的插件版本；若 3.9.0 无对应插件，允许将 OpenSearch 降为最近一个有 IK 插件的版本，并在待确认清单记录。
2. **OpenSearch 安全插件**：开发期 `plugins.security.disabled=true`（compose 已设），验证命令走 http；二期生产必须启用 TLS + 初始口令。
3. **建库账号 SQL 模板**：13 个库命名 `credit_sys00 ... credit_sys13`（按总表对齐），账号 `REVOKE ALL ON DATABASE ... FROM PUBLIC`。
4. **分区与归档（pg_partman）**：单机阶段不启用，列入二期清单。

## 七、验证清单（全部通过才算完成）

| 编号 | 命令 | 期望 |
|---|---|---|
| V-00-01 | `docker compose ps`（sys-00-infra 目录） | 全部 Up / healthy |
| V-00-02 | `pg_isready -h 127.0.0.1 -p 5432` | accepting connections |
| V-00-03 | `mysql -h127.0.0.1 -P3306 -uroot -p -e "select 1"` | 返回 1 |
| V-00-04 | `valkey-cli -p 6379 ping` | PONG |
| V-00-05 | `valkey-cli -p 6380 info persistence \| grep aof_enabled` | aof_enabled:1 |
| V-00-06 | `curl -s localhost:9200/_cluster/health` | "status":"green"，number_of_nodes:1 |
| V-00-07 | `etcdctl --endpoints=http://127.0.0.1:2379 put smoke ok && etcdctl get smoke` | "ok" |
| V-00-08 | `curl -s localhost:9333/cluster/healthz`（SeaweedFS）与 S3 冒烟：mc ls | 均正常响应 |
| V-00-09 | `curl -s localhost:9090/-/healthy` | Prometheus is Healthy |
| V-00-10 | `curl -s localhost:3000/api/health` | 含 "database":"ok" |

交付物：变更文件清单（绝对路径）、执行日志、验证结果表（编号/结果/原始输出）、待确认清单（无则写"无"）。

## 八、禁止事项（沿袭原文档）

- 不得改版本号、端口、接口路径与配置键名；不得引入清单外组件；
- 不得跳过验证，不得把未执行的命令写成通过；
- 文档未覆盖的情况停止执行，输出待确认清单，不自行决定。
