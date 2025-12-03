import sqlite3
from flask import g
import os

# データベースファイルのパスを正しく設定
DATABASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(DATABASE_DIR, "rover_database.db")


def get_db():
    """リクエスト内で共有されるデータベース接続を取得する"""
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE_PATH)
        db.row_factory = sqlite3.Row
    return db


def close_connection(exception):
    """リクエスト終了時にデータベース接続を閉じる"""
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()


def init_db():
    """データベースのテーブルを初期化する"""
    # 既にファイルが存在する場合は初期化しない
    if os.path.exists(DATABASE_PATH):
        print("Database already exists. Skipping initialization.")
        return

    print("Initializing new database...")
    with sqlite3.connect(DATABASE_PATH) as conn:
        cursor = conn.cursor()

        # 1. users テーブル
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
            """
        )

        # 2. routes テーブル
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS routes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                name TEXT NOT NULL,
                path_data TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
            """
        )

        # 3. photos テーブル (GPS情報を含む)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS photos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                route_id INTEGER,
                filename TEXT NOT NULL,
                taken_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                latitude REAL,
                longitude REAL,
                FOREIGN KEY (route_id) REFERENCES routes (id)
            )
            """
        )

        # 4. detections テーブル (画像解析結果用・新規追加)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS detections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                photo_id INTEGER,
                plant_type TEXT,
                result TEXT,
                confidence REAL,
                FOREIGN KEY (photo_id) REFERENCES photos (id)
            )
            """
        )

        # 5. notifications テーブル (異常検知連携用・拡張)
        cursor.execute(
            """
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
            """
        )

        conn.commit()
    print("Database initialized.")


def query_db(query, args=(), one=False):
    """
    データベースに対してクエリを実行し、結果を取得する
    （SELECT 以外も commit する汎用ラッパー）
    """
    db = get_db()
    cur = db.execute(query, args)
    rv = cur.fetchall()
    db.commit()
    cur.close()
    return (rv[0] if rv else None) if one else rv


def init_app(app):
    """FlaskアプリにDBの後片付け処理を登録する"""
    app.teardown_appcontext(close_connection)


# ============================================================
# 便利関数群
# ============================================================

def get_routes_with_photos(user_id):
    """
    ユーザーの全ルートと、関連する写真情報を取得する。
    route.thumbnail には最初の写真（なければ placeholder.jpg）を設定。
    """
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM routes WHERE user_id = ? ORDER BY created_at DESC",
        [user_id],
    )
    routes = cursor.fetchall()

    if not routes:
        conn.close()
        return []

    routes_with_photos = []
    for route in routes:
        cursor.execute(
            "SELECT filename FROM photos WHERE route_id = ? ORDER BY taken_at ASC",
            [route["id"]],
        )
        photos = cursor.fetchall()

        route_dict = dict(route)
        route_dict["photos"] = [p["filename"] for p in photos]
        # サムネイル（最初の写真）を設定。写真がなければ placeholder.jpg
        route_dict["thumbnail"] = (
            photos[0]["filename"] if photos else "placeholder.jpg"
        )
        routes_with_photos.append(route_dict)

    conn.close()
    return routes_with_photos


def get_route_name_by_id(route_id):
    """
    ルートIDからルート名を取得する (network_handler等で使用)
    """
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT name FROM routes WHERE id = ?", [route_id])
        route = cursor.fetchone()
        if route:
            return route["name"]
        else:
            return None
    except Exception as e:
        print(f"DB Error in get_route_name_by_id: {e}")
        return None
    finally:
        conn.close()


def add_photo_record(route_id, filename, lat, lon):
    """
    写真の記録をデータベースに追加する (GPS情報付き)
    """
    conn = sqlite3.connect(DATABASE_PATH)
    try:
        conn.execute(
            "INSERT INTO photos (route_id, filename, latitude, longitude) VALUES (?, ?, ?, ?)",
            (route_id, filename, lat, lon)
        )
        conn.commit()
        print(f"DB: Photo record saved: {filename}, ({lat}, {lon})")
    except Exception as e:
        print(f"DB Error in add_photo_record: {e}")
    finally:
        conn.close()