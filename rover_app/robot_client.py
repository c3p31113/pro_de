import asyncio
import websockets
import json
import move
from camera_opencv import Camera
import time
import os

# --- ライブラリのインポートを試行 ---
try:
    import serial
    import pynmea2
    IS_GPS_AVAILABLE = True
except ImportError:
    IS_GPS_AVAILABLE = False
    print("⚠️ GPS libraries (pyserial, pynmea2) not found. Running in non-GPS mode.")

# --- 設定 ---
PC_IP_ADDRESS = "192.168.1.8" # あなたのPCのIPアドレス
WEBSOCKET_URI = f"ws://{PC_IP_ADDRESS}:8888"
PHOTO_SAVE_DIR = "/home/pi/rover_photos"

# --- グローバル変数 ---
current_gps_coords = None
is_gps_connected = False

# --- GPSモジュールからデータを読み取るタスク ---
def gps_reader_task():
    """バックグラウンドでGPSデータを読み取り、接続状態を更新する"""
    global current_gps_coords, is_gps_connected
    if not IS_GPS_AVAILABLE:
        return # ライブラリがなければ何もしない

    while True: # 接続が切れても再試行し続ける
        try:
            # ご使用のGPSモジュールに合わせてシリアルポート名を変更
            ser = serial.Serial('/dev/ttyAMA0', 9600, timeout=5.0)
            print("🛰️ GPS module connected. Waiting for data...")
            is_gps_connected = True
            
            while True:
                line = ser.readline().decode('ascii', errors='replace')
                if line.startswith('$GPGGA'):
                    msg = pynmea2.parse(line)
                    if msg.latitude != 0.0: # 有効なデータか確認
                        current_gps_coords = (msg.latitude, msg.longitude)
        except serial.SerialException:
            if is_gps_connected:
                print("❌ GPS module disconnected. Will retry.")
            is_gps_connected = False
            current_gps_coords = None
            time.sleep(5) # 5秒後に再接続を試みる
        except Exception as e:
            # print(f"GPS read error: {e}")
            pass

# --- メイン処理 ---
async def robot_main():
    cam = Camera()
    os.makedirs(PHOTO_SAVE_DIR, exist_ok=True)

    # GPS読み取りを別スレッドで開始
    import threading
    if IS_GPS_AVAILABLE:
        gps_thread = threading.Thread(target=gps_reader_task, daemon=True)
        gps_thread.start()
        print("GPS読み取りスレッドを起動します...")
        gps_thread = threading.Thread(target=gps_reader_task, daemon=True)
        gps_thread.start()

    while True:
        try:
            async with websockets.connect(WEBSOCKET_URI) as websocket:
                print("✅ Connected to PC server.")
                
                is_recording = False
                recorded_path = []

                # タスク1: PCからの命令を受信
                async def receive_commands():
                    nonlocal is_recording, recorded_path
                    async for message in websocket:
                        try:
                            data = json.loads(message)
                            command = data.get('command')
                            
                            # モーター制御 (これは共通)
                            speed = 60
                            if command in ['forward', 'backward', 'left', 'right', 'stop']:
                                if command == 'forward': move.move(speed, 'forward', 'no')
                                elif command == 'backward': move.move(speed, 'backward', 'no')
                                elif command == 'left': move.move(speed, 'no', 'left')
                                elif command == 'right': move.move(speed, 'no', 'right')
                                elif command == 'stop': move.motorStop()
                                # コマンド記録モードの場合のみ、操作を記録
                                if is_recording and not is_gps_connected:
                                    recorded_path.append({'command': command, 'time': time.time()})

                            elif command == 'start_recording':
                                is_recording = True
                                recorded_path = []
                                print(f"Recording started. (GPS Mode: {is_gps_connected})")
                                if not is_gps_connected: # コマンド記録モードの場合
                                    recorded_path.append({'command': 'start', 'time': time.time()})
                            
                            elif command == 'stop_recording':
                                is_recording = False
                                route_id = data.get('route_id')
                                if not is_gps_connected: # コマンド記録モードの場合
                                    recorded_path.append({'command': 'end', 'time': time.time()})
                                
                                save_command = {
                                    'command': 'save_path', 'route_id': route_id,
                                    'path_data': recorded_path,
                                    'is_gps_path': is_gps_connected # GPS経路かどうかをPCに伝える
                                }
                                await websocket.send(json.dumps(save_command))
                                print(f"Recording stopped. Sent {len(recorded_path)} points.")

                            elif command == 'take_photo':
                                route_id = data.get('route_id')
                                filename = f"photo_{route_id}_{int(time.time())}.jpg"
                                filepath = os.path.join(PHOTO_SAVE_DIR, filename)
                                
                                if cam.take_photo(filepath):
                                    print(f"📸 Photo saved: {filepath}")
                                    response = {
                                        'command': 'photo_taken', 'status': 'ok',
                                        'route_id': route_id, 'filename': filename
                                    }
                                    # GPSが接続されていれば、位置情報も追加
                                    if is_gps_connected and current_gps_coords:
                                        response['location'] = current_gps_coords
                                    await websocket.send(json.dumps(response))

                        except Exception as e:
                            print(f"Error processing command: {e}")

                # タスク2: 映像とデータを送信
                async def stream_data():
                    last_gps_send_time = time.time()
                    while True:
                        frame = cam.get_frame()
                        if frame:
                            await websocket.send(frame)

                        now = time.time()
                        if (now - last_gps_send_time > 1): # 1秒ごとに
                            last_gps_send_time = now
                            if is_gps_connected and current_gps_coords:
                                # 捕捉成功
                                gps_payload = {
                                    "type": "gps_update",
                                    "data": current_gps_coords
                                }
                                await websocket.send(json.dumps(gps_payload))
                            elif is_gps_connected:
                                # 接続中だが未捕捉
                                gps_payload = {"type": "gps_status", "data": "Fixing..."}
                                await websocket.send(json.dumps(gps_payload))
                            else:
                                # GPS未接続
                                gps_payload = {"type": "gps_status", "data": "Disconnected"}
                                await websocket.send(json.dumps(gps_payload))

                        # GPSモードで記録中の場合、座標をリストに追加
                        if is_recording and is_gps_connected and current_gps_coords:
                            if not recorded_path or recorded_path[-1] != list(current_gps_coords):
                                recorded_path.append(list(current_gps_coords))

                        await asyncio.sleep(1/30)

                await asyncio.gather(receive_commands(), stream_data())

        except Exception as e:
            print(f"Connection error: {e}. Reconnecting in 5 seconds...")
            await asyncio.sleep(5)
