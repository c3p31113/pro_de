# pdf_create.py
import io
import os
import sqlite3

from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph,
    Spacer, Image
)
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.platypus.flowables import Flowable

# ------------------------------------------------------------
# パス設定
# ------------------------------------------------------------
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
DB_PATH    = os.path.join(BASE_DIR, "rover_database.db")
PHOTO_DIR  = os.path.join(BASE_DIR, "static", "photos")
RESULT_DIR = os.path.join(BASE_DIR, "static", "results")

# ------------------------------------------------------------
# 日本語フォント（文字化け対策）
# ------------------------------------------------------------
FONT_PATH = os.path.join(BASE_DIR, "ipaexg.ttf")
FONT_NAME = "IPAexGothic"

try:
    pdfmetrics.registerFont(TTFont(FONT_NAME, FONT_PATH))
    print(f"[PDF] フォント登録完了: {FONT_PATH}")
except Exception as e:
    print(f"[PDF] フォント読み込み失敗: {e}")
    FONT_NAME = "Helvetica"  # フォールバック

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(
    name="J-NORMAL",
    parent=styles["Normal"],
    fontName=FONT_NAME,
    fontSize=10,
    leading=14
))
styles.add(ParagraphStyle(
    name="J-TITLE",
    parent=styles["Heading1"],
    fontName=FONT_NAME,
    fontSize=18,
    leading=22
))
styles.add(ParagraphStyle(
    name="J-H2",
    parent=styles["Heading2"],
    fontName=FONT_NAME,
    fontSize=12,
    leading=16
))


# ------------------------------------------------------------
# DB ヘルパー
# ------------------------------------------------------------
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ------------------------------------------------------------
# PDF 内の画像に URL を埋め込むためのクラス :contentReference[oaicite:3]{index=3}
# ------------------------------------------------------------
class LinkedImage(Image):
    def __init__(self, filename, width=None, height=None, kind='direct', url=None):
        super().__init__(filename, width, height, kind)
        self.url = url

    def draw(self):
        super().draw()
        if self.url:
            # 画像全体をクリック可能領域にしてブラウザで URL を開く
            self.canv.linkURL(
                url=self.url,
                rect=(0, 0, self.drawWidth, self.drawHeight),
                relative=0,  # 絶対URL
                thickness=0
            )


# ============================================================
# 病害 PDF 生成本体
# ============================================================
def generate_disease_report(user_id: int):
    """
    notifications 内の「病害検知」（detections.result='desease'）だけを PDF にまとめる。
    戻り値:
        バイナリバッファ (io.BytesIO) / 病害が無いときは None
    """

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            n.id          AS notif_id,
            n.timestamp,
            d.id          AS detection_id,
            d.photo_id    AS photo_id,
            d.plant_type,
            d.result,
            d.confidence,
            p.filename,
            p.taken_at
        FROM notifications n
        JOIN detections d ON n.detection_id = d.id
        JOIN photos     p ON d.photo_id     = p.id
        WHERE n.user_id = ?
          AND d.result  = 'desease'
        ORDER BY n.timestamp DESC
    """, (user_id,))
    rows = cur.fetchall()
    conn.close()

    if len(rows) == 0:
        # 病害が無い
        return None

    # --------------------------------------------------------
    # PDF 作成
    # --------------------------------------------------------
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=20*mm,
        rightMargin=20*mm,
        topMargin=20*mm,
        bottomMargin=20*mm
    )

    flow = []

    # タイトル
    flow.append(Paragraph("植物異常（病害）検知レポート", styles["J-TITLE"]))
    flow.append(Spacer(1, 6*mm))

    # 概要
    flow.append(Paragraph(f"対象ユーザーID: {user_id}", styles["J-NORMAL"]))
    flow.append(Paragraph(f"病害検知件数: {len(rows)} 件", styles["J-NORMAL"]))
    flow.append(Spacer(1, 5*mm))

    # テーブルヘッダ
    table_data = [[
        Paragraph("画像", styles["J-NORMAL"]),
        Paragraph("植物種", styles["J-NORMAL"]),
        Paragraph("検知内容", styles["J-NORMAL"]),
        Paragraph("信頼度", styles["J-NORMAL"]),
        Paragraph("撮影日時", styles["J-NORMAL"]),
    ]]

    # 各行
    for r in rows:
        photo_id = r["photo_id"]

        # まず結果画像 (static/results/photo_<id>.jpg)、なければ元画像 (static/photos/filename)
        result_path = os.path.join(RESULT_DIR, f"photo_{photo_id}.jpg")
        if os.path.exists(result_path):
            img_path = result_path
        else:
            img_path = os.path.join(PHOTO_DIR, r["filename"])

        if os.path.exists(img_path):
            # PDF 画像クリック → Flask の /image/<photo_id> へ
            img_url = f"http://127.0.0.1:5000/image/{photo_id}"
            img = LinkedImage(img_path, width=30*mm, height=30*mm, url=img_url)
        else:
            img = Paragraph("画像なし", styles["J-NORMAL"])

        conf_text = f"{r['confidence']}%" if r["confidence"] is not None else "-"

        table_data.append([
            img,
            Paragraph(r["plant_type"] or "-", styles["J-NORMAL"]),
            Paragraph(r["result"] or "-", styles["J-NORMAL"]),
            Paragraph(conf_text, styles["J-NORMAL"]),
            Paragraph(str(r["taken_at"]) if r["taken_at"] else "-", styles["J-NORMAL"]),
        ])

    # テーブルを整形
    table = Table(
        table_data,
        colWidths=[35*mm, 30*mm, 40*mm, 20*mm, 40*mm]
    )
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTNAME", (0, 0), (-1, -1), FONT_NAME),
    ]))

    flow.append(table)

    doc.build(flow)
    buffer.seek(0)
    return buffer
