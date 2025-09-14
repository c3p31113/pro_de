import cv2
import numpy as np
import os
import sys
import joblib
from skimage import feature
import glob
from PIL import Image, ImageDraw, ImageFont

# --- 特徴量抽出関数 (変更なし) ---
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
    hog_feats = get_hog_features(image)
    lbp_feats = get_lbp_features(image)
    return np.concatenate([color_feats, hog_feats, lbp_feats])

# --- メイン処理 ---
if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # 入力・出力フォルダ、フォントのパスを設定
    TARGET_DIR = os.path.join(script_dir, "hantei")
    OUTPUT_DIR = os.path.join(script_dir, "dataset_results")
    FONT_PATH = os.path.join(script_dir, "HGRGE.TTC")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # モデルファイルのパス
    species_model_path = os.path.join(script_dir, 'plant_species_model.pkl')
    health_model_path = os.path.join(script_dir, 'plant_health_model.pkl')

    print("モデルファイルを読み込んでいます...")
    try:
        species_model = joblib.load(species_model_path)
        health_model = joblib.load(health_model_path)
    except Exception as e:
        print(f"エラー: モデルの読み込みに失敗しました。 {e}"); sys.exit(1)
    print("モデルの読み込み完了。")

    if not os.path.isdir(TARGET_DIR):
        print(f"エラー: 判定対象のフォルダが見つかりません: {TARGET_DIR}"); sys.exit(1)
        
    print("-" * 50)
    print(f"処理対象フォルダ: {TARGET_DIR}")
    
    image_paths = glob.glob(os.path.join(TARGET_DIR, '*.*'))
    image_paths = [p for p in image_paths if p.lower().endswith(('.png', '.jpg', '.jpeg'))]

    if not image_paths:
        print(f"フォルダ '{TARGET_DIR}' 内に判定対象の画像ファイルが見つかりませんでした。")
    else:
        print(f"--- {len(image_paths)} 件の画像を判定し、結果を保存します ---")
        for i, image_path in enumerate(image_paths):
            print(f"\n[{i+1}/{len(image_paths)}] 処理中: {os.path.basename(image_path)}")
            try:
                # 画像読み込み
                n = np.fromfile(image_path, np.uint8)
                image_cv = cv2.imdecode(n, cv2.IMREAD_COLOR)
                if image_cv is None: raise IOError("画像として読み込めません。")

                # 特徴量抽出
                features = extract_combined_features(image_cv).reshape(1, -1)

                species_probs = species_model['model'].predict_proba(features)[0]
                pred_species_idx = np.argmax(species_probs)
                species_confidence = species_probs[pred_species_idx]
                predicted_species = species_model['labels'][pred_species_idx]

                health_probs = health_model['model'].predict_proba(features)[0]
                pred_health_idx = np.argmax(health_probs)
                health_confidence = health_probs[pred_health_idx]
                predicted_health = health_model['labels'][pred_health_idx]

                # コンソールへの表示
                print(f"  -> 種類: {predicted_species} ({species_confidence:.1%}), 状態: {predicted_health} ({health_confidence:.1%})")

                # Pillowを使って画像に日本語テキストを描画
                image_pil = Image.fromarray(cv2.cvtColor(image_cv, cv2.COLOR_BGR2RGB))
                draw = ImageDraw.Draw(image_pil)
                font_size = int(image_pil.width / 30)
                font = ImageFont.truetype(FONT_PATH, font_size)
                
                text = f"種類: {predicted_species} ({species_confidence:.1%})\n状態: {predicted_health} ({health_confidence:.1%})"
                
                text_bbox = draw.textbbox((0, 0), text, font=font)
                text_width = text_bbox[2] - text_bbox[0]
                text_height = text_bbox[3] - text_bbox[1]
                position = (image_pil.width - text_width - 10, 10)
                
                draw.rectangle(
                    (position[0]-5, position[1]-5, position[0]+text_width+5, position[1]+text_height+5),
                    fill=(0,0,0,128)
                )
                draw.text(position, text, font=font, fill=(255, 255, 255))

                image_result = cv2.cvtColor(np.array(image_pil), cv2.COLOR_RGB2BGR)
                
                # 判定結果をファイルに保存
                output_filename = os.path.basename(image_path)
                output_path = os.path.join(OUTPUT_DIR, output_filename)
                
                is_success, im_buf_arr = cv2.imencode(os.path.splitext(output_path)[1], image_result)
                if is_success:
                    im_buf_arr.tofile(output_path)
                    print(f"  -> 結果を保存しました: {output_path}")
                else:
                    print("  -> 結果の保存に失敗しました。")

            except Exception as e:
                print(f"  -> 警告: 処理中にエラーが発生しました: {e}")
                continue

    print("-" * 50)
    print("全ての処理が完了しました。")