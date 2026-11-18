# AGENTS.md

智能信贷系统的**外围系统**实施工程。本仓库只做两件事：提供共享基础服务（SYS-00）与智能文档处理能力（SYS-01），并把结果接入既有的原子智能体工程（scaff-credit-agents）。**不包含信贷业务主体代码。**

## 1. 仓库与地址

| 仓库 | 本地路径 | 远程 | 说明 |
|---|---|---|---|
| credit-platform（本工程） | `credit-platform/` | 暂无远程、**未纳入 Git** | 基础设施与文档 |
| scaff-credit-agents（原子智能体） | `scaff-credit-agents/` | `https://github.com/pandq-certer/scaff-credit-agents`（main） | Java 多模块，已纳入 Git |

两个目录平级，互不混入；改原子智能体只允许动 Real Provider 适配器与 `application.yml`。

## 2. 技术栈

| 层 | 组件 | 版本 |
|---|---|---|
| 编排 | Docker Compose（单机单体，无主备） | Docker 29.x / 12GB / 10C |
| 关系库 | PostgreSQL | 18.7 |
| 关系库（RAGFlow） | MySQL | 8.4.13 |
| 文档库 | FerretDB + `postgres-documentdb` | 2.7.0 + PG17 |
| 缓存/队列 | Valkey ×2（cache 无持久化 / queue AOF） | 9.0.7 |
| 搜索 | OpenSearch + analysis-ik | 3.9.0 + 3.9.0 |
| 对象存储 | SeaweedFS（S3 桶级身份） | 3.96（digest 固定） |
| 配置中心 | etcd | v3.7.3 |
| 监控 | Prometheus / Grafana | v3.16.0 / 13.3.1 |
| OCR 服务 | Python 3.11 + FastAPI + PaddleOCR + PaddlePaddle | 3.7.0 / 3.2.0（PP-OCRv5_server） |
| 解析服务 | docling（自研 OcrEngine 插件）+ OpenCV + FFmpeg | 2.150.1 / 7.1.5（LGPL 参数） |
| 原子智能体 | Java 21 + Spring Boot + Maven 多模块 + Nacos | 3.4.3 |

## 3. 目录结构

```
credit-platform/                     # 工作区根（非 git）
├── AGENTS.md                        # 本文件
├── credit-platform/
│   ├── docs/                        # 修正稿 + 交付报告 + 任务进度表
│   ├── sys-00-infra/
│   │   ├── docker-compose.yml       # 11 个容器
│   │   ├── .env                     # 全部密钥（不入库）
│   │   ├── scripts/                 # 建库/建桶/装 IK/生成 S3 配置
│   │   ├── opensearch/              # 索引模板 credit_docs
│   │   ├── prometheus/  grafana/    # 监控配置与 provisioning
│   │   ├── secrets/                 # SeaweedFS S3 身份（生成物）
│   │   └── evidence/                # V-00 原始输出
│   └── sys-01-docproc/
│       ├── docker-compose.yml       # ocr(8101) + parse(8102)
│       ├── ocr_server/              # FastAPI；app/{engine,quality,preprocess,main}.py
│       ├── parse_server/            # docling；app/{pipeline,ocr_plugin,db,main}.py
│       ├── scripts/                 # 采样、压测、金标生成与评测
│       ├── golden/                  # 20 页合成金标集 + manifest
│       ├── samples/  data/          # 样例与临时目录
│       └── evidence/                # V-01 / T-01 / P3 原始输出
└── scaff-credit-agents/             # git 仓库，71 个模块
    ├── ocr-agent/  doc-parse-agent/  image-agent/   # 三个已对接 SYS-01
    ├── scene-bff/                   # 场景编排层 BFF
    ├── bai-common/                  # 公共异常/契约
    └── <其余业务智能体模块>
```

## 4. 端口

| 端口 | 服务 | 端口 | 服务 |
|---|---|---|---|
| 8101 | OCR（SYS-01） | 8102 | 解析（SYS-01） |
| 5432 | PostgreSQL | 3306 | MySQL |
| 27017 | FerretDB | 6379 / 6380 | Valkey cache / queue |
| 9200 / 9300 | OpenSearch | 9333 / 8333 | SeaweedFS master / S3 |
| 2379 / 2380 | etcd | 9090 | Prometheus |
| 3000 | Grafana | 18101/18143/18155 | 本地冒烟临时端口（勿占用） |

