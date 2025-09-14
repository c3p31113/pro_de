import asyncio
import websockets
import json
import os
import datetime
import move
import camera_opencv as camera
import database as db

speed_set = 100
rad = 0.5
is_recording = False
current_path = []
cam = camera.Camera()

PHOTO_SAVE_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'static', 'photos')
if not os.path.exists(PHOTO_SAVE_DIR):
    os.makedirs(PHOTO_SAVE_DIR)

def robot_ctrl(command):
    global current_path, is_recording
    if is_recording and command in ['forward', 'backward', 'left', 'right', 'stop']:
        current_path.append(command)
    
    if command == 'forward':
        move.move(speed_set, 'forward', 'no', rad)
    elif command == 'backward':
        move.move(speed_set, 'backward', 'no', rad)
    elif command == 'left':
        move.move(speed_set, 'no', 'left', rad)
    elif command == 'right':
        move.move(speed_set, 'no', 'right', rad)
    elif command == 'stop':
        move.motorStop()

async def handler(websocket, path):
    global is_recording, current_path
    print("Client connected")
    try:
        async for message in websocket:
            data = json.loads(message)
            command = data.get('command')
            route_id = data.get('route_id')
            
            response = {'status': 'ok', 'command': command}

            if command in ['forward', 'backward', 'left', 'right', 'stop']:
                robot_ctrl(command)
            elif command == 'start_recording':
                is_recording = True
                current_path = []
                response['message'] = 'Recording started'
            elif command == 'stop_recording':
                is_recording = False
                if route_id and current_path:
                    path_json = json.dumps(current_path)
                    db.query_db('UPDATE routes SET path_data = ? WHERE id = ?', [path_json, route_id])
                    response['message'] = 'Recording stopped and path saved'
                else:
                    response['message'] = 'Recording stopped, but no path to save'
                current_path = []
            elif command == 'take_photo':
                if route_id:
                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"photo_{timestamp}.jpg"
                    filepath = os.path.join(PHOTO_SAVE_DIR, filename)
                    success = cam.take_photo(filepath)
                    if success:
                        db.query_db('INSERT INTO photos (route_id, filename) VALUES (?, ?)', [route_id, filename])
                        response['message'] = 'Photo taken and saved'
                        response['filename'] = filename
                    else:
                        response['status'] = 'error'
                        response['message'] = 'Failed to take photo'
                else:
                    response['status'] = 'error'
                    response['message'] = 'Route ID not provided'
            
            await websocket.send(json.dumps(response))
    except websockets.exceptions.ConnectionClosed:
        print("Client disconnected")
    finally:
        move.motorStop()

async def main():
    move.setup()
    async with websockets.serve(handler, "0.0.0.0", 8888):
        print("WebSocket server started at ws://0.0.0.0:8888")
        await asyncio.Future()

def run_websocket_server():
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nWebSocket server terminated.")
    finally:
        move.destroy()
        print("GPIO cleanup complete.")