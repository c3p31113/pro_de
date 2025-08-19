# -*- coding: utf-8 -*-
"""
Raspberry Pi + Picamera2 で動かす多クラス版リアルタイム判定
 - 種類モデル(plant_species_model.pkl)と健康モデル(plant_health_model.pkl)を読み込み
 - フレームごとに特徴量(HSVヒスト+HOG+LBP) → 種類・健康を推定
 - 右上に「種類 / 状態(確率)」を描画
使い方:
  python3 raspi_realtime_multi.py --display        # HDMIにプレビュー表示
  python3 raspi_realtime_multi.py --headless       # 表示なし（保存のみ）
  python3 raspi_realtime_multi.py --save-every 10  # 判定成功ごとにN枚に1枚保存
"""

import os, sys, time, argparse, cv2, joblib, numpy as np
from skimage import feature
from datetime import datetime

# ==== Picamera2 ====
from picamera2 import Picamera2
try:
    from libcamera import controls
except Exception:
    controls = None

# ==== 設定 ====
SPECIES_MODEL_FILE = "plant_species_model.pkl"
HEALTH_MODEL_FILE  = "plant_health_model.pkl"
FONT_PATH          = "HGRGE.TTC"  # なければ等幅フォントにフォールバック
OUTPUT_DIR         = "results_multi"

# 速度と画質のバランス（必要に応じて変更）
CAPTURE_W, CAPTURE_H = 640, 480
PROCESS_EVERY_N = 2  # Nフレームに1回だけ推論（負荷軽減）

# ==== 特徴量（元コードのまま） ====
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
    block_size = (16, 16); block_stride = (8, 8); cell_size = (8, 8); nbins = 9
    hog = cv2.HOGDescriptor(win_size, block_size, block_stride, cell_size, nbins)
    hog_features = hog.compute(resized_image)
    if hog_features is None: return np.zeros(hog.getDescriptorSize())
    return hog_features.flatten()

def get_lbp_features(image, resize_dim=(256, 256), P=24, R=3):
    gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    resized_image = cv2.resize(gray_image, resize_dim)
    lbp = feature.local_binary_pattern(resized_image, P, R, method="uniform")
    (hist, _) = np.histogram(lbp.ravel(), bins=np.arange(0, P + 3), range=(0, P + 2))
    hist = hist.astype("float"); hist /= (hist.sum() + 1e-6)
    return hist

def extract_combined_features(image):
    color_feats = get_color_features(image)
    hog_feats   = get_hog_features(image)
    lbp_feats   = get_lbp_features(image)
    return np.concatenate([color_feats, hog_feats, lbp_feats])

# ==== 右上に注記描画（元の体裁を踏襲） ====
def draw_annotation(bgr, text, font_path):
    from PIL import Image, ImageDraw, ImageFont
    pil = Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(pil)
    try:
        font = ImageFont.truetype(font_path, max(16, int(pil.width/30)))
    except Exception:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    pos = (pil.width - w - 10, 10)
    # 半透明黒
    overlay = Image.new("RGBA", (w + 10, h + 10), (0, 0, 0, 180))
    pil.paste(overlay, (pos[0]-5, pos[1]-5), overlay)
    draw.text(pos, text, font=font, fill=(255, 255, 255))
    return cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--display", action="store_true", help="OpenCVでプレビュー表示")
    ap.add_argument("--headless", action="store_true", help="表示なし（保存のみ）")
    ap.add_argument("--save-every", type=int, default=10, help="保存間隔（推論成功N回ごと）")
    args = ap.parse_args()
    if args.display and args.headless:
        print("display と headless は同時指定できません"); sys.exit(1)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # モデル読み込み
    try:
        species_model = joblib.load(SPECIES_MODEL_FILE)
        health_model  = joblib.load(HEALTH_MODEL_FILE)
    except Exception as e:
        print(f"モデル読み込みに失敗: {e}")
        sys.exit(1)

    # Picamera2 初期化
    picam2 = Picamera2()
    config = picam2.create_preview_configuration(
        main={"size": (CAPTURE_W, CAPTURE_H), "format": "RGB888"}
    )
    picam2.configure(config)

    # AF対応カメラなら継続AF（無視される場合あり）
    if controls is not None:
        try:
            picam2.set_controls({"AfMode": controls.AfModeEnum.Continuous})
        except Exception:
            pass

    picam2.start()
    time.sleep(0.2)

    print("リアルタイム判定を開始（Ctrl+Cで終了）")
    frame_count = 0
    saved_ok = 0

    try:
        while True:
            frame = picam2.capture_array()     # RGB
            bgr   = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

            if frame_count % PROCESS_EVERY_N == 0:
                feats = extract_combined_features(bgr).reshape(1, -1)

                # 種類推定（確率）
                clf_s = species_model['model']
                labels_s = species_model['labels']
                if not hasattr(clf_s, "predict_proba"):
                    raise RuntimeError("species model does not support predict_proba")
                probs_s = clf_s.predict_proba(feats)[0]
                idx_s   = int(np.argmax(probs_s))
                species = labels_s[idx_s]
                conf_s  = float(probs_s[idx_s])

                # 健康推定（確率）
                clf_h = health_model['model']
                labels_h = health_model['labels']
                if not hasattr(clf_h, "predict_proba"):
                    raise RuntimeError("health model does not support predict_proba")
                probs_h = clf_h.predict_proba(feats)[0]
                idx_h   = int(np.argmax(probs_h))
                health  = labels_h[idx_h]
                conf_h  = float(probs_h[idx_h])

                text = f"種類: {species} ({conf_s:.1%})\n状態: {health} ({conf_h:.1%})"
                disp = draw_annotation(bgr, text, FONT_PATH)

                # 保存（間引き）
                if (saved_ok % max(1, args.save_every)) == 0:
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                    out = os.path.join(OUTPUT_DIR, f"{species}_{health}_{ts}.jpg")
                    ok, buf = cv2.imencode(".jpg", disp)
                    if ok: buf.tofile(out)
                saved_ok += 1
            else:
                disp = bgr

            if args.headless:
                pass
            else:
                cv2.imshow("Plant Monitor (multi)", disp)
                if cv2.waitKey(1) & 0xFF == 27:  # ESC
                    break

            frame_count += 1

    except KeyboardInterrupt:
        pass
    finally:
        try:
            picam2.stop()
        except Exception:
            pass
        cv2.destroyAllWindows()
        print("終了しました。")

if __name__ == "__main__":
    main()
