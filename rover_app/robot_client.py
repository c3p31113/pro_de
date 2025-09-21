import asyncio
import websockets
import json
import move
from camera_opencv import Camera
import time
import os

# --- 設定 ---
PC_IP_ADDRESS = "192.168.1.8" # あなたのPCのIPアドレス
WEBSOCKET_URI = f"ws://{PC_IP_ADDRESS}:8888" # ロボット専用ポート

# 写真を保存するディレクトリ
PHOTO_SAVE_DIR = "/home/a-18/test1/photos" # ご自身の環境に合わせて変更してください

# --- メイン処理 ---
async def robot_main():
    # カメラを初期化
    cam = Camera()
    
    # 写真保存ディレクトリがなければ作成
    os.makedirs(PHOTO_SAVE_DIR, exist_ok=True)
    print(f"Photo save directory: {PHOTO_SAVE_DIR}")

    # サーバーへ再接続し続けるループ
    while True:
        try:
            async with websockets.connect(WEBSOCKET_URI) as websocket:
                print("✅ Connected to PC server.")

                # タスク1: PCからの命令を受信し続ける
                async def receive_commands():
                    async for message in websocket:
                        try:
                            data = json.loads(message)
                            command = data.get('command')
                            route_id = data.get('route_id') # ルートIDも受け取る
                            
                            print(f"Received command: '{command}' for route: {route_id}")
                            
                            speed = 60 # 速度

                            if command == 'forward':
                                move.move(speed, 'forward', 'no')
                            elif command == 'backward':
                                move.move(speed, 'backward', 'no')
                            elif command == 'left':
                                move.move(speed, 'no', 'left')
                            elif command == 'right':
                                move.move(speed, 'no', 'right')
                            elif command == 'stop':
                                move.motorStop()
                            elif command == 'take_photo':
                                # 写真を撮影してファイル名を生成
                                filename = f"route_{route_id}_{int(time.time())}.jpg"
                                filepath = os.path.join(PHOTO_SAVE_DIR, filename)
                                
                                if cam.take_photo(filepath):
                                    print(f"📸 Photo saved: {filepath}")
                                    # 撮影成功をサーバーに通知
                                    response = {'command': 'take_photo', 'status': 'ok', 'filename': filename}
                                    await websocket.send(json.dumps(response))
                                else:
                                    print("❌ Failed to take photo.")

                        except json.JSONDecodeError:
                            print(f"Error: Received non-JSON message: {message}")
                        except Exception as e:
                            print(f"Error processing command: {e}")

                # タスク2: カメラ映像をPCに送信し続ける
                async def stream_video():
                    while True:
                        frame = cam.get_frame()
                        if frame:
                            await websocket.send(frame)
                        await asyncio.sleep(1/30) # 約30fps

                # 2つのタスクを並行して実行
                await asyncio.gather(receive_commands(), stream_video())

        except (websockets.exceptions.ConnectionClosed, ConnectionRefusedError):
            print("Connection lost. Reconnecting in 5 seconds...")
            await asyncio.sleep(5)
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            print("Retrying in 5 seconds...")
            await asyncio.sleep(5)


if __name__ == "__main__":
    move.setup()
    try:
        asyncio.run(robot_main())
    except KeyboardInterrupt:
        print("\nProgram terminated by user.")
    finally:
        move.destroy()