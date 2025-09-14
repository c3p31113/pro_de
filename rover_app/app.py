import threading
import webSocket_handler
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, Response
from werkzeug.security import generate_password_hash, check_password_hash
import database as db
from camera_opencv import Camera
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key'

db.init_db()

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('select_route'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = db.query_db('SELECT * FROM users WHERE username = ?', [username], one=True)
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            return redirect(url_for('select_route'))
        else:
            return render_template('login.html', error="IDまたはパスワードが間違っています。")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/top')
def top():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('top.html')

@app.route('/select_route')
def select_route():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    routes = db.get_routes_with_photos(session['user_id'])
    return render_template('select_route.html', routes=routes)

@app.route('/control/<int:route_id>')
def control(route_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    route = db.query_db('SELECT * FROM routes WHERE id = ?', [route_id], one=True)
    if not route:
        return "Route not found", 404
    return render_template('control.html', route_name=route['name'], route_id=route_id)
    
@app.route('/settings')
def settings():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('settings.html')

@app.route('/api/add_route', methods=['POST'])
def add_route():
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'Not logged in'}), 401
    route_name = request.json.get('name')
    if not route_name:
        return jsonify({'status': 'error', 'message': 'Route name is required'}), 400
    
    conn = db.get_db()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO routes (user_id, name, path_data) VALUES (?, ?, ?)',
                   (session['user_id'], route_name, '[]'))
    conn.commit()
    new_route_id = cursor.lastrowid
    return jsonify({'status': 'success', 'new_route_id': new_route_id})

@app.route('/api/rename_route/<int:route_id>', methods=['POST'])
def rename_route(route_id):
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'Not logged in'}), 401
    new_name = request.json.get('name')
    if not new_name:
        return jsonify({'status': 'error', 'message': 'New name is required'}), 400
    
    db.query_db('UPDATE routes SET name = ? WHERE id = ? AND user_id = ?', 
                [new_name, route_id, session['user_id']])
    return jsonify({'status': 'success'})

def gen(camera):
    while True:
        frame = camera.get_frame()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/video_feed')
def video_feed():
    return Response(gen(Camera()),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    with app.app_context():
        if not db.query_db('SELECT * FROM users WHERE username = ?', ['admin'], one=True):
            conn = db.get_db()
            conn.execute('INSERT INTO users (username, password) VALUES (?, ?)',
                         ['admin', generate_password_hash('password')])
            conn.commit()

    ws_thread = threading.Thread(target=webSocket_handler.run_websocket_server)
    ws_thread.daemon = True
    ws_thread.start()

    print("Flask server starting on http://0.0.0.0:5000")
    app.run(host='0.0.0.0', port=5000, threaded=True, use_reloader=False)