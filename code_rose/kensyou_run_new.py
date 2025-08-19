# kensyou_run_new.py
# -*- coding: utf-8 -*-

import os
import sys
import glob
import cv2
import joblib
import numpy as np
from skimage import feature
from PIL import Image, ImageDraw, ImageFont

# =========================
# 設定（必要に応じて変更）
# =========================
TARGET_LABEL = "rose"                  # 学習時の「バラ」ラベル名（pkl内の target_label と一致させる）
SPECIES_MODEL_FILE = "plant_species_model.pkl"
HEALTH_MODEL_FILE  = "plant_health_model.pkl"

INPUT_DIR  = "hantei"                  # 判定対象画像フォルダ（本スクリプトと同階層）
OUTPUT_DIR = "dataset_results"         # 結果保存先
FONT_PATH  = "HGRGE.TTC"               # 日本語フォント（無ければ等幅にフォールバック）

# 植物フィルタのしきい値（画面中の植生割合）
VEGETATION_RATIO_THRESHOLD = 0.08      # 8% 未満なら「非植物」とみなしてスキップ

# バラ判定ゲートのしきい値（Fail-closed）
BINARY_PROB_THRESHOLD   = 0.80         # SVC の rose 確率の下限
BINARY_MARGIN_THRESHOLD = 0.15         # rose確率 と 他クラス最大確率の差の下限
ONECLASS_DECISION_TH    = 0.20         # OneClassSVM の decision_function の下限

# ====================================
# 特徴量抽出（学習と同じ前処理を使用）
# ====================================
def get_color_features(image, resize_dim=(256, 256)):
    image_resized = cv2.resize(image, resize_dim)
    hsv_image = cv2.cvtColor(image_resized, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv_image], [0, 1], None, [30, 32], [0, 180, 0, 256])
    cv2.normalize(hist, hist, 0, 1, cv2.NORM_MINMAX)
    return hist.flatten()

def get_hog_features(image, resize_dim=(128, 128)):
    gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    resized_image = cv2.resize(gray_image, resize_dim)
    win_size = resize_dim
    block_size = (16, 16)
    block_stride = (8, 8)
    cell_size = (8, 8)
    nbins = 9
    hog = cv2.HOGDescriptor(win_size, block_size, block_stride, cell_size, nbins)
    hog_features = hog.compute(resized_image)
    if hog_features is None:
        return np.zeros(hog.getDescriptorSize())
    return hog_features.flatten()

def get_lbp_features(image, resize_dim=(256, 256), P=24, R=3):
    gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    resized_image = cv2.resize(gray_image, resize_dim)
    lbp = feature.local_binary_pattern(resized_image, P, R, method="uniform")
    (hist, _) = np.histogram(lbp.ravel(), bins=np.arange(0, P + 3), range=(0, P + 2))
    hist = hist.astype("float")
    hist /= (hist.sum() + 1e-6)
    return hist

def extract_combined_features(image):
    color_feats = get_color_features(image)
    hog_feats   = get_hog_features(image)
    lbp_feats   = get_lbp_features(image)
    return np.concatenate([color_feats, hog_feats, lbp_feats])

