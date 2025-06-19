import cv2
import numpy as np
import os
import joblib

# --- 関数定義 ---
def extract_hsv_histogram_from_path(image_path, resize_dim=(256, 256)):
    """
    画像ファイルパスからHSVヒストグラムを抽出する。
    """
    image = cv2.imread(image_path)
    if image is None:
        print(f"警告: 画像を読み込めませんでした - {image_path}")
        return None
    
    image_resized = cv2.resize(image, resize_dim)
    hsv_image = cv2.cvtColor(image_resized, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv_image], [0, 1], None, [30, 32], [0, 180, 0, 256])
    cv2.normalize(hist, hist, 0, 1, cv2.NORM_MINMAX)
    return hist.flatten()

# --- メイン処理 ---
LABELS = ["daisy", "dandelion", "rose", "sunflower", "tulip"]

# ★保存したモデルファイルのパス
MODEL_FILENAME = 'flower_model.pkl'

# ★判定したい新しい画像のパス
NEW_IMAGE_PATH = "./dataset/newFlow/new_flower_image2.jpg"

if not os.path.exists(MODEL_FILENAME):
    print(f"エラー: モデルファイル '{MODEL_FILENAME}' が見つかりません。先に訓練用のスクリプトを実行してください。")
elif not os.path.exists(NEW_IMAGE_PATH):
    print(f"エラー: 画像ファイル '{NEW_IMAGE_PATH}' が見つかりません。")
else:
    # 訓練済みモデルを読み込む
    print(f"モデル '{MODEL_FILENAME}' を読み込んでいます...")
    loaded_model = joblib.load(MODEL_FILENAME)
    print("モデルの読み込みが完了しました。")

    # 新しい画像の特徴量を抽出
    new_features = extract_hsv_histogram_from_path(NEW_IMAGE_PATH)

    if new_features is not None:
        # 予測を実行
        prediction = loaded_model.predict([new_features])
        prediction_proba = loaded_model.predict_proba([new_features])
        
        predicted_label = LABELS[prediction[0]]
        confidence = prediction_proba[0][prediction[0]]
        
        print("\n--- 予測結果 ---")
        print(f"ファイル: {os.path.basename(NEW_IMAGE_PATH)}")
        print(f"予測された花の種類: {predicted_label} (確信度: {confidence:.2%})")

