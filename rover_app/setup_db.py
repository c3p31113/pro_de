# setup_db.py
import sqlite3
import os
from werkzeug.security import generate_password_hash

DB_NAME = "rover_database.db"
IMAGE_DIR = "sample_images"


def setup_database():
    # sample_images フォルダがなければ作成
    if not os.path.exists(IMAGE_DIR):
        os.makedirs(IMAGE_DIR)

    # DBへ接続
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    print("\n=== データベース初期化開始 ===")

    # -----------------------------------
    # 1. users テーブル
    # -----------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    # admin 登録（なければ）
    cur.execute("SELECT * FROM users WHERE username = ?", ("admin",))
    if cur.fetchone() is None:
        cur.execute(
            "INSERT INTO users (username, password) VALUES (?, ?)",
            ("admin", generate_password_hash("password"))
        )
        print("✔ admin（password: password）を作成しました。")
    conn.commit()

    # -----------------------------------
    # 2. routes テーブル
    # -----------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS routes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT NOT NULL,
            path_data TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)

    # 解析用のデフォルト経路を1つ作る
    cur.execute("INSERT INTO routes (user_id, name) VALUES (?, ?)",
                (1, "サンプル経路"))
    route_id = cur.lastrowid
    print(f"✔ route 作成: ID={route_id}")

    conn.commit()

    # -----------------------------------
    # 3. photos テーブル
    # -----------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            route_id INTEGER,
            filename TEXT NOT NULL,
            taken_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            latitude REAL,
            longitude REAL,
            FOREIGN KEY (route_id) REFERENCES routes (id)
        )
    """)

    # -----------------------------------
    # 4. detections テーブル（解析結果）
    # -----------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS detections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            photo_id INTEGER,
            plant_type TEXT,
            result TEXT,
            confidence REAL,
            FOREIGN KEY (photo_id) REFERENCES photos (id)
        )
    """)

    # -----------------------------------
    # 5. notifications テーブル
    # -----------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            detection_id INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            event_type TEXT NOT NULL,
            severity TEXT,
            status TEXT DEFAULT '未対応',
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (detection_id) REFERENCES detections (id)
        )
    """)

    conn.commit()

    # ----------------------------------------------------
    # sample_images 内の画像を photos に登録
    # ----------------------------------------------------
    count = 0
    for filename in os.listdir(IMAGE_DIR):
        if filename.lower().endswith((".jpg", ".jpeg", ".png")):
            filepath = os.path.join(IMAGE_DIR, filename)

            # static/photos にコピーしないと Flask が読み取れないため
            static_photo_dir = os.path.join("static", "photos")
            os.makedirs(static_photo_dir, exist_ok=True)
            dst = os.path.join(static_photo_dir, filename)

            with open(filepath, "rb") as src, open(dst, "wb") as out:
                out.write(src.read())

            cur.execute(
                "INSERT INTO photos (route_id, filename) VALUES (?, ?)",
                (route_id, filename)
            )
            count += 1
            print(f"✔ 写真登録: {filename}")

    conn.commit()

    print(f"\n=== 完了：{count} 枚の画像を登録しました ===")
    conn.close()


if __name__ == "__main__":
    setup_database()
