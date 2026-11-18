# SYS-01 智能文档处理系统 · 阶段二交付报告

> 实施日期：2026-11-16
> 依据：`docs/SYS-01-智能文档处理-单体版-修正稿.md`
> 形态：单机 Docker Compose（OCR 8101 + 解析 8102），复用 SYS-00 PostgreSQL `credit_sys01`

## 一、变更清单

| 文件 | 动作 | 说明 |
|---|---|---|
| `sys-01-docproc/docker-compose.yml` | 新建 | ocr(8101)、parse(8102)，parse 接入 `credit-sys-00_default` 网络；OCR 固定 `linux/amd64` |
| `sys-01-docproc/ocr_server/Dockerfile` | 新建 | Python 3.11 + PaddleOCR 3.7.0 + PP-OCRv5_server；构建期预热模型并生成 sha256 清单 |
| `sys-01-docproc/ocr_server/requirements.txt` | 新建 | paddlepaddle 3.2.0（arm64 无 3.3 wheel；PaddleOCR 未锁定 paddle 版本）、paddleocr 3.7.0、opencv-python-headless 5.0.0.93 |
| `sys-01-docproc/ocr_server/config.yaml` | 新建 | 修正稿 5.1 配置（workers=2、CPU、qmin=0.6） |
| `sys-01-docproc/ocr_server/app/*.py` | 新建 | FastAPI `/healthz` `/ocr` `/v1/ocr`；预处理、五维质量评估、统一契约（block_id/bbox 0-1/polygon/confidence/trace_id） |
| `sys-01-docproc/ocr_server/app/main.py`、`quality.py` | 修改（阶段三） | 新增 `POST /v1/quality` 五维质量明细，供 image-agent 质检链路使用；`assess()` 综合分与阈值未改 |
| `sys-01-docproc/parse_server/Dockerfile` | 新建 | 多阶段：FFmpeg 7.1.5 LGPL 构建 + docling 2.150.1 运行镜像 |
| `sys-01-docproc/parse_server/vendor/FFmpeg-n7.1.5.tar.gz` | 新建 | 内置 FFmpeg 源码包（ffmpeg.org 下载过慢，tag n7.1.5 与官方一致） |
| `sys-01-docproc/parse_server/app/ocr_plugin.py` | 新建 | **自研 docling 外部 OCR 插件**（entry point group `docling`，`ocr_engines()` 注册）；HTTP 调 8101 并按 block 回填 TextCell |
| `sys-01-docproc/parse_server/app/pipeline.py` | 新建 | PdfPipelineOptions(do_ocr=true, 外部插件, 表格结构)，block/table/image/page 抽取，跨页表合并 |
| `sys-01-docproc/parse_server/app/db.py` | 新建 | `credit_sys01` 建表与落库（parse_task/doc_page/doc_block/doc_table/doc_image/quality_review） |
| `sys-01-docproc/parse_server/app/main.py` | 新建 | `/v1/parse` `/parse` `/healthz`；40001/40002/40003/40004；质量复核接口 |
| `sys-01-docproc/scripts/gen_samples.py` | 新建 | 冒烟样本（jpg/纯扫描 pdf/docx/html/xlsx/加密 pdf/音频） |
| `sys-01-docproc/scripts/gen_golden.py` | 新建 | T-01-03 金标集生成器：渲染 20 类信贷单据 → 300dpi 扫描退化（旋转/噪声/光照/JPEG） |
| `sys-01-docproc/scripts/eval_golden.py` | 新建 | V-01-05 字符准确率评测（编辑距离；图片先转单页 PDF 再解析） |
| `sys-01-docproc/scripts/eval_tables.py` | 新建 | T-01-07 表格结构评测（跨页/合并表头/财务/税务 4 例） |
| `sys-01-docproc/scripts/load_test.py` | 新建 | T-01-09 并发压测 |
| `sys-01-docproc/golden/` | 新建 | 20 页合成扫描件 + 校对稿 + 表格参考（来源标注 `synthetic-self-generated`） |
| `sys-01-docproc/evidence/*.log` | 新建 | 验证原始输出（含 `V-01-05-rootcause.log` 归因） |

## 二、关键执行日志

