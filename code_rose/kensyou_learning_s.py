import cv2
import numpy as np
import os
import sys
import joblib
from skimage import feature
from sklearn.model_selection import train_test_split
from sklearn.svm import SVC, OneClassSVM
from sklearn.metrics import accuracy_score, classification_report
import glob

# ===== 設定 =====
TARGET_LABEL = "rose"   # バラのフォルダ名（例: "rose" / "バラ" などに変更してください）
DATASET_NAME = "dataset_normal"
MODEL_NAME   = "plant_species_model.pkl"

# --- 特徴量抽出関数（元コードを流用） ---
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
    hog_feats = get_hog_features(image)
    lbp_feats = get_lbp_features(image)
    combined = np.concatenate([color_feats, hog_feats, lbp_feats])
    return combined

def load_images_from_folder(folder_path):
    image_paths = glob.glob(os.path.join(folder_path, '*.*'))
    image_paths = [p for p in image_paths if p.lower().endswith(('.png', '.jpg', '.jpeg'))]
    images = []
    for image_path in image_paths:
        try:
            n = np.fromfile(image_path, np.uint8)
            img = cv2.imdecode(n, cv2.IMREAD_COLOR)
            if img is None: raise IOError("imdecode failed")
            images.append(img)
        except Exception as e:
            print(f"警告: 読み込み失敗 - {os.path.basename(image_path)}: {e}")
    return images

if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    DATASET_ROOT = os.path.join(script_dir, DATASET_NAME)
    MODEL_FILENAME = os.path.join(script_dir, MODEL_NAME)

    if not os.path.isdir(DATASET_ROOT):
        print(f"エラー: 学習データフォルダ '{DATASET_ROOT}' が見つかりません。")
        sys.exit(1)

    # normal 配下のサブフォルダを列挙
    sub_dirs = [d.name for d in os.scandir(DATASET_ROOT) if d.is_dir()]
    if not sub_dirs:
        print(f"エラー: '{DATASET_ROOT}' 内にサブフォルダがありません。")
        sys.exit(1)
    if TARGET_LABEL not in sub_dirs:
        print(f"エラー: TARGET_LABEL='{TARGET_LABEL}' のフォルダが '{DATASET_ROOT}' にありません。")
        print(f"存在する候補: {sub_dirs}")
        sys.exit(1)

    print("\n=== データ読込 ===")
    print(f"データセット: {DATASET_ROOT}")
    print(f"ターゲット（バラ）: '{TARGET_LABEL}'")

    # 画像とラベルの作成
    features = []
    labels = []  # バイナリ時: 1=rose, 0=not-rose / 1クラス時: ダミー(すべて1)

    # バラ画像
    rose_imgs = load_images_from_folder(os.path.join(DATASET_ROOT, TARGET_LABEL))
    if len(rose_imgs) == 0:
        print("エラー: バラ画像が見つかりません。")
        sys.exit(1)

    for img in rose_imgs:
        feat = extract_combined_features(img)
        features.append(feat); labels.append(1)
        # 左右反転で水増し
        flipped = cv2.flip(img, 1)
        features.append(extract_combined_features(flipped)); labels.append(1)

    # バラ以外の画像（あれば2値分類、無ければ1クラス学習へ）
    other_dirs = [d for d in sub_dirs if d != TARGET_LABEL]
    other_count = 0
    for od in other_dirs:
        odir = os.path.join(DATASET_ROOT, od)
        oimgs = load_images_from_folder(odir)
        for img in oimgs:
            feat = extract_combined_features(img)
            features.append(feat); labels.append(0)
            flipped = cv2.flip(img, 1)
            features.append(extract_combined_features(flipped)); labels.append(0)
        other_count += len(oimgs)

    features = np.array(features, dtype=np.float32)
    labels = np.array(labels, dtype=np.int32)

    print(f"バラ画像: {len(rose_imgs)}枚 / バラ以外: {other_count}枚")
    print(f"総サンプル(反転含む): {len(features)}")

    model_data_to_save = {"target_label": TARGET_LABEL}

    if other_count > 0:
        # ===== 2値分類（バラ vs バラ以外） =====
        print("\n=== 学習モード: バイナリ分類（SVC） ===")
        X_train, X_test, y_train, y_test = train_test_split(
            features, labels, test_size=0.2, random_state=42, stratify=labels
        )
        clf = SVC(kernel='rbf', C=10, probability=True, random_state=42)
        print("学習中...")
        clf.fit(X_train, y_train)
        print("評価中...")
        y_pred = clf.predict(X_test)
        acc = accuracy_score(y_test, y_pred)
        print(f"Accuracy: {acc:.4f}")
        print(classification_report(y_test, y_pred, target_names=["not_rose", "rose"]))

        model_data_to_save.update({
            "mode": "binary",
            "model": clf,
            "labels": ["not_rose", "rose"]
        })

    else:
        # ===== 1クラス学習（バラだけ） =====
        print("\n=== 学習モード: 1クラス（OneClassSVM） ===")
        # OneClassSVM: 正常（バラ）集合のみから学習し、外れ値を「バラ以外」と判定
        # nu は外れ値の想定割合（小さいほど厳しめ）。必要に応じて調整。
        clf = OneClassSVM(kernel='rbf', gamma='scale', nu=0.05)
        print("学習中...")
        clf.fit(features)  # すべてバラの特徴
        # 参考: decision_function > 0 を「バラ」とみなす
        model_data_to_save.update({
            "mode": "one-class",
            "model": clf,
            "decision_rule": "decision_function(x) > 0 => rose"
        })
        print("学習完了（評価は省略：負例が無いため）")

    joblib.dump(model_data_to_save, os.path.join(script_dir, MODEL_NAME))
    print(f"\nモデルを保存しました: {MODEL_FILENAME}")
