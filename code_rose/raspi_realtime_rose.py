# -*- coding: utf-8 -*-
"""
Raspberry Pi (Bookworm/Bullseye) + Picamera2 用
Piカメラからフレームを取得して、植物フィルタ→バラ判定→健康判定→オーバーレイ表示/保存

使い方:
  python3 raspi_realtime_rose.py --display   # HDMIにプレビュー表示
  python3 raspi_realtime_rose.py --headless  # 表示なし（保存のみ）
"""

import os, sys, time, argparse, cv2, joblib, numpy as np
from skimage import feature
from datetime import datetime

# ===== Picamera2 =====
from picamera2 import Picamera2
try:
    from libcamera import controls  # AF制御など（対応カメラのみ）
except Exception:
    controls = None

# ======= 設定 =======
TARGET_LABEL = "rose"
SPECIES_MODEL_FILE = "plant_species_model.pkl"
HEALTH_MODEL_FILE  = "plant_health_model.pkl"

OUTPUT_DIR   = "results"         # 保存先
FONT_PATH    = "HGRGE.TTC"       # 日本語フォント（無ければ自動フォールバック）

# カメラ解像度（処理負荷と精度の折衷）
CAPTURE_W, CAPTURE_H = 640, 480

# 処理負荷を下げるため「Nフレームに1回」判定
PROCESS_EVERY_N = 2

# 植物フィルタのしきい値
VEGETATION_RATIO_TH = 0.08  # 8% 未満は非植物とみなす

# バラ判定ゲート（Fail-closed）
BINARY_PROB_TH       = 0.80
BINARY_MARGIN_TH     = 0.15
ONECLASS_DECISION_TH = 0.20

# ======= 特徴量（学習と同じもの）=======
def vegetation_mask(bgr):
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    mask1 = cv2.inRange(hsv, (25, 30, 20), (95, 255, 255))  # 緑域ひろめ
    b,g,r = cv2.split(bgr.astype(np.float32))
    exg = 2*g - r - b
    exg = cv2.normalize(exg, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    _, mask2 = cv2.threshold(exg, 140, 255, cv2.THRESH_BINARY)
    mask = cv2.bitwise_or(mask1, mask2)
    mask = cv2.medianBlur(mask, 5)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5,5), np.uint8))
    return mask

def vegetation_ratio(bgr):
    m = vegetation_mask(bgr)
    return (m>0).mean()

def extract_shape_features(bgr):
    h, w = bgr.shape[:2]
    img_area = float(h*w)
    mask = vegetation_mask(bgr)
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return np.zeros(14, dtype=np.float32)

    c = max(cnts, key=cv2.contourArea)
    area = cv2.contourArea(c)
    perim = cv2.arcLength(c, True) + 1e-6
    x,y,wbox,hbox = cv2.boundingRect(c)
    hull = cv2.convexHull(c)
    hull_area = cv2.contourArea(hull) + 1e-6

    area_ratio   = area / img_area
    circularity  = (4.0*np.pi*area) / (perim*perim)
    solidity     = area / hull_area
    extent       = area / float(wbox*hbox + 1e-6)
    aspect_ratio = wbox / float(hbox + 1e-6)

    if len(c) >= 5:
        (_, _), (MA, ma), _ = cv2.fitEllipse(c)
        a = max(MA, ma) / 2.0; b = min(MA, ma) / 2.0
        ecc = np.sqrt(max(0.0, 1.0 - (b*b)/(a*a)))
    else:
        ecc = 0.0

    edges = cv2.Canny(cv2.GaussianBlur(cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY),(5,5),0), 80, 160)
    edge_density = (edges & (mask>0)).sum() / (mask>0).sum() if (mask>0).any() else 0.0

    hu = cv2.HuMoments(cv2.moments(c)).flatten()
    hu = -np.sign(hu) * np.log10(np.abs(hu) + 1e-12)

    feats = np.array([area_ratio, circularity, solidity, extent, aspect_ratio, ecc, edge_density], dtype=np.float32)
    return np.concatenate([feats, hu.astype(np.float32)])

def get_color_features(image, resize_dim=(256,256)):
    img = cv2.resize(image, resize_dim)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0,1], None, [30,32], [0,180, 0,256])
    cv2.normalize(hist, hist, 0, 1, cv2.NORM_MINMAX)
    return hist.flatten()

def get_hog_features(image, resize_dim=(128,128)):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    resized = cv2.resize(gray, resize_dim)
    hog = cv2.HOGDescriptor(resize_dim, (16,16), (8,8), (8,8), 9)
    h = hog.compute(resized)
    return (np.zeros(hog.getDescriptorSize()) if h is None else h.flatten())

def get_lbp_features(image, resize_dim=(256,256), P=24, R=3):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    resized = cv2.resize(gray, resize_dim)
    lbp = feature.local_binary_pattern(resized, P, R, method="uniform")
    hist, _ = np.histogram(lbp.ravel(), bins=np.arange(0, P+3), range=(0, P + 2))
    hist = hist.astype("float"); hist /= (hist.sum() + 1e-6)
    return hist

