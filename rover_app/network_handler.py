import asyncio
import websockets
import json
import database as db
import os
import base64

# --- グローバル変数 ---
clients = {
    "robot": None,
    "browsers": set()
}
latest_video_frame = None
STATIC_DIR = os.path.dirname(os.path.abspath(__file__))
PHOTO_SAVE_DIR = os.path.join(STATIC_DIR, 'static', 'photos')

flask_app = None

# --- ブラウザへ映像を配信し続けるタスク ---
async def broadcast_frames():
    """30fpsで全ブラウザに映像を送り続ける"""
    while True:
        if latest_video_frame and clients["browsers"]:
            await asyncio.gather(
                *[client.send(latest_video_frame) for client in clients["browsers"]],
                return_exceptions=True  # 送信エラーが発生してもタスクを止めない
            )
        await asyncio.sleep(1/30)

# --- ロボット専用のハンドラ (ポート8888) ---
async def robot_handler(websocket):
    """ロボットからの接続を処理。映像フレームと各種通知を受け取る。"""
    clients["robot"] = websocket
    print("Robot connected on port 8888.")
    try:
        async for message in websocket:
            # メッセージがバイナリ(映像)かテキスト(JSON)かを判断
            if isinstance(message, bytes):
                global latest_video_frame
                latest_video_frame = message
            else:
                data = json.loads(message)
                command = data.get('command')
                msg_type = data.get('type')

                if command == 'save_path':
                    # 経路保存コマンドの場合、データベースに書き込む
                    route_id = data.get('route_id')
                    path_data_json = json.dumps(data.get('path_data'))
                    if flask_app:
                        with flask_app.app_context():
                            db.query_db('UPDATE routes SET path_data = ? WHERE id = ?', [path_data_json, route_id])
                            print(f"Route path for ID:{route_id} saved to database.")
                    else:
                        print("Error: flask_app is not initialized.")

                elif command == 'photo_taken':
                    print("写真撮影通知を受信...")
                    route_id = data.get('route_id')
                    original_filename = data.get('filename')
                    location_data = data.get('location')
                    image_data_base64 = data.get('image_data') 

                    route_name = "unknown_route"
                    if flask_app:
                        with flask_app.app_context():
                            route_name = db.get_route_name_by_id(route_id) or "unknown_route"

                            safe_route_name = "".join(c if c.isalnum() else "_" for c in route_name)
                            route_specific_dir = os.path.join(PHOTO_SAVE_DIR, safe_route_name)
                            try:
                                os.makedirs(route_specific_dir, exist_ok=True)
                            except Exception as e:
                                route_specific_dir = PHOTO_SAVE_DIR

                            # 写真保存
                            if image_data_base64 and original_filename:
                                try:
                                    save_path = os.path.join(route_specific_dir, original_filename)
                                    image_data = base64.b64decode(image_data_base64)
                                    with open(save_path, "wb") as f:
                                        f.write(image_data)
                                    print(f"写真をサーバーに保存しました: {save_path}")
                                except Exception as e:
                                    print(f"サーバーへの写真保存に失敗: {e}")

                            new_relative_path = os.path.join(safe_route_name, original_filename)
                            new_relative_path = new_relative_path.replace(os.path.sep, '/') 

                            # DB保存
                            if route_id and location_data:
                                db.add_photo_record(route_id, new_relative_path, location_data[0], location_data[1])
                    
                    # (ブラウザへの転送処理はDBを使わないのでそのまま)
                    if 'image_data' in data:
                        del data['image_data'] 
                    data['filename'] = new_relative_path 
                    if clients["browsers"]:
                         await asyncio.gather(*[client.send(json.dumps(data)) for client in clients["browsers"]], return_exceptions=True)

                elif msg_type == 'gps_update' or msg_type == 'gps_status':
                    if clients["browsers"]:
                         await asyncio.gather(*[client.send(message) for client in clients["browsers"]], return_exceptions=True)

                else:
                    if clients["browsers"]:
                         await asyncio.gather(*[client.send(message) for client in clients["browsers"]], return_exceptions=True)

    finally:
        clients["robot"] = None
        print("❌ Robot disconnected.")

# --- ブラウザ専用のハンドラ (ポート8889) ---
async def browser_handler(websocket):
    """ブラウザからの接続を処理。操作命令をロボットに転送する。"""
    clients["browsers"].add(websocket)
    print(f"Browser connected. Total: {len(clients['browsers'])}")
    try:
        async for message in websocket:
            # 受信データをJSONとしてパース
            try:
                data = json.loads(message)
            except json.JSONDecodeError:
                continue

            command = data.get("command")

            # 経路再生コマンドの場合、DBから経路データを取得して付与
            if command == "replay_path":
                route_id = data.get("route_id")
                
                if flask_app:
                    with flask_app.app_context():
                        # DB参照
                        row = db.query_db("SELECT path_data FROM routes WHERE id = ?", [route_id], one=True)
                        
                        if row and row["path_data"]:
                            # JSON文字列として保存されているデータをリストに戻す
                            data["path_data"] = json.loads(row["path_data"])
                            print(f"Replay: Path data loaded for Route ID {route_id}")
                        else:
                            print(f"Replay: No path data found for Route ID {route_id}")
                else:
                     print("Error: flask_app is not initialized.")
                
                # データを更新したJSON文字列を再生成
                message = json.dumps(data)

            # ロボットへ転送
            if clients["robot"]:
                await clients["robot"].send(message)
    finally:
        clients["browsers"].remove(websocket)
        print(f"Browser disconnected. Total: {len(clients['browsers'])}")

# --- サーバー起動処理 ---
async def main():
    print("Starting network handler...")
    broadcaster = asyncio.create_task(broadcast_frames())

    robot_server = websockets.serve(robot_handler, "0.0.0.0", 8888)
    browser_server = websockets.serve(browser_handler, "0.0.0.0", 8889)

    print("Network handler server started.")
    print("  - Robot should connect to ws://<PC_IP>:8888")
    print("  - Browsers should connect to ws://<PC_IP>:8889")

    await asyncio.gather(robot_server, browser_server, broadcaster)

def run_network_server(app):
    global flask_app
    flask_app = app
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nNetwork handler server terminated.")