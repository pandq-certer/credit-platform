"""生成 SYS-01 冒烟样本（非金标数据集；金标需真实扫描件 + 人工校对）。"""
import math
import os
import struct
import wave

from PIL import Image, ImageDraw, ImageFilter, ImageFont
from docx import Document
from openpyxl import Workbook
from pypdf import PdfReader, PdfWriter

ROOT = os.path.join(os.path.dirname(__file__), "..", "samples")
FONT_PATH = "/System/Library/Fonts/Supplemental/Songti.ttc"


def font(size):
    return ImageFont.truetype(FONT_PATH, size, index=0)


def make_page(title, lines, table_rows):
    img = Image.new("RGB", (1654, 2339), "white")  # A4 200dpi
    d = ImageDraw.Draw(img)
    y = 160
    d.text((120, y), title, fill="black", font=font(64))
    y += 120
    for line in lines:
        d.text((120, y), line, fill="black", font=font(40))
        y += 76
    y += 40
    x0, col_w, row_h = 120, 460, 70
    for r, row in enumerate(table_rows):
        for c, cell in enumerate(row):
            x1 = x0 + c * col_w
            y1 = y + r * row_h
            d.rectangle([x1, y1, x1 + col_w, y1 + row_h], outline="black", width=2)
            d.text((x1 + 12, y1 + 12), str(cell), fill="black", font=font(32))
    return img


def main():
    os.makedirs(ROOT, exist_ok=True)

    p1 = make_page(
        "个人经营性贷款申请表",
        [
            "申请人姓名：张伟    身份证号：310101198801011234",
            "申请金额：人民币 500,000 元    期限：36 个月",
            "经营主体：上海示例商贸有限公司",
            "统一社会信用代码：91310101MA1FL8XK2P",
            "联系电话：13800138000    联系地址：上海市黄浦区示例路 88 号",
        ],
        [
            ["项目", "内容", "备注"],
            ["年营业收入", "2,800,000", "近12个月"],
            ["净利润", "360,000", "审计口径"],
            ["负债合计", "900,000", "含本次申请"],
        ],
    )
    p1.save(os.path.join(ROOT, "sample.jpg"), quality=92)

    p2 = make_page(
        "抵押物清单",
        [
            "抵押物名称：住宅    坐落：上海市浦东新区示例路 100 弄 8 号 501 室",
            "建筑面积：128.6 平方米    评估价值：6,500,000 元",
            "产权证号：沪(2020)浦字不动产权第 0123456 号",
            "抵押率：50%    抵押权人：示例银行股份有限公司",
        ],
        [
            ["序号", "抵押物", "评估价", "抵押率"],
            ["1", "住宅", "6,500,000", "50%"],
            ["2", "车位", "350,000", "50%"],
        ],
    )
    p1.save(os.path.join(ROOT, "scanned.pdf"), "PDF", resolution=200.0,
            save_all=True, append_images=[p2])

    p1.filter(ImageFilter.GaussianBlur(radius=6)).save(os.path.join(ROOT, "blur.jpg"), quality=85)
    Image.eval(p1, lambda v: int(v * 0.18)).save(os.path.join(ROOT, "dark.jpg"), quality=85)

    doc = Document()
    doc.add_heading("智能信贷文档解析冒烟样本", level=1)
    doc.add_paragraph("本文件用于验证 DOCX 解析链路，包含标题、段落与表格。")
    doc.add_paragraph("借款用途：生产经营周转；还款方式：等额本息。")
    t = doc.add_table(rows=3, cols=3)
    for r, row in enumerate([["项目", "金额", "期限"], ["授信额度", "500000", "36期"],
                             ["年利率", "4.35%", "—"]]):
        for c, val in enumerate(row):
            t.cell(r, c).text = val
    doc.save(os.path.join(ROOT, "sample.docx"))

    with open(os.path.join(ROOT, "sample.html"), "w", encoding="utf-8") as f:
        f.write("""<!doctype html><html><head><meta charset="utf-8"><title>信贷资料</title></head>
<body><h1>企业授信申请</h1><p>企业名称：上海示例商贸有限公司</p>
<p>申请金额：人民币壹佰万元整。</p>
<table border="1"><tr><th>指标</th><th>数值</th></tr>
<tr><td>资产负债率</td><td>42%</td></tr><tr><td>流动比率</td><td>1.8</td></tr></table>
</body></html>""")

    wb = Workbook()
    ws = wb.active
    ws.title = "授信测算"
    ws.append(["项目", "2024年", "2025年", "同比"])
    ws.append(["营业收入", 2400000, 2800000, "16.7%"])
    ws.append(["净利润", 300000, 360000, "20.0%"])
    ws.append(["负债合计", 800000, 900000, "12.5%"])
    ws.merge_cells("A1:A1")
    wb.save(os.path.join(ROOT, "sample.xlsx"))

    writer = PdfWriter()
    for page in PdfReader(os.path.join(ROOT, "scanned.pdf")).pages:
        writer.add_page(page)
    writer.encrypt("secret123")
    with open(os.path.join(ROOT, "encrypted.pdf"), "wb") as f:
        writer.write(f)

    sr = 44100
    with wave.open(os.path.join(ROOT, "audio.wav"), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sr)
        frames = bytearray()
        for i in range(sr * 3):
            v = int(12000 * math.sin(2 * math.pi * 440 * i / sr))
            frames += struct.pack("<hh", v, v)
        w.writeframes(bytes(frames))

    print("samples written to", os.path.abspath(ROOT))


if __name__ == "__main__":
    main()
