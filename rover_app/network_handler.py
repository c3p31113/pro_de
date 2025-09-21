import asyncio
import websockets

# --- グローバル変数 ---
# 接続されているクライアントを管理
clients = {
    "robot": None,
    "browsers": set()
}
# 最新のビデオフレームを保存
latest_video_frame = None

# --- ブラウザへ映像を配信し続けるタスク ---
async def broadcast_frames():
    """30fpsで全ブラウザに映像を送り続ける"""
    while True:
        if latest_video_frame and clients["browsers"]:
            # コルーチンを作成し、asyncio.waitで並行して送信
            await asyncio.gather(
                *[client.send(latest_video_frame) for client in clients["browsers"]]
            )
        # 約30fpsになるように待機
        await asyncio.sleep(1/30)

# --- ロボット専用のハンドラ (ポート8888) ---
async def robot_handler(websocket):
    """ロボットからの接続を処理。映像フレームを受け取るだけ。"""
    clients["robot"] = websocket
    print("✅ Robot connected on port 8888.")
    try:
        # ロボットからはビデオフレームが送られ続ける
        async for frame in websocket:
            global latest_video_frame
            latest_video_frame = frame
    finally:
        clients["robot"] = None
        print("❌ Robot disconnected.")

# --- ブラウザ専用のハンドラ (ポート8889) ---
async def browser_handler(websocket):
    """ブラウザからの接続を処理。操作命令を受け取るだけ。"""
    clients["browsers"].add(websocket)
    print(f"✅ Browser connected on port 8889. Total browsers: {len(clients['browsers'])}")
    try:
        # ブラウザからは操作命令が送られてくる
        async for command in websocket:
            if clients["robot"]:
                await clients["robot"].send(command)
    finally:
        clients["browsers"].remove(websocket)
        print(f"❌ Browser disconnected. Total browsers: {len(clients['browsers'])}")

# --- サーバー起動処理 ---
async def main():
    print("Starting network handler...")
    # 映像配信タスクを開始
    broadcaster = asyncio.create_task(broadcast_frames())
    
    # ロボット用サーバー(8888)とブラウザ用サーバー(8889)を同時に起動
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