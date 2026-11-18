"""生成 T-01-03 金标数据集（合成扫描件 + 渲染源底稿）。

说明：用户无法提供真实业务扫描件，本脚本生成 20 页合成的信贷业务单据，
transcripts 为渲染时的精确源文本，作为 V-01-05 的字符准确率基准。
数据集标注为 synthetic，不等同于真实业务扫描验收。
"""
import csv
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOLDEN = os.path.join(ROOT, "golden")
SCANS = os.path.join(GOLDEN, "scans")
TRANS = os.path.join(GOLDEN, "transcripts")
TABLES = os.path.join(GOLDEN, "tables")

W, H = 2480, 3508  # A4 300dpi
M = 170
FONT_BOLD = "/System/Library/Fonts/Supplemental/Songti.ttc"
BODY_SIZE, TABLE_SIZE, TITLE_SIZE = 52, 42, 78


def font(size):
    return ImageFont.truetype(FONT_BOLD, size, index=1)  # 宋体加粗，接近公文打印


PAGES = [
    {
        "title": "个人经营性贷款申请表",
        "lines": [
            "申请人：张伟",
            "身份证号：310101198801011234",
            "联系电话：13800138000",
            "经营主体：上海示例商贸有限公司",
            "统一社会信用代码：91310101MA1FL8XK2P",
            "申请金额：人民币500,000元",
            "申请期限：36个月",
            "还款方式：等额本息",
        ],
        "table": [
            ["项目", "内容", "备注"],
            ["年营业收入", "2,800,000", "近12个月"],
            ["净利润", "360,000", "经审计"],
            ["现有负债", "900,000", "含本次申请"],
        ],
    },
    {
        "title": "申请人资产负债情况表",
        "lines": ["截至2026年10月31日（单位：元）"],
        "table": [
            ["科目", "年初数", "期末数", "变动率"],
            ["货币资金", "320,000", "410,000", "28.1%"],
            ["应收账款", "680,000", "750,000", "10.3%"],
            ["存货", "450,000", "520,000", "15.6%"],
            ["固定资产", "1,200,000", "1,150,000", "-4.2%"],
            ["短期借款", "600,000", "650,000", "8.3%"],
            ["应付账款", "380,000", "420,000", "10.5%"],
            ["所有者权益", "1,670,000", "1,760,000", "5.4%"],
        ],
    },
    {
        "title": "近12个月银行流水汇总",
        "lines": ["账户名称：上海示例商贸有限公司", "账号：3100 1234 5678 9012"],
        "table": [
            ["月份", "收入笔数", "收入金额", "支出金额"],
            ["2025-11", "42", "186,000", "152,000"],
            ["2025-12", "51", "221,000", "198,000"],
            ["2026-01", "38", "165,000", "143,000"],
            ["2026-02", "29", "132,000", "118,000"],
            ["2026-03", "47", "205,000", "176,000"],
            ["2026-04", "53", "238,000", "201,000"],
            ["2026-05", "49", "219,000", "187,000"],
            ["2026-06", "45", "198,000", "169,000"],
            ["2026-07", "58", "262,000", "224,000"],
            ["2026-08", "55", "247,000", "210,000"],
            ["2026-09", "61", "281,000", "236,000"],
            ["2026-10", "57", "259,000", "218,000"],
        ],
    },
    {
        "title": "购销合同（节选）",
        "lines": [
            "甲方：上海示例商贸有限公司",
            "乙方：苏州示例供应链有限公司",
            "合同编号：HT-2026-0918",
            "合同金额：人民币壹佰贰拾万元整",
            "付款方式：货到验收后30日内电汇",
            "履约期限：2026年10月1日至2027年9月30日",
            "争议解决：提交上海仲裁委员会仲裁",
        ],
        "table": [
            ["品名", "数量", "单价", "金额"],
            ["钢材", "120吨", "6,800", "816,000"],
            ["铝材", "45吨", "8,520", "383,400"],
            ["合计", "—", "—", "1,199,400"],
        ],
    },
    {
        "title": "企业营业执照信息",
        "lines": [
            "名称：上海示例商贸有限公司",
            "类型：有限责任公司（自然人投资或控股）",
            "法定代表人：张伟",
            "注册资本：人民币200万元整",
            "成立日期：2018年3月12日",
            "营业期限：2018年3月12日至2038年3月11日",
            "住所：上海市黄浦区示例路88号",
            "经营范围：金属材料、建筑材料、五金交电销售",
        ],
        "table": [
            ["登记事项", "登记内容"],
            ["统一社会信用代码", "91310101MA1FL8XK2P"],
            ["登记机关", "上海市黄浦区市场监督管理局"],
        ],
    },
    {
        "title": "企业近三年财务报表摘要",
        "lines": ["单位：元"],
        "table": [
            ["项目", "2023年", "2024年", "2025年"],
            ["营业收入", "2,100,000", "2,400,000", "2,800,000"],
            ["营业成本", "1,680,000", "1,910,000", "2,210,000"],
            ["利润总额", "260,000", "300,000", "360,000"],
            ["净利润", "195,000", "225,000", "270,000"],
            ["资产总额", "3,200,000", "3,500,000", "3,900,000"],
            ["负债总额", "1,600,000", "1,740,000", "1,900,000"],
            ["资产负债率", "50.0%", "49.7%", "48.7%"],
        ],
    },
    {
        "title": "纳税申报表摘要",
        "lines": ["纳税人识别号：91310101MA1FL8XK2P", "税款所属期：2025年度"],
        "table": [
            ["税种", "计税依据", "税率", "应纳税额"],
            ["增值税", "2,680,000", "13%", "348,400"],
            ["企业所得税", "360,000", "25%", "90,000"],
            ["城市维护建设税", "348,400", "7%", "24,388"],
            ["教育费附加", "348,400", "3%", "10,452"],
            ["印花税", "1,199,400", "0.03%", "360"],
            ["合计", "—", "—", "473,600"],
        ],
    },
    {
        "title": "征信报告摘要",
        "lines": ["报告编号：ZX-2026-1108", "查询日期：2026年11月8日"],
        "table": [
            ["授信机构", "授信额度", "已用额度", "还款状态"],
            ["示例银行", "800,000", "650,000", "正常"],
            ["示例农商行", "300,000", "120,000", "正常"],
            ["示例小额贷款公司", "100,000", "0", "已结清"],
            ["合计", "1,200,000", "770,000", "—"],
        ],
    },
    {
        "title": "抵押物清单",
        "lines": ["所有权人：张伟", "抵押物所在地：上海市浦东新区"],
        "table": [
            ["序号", "抵押物名称", "权证号", "评估价值", "抵押率"],
            ["1", "住宅", "沪(2020)浦字0123456", "6,500,000", "50%"],
            ["2", "车位", "沪(2020)浦字0123457", "350,000", "50%"],
            ["合计", "—", "—", "6,850,000", "—"],
        ],
    },
    {
        "title": "抵押物明细（续一）",
        "lines": ["接上页，抵押物明细如下"],
        "table": [
            ["序号", "抵押物名称", "权证号", "评估价值", "抵押率"],
            ["3", "商铺", "沪(2019)浦字0098765", "4,200,000", "45%"],
            ["4", "厂房", "沪(2018)闵字0065432", "8,800,000", "40%"],
            ["5", "土地使用权", "沪(2018)闵字0065433", "5,600,000", "35%"],
        ],
    },
    {
        "title": "抵押物明细（续二）",
        "lines": ["接上页"],
        "table": [
            ["序号", "抵押物名称", "权证号", "评估价值", "抵押率"],
            ["6", "设备", "沪备2021-0321", "1,200,000", "30%"],
            ["7", "车辆", "沪A12345", "280,000", "30%"],
            ["合计", "—", "—", "21,028,000", "—"],
        ],
    },
    {
        "title": "保证人信息",
        "lines": ["保证人：李娜", "与申请人关系：配偶"],
        "table": [
            ["项目", "内容"],
            ["身份证号", "310101199002021234"],
            ["工作单位", "上海示例咨询有限公司"],
            ["年收入", "240,000"],
            ["名下房产", "1套"],
            ["对外担保", "0"],
            ["征信状态", "正常"],
        ],
    },
    {
        "title": "代发工资流水",
        "lines": ["单位：上海示例商贸有限公司", "期间：2026年5月至10月"],
        "table": [
            ["姓名", "岗位", "月均实发", "发放月数"],
            ["张伟", "总经理", "18,000", "6"],
            ["王强", "销售经理", "12,000", "6"],
            ["李娜", "财务主管", "15,000", "6"],
            ["赵敏", "行政专员", "8,000", "6"],
        ],
    },
    {
        "title": "应收账款清单",
        "lines": ["截至2026年10月31日", "单位：元"],
        "table": [
            ["客户名称", "合同金额", "已收金额", "账龄"],
            ["示例建设集团", "860,000", "600,000", "90天"],
            ["示例装饰工程", "420,000", "300,000", "60天"],
            ["示例机电设备", "380,000", "380,000", "30天"],
            ["示例物流有限公司", "260,000", "180,000", "120天"],
            ["合计", "1,920,000", "1,460,000", "—"],
        ],
    },
    {
        "title": "授信审批意见",
        "lines": [
            "审批结论：同意授信",
            "授信品种：流动资金贷款",
            "授信金额：人民币500,000元",
            "授信期限：36个月",
            "担保方式：房产抵押加配偶保证",
        ],
        "table": [
            ["授信审批要素", "", "", ""],
            ["要素", "内容", "审批人", "日期"],
            ["利率", "4.35%", "王主任", "2026-11-10"],
            ["额度", "500,000", "王主任", "2026-11-10"],
        ],
        "merged_header": True,
    },
    {
        "title": "风险提示与免责声明",
        "lines": [
            "本报告基于申请人提供的资料及公开信息整理，仅供授信审批参考。",
            "申请人应保证所提供资料真实、完整、有效，如有虚假应承担相应法律责任。",
            "本报告不构成对申请人未来经营状况和还款能力的保证。",
            "授信审批应结合贷前调查、实地走访及征信查询结果综合判断。",
            "未经授权，不得将本报告用于授信审批以外的其他用途。",
        ],
        "table": None,
    },
    {
        "title": "贷后检查记录",
        "lines": ["检查日期：2026年10月20日", "检查人：陈经理"],
        "table": [
            ["检查项目", "检查结果", "备注"],
            ["经营场所", "正常", "现场走访"],
            ["库存情况", "正常", "账实相符"],
            ["还款记录", "正常", "无逾期"],
            ["对外担保", "无", "征信复核"],
            ["重大事项", "无", "无诉讼"],
        ],
    },
    {
        "title": "还款计划表",
        "lines": ["贷款金额500,000元", "年利率4.35%", "期限36个月"],
        "table": [
            ["期次", "应还本金", "应还利息", "月供"],
            ["1", "13,888.89", "1,812.50", "15,701.39"],
            ["2", "13,888.89", "1,762.15", "15,651.04"],
            ["3", "13,888.89", "1,711.79", "15,600.68"],
            ["4", "13,888.89", "1,661.44", "15,550.33"],
            ["5", "13,888.89", "1,611.08", "15,499.97"],
            ["6", "13,888.89", "1,560.73", "15,449.62"],
        ],
    },
    {
        "title": "费用明细",
        "lines": ["单位：元"],
        "table": [
            ["费用项目", "金额", "收取方式"],
            ["抵押评估费", "3,500", "一次性"],
            ["抵押登记费", "550", "一次性"],
            ["公证费", "800", "一次性"],
            ["账户管理费", "0", "免收"],
            ["提前还款违约金", "0", "免收"],
            ["合计", "4,850", "—"],
        ],
    },
    {
        "title": "附件清单与签署页",
        "lines": [
            "附件一：申请人身份证复印件",
            "附件二：营业执照复印件",
            "附件三：近12个月银行流水",
            "附件四：购销合同原件",
            "附件五：抵押物权证复印件",
            "申请人声明：以上资料真实有效。",
        ],
        "table": [
            ["签署人", "身份", "签字日期"],
            ["张伟", "申请人", "2026-11-10"],
            ["李娜", "保证人", "2026-11-10"],
        ],
    },
]


