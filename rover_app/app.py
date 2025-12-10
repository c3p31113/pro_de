import threading
import os
from datetime import datetime
from functools import wraps
from flask import (
    Flask, render_template, request, redirect,
    url_for, session, jsonify, Response,
    abort, send_from_directory, render_template_string
)
from werkzeug.security import generate_password_hash, check_password_hash

# 独自のモジュール
import network_handler
from database import (
    get_db, query_db, init_db, init_app, get_routes_with_photos
)

# 画像解析・PDF関連
from kensyou_run_vision import analyze_image_from_db
from pdf_create import generate_disease_report

app = Flask(__name__)
app.secret_key = "change-this-secret-key" # 本番環境では複雑なキーに変更

# --- DB 初期化 ---
init_app(app)
with app.app_context():
    init_db()

# --- 画像保存フォルダ ---
PHOTO_DIR = os.path.join(app.static_folder, "photos")
RESULT_DIR = os.path.join(app.static_folder, "results")
os.makedirs(PHOTO_DIR, exist_ok=True)
os.makedirs(RESULT_DIR, exist_ok=True)


# 共通：ログイン必須デコレータ
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


# ログイン / ログアウト / ルート
@app.route("/")
def index():
    # app.pyのロジック: ログイン済みならTOPへ
    if "user_id" in session:
        return redirect(url_for("top"))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    # ログイン済みならリダイレクト
    if "user_id" in session:
        return redirect(url_for("top"))

    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        user = query_db(
            "SELECT * FROM users WHERE username = ?",
            [username],
            one=True
        )

        if user and check_password_hash(user["password"], password):
            session.clear() # セッションの競合を防ぐためクリア
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            return redirect(url_for("top"))
        else:
            error = "IDまたはパスワードが間違っています。" # app.pyのメッセージに統一

    return render_template("login.html", error=error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# トップページ
@app.route("/top")
@login_required
def top():
    return render_template("top.html", username=session.get("username"))


# 仮想マップ（経路選択）
@app.route("/select_route")
@login_required
def select_route():
    user_id = session["user_id"]
    routes = get_routes_with_photos(user_id)
    return render_template("select_route.html", routes=routes)


@app.route("/api/add_route", methods=["POST"])
@login_required
def api_add_route():
    # app.pyのJSON取得ロジックも考慮
    data = request.get_json() or request.json or {}
    name = data.get("name")
    if not name:
        return jsonify({"status": "error", "message": "Name is required"}), 400

    db_conn = get_db()
    cur = db_conn.cursor()
    cur.execute(
        "INSERT INTO routes (user_id, name) VALUES (?, ?)",
        (session["user_id"], name)
    )
    db_conn.commit()
    new_id = cur.lastrowid
    return jsonify({"status": "success", "new_route_id": new_id})


@app.route("/api/rename_route/<int:route_id>", methods=["POST"])
@login_required
def api_rename_route(route_id):
    data = request.get_json() or {}
    new_name = data.get("name", "").strip()
    if not new_name:
        return jsonify({"status": "error", "message": "New name is required"}), 400

    # 所有権確認
    route = query_db("SELECT id FROM routes WHERE id = ? AND user_id = ?", [route_id, session["user_id"]], one=True)
    if not route:
        return jsonify({"status": "error", "message": "Route not found or permission denied"}), 404

    query_db(
        "UPDATE routes SET name = ? WHERE id = ?",
        [new_name, route_id],
    )
    return jsonify({"status": "success"})

# ローバー操作
@app.route("/control/") # app.pyのようにIDなしも許容
@app.route("/control/<int:route_id>")
@login_required
def control(route_id=None):
    route_name = "新規経路"
    
    if route_id:
        route = query_db(
            "SELECT * FROM routes WHERE id = ? AND user_id = ?",
            [route_id, session["user_id"]],
            one=True
        )
        if route:
            route_name = route["name"]
        else:
            # 存在しない、または権限がない場合は選択画面へ
            return redirect(url_for("select_route"))
    
    # route_idがNoneの場合は "新規経路" として表示 (app.pyの挙動)
    return render_template(
        "control.html",
        route_id=route_id,
        route_name=route_name
    )


@app.route("/api/move", methods=["POST"])
@login_required
def api_move():
    data = request.get_json() or {}
    direction = data.get("direction")
    # 実機連携用のログ出力
    print(f"[DEBUG] MOVE command: {direction}")
    return jsonify({"status": "ok"})


@app.route("/api/photo", methods=["POST"])
@login_required
def api_photo():
    # 画像保存API (ダミー実装)
    data = request.get_json() or {}
    route_id = data.get("route_id")

    dummy_filename = "sample.jpg"
    dummy_path = os.path.join(PHOTO_DIR, dummy_filename)

    if not os.path.exists(dummy_path):
        return jsonify({"status": "error", "message": "sample.jpg missing"}), 500

    db_conn = get_db()
    cur = db_conn.cursor()
    cur.execute(
        "INSERT INTO photos (route_id, filename) VALUES (?, ?)",
        (route_id, dummy_filename)
    )
    db_conn.commit()
    new_photo_id = cur.lastrowid

    return jsonify({"status": "success", "photo_id": new_photo_id})


@app.route("/video_feed")
@login_required
def video_feed():
    dummy_filename = "sample.jpg"
    return send_from_directory(PHOTO_DIR, dummy_filename)

# 現在位置 / 設定
@app.route("/location")
@login_required
def location():
    return render_template("location.html")


@app.route("/settings")
@login_required
def settings():
    return render_template("settings.html")


# 異常検知フロー
@app.route("/notifications")
@login_required
def notifications_redirect():
    # トップメニューからは解析フローへ誘導
    return redirect(url_for("pre_analyze"))


@app.route("/pre_analyze")
@login_required
def pre_analyze():
    return render_template("index.html")


@app.route("/notifications_page")
@login_required
def notifications_page():
    # 通知一覧表示
    user_id = session["user_id"]

    notifications = query_db(
        """
        SELECT
            n.id,
            n.timestamp,
            n.event_type,
            n.severity,
            n.status,
            n.detection_id,
            d.result AS detection_result,
            d.confidence,
            p.id   AS photo_id,
            p.filename
        FROM notifications n
        LEFT JOIN detections d ON n.detection_id = d.id
        LEFT JOIN photos     p ON d.photo_id = p.id
        WHERE n.user_id = ?
        ORDER BY n.timestamp DESC
        """,
        [user_id]
    )

    return render_template("notifications.html", notifications=notifications)


# PDF レポート生成
@app.route("/create_report")
@login_required
def create_report():
    user_id = session["user_id"]
    pdf_buffer = generate_disease_report(user_id)

    if pdf_buffer is None:
        return "病害検知が無いためPDFを作成できません。", 400

    filename = f"disease_report_user{user_id}.pdf"

    return Response(
        pdf_buffer.getvalue(),
        mimetype="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

# 画像拡大ページ
@app.route("/image/<int:photo_id>")
@login_required
def show_image(photo_id):
    result_filename = f"photo_{photo_id}.jpg"
    if not os.path.exists(os.path.join(RESULT_DIR, result_filename)):
        return "画像が見つかりません", 404

    html = """
    <!DOCTYPE html>
    <html lang="ja">
    <head>
        <meta charset="UTF-8">
        <title>画像拡大表示</title>
        <style>
            body { background:#f7f7f7; text-align:center; margin:0; padding:20px; }
            img  { max-width:90%%; height:auto; border:3px solid #ccc; border-radius:10px; }
            h2   { font-family:sans-serif; color:#333; }
        </style>
    </head>
    <body>
        <h2>解析結果画像 (ID: {{ photo_id }})</h2>
        <img src="{{ url_for('result_image', photo_id=photo_id) }}">
    </body>
    </html>
    """
    return render_template_string(html, photo_id=photo_id)


#画像解析
def _analyze_local_photo(path):
    with open(path, "rb") as f:
        img_bytes = f.read()
    return analyze_image_from_db(img_bytes)


def _map_status_to_category(status_raw, plant_name):
    """
    kensyou_run_vision から返ってくるステータスを
    DBに保存するカテゴリ文字列へ変換する。

    ここではすべて日本語で統一：
      - 「バラではない」
      - 「普通」
      - 「異常」
    """
    # バラ以外 or 判定不能
    if plant_name is None or status_raw == "バラではない":
        return "バラではない"

    s_lower = str(status_raw).lower()

    # 「普通」扱い
    if (
        "healthy" in s_lower
        or "normal" in s_lower
        or "正常" in str(status_raw)
        or "普通" in str(status_raw)
    ):
        return "普通"

    # それ以外は「異常」
    return "異常"


@app.route("/analyze_db")
@login_required
def analyze_db():
    photos = query_db(
        """
        SELECT p.id, p.filename
        FROM photos p
        LEFT JOIN detections d ON d.photo_id = p.id
        WHERE d.id IS NULL
        """
    )

    results_for_view = []
    db_conn = get_db()
    cur = db_conn.cursor()

    # === 解析セッション作成 ===
    started = datetime.now().isoformat(timespec="seconds")
    cur.execute(
        "INSERT INTO analysis_sessions (user_id, started_at) VALUES (?, ?)",
        (session["user_id"], started)
    )
    db_conn.commit()
    session_id = cur.lastrowid

    for row in photos:
        photo_id = row["id"]
        filename = row["filename"]
        path = os.path.join(PHOTO_DIR, filename)

        if not os.path.exists(path):
            print(f"[WARN] photo not found: {path}")
            continue

        try:
            status_raw, conf, plant_name, annotated_bytes = _analyze_local_photo(path)

            # status_raw / plant_name は kensyou_run_vision 側で
            # 「普通」「異常」「バラではない」「バラ」等の日本語になっている想定
            category = _map_status_to_category(status_raw, plant_name)
            conf_value = float(conf) if conf is not None else None

            # --- 解析結果を detections へ登録（session_id 追加） ---
            cur.execute(
                "INSERT INTO detections (photo_id, plant_type, result, confidence, session_id) "
                "VALUES (?, ?, ?, ?, ?)",
                (photo_id, plant_name, category, conf_value, session_id)
            )
            db_conn.commit()
            detection_id = cur.lastrowid

            # --- 「異常」のときだけ notifications へ ---
            if category == "異常":
                cur.execute(
                    """
                    INSERT INTO notifications (user_id, detection_id, event_type, severity)
                    VALUES (?, ?, '病害検知', '高')
                    """,
                    (session["user_id"], detection_id)
                )
                db_conn.commit()

            # 解析結果画像を保存
            with open(os.path.join(RESULT_DIR, f"photo_{photo_id}.jpg"), "wb") as f:
                f.write(annotated_bytes)

            conf_display = "-" if conf_value is None else f"{conf_value:.1f}%"

            # 画面表示用：バラ or バラではない、日本語カテゴリ
            plant_display = plant_name or "バラではない"
            results_for_view.append(
                (photo_id, plant_display, category, conf_display)
            )

        except Exception as e:
            print("[ERROR] analyze failed:", e)
            # 失敗時も日本語で表示
            results_for_view.append((photo_id, "バラではない", "解析失敗", "-"))

    # === 解析終了時間を更新 ===
    finished = datetime.now().isoformat(timespec="seconds")
    cur.execute(
        "UPDATE analysis_sessions SET finished_at = ? WHERE id = ?",
        (finished, session_id)
    )
    db_conn.commit()

    return render_template("result_list.html", results=results_for_view)


@app.route("/result_image/<int:photo_id>")
@login_required
def result_image(photo_id):
    filename = f"photo_{photo_id}.jpg"
    path = os.path.join(RESULT_DIR, filename)

    if not os.path.exists(path):
        return "画像なし", 404

    return send_from_directory(RESULT_DIR, filename)



# 解析履歴ページ
@app.route("/analysis_history")
@login_required
def analysis_history():
    sessions = query_db(
        """
        SELECT * FROM analysis_sessions
        WHERE user_id = ?
        ORDER BY started_at DESC
        """,
        [session["user_id"]]
    )
    return render_template("analysis_history.html", sessions=sessions)



# セッションごとの解析結果
@app.route("/analysis_session/<int:session_id>")
@login_required
def analysis_session_detail(session_id):
    detections = query_db(
        """
        SELECT d.*, p.filename
        FROM detections d
        LEFT JOIN photos p ON d.photo_id = p.id
        WHERE d.session_id = ?
        ORDER BY d.id DESC
        """,
        [session_id]
    )

    return render_template("analysis_session_detail.html",
                           detections=detections,
                           session_id=session_id)


#起動
if __name__ == "__main__":
    with app.app_context():
        # adminユーザー作成 (app.pyのロジック統合)
        if not query_db("SELECT * FROM users WHERE username = ?", ["admin"], one=True):
            conn = get_db()
            conn.execute(
                "INSERT INTO users (username, password) VALUES (?, ?)",
                ["admin", generate_password_hash("password")]
            )
            conn.commit()
            print("[INFO] admin user created.")

    # WebSocketサーバー起動
    ws_thread = threading.Thread(target=network_handler.run_network_server, args=(app,))
    ws_thread.daemon = True
    ws_thread.start()

    print("Flask server starting on http://172.20.21.58")

    app.run(host="0.0.0.0", port=5000, threaded=True, use_reloader=False)