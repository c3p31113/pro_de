import sqlite3
import os
from werkzeug.security import generate_password_hash

# ----------------------------------------
# ベースディレクトリ
# ----------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# DB ファイル
DB_NAME = os.path.join(BASE_DIR, "rover_database.db")

# サンプル画像ディレクトリ
IMAGE_DIR = os.path.join(BASE_DIR, "sample_images")


def reset_database():
    """
    Flask（Web）から呼び出すためのDB初期化関数
    """
    setup_database()


def setup_database():
    os.makedirs(IMAGE_DIR, exist_ok=True)

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    print("\n=== データベース初期化開始 ===")

    # ----------------------------------------
    # テーブル作成（存在しなければ）
    # ----------------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

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
    # routes 以外のデータを削除
    # ----------------------------------------
    print("\n=== 既存データ削除（routes は保持） ===")

    cur.execute("PRAGMA foreign_keys = OFF;")

    tables_to_clear = [
        "notifications",
        "detections",
        "analysis_sessions",
        "photos",
    ]

    for table in tables_to_clear:
        cur.execute(f"DELETE FROM {table};")
        print(f"✔ {table} をクリア")

    cur.execute("""
        DELETE FROM sqlite_sequence
        WHERE name IN ('notifications', 'detections', 'analysis_sessions', 'photos', 'users');
    """)

    cur.execute("PRAGMA foreign_keys = ON;")
    conn.commit()

    # ----------------------------------------
    # admin ユーザー作成
    # ----------------------------------------
    cur.execute(
        "INSERT INTO users (username, password) VALUES (?, ?)",
        ("admin", generate_password_hash("password"))
    )
    admin_id = cur.lastrowid
    print("✔ admin ユーザー作成（password: password）")

    conn.commit()

    # ----------------------------------------
    # routes の取得 or 作成
    # ----------------------------------------
    cur.execute("SELECT id FROM routes ORDER BY id LIMIT 1")
    row = cur.fetchone()

    if row:
        route_id = row[0]
        print(f"✔ 既存 route を使用: ID={route_id}")
    else:
        cur.execute(
            "INSERT INTO routes (user_id, name) VALUES (?, ?)",
            (admin_id, "サンプル経路")
        )
        route_id = cur.lastrowid
        print(f"✔ 新規 route 作成: ID={route_id}")

    conn.commit()

    # ----------------------------------------
    # sample_images を photos に登録
    # ----------------------------------------
    static_photo_dir = os.path.join(BASE_DIR, "static", "photos")
    os.makedirs(static_photo_dir, exist_ok=True)

    count = 0

    for filename in os.listdir(IMAGE_DIR):
        ext = os.path.splitext(filename)[1].lower()
        if ext not in [".jpg", ".jpeg", ".png", ".jfif"]:
            continue

        src = os.path.join(IMAGE_DIR, filename)
        dst = os.path.join(static_photo_dir, filename)

        with open(src, "rb") as fsrc, open(dst, "wb") as fdst:
            fdst.write(fsrc.read())

        cur.execute(
            "INSERT INTO photos (route_id, filename) VALUES (?, ?)",
            (route_id, filename)
        )

        count += 1
        print(f"✔ 写真登録: {filename}")

    conn.commit()
    conn.close()

    print(f"\n=== 完了：{count} 件の画像を登録しました ===")


if __name__ == "__main__":
    setup_database()