def wrap(text, fnt, max_width):
    lines, cur = [], ""
    for ch in text:
        if fnt.getlength(cur + ch) <= max_width:
            cur += ch
        else:
            lines.append(cur)
            cur = ch
    if cur:
        lines.append(cur)
    return lines


def draw_table(draw, y, rows, merged_header=False):
    ncols = max(len(r) for r in rows)
    avail = W - 2 * M
    weights = []
    for c in range(ncols):
        longest = max(len(str(r[c])) if c < len(r) else 0 for r in rows)
        weights.append(max(longest, 6))
    total = sum(weights)
    widths = [int(avail * w / total) for w in weights]
    widths[-1] += avail - sum(widths)

    fnt = font(TABLE_SIZE)
    row_h = 86
    table_top = y
    for ri, row in enumerate(rows):
        # 合并表头：整行合并
        if merged_header and ri == 0:
            draw.rectangle([M, y, W - M, y + row_h], outline="black", width=3)
            txt = str(row[0])
            tw = draw.textlength(txt, font=fnt)
            draw.text(((W - 2 * M - tw) / 2 + M, y + 18), txt, fill="black", font=fnt)
            y += row_h
            continue
        x = M
        for ci in range(ncols):
            w = widths[ci]
            draw.rectangle([x, y, x + w, y + row_h], outline="black", width=2)
            txt = str(row[ci]) if ci < len(row) else ""
            tw = draw.textlength(txt, font=fnt)
            if tw > w - 20:
                txt = txt[: max(1, int(len(txt) * (w - 20) / tw) - 1)]
                tw = draw.textlength(txt, font=fnt)
            draw.text((x + (w - tw) / 2, y + 18), txt, fill="black", font=fnt)
            x += w
        y += row_h
    return y - table_top


