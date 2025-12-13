import sqlite3
import os
from werkzeug.security import generate_password_hash

# ----------------------------------------
# ベースディレクトリ（setup_db.py がある場所）
# ----------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# DB を project_db 配下に保存
DB_NAME = os.path.join(BASE_DIR, "rover_database.db")

# sample_images01 の絶対パスを指定
IMAGE_DIR = os.path.join(BASE_DIR, "sample_images")

def setup_database():
    # sample_images01 がなければ作成
    os.makedirs(IMAGE_DIR, exist_ok=True)

    # DB 接続
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    print("\n=== データベース初期化開始 ===")

    # ----------------------------------------
    # users テーブル
    # ----------------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    cur.execute("SELECT * FROM users WHERE username = ?", ("admin",))
    if cur.fetchone() is None:
        cur.execute(
            "INSERT INTO users (username, password) VALUES (?, ?)",
            ("admin", generate_password_hash("password"))
        )
        print("✔ admin（password: password）を作成しました。")
    conn.commit()

    # ----------------------------------------
    # routes テーブル
    # ----------------------------------------
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

    cur.execute("SELECT COUNT(*) FROM routes")
    if cur.fetchone()[0] == 0:
        cur.execute("INSERT INTO routes (user_id, name) VALUES (?, ?)", (1, "サンプル経路"))
        route_id = cur.lastrowid
        print(f"✔ route 作成: ID={route_id}")
    else:
        cur.execute("SELECT id FROM routes ORDER BY id LIMIT 1")
        route_id = cur.fetchone()[0]
        print(f"✔ 既存の route を使用: ID={route_id}")

    conn.commit()

    # ----------------------------------------
    # photos テーブル
    # ----------------------------------------
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

    # ----------------------------------------
    # analysis_sessions、detections、notifications
    # ----------------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS analysis_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            started_at DATETIME NOT NULL,
            finished_at DATETIME,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS detections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            photo_id INTEGER,
            plant_type TEXT,
            result TEXT,
            confidence REAL,
            session_id INTEGER,
            FOREIGN KEY (photo_id) REFERENCES photos (id),
            FOREIGN KEY (session_id) REFERENCES analysis_sessions (id)
        )
    """)

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

    # ----------------------------------------
    # sample_images01 の画像を DB に登録
    # ----------------------------------------
    static_photo_dir = os.path.join(BASE_DIR, "static", "photos")
    os.makedirs(static_photo_dir, exist_ok=True)

    count = 0

    for filename in os.listdir(IMAGE_DIR):
        # 拡張子チェックを強化
        ext = os.path.splitext(filename)[1].lower()
        if ext not in [".jpg", ".jpeg", ".png", ".jfif"]:
            continue

        src = os.path.join(IMAGE_DIR, filename)
        dst = os.path.join(static_photo_dir, filename)

        # static/photos にコピー
        with open(src, "rb") as fsrc, open(dst, "wb") as fdst:
            fdst.write(fsrc.read())

        # DB に未登録なら追加
        cur.execute(
            "SELECT id FROM photos WHERE route_id = ? AND filename = ?",
            (route_id, filename)
        )
        if cur.fetchone() is None:
            cur.execute(
                "INSERT INTO photos (route_id, filename) VALUES (?, ?)",
                (route_id, filename)
            )
            count += 1
            print(f"✔ 写真登録: {filename}")
        else:
            print(f"・既に登録済み: {filename}")

    conn.commit()
    conn.close()

    print(f"\n=== 完了：{count} 件の画像を登録しました ===")


if __name__ == "__main__":
    setup_database()

