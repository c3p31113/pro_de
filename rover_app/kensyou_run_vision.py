"""
画像解析実行スクリプト(DB版)。

- static/photos や DB登録写真を対象にAI推論を実行
- 植物種別(例: Rose/Not Rose)や健康状態(normal/desease)を推定
- 結果をdetections/notificationsなどに保存し、Web側で表示できるようにする
"""
import cv2
import numpy as np
import tensorflow as tf
from tensorflow.keras.applications.mobilenet_v2 import preprocess_input
from PIL import Image, ImageDraw, ImageFont
import os

# BASE_DIR: 主要な設定値（パス/閾値など）。
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# モデル・ラベル・フォント
# HEALTH_MODEL_FILE: 主要な設定値（パス/閾値など）。
HEALTH_MODEL_FILE  = os.path.join(BASE_DIR, "plant_health_cnn_model.h5")
# HEALTH_LABELS_FILE: 主要な設定値（パス/閾値など）。
HEALTH_LABELS_FILE = os.path.join(BASE_DIR, "plant_health_cnn_labels.txt")
# FONT_PATH: 主要な設定値（パス/閾値など）。
FONT_PATH = os.path.join(BASE_DIR, "HGRGE.TTC")

# IMG_SIZE: 主要な設定値（パス/閾値など）。
IMG_SIZE = (224, 224)
# VEGETATION_RATIO_THRESHOLD: 主要な設定値（パス/閾値など）。
VEGETATION_RATIO_THRESHOLD = 0.08   # 草本比率


# ---------------- モデル読み込み ----------------
health_model = tf.keras.models.load_model(HEALTH_MODEL_FILE)
with open(HEALTH_LABELS_FILE, "r", encoding="utf-8") as f:
    health_labels = [line.strip() for line in f.readlines()]


# ---------------- 植物マスク ----------------
def vegetation_mask(bgr):
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    mask1 = cv2.inRange(hsv, (25, 30, 20), (95, 255, 255))

    b, g, r = cv2.split(bgr.astype(np.float32))
    exg = 2*g - r - b
    exg_norm = cv2.normalize(exg, None, 0, 255,
                             cv2.NORM_MINMAX).astype(np.uint8)
    _, mask2 = cv2.threshold(exg_norm, 140, 255, cv2.THRESH_BINARY)

    mask = cv2.bitwise_or(mask1, mask2)
    mask = cv2.medianBlur(mask, 5)
    return mask


#注釈描画 
def draw_annotation(bgr, text):
    pil_img = Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(pil_img)
    font = ImageFont.truetype(FONT_PATH, 35)
    draw.text((10, 10), text, fill=(255, 255, 255), font=font)
    return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)


#メイン解析（DB画像）
def analyze_image_from_db(image_bytes):
    """
    DBから渡された image_bytes（JPEGバイト列）を解析。
    返り値:
        status_raw     → "普通" / "異常" / "バラではない"
        confidence     → 0〜100 の float
        plant_name     → "バラ"
        annotated_img  → JPEGバイト列
    """

    n = np.frombuffer(image_bytes, np.uint8)
    bgr = cv2.imdecode(n, cv2.IMREAD_COLOR)

    #植物チェック
    mask = vegetation_mask(bgr)
    ratio = (mask > 0).mean()

    if ratio < VEGETATION_RATIO_THRESHOLD:
        text = "バラではない"
        annotated = draw_annotation(bgr, text)
        ok, buf = cv2.imencode(".jpg", annotated)
        return "バラではない", None, None, buf.tobytes()

    #植物領域の切り出し
    contours, _ = cv2.findContours(
        mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        text = "バラではない"
        annotated = draw_annotation(bgr, text)
        ok, buf = cv2.imencode(".jpg", annotated)
        return "バラではない", None, None, buf.tobytes()

    c = max(contours, key=cv2.contourArea)
    x, y, w, h = cv2.boundingRect(c)
    crop = bgr[y:y+h, x:x+w]

    #健康状態判定（CNN）
    rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
    resized = cv2.resize(rgb, IMG_SIZE)
    img_array = tf.expand_dims(
        tf.cast(resized, dtype=tf.float32), 0)
    img_preprocessed = preprocess_input(img_array)

    preds = health_model.predict(img_preprocessed)
    score = tf.nn.softmax(preds[0])

    idx = np.argmax(score)
    label = health_labels[idx]      # モデル上のラベル（英語）
    conf = float(score[idx])        # 0〜1
    conf_percent = round(conf * 100, 1)
    plant_name = "バラ"
    status = convert_label_to_status(label)
    annotated = draw_annotation(
        bgr, f"{status} ({conf_percent:.1f}%)"
    )
    ok, buf = cv2.imencode(".jpg", annotated)

    return status, conf_percent, plant_name, buf.tobytes()


#ラベル文字列のマッピング 
def convert_label_to_status(raw):
    """
    model → "普通" / "異常" へ変換する
    """
    s = raw.lower()

    # モデルのラベルが "normal", "healthy", "健康" などの場合
    if "healthy" in s or "normal" in s or "健康" in s:
        return "普通"

    # それ以外はすべて病害扱い
    return "異常"

if __name__ == "__main__":
    with open("test.jpg", "rb") as f:
        b = f.read()

    result = analyze_image_from_db(b)
    print(result)