# ====================================
# 植物らしさフィルタ（HSV + ExG）
# ====================================
def vegetation_ratio(bgr):
    """
    画像中の植生（緑っぽい）画素の割合を 0.0〜1.0 で返す。
    """
    # HSV の緑域
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    mask1 = cv2.inRange(hsv, (25, 30, 20), (95, 255, 255))  # やや広め

    # Excess Green (ExG)
    b, g, r = cv2.split(bgr.astype(np.float32))
    exg = 2*g - r - b
    exg_norm = cv2.normalize(exg, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    _, mask2 = cv2.threshold(exg_norm, 140, 255, cv2.THRESH_BINARY)

    # 結合 → ノイズ除去
    mask = cv2.bitwise_or(mask1, mask2)
    mask = cv2.medianBlur(mask, 5)
    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

    return (mask > 0).mean()

# ====================================
# 「バラかどうか」判定（Fail-closed）
# ====================================
def is_rose(features,
            species_model,
            prob_threshold=BINARY_PROB_THRESHOLD,
            margin=BINARY_MARGIN_THRESHOLD,
            oneclass_threshold=ONECLASS_DECISION_TH,
            target_label=TARGET_LABEL):
    """
    True のときのみ「バラ」とみなす。
    - binary(SVC): rose確率>=prob_threshold かつ (rose確率-他最大)>=margin
    - one-class : decision_function > oneclass_threshold
    - ラベル不備やエラー時は False（Fail-closed）
    """
    if not isinstance(species_model, dict):
        return False

    mode = species_model.get("mode", None)
    clf  = species_model.get("model", None)
    if mode is None or clf is None:
        return False

    # One-class（バラのみで学習）
    if mode == "one-class":
        try:
            score = float(clf.decision_function(features)[0])
            return score > oneclass_threshold
        except Exception:
            return False

    # Binary（バラ vs その他）
    labels = species_model.get("labels", [])
    tgt    = species_model.get("target_label", target_label)
    if not labels or tgt not in labels:
        return False
    if not hasattr(clf, "predict_proba"):
        return False

    try:
        probs = clf.predict_proba(features)[0]
    except Exception:
        return False

    rose_idx   = labels.index(tgt)
    rose_prob  = float(probs[rose_idx])
    other_prob = float(np.max(np.delete(probs, rose_idx))) if len(probs) > 1 else 0.0
    return (rose_prob >= prob_threshold) and ((rose_prob - other_prob) >= margin)

# ====================================
# 画像への注記描画（元の体裁を維持）
# ====================================
def draw_annotation(bgr_image, text, font_path=FONT_PATH):
    image_pil = Image.fromarray(cv2.cvtColor(bgr_image, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(image_pil)
    font_size = max(16, int(image_pil.width / 30))
    try:
        font = ImageFont.truetype(font_path, font_size)
    except Exception:
        font = ImageFont.load_default()

    # 右上に黒半透明ボックス＋白文字
    text_bbox = draw.textbbox((0, 0), text, font=font)
    text_w = text_bbox[2] - text_bbox[0]
    text_h = text_bbox[3] - text_bbox[1]
    pos = (image_pil.width - text_w - 10, 10)

    # 半透明背景（RGBA）
    overlay = Image.new('RGBA', (text_w + 10, text_h + 10), (0, 0, 0, 180))
    image_pil.paste(overlay, (pos[0] - 5, pos[1] - 5), overlay)
    draw.text(pos, text, font=font, fill=(255, 255, 255))

    return cv2.cvtColor(np.array(image_pil), cv2.COLOR_RGB2BGR)

# ====================================
# メイン
# ====================================
def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    input_dir  = os.path.join(script_dir, INPUT_DIR)
    output_dir = os.path.join(script_dir, OUTPUT_DIR)
    os.makedirs(output_dir, exist_ok=True)

    species_model_path = os.path.join(script_dir, SPECIES_MODEL_FILE)
    health_model_path  = os.path.join(script_dir, HEALTH_MODEL_FILE)

    # モデル読込
    print("モデルを読み込み中...")
    try:
        species_model = joblib.load(species_model_path)
        health_model  = joblib.load(health_model_path)
    except Exception as e:
        print(f"エラー: モデル読み込みに失敗しました: {e}")
        sys.exit(1)
    print("モデル読み込み完了。")
    print(f"species mode={species_model.get('mode')} target_label={species_model.get('target_label')} labels={species_model.get('labels')}")

    if not os.path.isdir(input_dir):
        print(f"エラー: 判定対象フォルダが見つかりません: {input_dir}")
        sys.exit(1)

    image_paths = [p for p in glob.glob(os.path.join(input_dir, "*.*"))
                   if p.lower().endswith((".png", ".jpg", ".jpeg"))]

    if not image_paths:
        print(f"'{input_dir}' に画像がありません。")
        return

    print(f"--- {len(image_paths)} 件の画像を処理します ---")
    for idx, img_path in enumerate(image_paths, 1):
        print(f"\n[{idx}/{len(image_paths)}] {os.path.basename(img_path)}")
        try:
            # 画像読み込み（日本語パス対応）
            n = np.fromfile(img_path, np.uint8)
            bgr = cv2.imdecode(n, cv2.IMREAD_COLOR)
            if bgr is None:
                raise IOError("imdecode failed")

            # ① 植物フィルタ
            veg = vegetation_ratio(bgr)
            print(f"  植物らしさ: {veg*100:.1f}%")
            if veg < VEGETATION_RATIO_THRESHOLD:
                print("  -> 植物らしさ不足のためスキップ")
                continue

            # 特徴量抽出
            feats = extract_combined_features(bgr).reshape(1, -1)

            # ② バラ判定ゲート
            rose_flag = is_rose(
                feats, species_model,
                prob_threshold=BINARY_PROB_THRESHOLD,
                margin=BINARY_MARGIN_THRESHOLD,
                oneclass_threshold=ONECLASS_DECISION_TH,
                target_label=TARGET_LABEL
            )
            print(f"  バラ判定: {rose_flag}")
            if not rose_flag:
                print("  -> バラ以外または確信不足のためスキップ")
                continue

            # ここから先は元の健康判定ロジック
            clf_health = health_model['model']
            health_labels = health_model['labels']

            if not hasattr(clf_health, "predict_proba"):
                raise RuntimeError("health_model['model'] は predict_proba をサポートしていません。")

            health_probs = clf_health.predict_proba(feats)[0]
            pred_idx = int(np.argmax(health_probs))
            pred_label = health_labels[pred_idx]
            pred_conf  = float(health_probs[pred_idx])

            species_name = species_model.get("target_label", TARGET_LABEL)
            print(f"  -> 種類: {species_name}, 状態: {pred_label} ({pred_conf:.1%})")

            text = f"種類: {species_name}\n状態: {pred_label} ({pred_conf:.1%})"
            annotated = draw_annotation(bgr, text, font_path=os.path.join(script_dir, FONT_PATH))

            # 保存（拡張子を保つ）
            out_path = os.path.join(output_dir, os.path.basename(img_path))
            ok, buf = cv2.imencode(os.path.splitext(out_path)[1], annotated)
            if ok:
                buf.tofile(out_path)
                print(f"  -> 保存: {out_path}")
            else:
                print("  -> 保存に失敗しました")

        except Exception as e:
            print(f"  -> 警告: 処理中にエラーが発生: {e}")
            continue

    print("\nすべての処理が終了しました。")

if __name__ == "__main__":
    main()