```bash
# OCR（amd64，规避 arm64 Paddle 段错误）
docker compose build ocr          # 构建期下载 PP-OCRv5_server_det/rec + 生成 /models/model-sha256.txt
docker compose up -d ocr
curl -s localhost:8101/healthz     # {"status":"ok","model":"PP-OCRv5_server"}

# 解析（arm64 原生，FFmpeg LGPL 静态嵌入）
docker compose build parse
docker compose up -d parse
curl -F file=@samples/scanned.pdf localhost:8102/v1/parse

# T-01-03 金标集（用户无附件，授权自行生成）
python3 scripts/gen_golden.py        # 20 页 2480x3508 @300dpi + 校对稿 + 表格参考 + manifest.csv
# V-01-05 / T-01-07
python3 -u scripts/eval_golden.py    # weighted_char_accuracy=0.9746 -> FAIL(<0.98)
python3 -u scripts/eval_tables.py    # mean_table_score=0.9794 -> PASS(>=0.90)
```

## 三、验证结果表

| 编号 | 命令 | 预期 | 实际 | 结论 |
|---|---|---|---|---|
| V-01-01 | `curl localhost:8101/healthz` | `{"status":"ok","model":"PP-OCRv5_server"}` | 完全一致 | 通过 |
| V-01-02 | `curl -F file=@sample.jpg localhost:8101/ocr` | 统一契约 | 20 blocks；字段 `block_id/bbox(0-1)/polygon(4点0-1)/confidence/parser/trace_id` 齐全，示例 bbox `[0.0677,0.0701,0.4655,0.1082]` | 通过 |
| V-01-03 | 解析纯扫描 PDF | markdown 含正文（适配器生效） | 2 页 / 16 blocks / 2 tables / 575 字 markdown，正文来自 8101 OCR | 通过 |
| V-01-04 | 解析 PDF/DOCX/HTML/XLSX | 四类均有结构与表格 | PDF(16 blocks,2 表)；DOCX(3 blocks,1 表)；HTML(3 blocks,1 表)；XLSX(1 表) | 通过 |
| V-01-05 | 金标 20 页比对 | 字符准确率 ≥98% | **0.9746（FAIL）**；18 页 ≥0.97，低分 page-013 0.8737 / page-015 0.8475 / page-018 0.8732 | **未达标（如实报告）** |
| V-01-06 | `ffprobe` 转码输出 | codec/采样率符合预期 | FFmpeg 7.1.5；wav→mp3：`codec_name=mp3 sample_rate=44100 channels=2`；aac 同样可解 | 通过 |
| V-01-07 | 模糊/过暗样本送 OCR | 40003 + 原因码 | 模糊：`40003 ["BLUR","GLARE"]`；过暗：`40003 ["BLUR","TOO_DARK"]` | 通过 |
| V-01-08 | 加密 PDF 送解析 | 40004 + needs_manual=true | `{"error_code":40004,"needs_manual":true}` | 通过 |

补充（任务卡）：

| 任务 | 结果 |
|---|---|
| T-01-03 金标集 | 20 页扫描件 + 20 份校对稿 + 20 份表格参考（含跨页续表期望矩阵）+ `manifest.csv`（21 行），`source=synthetic-self-generated` 已入库标注；详见待确认第 10 条 |
| T-01-06 落库 | `parse_task/doc_page/doc_block/doc_table` 均有数据；同一文件重复解析 block_id 完全一致（16/16） |
| T-01-07 表格后处理 | `eval_tables.py` 4 例：跨页续表 7x5 正确（shape=1.0, text_sim=0.9798）、合并表头 4x4（1.0 / 0.8636）、财务表 8x4（1.0 / 1.0）、税务表 7x4（1.0 / 0.9921）；**mean_table_score=0.9794 ≥0.90 → 通过** |
| T-01-08 质量抽检 | 低置信块（0.556）入队；`GET /v1/quality/review`、`POST /v1/quality/review/{id}` 复核可用 |
| T-01-09 压测 | 5 并发 × 10 页（合计 50 页），0 错误；P50=596.2s，P95=983.9s（CPU + Rosetta 串行基线，远超 GPU 目标 60s，作为基线如实记录） |

## 四、待确认清单