def render_page(page, path):
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    y = M
    d.text((M, y), page["title"], fill="black", font=font(TITLE_SIZE))
    y += TITLE_SIZE + 60
    body = font(BODY_SIZE)
    for line in page["lines"]:
        for seg in wrap(line, body, W - 2 * M):
            d.text((M, y), seg, fill="black", font=body)
            y += BODY_SIZE + 26
    y += 40
    if page.get("table"):
        draw_table(d, y, page["table"], page.get("merged_header", False))

    # 轻度扫描退化：微旋转 + 噪声 + 光照不均
    img = img.rotate(0.25, resample=Image.BICUBIC, fillcolor="white")
    arr = np.asarray(img).astype(np.int16)
    rng = np.random.default_rng(20261117)
    arr += rng.normal(0, 3.0, arr.shape).astype(np.int16)
    h, w = arr.shape[:2]
    yy = np.linspace(-1, 1, h)[:, None]
    xx = np.linspace(-1, 1, w)[None, :]
    shade = 1.0 - 0.03 * (xx ** 2 + yy ** 2)
    arr = np.clip(arr * shade[..., None], 0, 255).astype(np.uint8)
    Image.fromarray(arr).save(path, quality=92, dpi=(300, 300))


def main():
    for d in (SCANS, TRANS, TABLES):
        os.makedirs(d, exist_ok=True)

    manifest = []
    for i, page in enumerate(PAGES, start=1):
        name = f"page-{i:03d}.jpg"
        render_page(page, os.path.join(SCANS, name))

        text = [page["title"], *page["lines"]]
        if page.get("table"):
            for row in page["table"]:
                text.append(" ".join(str(c) for c in row))
        with open(os.path.join(TRANS, f"page-{i:03d}.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(text) + "\n")

        if page.get("table"):
            with open(os.path.join(TABLES, f"page-{i:03d}.csv"), "w",
                      encoding="utf-8", newline="") as f:
                csv.writer(f).writerows(page["table"])

        manifest.append(
            [f"scans/{name}", f"transcripts/page-{i:03d}.txt",
             "synthetic-self-generated", "auto:render-source", "2026-11-17",
             "合成扫描件，非真实业务扫描"]
        )

    # 跨页续表合并 CSV（第10-11页）
    combined = PAGES[9]["table"] + PAGES[10]["table"][1:]
    with open(os.path.join(TABLES, "page-010-011-merged.csv"), "w",
              encoding="utf-8", newline="") as f:
        csv.writer(f).writerows(combined)
    manifest.append(
        ["scans/page-010.jpg+page-011.jpg", "transcripts/page-010.txt+page-011.txt",
         "synthetic-self-generated", "auto:render-source", "2026-11-17",
         "跨页续表（T-01-07）"]
    )

    with open(os.path.join(GOLDEN, "manifest.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["page_file", "transcript_file", "source", "corrected_by",
                    "corrected_at", "notes"])
        w.writerows(manifest)

    print(f"generated {len(PAGES)} pages -> {GOLDEN}")


if __name__ == "__main__":
    main()
