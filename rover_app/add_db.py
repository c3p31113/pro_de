import sqlite3
import json
import time

# --- 設定 ---
# 実際のデータベースファイル名に合わせて変更してください
# flaskの構成によっては "instance/database.db" などの場合もあります
DB_PATH = "rover_database.db"

# ユーザーID (通常は1)
USER_ID = 1

# --- ダミーの座標データ (横浜周辺を想定した例) ---
# type: 'start' (開始), 'move' (移動), 'photo' (撮影), 'stop' (終了)
dummy_path = [
    {"lat": 35.465700, "lon": 139.622000, "type": "start"},
    {"lat": 35.465710, "lon": 139.622010, "type": "move"},
    {"lat": 35.465720, "lon": 139.622020, "type": "move"},
    {"lat": 35.465730, "lon": 139.622030, "type": "photo"}, # ここで撮影動作が入る
    {"lat": 35.465740, "lon": 139.622040, "type": "move"},
    {"lat": 35.465750, "lon": 139.622050, "type": "move"},
    {"lat": 35.465760, "lon": 139.622060, "type": "stop"}
]

def add_dummy_route():
    try:
        # データベースに接続
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # 経路データをJSON文字列に変換
        json_data = json.dumps(dummy_path)
        
        # ルート名
        route_name = f"テスト経路_{int(time.time())}"

        # INSERT実行
        cursor.execute(
            "INSERT INTO routes (user_id, name, path_data) VALUES (?, ?, ?)",
            (USER_ID, route_name, json_data)
        )
        
        conn.commit()
        new_id = cursor.lastrowid
        print(f"成功: 新しいダミー経路を作成しました。")
        print(f"ID: {new_id}")
        print(f"名前: {route_name}")
        print("Web画面をリロードして確認してください。")

    except sqlite3.Error as e:
        print(f"エラーが発生しました: {e}")
        print("DBファイルのパスが間違っていないか確認してください。")
    
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    add_dummy_route()