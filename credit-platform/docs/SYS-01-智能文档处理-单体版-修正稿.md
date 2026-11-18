# SYS-01 智能文档处理系统 · 单体版修正稿

> 版本：V2.0-单机版（2026-11-16）
> 依据：`智能信贷标准系统集成设计_SYS-01_智能文档处理系统.docx` 修正而成
> 变更原则：单体部署、CPU 起步（GPU 可选）、补齐原稿缺失的自研产出物定义

## 一、相对原 docx / Trae 提示词的修正点

| # | 原稿问题 | 本稿修正 |
|---|---|---|
| 1 | docling `do_ocr=False` 只是关闭内置 OCR，**"对接外部 OCR"是自研胶水层，但原稿只有配置片段没有产出物定义** | 新增 **T-01-08 外部 OCR 适配器**任务卡，明确接口契约（见 5.2） |
| 2 | V-01-03 用默认 `DocumentConverter()`（内置 OCR 开启），与生产配置矛盾 | 改为验证本项目生产 converter 实例（带适配器） |
| 3 | V-01-05 需要"人工校对稿"但无准备步骤 | 新增 **T-01-06 前置：金标数据集准备**（20 页扫描件 + 人工校对稿 + 复杂表格样本） |
| 4 | FFmpeg LGPL 编译配置缺失 | 补 configure 参数（见 5.4）；开发期允许先用发行版二进制，生产前必须换 LGPL 构建 |
| 5 | `use_gpu: true` 与部署单元"GPU 可选"矛盾 | 统一为 **CPU 起步、`use_gpu` 配置开关**；P95 验收在 GPU 就绪后复测 |
| 6 | docling 2.150.0 | 修正为 **2.150.1**（PyPI 2026-11-16 核实） |
| 7 | 提示词丢失主文档补齐项（坐标契约、质量退回 40003、加密 PDF） | 契约字段表落到本稿 5.3，任务卡引用 |
| 8 | 投喂顺序表 SYS-01 前置 SYS-03（无技术依据） | 本稿前置仅 **SYS-00** |

## 二、组件版本表（已核实 2026-11-16）

| 组件 | 版本 | 许可 | 核实结果 |
|---|---|---|---|
| PaddleOCR | 3.7.0 | Apache-2.0 | ✅ PyPI 当前版（核实 2026-11-16） |
| docling | **2.150.1** | MIT | ⚠️ 原稿 2.150.0 → 修正为 PyPI 当前版 |
| opencv-python-headless | 5.0.0.93 | Apache-2.0 | ✅ PyPI 当前版 |
| FFmpeg | 7.1.5 | LGPL-2.1/GPL | ✅ 7.1 分支最新 patch（2026-06-20，endoflife.date） |

## 三、部署单元表（全部单体，单机）

| 单元 | 形态 | 端口 | 副本 | 说明 |
|---|---|---|---|---|
| OCR 服务（FastAPI 封装 PaddleOCR） | 容器（python:3.11-slim + pip paddleocr 3.7.0） | 8101 | 1 | CPU 起步；挂载 /models、/data/tmp |
| 文档解析服务（docling + 适配器） | 容器（同基础镜像 + docling 2.150.1） | 8102 | 1 | OCR 走 8101 适配器，不装第二套 OCR 模型 |
| OpenCV 预处理 | OCR 服务进程内 | — | — | 纠偏/去噪/质量五维 |
| FFmpeg | 优先嵌入 OCR/解析容器；开发期可用宿主机二进制 | — | — | 音频抽取与转码 |
| PostgreSQL（parse_task/text_block/evidence 落库） | 复用 SYS-00 PG，库 `credit_sys01` | 5432 | 1 | 表结构见原文档第 4.2 章 |

内存预算：OCR 服务 ~3-4G（模型加载）+ 解析服务 ~2G ≈ **6GB**。与 SYS-00 合计约 13GB，建议开发机 16GB 以上 / 建议 32GB。

## 四、实施步骤

- **T-01-01 构建 OCR 镜像**。输入：基础镜像、pip 源、模型目录。动作：装依赖、下载 PP-OCRv5 det/rec/cls 模型并校验哈希、非 root 用户。完成标志：镜像启动，`/healthz` 通过。
- **T-01-02 实现 OCR 接口**。动作：文件校验 → OpenCV 预处理（deskew/max_side=3000）→ 推理 → **坐标归一化输出统一契约（5.3）** → 质量不合格返回 40003 + 原因码。完成标志：返回统一契约。
- **T-01-03 金标数据集准备（新增，V-01-05 前置）**。动作：准备 20 页扫描件 + 人工校对稿 + 含跨页/合并单元格的复杂表格样本，入库标注来源。完成标志：金标目录就绪。
- **T-01-04 外部 OCR 适配器（新增，关键自研项）**。动作：按 5.2 实现 docling 自定义 OCR 插件，注册进 pipeline；扫描页文本由 8101 回填。完成标志：纯扫描 PDF 解析出含文本的 markdown/结构。
- **T-01-05 部署解析服务**。动作：docling pipeline 配置（5.1）+ 适配器注册；PDF/DOCX/HTML/XLSX 各一冒烟样本。完成标志：四类格式均可解析。
- **T-01-06 统一中间结构落库**。动作：block/table/image/page 四类节点写入 PG `credit_sys01`。完成标志：下游可查询、block_id 稳定可复现。
- **T-01-07 表格后处理**。动作：跨页合并、表头修正、单元格矩阵输出。完成标志：金标表格结构正确率 ≥90%。
- **T-01-08 质量抽检队列**。动作：置信度低于阈值入队列，提供复核接口。完成标志：抽检记录可追溯。
- **T-01-09 压测**。动作：50 页文档并发 5，CPU 模式先测基线，GPU 就绪后复测 P95 ≤60 秒。完成标志：留压测报告。

