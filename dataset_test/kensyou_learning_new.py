import cv2
import numpy as np
import os
from sklearn.model_selection import train_test_split
from sklearn.svm import SVC
from sklearn.metrics import accuracy_score, classification_report
import joblib

# --- 関数定義 ---
def _process_image_to_histogram(image, resize_dim=(256, 256)):
    """
    画像オブジェクトからHSV色ヒストグラムを抽出し、特徴量ベクトルを返す。
    """
    image_resized = cv2.resize(image, resize_dim)
    hsv_image = cv2.cvtColor(image_resized, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv_image], [0, 1], None, [30, 32], [0, 180, 0, 256])
    cv2.normalize(hist, hist, 0, 1, cv2.NORM_MINMAX)
    return hist.flatten()

# --- メイン処理 ---
DATASET_MAPPING = {
    "normal": "./dataset/normal/",
    "disease": "./dataset/disease/"
}

MODEL_FILENAME = 'plant_health_model.pkl'

features = []
labels_str = [] # ラベル名を文字列として保存するリスト

print("\n特徴量抽出を開始します... (データ拡張: 水平反転あり)")

# ★★★ 変更点: 辞書をループして、指定されたラベルでデータを収集 ★★★
for label, parent_path in DATASET_MAPPING.items():
    if not os.path.exists(parent_path):
        print(f"警告: データセットフォルダ '{parent_path}' が見つかりません。スキップします。")
        continue

    print(f"\n--- ラベル '{label}' のデータを処理中 (フォルダ: '{parent_path}') ---")

    # 指定されたフォルダ以下の画像ファイルをすべて取得 (os.walkで再帰的に検索)
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
        original_image = cv2.imread(image_path)
        if original_image is None:
            print(f"警告: 画像を読み込めませんでした - {image_path}")
            continue

        # 1. 元の画像から特徴量を抽出
        hist_original = _process_image_to_histogram(original_image)
        features.append(hist_original)
        labels_str.append(label) # ★ 固定のラベルを付与

        # 2. 水平反転した画像からも特徴量を抽出 (データ拡張)
        flipped_image = cv2.flip(original_image, 1)
        hist_flipped = _process_image_to_histogram(flipped_image)
        features.append(hist_flipped)
        labels_str.append(label) # ★ 固定のラベルを付与

if len(features) == 0:
    print("エラー: 特徴量が抽出されませんでした。画像ファイルを確認してください。")
else:
    # 収集したラベル名から重複を除き、アルファベット順にソートして最終的なラベルリストとする
    LABELS = sorted(list(set(labels_str)))
    # ラベル名とインデックス(数値)を対応させる辞書を作成
    label_to_index = {label: i for i, label in enumerate(LABELS)}
    # 文字列のラベルリストを数値のリストに変換
    labels_numeric = [label_to_index[name] for name in labels_str]

    print("\n--- 認識するクラス一覧 ---")
    print(LABELS) # -> ['disease', 'normal'] と表示されるはず

    features = np.array(features)
    labels = np.array(labels_numeric)
    print(f"\n特徴量抽出が完了しました。総データ数: {len(features)}")

    # データを訓練用とテスト用に分割
    X_train, X_test, y_train, y_test = train_test_split(
        features, labels, test_size=0.2, random_state=42, stratify=labels
    )

    print("\nモデルの訓練を開始します...")
    model = SVC(kernel='rbf', C=10, probability=True, random_state=42)
    model.fit(X_train, y_train)
    print("モデルの訓練が完了しました。")

    print("\n--- モデル性能評価 ---")
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    print(f"正解率 (Accuracy): {accuracy:.4f}")
    print("\n分類レポート:")
    print(classification_report(y_test, y_pred, target_names=LABELS))

    # モデルと最終的なラベルリストを一緒に保存
    model_data_to_save = {
        'model': model,
        'labels': LABELS
    }
    joblib.dump(model_data_to_save, MODEL_FILENAME)
    print(f"\n訓練済みモデルとラベルを '{MODEL_FILENAME}' として保存しました。")