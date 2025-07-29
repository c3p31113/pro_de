import cv2
import numpy as np
import os
from sklearn.model_selection import train_test_split
from sklearn.svm import SVC
from sklearn.metrics import accuracy_score, classification_report
import joblib
from skimage import feature


def get_color_features(image, resize_dim=(256, 256)):
    """画像からHSV色ヒストグラムを抽出する"""
    image_resized = cv2.resize(image, resize_dim)
    hsv_image = cv2.cvtColor(image_resized, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv_image], [0, 1], None, [30, 32], [0, 180, 0, 256])
    cv2.normalize(hist, hist, 0, 1, cv2.NORM_MINMAX)
    return hist.flatten()

def get_hog_features(image, resize_dim=(128, 128)):
    """画像からHOG特徴量を抽出する"""
    gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    resized_image = cv2.resize(gray_image, resize_dim)
    
    # HOGパラメータ
    win_size = resize_dim
    block_size = (16, 16)
    block_stride = (8, 8)
    cell_size = (8, 8)
    nbins = 9
    
    hog = cv2.HOGDescriptor(win_size, block_size, block_stride, cell_size, nbins)
    hog_features = hog.compute(resized_image)
    
    # hog_featuresがNoneになる場合への対策
    if hog_features is None:
        return np.zeros(hog.getDescriptorSize())
        
    return hog_features.flatten()

def get_lbp_features(image, resize_dim=(256, 256), P=24, R=3):
    """画像からLBP特徴量を抽出する"""
    gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    resized_image = cv2.resize(gray_image, resize_dim)
    
    # LBP特徴を計算
    lbp = feature.local_binary_pattern(resized_image, P, R, method="uniform")
    
    # LBP画像のヒストグラムを計算して特徴量とする
    (hist, _) = np.histogram(lbp.ravel(),
                             bins=np.arange(0, P + 3),
                             range=(0, P + 2))
    
    # ヒストグラムを正規化
    hist = hist.astype("float")
    hist /= (hist.sum() + 1e-6) # ゼロ除算を避ける
    
    return hist

def extract_combined_features(image):
    color_feats = get_color_features(image)
    hog_feats = get_hog_features(image)
    lbp_feats = get_lbp_features(image)
    
    # すべての特徴量を一つのベクトルに結合
    combined = np.concatenate([color_feats, hog_feats, lbp_feats])
    return combined

# --- メイン処理 ---
script_dir = os.path.dirname(os.path.abspath(__file__))
DATASET_MAPPING = {
    "normal": os.path.join(script_dir, "dataset_disease", "normal"),
    "disease": os.path.join(script_dir, "dataset_disease", "disease")
}
MODEL_FILENAME = os.path.join(script_dir, 'plant_health_model.pkl')

features = []
labels_str = []

print("\n特徴量抽出を開始します... (色+HOG+LBP, データ拡張: 水平反転あり)")

for label, parent_path in DATASET_MAPPING.items():
    if not os.path.exists(parent_path):
        print(f"警告: データセットフォルダ '{parent_path}' が見つかりません。スキップします。")
        continue

    print(f"\n--- ラベル '{label}' のデータを処理中 (フォルダ: '{parent_path}') ---")
    image_files = []
    for root, _, files in os.walk(parent_path):
        for filename in files:
            if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                image_files.append(os.path.join(root, filename))

    if not image_files:
        print(f"警告: '{parent_path}' 内に画像ファイルが見つかりません。")
        continue

    print(f"'{label}' として {len(image_files)} 個の画像ファイルを処理します...")
    for image_path in image_files:
        try:
            n = np.fromfile(image_path, np.uint8)
            original_image = cv2.imdecode(n, cv2.IMREAD_COLOR)
            if original_image is None: raise IOError
        except Exception as e:
            print(f"警告: 画像を読み込めませんでした - {image_path}, エラー: {e}")
            continue

        # 元の画像から結合特徴を抽出
        combined_original = extract_combined_features(original_image)
        features.append(combined_original)
        labels_str.append(label)

        # 水平反転した画像から結合特徴を抽出
        flipped_image = cv2.flip(original_image, 1)
        combined_flipped = extract_combined_features(flipped_image)
        features.append(combined_flipped)
        labels_str.append(label)

# --- 以降のモデル学習・評価部分は変更なし ---
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
    print(f"各データの特徴量の次元数: {features.shape[1]}")
    
    model = SVC(kernel='rbf', C=10, probability=True, random_state=42)

    if len(LABELS) > 1:
        print("\n[INFO] クラスが複数検出されたため、分割・評価処理を実行します。")
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
        print("\n[INFO] クラスが1つのため、全データで学習し、評価はスキップします。")
        print("モデルの訓練を開始します...")
        model.fit(features, labels)
        print("モデルの訓練が完了しました。")
        print("\n--- モデル性能評価 ---")
        print("評価はスキップされました（クラスが1つのため）。")
        print("警告: このモデルは分類能力を持ちません。")

    model_data_to_save = {'model': model, 'labels': LABELS}
    joblib.dump(model_data_to_save, MODEL_FILENAME)
    print(f"\n訓練済みモデルとラベルを '{MODEL_FILENAME}' として保存しました。")