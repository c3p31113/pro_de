import threading
import network_handler
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import database as db
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key' # 本番環境ではもっと複雑なキーに変更してください

# --- データベースの初期化 ---
# データベースファイルがなければ作成
db.init_db()
# Flaskアプリにデータベース管理機能を登録
db.init_app(app)


# --- Webページの表示 (ルート) ---

@app.route('/')
def index():
    # ログインしていればTOPページへ
    if 'user_id' in session:
        return redirect(url_for('top'))
    # していなければログインページへ
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = db.query_db('SELECT * FROM users WHERE username = ?', [username], one=True)
        
        if user and check_password_hash(user['password'], password):
            session.clear()
            session['user_id'] = user['id']
            session['username'] = user['username']
            return redirect(url_for('top'))
        else:
            error = 'IDまたはパスワードが間違っています。'
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
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

@app.route('/control/')
@app.route('/control/<int:route_id>')
def control(route_id=None):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    route_name = "新規経路"
    if route_id:
        route = db.query_db('SELECT * FROM routes WHERE id = ? AND user_id = ?', [route_id, session['user_id']], one=True)
        if route:
            route_name = route['name']
        else: # 存在しない、または権限のないルートIDの場合はルート選択へ
            return redirect(url_for('select_route'))

    return render_template('control.html', route_id=route_id, route_name=route_name)

@app.route('/settings')
def settings():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('settings.html')

@app.route('/location')
def location():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('location.html')

@app.route('/notifications')
def notifications():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # データベースから通知を取得
    notifs = db.query_db('SELECT * FROM notifications WHERE user_id = ? ORDER BY timestamp DESC', [session['user_id']])
    
    return render_template('notifications.html', notifications=notifs)


# --- JavaScriptから呼び出されるAPI ---

@app.route('/api/add_route', methods=['POST'])
def add_route():
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'Not logged in'}), 401
    
    data = request.json
    name = data.get('name')
    if not name:
        return jsonify({'status': 'error', 'message': 'Name is required'}), 400

    db.query_db('INSERT INTO routes (user_id, name) VALUES (?, ?)', [session['user_id'], name])
    new_route = db.query_db('SELECT id FROM routes WHERE user_id = ? ORDER BY id DESC LIMIT 1', [session['user_id']], one=True)
    
    return jsonify({'status': 'success', 'new_route_id': new_route['id']})

@app.route('/api/rename_route/<int:route_id>', methods=['POST'])
def rename_route(route_id):
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'Not logged in'}), 401
    
    data = request.json
    new_name = data.get('name')
    if not new_name:
        return jsonify({'status': 'error', 'message': 'New name is required'}), 400

    # 念のため、そのルートの所有者であるかを確認
    route = db.query_db('SELECT id FROM routes WHERE id = ? AND user_id = ?', [route_id, session['user_id']], one=True)
    if not route:
        return jsonify({'status': 'error', 'message': 'Route not found or permission denied'}), 404

    db.query_db('UPDATE routes SET name = ? WHERE id = ?', [new_name, route_id])
    return jsonify({'status': 'success'})


# --- サーバー起動 ---
if __name__ == '__main__':
    with app.app_context():
        # 'admin'ユーザーがなければ作成 (パスワードは 'password')
        if not db.query_db('SELECT * FROM users WHERE username = ?', ['admin'], one=True):
            conn = db.get_db()
            conn.execute('INSERT INTO users (username, password) VALUES (?, ?)',
                         ['admin', generate_password_hash('password')])
            conn.commit()

    ws_thread = threading.Thread(target=network_handler.run_network_server)
    ws_thread.daemon = True
    ws_thread.start()

    print("Flask server starting on http://172.20.21.60:5000")
    app.run(host='0.0.0.0', port=5000, threaded=True, use_reloader=False)