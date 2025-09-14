import sqlite3
from flask import g
import os

DATABASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(DATABASE_DIR, 'rover_database.db')

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE_PATH)
        db.row_factory = sqlite3.Row
    return db

def init_db():
    if os.path.exists(DATABASE_PATH):
        return
    with sqlite3.connect(DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )''')
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS routes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT NOT NULL,
            path_data TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )''')
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            route_id INTEGER,
            filename TEXT NOT NULL,
            taken_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (route_id) REFERENCES routes (id)
        )''')
        conn.commit()

def query_db(query, args=(), one=False):
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(query, args)
    rv = cur.fetchall()
    conn.commit()
    conn.close()
    return (rv[0] if rv else None) if one else rv
    
def get_routes_with_photos(user_id):
    routes = query_db('SELECT * FROM routes WHERE user_id = ? ORDER BY created_at DESC', [user_id])
    if not routes:
        return []
    routes_with_photos = []
    for route in routes:
        photos = query_db('SELECT filename FROM photos WHERE route_id = ? ORDER BY taken_at ASC', [route['id']])
        route_dict = dict(route)
        route_dict['photos'] = [p['filename'] for p in photos]
        route_dict['thumbnail'] = photos[0]['filename'] if photos else None
        routes_with_photos.append(route_dict)
    return routes_with_photos