def gps_reader_task():
    global current_gps_coords, is_gps_connected
    if not IS_GPS_AVAILABLE:
        print("⚠️ GPSライブラリがないため、GPSタスクを起動しません。")
        return # ライブラリがなければ何もしない

    while True: # 接続が切れても再試行し続ける
        ser = None # try/finally のために先に定義
        try:
            # ★★★ ご使用のUSB GPSレシーバーのポート名に変更してください ★★★
            port = '/dev/ttyACM0' # (または /dev/ttyACM0)
            ser = serial.Serial(port, 9600, timeout=5.0)
            print(f"🛰️ GPSモジュール ({port}) に接続しました。")
            is_gps_connected = True
            
            while True:
                line_bytes = ser.readline()
                if not line_bytes:
                    # タイムアウト（データが来ていない）場合は何もしない
                    continue
                
                line = line_bytes.decode('utf-8', errors='ignore')
                
                if line.startswith('$GPGGA') or line.startswith('$GNGGA'):
                    try:
                        msg = pynmea2.parse(line)
                        if msg.latitude != 0.0 and msg.longitude != 0.0:
                            # グローバル変数を更新
                            current_gps_coords = (round(msg.latitude, 6), round(msg.longitude, 6))
                        else:
                            current_gps_coords = None # 衛星未捕捉
                    except pynmea2.ParseError:
                        pass # パースエラーは無視

        except serial.SerialException:
            print(f"🔌 GPSポート {port} が見つかりません。5秒後に再試行します...")
            is_gps_connected = False
            current_gps_coords = None
            time.sleep(5)
        except Exception as e:
            print(f"GPSスレッドでエラー: {e}")
            is_gps_connected = False
            current_gps_coords = None
            time.sleep(5)
        finally:
            if ser and ser.is_open:
                ser.close()
                print("🛰️ GPSポートを閉じました。")


if __name__ == "__main__":
    move.setup()
    try:
        asyncio.run(robot_main())
    except KeyboardInterrupt:
        print("\nProgram terminated by user.")
    finally:
        move.destroy()