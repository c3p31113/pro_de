import cv2
import numpy as np
import os
import sys
import joblib
from skimage import feature
from sklearn.model_selection import train_test_split
from sklearn.svm import SVC
from sklearn.metrics import accuracy_score, classification_report
import glob

# --- 特徴量抽出関数 ---

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

# --- メイン処理 ---
if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    DATASET_ROOT = os.path.join(script_dir, "dataset_normal")
    MODEL_FILENAME = os.path.join(script_dir, 'plant_species_model.pkl')

    features = []
    labels_str = []

    print("\n'normal'フォルダ内のフォルダ名をラベルとしてモデル学習を開始します。")
    print(f"データセットルート: '{DATASET_ROOT}'")

    if not os.path.isdir(DATASET_ROOT):
        print(f"エラー: 学習データフォルダ '{DATASET_ROOT}' が見つかりません。")
        sys.exit(1)

    # normalフォルダ内のサブフォルダ（＝ラベル）を取得
    try:
        sub_dirs = [d.name for d in os.scandir(DATASET_ROOT) if d.is_dir()]
    except Exception as e:
        print(f"エラー: データセットフォルダの読み取りに失敗しました。 {e}")
        sys.exit(1)

    if not sub_dirs:
        print(f"エラー: '{DATASET_ROOT}' 内にラベルとなるサブフォルダが見つかりません。")
        sys.exit(1)

    # 各サブフォルダをループ処理
    for label in sub_dirs:
        folder_path = os.path.join(DATASET_ROOT, label)
        print(f"\n--- ラベル '{label}' のデータを処理中 ---")
        
        image_paths = glob.glob(os.path.join(folder_path, '*.*'))
        image_paths = [p for p in image_paths if p.lower().endswith(('.png', '.jpg', '.jpeg'))]

        if not image_paths:
            print(f"警告: フォルダ '{folder_path}' 内に画像が見つかりません。")
            continue

        print(f"{len(image_paths)} 個の画像を処理します...")
        for image_path in image_paths:
            try:
                n = np.fromfile(image_path, np.uint8)
                original_image = cv2.imdecode(n, cv2.IMREAD_COLOR)
                if original_image is None: raise IOError
            except Exception as e:
                print(f"警告: 画像を読み込めませんでした - {os.path.basename(image_path)}, エラー: {e}")
                continue

            # 元の画像と水平反転した画像の両方から特徴量を抽出
            combined_original = extract_combined_features(original_image)
            features.append(combined_original)
            labels_str.append(label)

            flipped_image = cv2.flip(original_image, 1)
            combined_flipped = extract_combined_features(flipped_image)
            features.append(combined_flipped)
            labels_str.append(label)

    # --- モデル学習・評価 (変更なし) ---
    if len(features) == 0:
        print("エラー: 特徴量が抽出されませんでした。画像ファイルを確認してください。")
    else:
        LABELS = sorted(list(set(labels_str)))
        label_to_index = {label: i for i, label in enumerate(LABELS)}
        labels_numeric = [label_to_index[name] for name in labels_str]

        print("\n--- 認識するクラス一覧 ---")
        print(LABELS)

        features = np.array(features)
        labels = np.array(labels_numeric)
        print(f"\n特徴量抽出が完了しました。総データ数: {len(features)}")
        
        model = SVC(kernel='rbf', C=10, probability=True, random_state=42)

        if len(LABELS) > 1:
            X_train, X_test, y_train, y_test = train_test_split(
                features, labels, test_size=0.2, random_state=42, stratify=labels
            )
            print("モデルの訓練を開始します...")
            model.fit(X_train, y_train)
            print("モデルの訓練が完了しました。")
            print("\n--- モデル性能評価 ---")
            y_pred = model.predict(X_test)
            accuracy = accuracy_score(y_test, y_pred)
            print(f"正解率 (Accuracy): {accuracy:.4f}")
            print("\n分類レポート:")
            print(classification_report(y_test, y_pred, target_names=LABELS))
        else:
            print("\n警告: クラスが1つ以下のため、評価をスキップして全データで学習します。")
            model.fit(features, labels)

        model_data_to_save = {'model': model, 'labels': LABELS}
        joblib.dump(model_data_to_save, MODEL_FILENAME)
        print(f"\n訓練済みモデルとラベルを '{MODEL_FILENAME}' として保存しました。")