前置：T-01-01 → T-01-02 →（T-01-03 ∥ T-01-04）→ T-01-05 → T-01-06 → T-01-07 → T-01-08 → T-01-09。

## 五、配置与契约

### 5.1 OCR 服务配置（ocr_server/config.yaml）

```yaml
server: { host: 0.0.0.0, port: 8101, workers: 2 }
ocr:
  model: PP-OCRv5_server
  use_gpu: false          # 单机 CPU 起步；有 GPU 改 true
  det_limit_side_len: 2000
  det_db_box_thresh: 0.5
  drop_score: 0.5
  return_word_box: true
preprocess: { deskew: true, denoise: false, max_side: 3000 }
quality:
  min_score: 0.6          # 低于则返回 40003 退回
refuse_reasons: [BLUR, SKEW, TOO_DARK, LOW_DPI, GLARE]
```

### 5.2 docling 外部 OCR 适配器（T-01-04 契约，必须自研）

docling 关闭内置 OCR 后不会自动调用外部服务，适配器是**唯一让扫描件有文本的环节**：

- 实现方式：docling 自定义 OCR 引擎插件（实现 docling 的 `OcrEngine` 接口并通过插件工厂注册，如 `paddleocr_http`），pipeline 的 `pipeline_options.ocr_options` 指向该引擎；
- 引擎职责：输入页位图 → HTTP 调用本机 8101 `/ocr` → 把返回的 `blocks[]`（text、polygon、bbox、confidence）映射回 docling 内部 OCR 结果结构（文本段 + 坐标 + 置信度）；
- 禁止行为：适配器内不得再装第二套 OCR 模型（如 easyocr/tesseract），也不得在 docling 侧重新识别；
- 验收：纯扫描 PDF（无文本层）经解析服务产出含正文文本的 markdown 与结构化节点。

生产 converter 关键参数（沿袭原稿）：

```python
opts.do_ocr = True                 # 打开，但引擎指向自研 paddleocr_http 适配器
opts.table_structure_options.do_cell_matching = True
opts.images_scale = 2.0
```

### 5.3 统一坐标与证据契约（TextBlock）

| 字段 | 类型 | 说明 |
|---|---|---|
| block_id | string | `{file_sha256}-p{page}-{seq}`，稳定可复现，证据链主键 |
| page | int | 从 1 起 |
| text | string | 识别文本 |
| bbox | [x1,y1,x2,y2] | 统一左上原点，0-1 相对坐标 |
| polygon | 4 点坐标 | 旋转/透视文本框 |
| confidence | float | 0-1 |
| parser | string | `paddleocr-3.7.0` / `docling-2.150.1` |
| trace_id | string | 解析任务 trace，下游溯源用 |

错误码：格式不支持 40001、解析失败 40002、**质量不合格 40003（附 refuse_reasons）**、加密文档 40004（needs_manual=true，不伪造结果）。

### 5.4 FFmpeg LGPL 构建（生产前必须）

```bash
./configure --enable-lgpl --disable-gpl --enable-shared --disable-static \
  --enable-libmp3lame --enable-libvorbis --enable-libopus \
  --prefix=/opt/credit/sys-01/ffmpeg
```

开发期允许用宿主机包管理器二进制联调，**上生产前替换为上述 LGPL 构建**并在交付物注明构建参数。

## 六、验证清单

| 编号 | 命令/操作 | 期望 |
|---|---|---|
| V-01-01 | `curl -s localhost:8101/healthz` | {"status":"ok","model":"PP-OCRv5_server"} |
| V-01-02 | `curl -F file=@sample.jpg localhost:8101/ocr` | 返回含 block_id/polygon/bbox/confidence 的统一契约 |
| V-01-03 | 调解析服务（8102）解析**纯扫描 PDF** | 产出含正文文本的 markdown（证明适配器生效） |
| V-01-04 | 调解析服务解析 PDF/DOCX/HTML/XLSX 冒烟样本 | 四类格式均产出结构与表格 |
| V-01-05 | 金标 20 页扫描件比对 | 字符准确率 ≥98% |
| V-01-06 | `ffprobe` 转码输出 | codec/采样率符合预期 |
| V-01-07 | 质量不合格样本（模糊/过暗）送 OCR | 返回 40003 + 原因码 |
| V-01-08 | 加密 PDF 送解析 | 返回 40004 + needs_manual=true |

## 七、与原子智能体对接（scaff-credit-agents 侧）

不改原子服务代码，仅改 Real Provider 配置指向（Mock 不动，随时可切回）：

```yaml
# ocr-agent / doc-parse-agent / image-agent application.yml
credit:
  provider: real
  sys01:
    base-url: http://localhost:8101   # OCR/质量
    parse-base-url: http://localhost:8102
    mode: sync          # 单机阶段同步；批量任务二期启用 /v1/tasks
```

对接工作量集中在 Real Provider 的请求/响应映射（原文档契约 → 本稿 5.3 契约），doc-parse 的正则 KV 与伪造 layout 全部替换为消费 `/v1/parse` 真实输出。

## 八、禁止事项

沿袭原稿全部条款，另加两条：
- 适配器不得引入第二套 OCR 模型；
- 禁止为通过 V-01-05 而调低 drop_score/阈值——指标不达标如实报告。