1. **arm64 Paddle 段错误**：paddlepaddle 3.1.1/3.2.0 在 Apple Silicon 原生 arm64 下，OCR 输入 >1000px 必现 `ConvKernel/Im2Col` SIGSEGV（≤1000px 正常，PIR/mkldnn 开关无效）。处置：**OCR 容器固定 `linux/amd64` 经 Rosetta 运行**，模型仍为 PP-OCRv5_server，契约不变；性能低于原生 x86 服务器，生产 x86 环境不受影响。
2. **paddlepaddle 版本**：修正稿只锁 PaddleOCR 3.7.0；arm64 无 3.3.x wheel，选用 3.2.0（amd64 镜像内同为 3.2.0，保证两平台一致）。
3. **FFmpeg configure**：修正稿 `--enable-lgpl` 在 FFmpeg 7.1.5 中不存在（仅 `--enable-gpl`）。改为语义等价的 `--disable-gpl --disable-nonfree`，产物 `ffmpeg -version` 不含 GPL；源码取自 GitHub tag `n7.1.5`（官方站限速），已内置 `vendor/`。
4. **docling 插件机制**：docling 2.150.1 通过 entry point 组 `docling` 发现插件（模块暴露 `ocr_engines()`），非独立 `ocr_engines` 组；已按实际机制注册，未改动 docling 源码。
5. **docling-core 版本漂移**：`BoundingBox.width/height/area` 在部分版本为属性而非方法，插件已做兼容（callable 判断）。
6. **模型下载通道**：docling 布局/表格模型从 `hf-mirror.com` 下载（huggingface.co 返回 502）；PaddleOCR 模型构建期从 bcebos 下载并生成 sha256 清单 `/models/model-sha256.txt`。
7. **镜像构建依赖国内镜像**：pip → 清华 PyPI，apt → 清华 Debian，基础镜像 → 1panel/南京大学镜像；版本号未变。
8. **镜像体积**：parse 镜像 10.8GB（docling 标准依赖含 CUDA 运行库）；如需瘦身可改用 docling-slim 的 CPU 组合，属优化项。
9. **并发模型**：解析服务单 worker + 进程内转换锁，避免 docling 并发不安全；压测 P95 反映串行基线，GPU/多副本阶段再复测。
10. **金标集为合成数据（非真实业务扫描）**：用户确认无附件并授权自行生成。`scripts/gen_golden.py` 以 20 类信贷单据模板渲染 2480×3508 @300dpi，叠加旋转 0.25°、高斯噪声 σ=3、光照渐变、JPEG q=92 模拟扫描退化；校对稿由渲染源文本直接导出（`corrected_by=auto:render-source`）。**局限**：不含真实印章、手写、折痕、透印、双面串影、复杂版式漂移，真实扫描件准确率预计低于本结果；上线前应替换为真实脱敏扫描件复测。
11. **V-01-05 未达标（0.9746 < 0.98）已定位根因，未做任何阈值妥协**：
    - 证据见 `sys-01-docproc/evidence/V-01-05-rootcause.log`。同一 page-013/page-018 直接调用 8101 引擎（与生产同参数 det_limit=2000）**识别完全正确**（page-013 末行为 `赵敏/行政专员/8,000/6`，page-018 六行数据齐全）；经 docling 解析后同样内容变为 `海 / 000'8 / 9`、`68.8885 809'`。差异发生在 **docling 表格 cell matching → `export_to_markdown()`** 环节，不是 PaddleOCR 能力问题。
    - page-015 低分是合并单元格文本 `授信审批要素` 在 4 个单元格各重复一次（表示层重复）。
    - 交叉印证：T-01-07 表格结构 4/4 形状正确、0.9794 通过，说明结构抽取本身可用。
    - 未采纳的处置：① 提高 `det_limit_side_len` 至 2560/3000——实测 2000 已能正确识别，无收益，且该值属修正稿 5.1 指定；② 调低 `drop_score`/质量阈值/评测归一化规则——修正稿第 149 行明确禁止。
    - **需用户决策**：是否允许将 markdown 表格改为由自有 `cells` 矩阵渲染（可消除合并单元格重复与 cell matching 错乱），或接受当前 97.46% 并以 T-01-07 0.9794 作为表格质量口径。改动会影响全部下游 markdown 消费方，故未擅自实施。
