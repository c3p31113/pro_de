import cv2
import numpy as np
import os
import joblib
from PIL import Image, ImageDraw, ImageFont
import glob

def draw_japanese_text_with_bg(image, text, org, font_path, font_size, text_color, bg_color, alpha=0.6):
    # OpenCVの画像(BGR)をPillowの画像(RGB)に変換
    pil_image = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
    
    # フォントを読み込み
    try:
        font = ImageFont.truetype(font_path, font_size)
    except IOError:
        print(f"警告: フォントファイル '{font_path}' が見つかりません。Pillowのデフォルトフォントで代替します。")
        font = ImageFont.load_default()

    # テキストの描画サイズを取得 (bboxを使うのが正確)
    text_bbox = ImageDraw.Draw(pil_image).textbbox(org, text, font=font)
    
    # 背景の矩形を計算
    padding = max(5, int(font_size * 0.2))
    bg_top_left = (org[0] - padding, org[1] - padding)
    bg_bottom_right = (text_bbox[2] + padding, text_bbox[3] + padding)

    # 半透明の背景を描画するためのオーバーレイを作成
    overlay = Image.new('RGBA', pil_image.size, (255, 255, 255, 0))
    draw_overlay = ImageDraw.Draw(overlay)
    
    bg_color_with_alpha = bg_color + (int(255 * alpha),)
    draw_overlay.rectangle([bg_top_left, bg_bottom_right], fill=bg_color_with_alpha)

    # 元の画像とオーバーレイを合成
    pil_image = Image.alpha_composite(pil_image.convert('RGBA'), overlay)

    # テキストを描画
    draw_text = ImageDraw.Draw(pil_image)
    draw_text.text(org, text, font=font, fill=text_color)

    # Pillowの画像(RGBA)をOpenCVの画像(BGR)に変換して返す
    return cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGBA2BGR)

def extract_hsv_histogram_from_path(image_path, resize_dim=(256, 256)):

    image = cv2.imread(image_path)
    if image is None:
        print(f"警告: 画像を読み込めませんでした - {image_path}")
        return None, None
    original_image = image.copy()
    image_resized = cv2.resize(image, resize_dim)
    hsv_image = cv2.cvtColor(image_resized, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv_image], [0, 1], None, [30, 32], [0, 180, 0, 256])
    cv2.normalize(hist, hist, 0, 1, cv2.NORM_MINMAX)
    return hist.flatten(), original_image

def draw_prediction_on_image(image, predicted_label, confidence, font_path):

    img_h, img_w, _ = image.shape

    # --- 画像サイズに基づいてフォントサイズを動的に調整 ---
    font_size = int((img_w / 1280.0) * 40)
    font_size = np.clip(font_size, 18, 100) # 最小・最大サイズを設定

    # --- 描画開始位置を画像の左上からのマージンで指定 ---
    margin_x = int(img_w * 0.02)
    margin_y = int(img_h * 0.02)
    org = (margin_x, margin_y)

    # --- ラベルに応じて日本語のテキストと背景色を決定 ---
    if predicted_label == 'normal':
        display_label = "健康"
        bg_color = (0, 128, 0)
    elif predicted_label == 'disease':
        display_label = "病害"
        bg_color = (180, 0, 0) # BGR順なので赤は(B,G,R)
    else:
        display_label = predicted_label
        bg_color = (128, 128, 128)

    text = f"{display_label} ({confidence:.1%})"
    
    # --- 新しい描画関数を呼び出す ---
    result_image = draw_japanese_text_with_bg(
        image, text, org, font_path, font_size,
        text_color=(255, 255, 255), bg_color=bg_color, alpha=0.6
    )
    return result_image

# --- メイン処理 ---
script_dir = os.path.dirname(os.path.abspath(__file__))
MODEL_FILENAME = os.path.join(script_dir, 'plant_health_model.pkl')
TARGET_DIR = os.path.join(script_dir, "hantei")
FONT_PATH = os.path.join(script_dir, "HGRGE.ttc")
OUTPUT_DIR = os.path.join(script_dir, "detected_results")

os.makedirs(OUTPUT_DIR, exist_ok=True)

if not os.path.exists(MODEL_FILENAME):
    print(f"エラー: モデルファイル '{MODEL_FILENAME}' が見つかりません。先に学習用スクリプトを実行してください。")
elif not os.path.isdir(TARGET_DIR):
    print(f"エラー: 判定対象のフォルダ '{TARGET_DIR}' が見つかりません。")
elif not os.path.exists(FONT_PATH):
    print(f"エラー: 指定されたフォントファイルが見つかりません: '{FONT_PATH}'")
    print("FONT_PATHの値を、お使いのPCに存在するフォントファイルのパスに修正してください。")
else:
    print(f"モデルファイル '{MODEL_FILENAME}' を読み込んでいます...")
    loaded_data = joblib.load(MODEL_FILENAME)
    loaded_model = loaded_data['model']
    LABELS = loaded_data['labels']
    print("モデルとラベルの読み込みが完了しました。")

    image_paths = glob.glob(os.path.join(TARGET_DIR, '*.jpg')) + \
                  glob.glob(os.path.join(TARGET_DIR, '*.jpeg')) + \
                  glob.glob(os.path.join(TARGET_DIR, '*.png'))

    if not image_paths:
        print(f"フォルダ '{TARGET_DIR}' 内に判定対象の画像ファイルが見つかりませんでした。")
    else:
        print(f"\n--- {len(image_paths)} 件の画像を判定します ---")

        # enumerateを使い、ループのインデックス(i)を取得
        for i, image_path in enumerate(image_paths):
            print(f"\n>> 処理中: {os.path.basename(image_path)}")
            
            new_features, original_image = extract_hsv_histogram_from_path(image_path)

            if new_features is not None:
                prediction = loaded_model.predict([new_features])
                prediction_proba = loaded_model.predict_proba([new_features])
                
                predicted_index = prediction[0]
                predicted_label = LABELS[predicted_index]
                confidence = prediction_proba[0][predicted_index]
                
                print(f"   予測結果: {predicted_label} (確信度: {confidence:.2%})")
                
                result_image = draw_prediction_on_image(original_image, predicted_label, confidence, FONT_PATH)

                filename = os.path.basename(image_path)
                output_path = os.path.join(OUTPUT_DIR, f"result_{os.path.splitext(filename)[0]}.jpg")
                cv2.imwrite(output_path, result_image)
                print(f"   結果を '{output_path}' に保存しました。")

                if i == 0:
                    print("\n   最初の画像の結果をウィンドウに表示します。")
                    print("   何かキーを押すとウィンドウが閉じて、残りの処理を続行します。")
                    cv2.imshow('最初の画像の結果', result_image)
                    cv2.waitKey(0)
                    cv2.destroyAllWindows()