def extract_combined_features(image):
    return np.concatenate([
        get_color_features(image),
        get_hog_features(image),
        get_lbp_features(image),
        extract_shape_features(image)
    ])

def is_rose(feats, species_model):
    mode = species_model.get("mode"); clf = species_model.get("model")
    if mode is None or clf is None:
        return False

    if mode == "one-class":
        try:
            s = float(clf.decision_function(feats)[0])
            return s > ONECLASS_DECISION_TH
        except Exception:
            return False

    labels = species_model.get("labels", [])
    tgt = species_model.get("target_label", TARGET_LABEL)
    if not labels or tgt not in labels:
        return False
    if not hasattr(clf, "predict_proba"):
        return False

    try:
        probs = clf.predict_proba(feats)[0]
    except Exception:
        return False

    ridx = labels.index(tgt)
    rose_p = float(probs[ridx])
    other  = float(np.max(np.delete(probs, ridx))) if len(probs)>1 else 0.0
    return (rose_p >= BINARY_PROB_TH) and ((rose_p - other) >= BINARY_MARGIN_TH)

def draw_annotation(bgr, text, font_path):
    from PIL import Image, ImageDraw, ImageFont
    pil = Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(pil)
    try:
        font = ImageFont.truetype(font_path, max(16, int(pil.width/30)))
    except Exception:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0,0), text, font=font)
    w = bbox[2]-bbox[0]; h = bbox[3]-bbox[1]
    pos = (pil.width - w - 10, 10)
    overlay = Image.new("RGBA", (w+10, h+10), (0,0,0,180))
    pil.paste(overlay, (pos[0]-5, pos[1]-5), overlay)
    draw.text(pos, text, font=font, fill=(255,255,255))
    return cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--display", action="store_true", help="HDMIにプレビュー表示（OpenCV）")
    ap.add_argument("--headless", action="store_true", help="表示なしで保存のみ")
    ap.add_argument("--save-every", type=int, default=10, help="保存間隔（バラ判定成功ごとにN枚に1枚）")
    args = ap.parse_args()
    if args.display and args.headless:
        print("display と headless は同時指定できません"); sys.exit(1)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # モデル読み込み
    try:
        species = joblib.load(SPECIES_MODEL_FILE)
        health  = joblib.load(HEALTH_MODEL_FILE)
    except Exception as e:
        print("モデル読み込み失敗:", e); sys.exit(1)

    # カメラ初期化
    picam2 = Picamera2()
    config = picam2.create_preview_configuration(
        main={"size": (CAPTURE_W, CAPTURE_H), "format": "RGB888"}
    )
    picam2.configure(config)

    # オートフォーカス（対応カメラのみ）
    if controls is not None:
        try:
            picam2.set_controls({"AfMode": controls.AfModeEnum.Continuous})
        except Exception:
            pass

    picam2.start()
    time.sleep(0.2)  # センサー安定待ち

    print("リアルタイム判定を開始（Ctrl+Cで終了）")
    frame_count = 0
    saved_count = 0

    try:
        while True:
            frame = picam2.capture_array()  # shape: (H,W,3) RGB
            bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

            if frame_count % PROCESS_EVERY_N == 0:
                veg = vegetation_ratio(bgr)
                rose_ok = False
                health_label = None
                conf = None

                if veg >= VEGETATION_RATIO_TH:
                    feats = extract_combined_features(bgr).reshape(1, -1)
                    if is_rose(feats, species):
                        # 健康判定
                        clf_h = health["model"]; labels_h = health["labels"]
                        probs = clf_h.predict_proba(feats)[0]
                        idx = int(np.argmax(probs)); conf = float(probs[idx])
                        health_label = labels_h[idx]
                        rose_ok = True

                # オーバーレイ
                if rose_ok:
                    species_name = species.get("target_label", TARGET_LABEL)
                    text = f"種類: {species_name}\n状態: {health_label} ({conf:.1%})"
                    disp = draw_annotation(bgr, text, FONT_PATH)
                    # 保存（間引き）
                    if (saved_count % max(1, args.save_every)) == 0:
                        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                        out = os.path.join(OUTPUT_DIR, f"rose_{ts}.jpg")
                        ok, buf = cv2.imencode(".jpg", disp)
                        if ok: buf.tofile(out)
                    saved_count += 1
                else:
                    # 参考用オーバーレイ（植物らしさだけ表示）
                    disp = bgr.copy()
                    cv2.putText(disp, f"veg:{veg*100:.1f}%", (10, 24),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 255), 2, cv2.LINE_AA)
            else:
                disp = bgr

            # 表示 or ヘッドレス
            if args.headless:
                # 何もしない（ループ継続）
                pass
            else:
                cv2.imshow("Rose Monitor", disp)
                if cv2.waitKey(1) & 0xFF == 27:  # ESCで終了
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