## 5. 常用命令

```bash
# SYS-00
cd credit-platform/sys-00-infra && docker compose up -d && docker compose ps

# SYS-01
cd credit-platform/sys-01-docproc && docker compose up -d --build
curl -s localhost:8101/healthz
curl -s -F file=@samples/sample.jpg localhost:8101/v1/ocr
curl -s -F file=@samples/sample.jpg localhost:8101/v1/quality
curl -s -F file=@samples/scanned.pdf localhost:8102/v1/parse

# 金标 / 表格评测
python3 scripts/eval_golden.py
python3 scripts/eval_tables.py

# 原子智能体
cd scaff-credit-agents
mvn -pl ocr-agent,doc-parse-agent,image-agent -am test
mvn -pl ocr-agent,doc-parse-agent,image-agent -am -DskipTests package
```

## 6. 硬性约定

1. **版本不擅自升级**；偏离修正稿（版本/架构/端口/契约）必须先获确认，并写入交付报告「待确认清单」。
2. **密钥只放 `.env`**，禁止写进代码、yml 默认值、Dockerfile、提交历史。
3. **不调低阈值凑指标**：`drop_score`、质量阈值、评测归一化规则均不可为过验收而改。
4. **失败项不得静默跳过**；每张任务卡必须产出：变更清单、执行日志、逐条验证表、待确认清单。
5. **不伪造数据**：抽不到的字段置低置信并标注，不用 0 或样本值填充。
6. 原子智能体侧只改 Real Provider 适配器 + `application.yml`，Mock 必须保留且可切回（`BAI_*_PROVIDER=mock`）。

## 7. 已知坑

| 现象 | 原因 | 处置 |
|---|---|---|
| OCR 容器段错误 SIGSEGV | PaddlePaddle arm64 在 >1000px 输入崩溃 | OCR 容器固定 `platform: linux/amd64`（Rosetta） |
| 调用 8101 返回 422 | Java HttpClient 默认发 h2c 升级，uvicorn 不支持 | 显式 `HttpClient.Version.HTTP_1_1` |
| OCR 被误报"服务不可达" | 默认 30s 超时短于 Rosetta 单页 20s+ | OCR 类超时设 180s，并单独捕获超时异常 |
| PG18 报 "unused mount/volume" | 官方镜像数据目录变更 | volume 挂 `/var/lib/postgresql` |
| FerretDB 报 `documentdb_api` 不存在 | 需要 DocumentDB 扩展 | 专用 `postgres-documentdb:17` 实例 |
| OpenSearch 模板落成空 | 3.x legacy `_template` 不接受 `template` 包裹 | 用 `_index_template/credit_docs` |
| docling 找不到 `paddleocr_http` | entry point 组是 `docling`，不是 `ocr_engines` | 模块暴露 `ocr_engines()` 并注册到 `docling` 组 |
| `'float' object is not callable` | docling-core 的 `bbox.width/height/area` 有的是属性 | callable 判断兼容 |
| 8102 拒收 jpg/png（40001） | 解析服务只支持 PDF/DOCX/HTML/XLSX | 图像走 8101 OCR；评测前先转单页 PDF |
| FFmpeg 7.1.5 无 `--enable-lgpl` | 该版本只有 `--enable-gpl` | 用 `--disable-gpl --disable-nonfree` |
| HuggingFace 502 | 直连不可用 | `HF_ENDPOINT=https://hf-mirror.com` |

## 8. 文档与进度

- 实施依据：[实施交接说明](credit-platform/docs/实施交接说明.md) → [SYS-00 修正稿](credit-platform/docs/SYS-00-共享基础服务池-单体版-修正稿.md) → [SYS-01 修正稿](credit-platform/docs/SYS-01-智能文档处理-单体版-修正稿.md)
- 交付记录：三份交付报告（阶段一/二/三）
- **进度看板**：[项目任务进度表](credit-platform/docs/项目任务进度表.md)（开工前必读，含待办与阻塞项）

当前状态：阶段一、二、三均已完成；阻塞项为 V-01-05 字符准确率 0.9746 < 0.98 的处置决策，以及金标集为合成数据需替换为真实扫描件。
