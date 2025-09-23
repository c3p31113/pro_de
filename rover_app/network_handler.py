import asyncio
import websockets
import json
import database as db

# --- グローバル変数 ---
clients = {
    "robot": None,
    "browsers": set()
}
latest_video_frame = None

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
    print("✅ Robot connected on port 8888.")
    try:
        async for message in websocket:
            # メッセージがバイナリ(映像)かテキスト(JSON)かを判断
            if isinstance(message, bytes):
                global latest_video_frame
                latest_video_frame = message
            else:
                data = json.loads(message)
                command = data.get('command')

                if command == 'save_path':
                    # 経路保存コマンドの場合、データベースに書き込む
                    route_id = data.get('route_id')
                    path_data_json = json.dumps(data.get('path_data'))
                    # is_gps_pathもDBに保存すると、後で再生方法を区別できる（将来的な拡張）
                    db.query_db('UPDATE routes SET path_data = ? WHERE id = ?', [path_data_json, route_id])
                    print(f"✅ Route path for ID:{route_id} saved to database.")

                elif command == 'photo_taken':
                    # 写真撮影完了通知の場合、DBに写真情報を保存
                    route_id = data.get('route_id')
                    filename = data.get('filename')
                    # ★ここが修正点★
                    # locationキーが存在する場合のみ、その値を取得。なければNoneになる。
                    location = data.get('location')

                    # (注: photosテーブルにlocationカラムを追加する必要がある)
                    db.query_db('INSERT INTO photos (route_id, filename) VALUES (?, ?)',
                                [route_id, filename])
                    print(f"✅ Photo info for '{filename}' saved to database.")

                    # ブラウザにも撮影完了を通知
                    if clients["browsers"]:
                         await asyncio.gather(*[client.send(message) for client in clients["browsers"]], return_exceptions=True)

    finally:
        clients["robot"] = None
        print("❌ Robot disconnected.")

# --- ブラウザ専用のハンドラ (ポート8889) ---
async def browser_handler(websocket):
    """ブラウザからの接続を処理。操作命令をロボットに転送する。"""
    clients["browsers"].add(websocket)
    print(f"✅ Browser connected on port 8889. Total browsers: {len(clients['browsers'])}")
    try:
        async for command in websocket:
            if clients["robot"]:
                await clients["robot"].send(command)
    finally:
        clients["browsers"].remove(websocket)
        print(f"❌ Browser disconnected. Total browsers: {len(clients['browsers'])}")

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

def run_network_server():
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nNetwork handler server terminated.")