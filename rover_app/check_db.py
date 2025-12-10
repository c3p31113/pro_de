# check_db.py
import sqlite3
import os
import base64

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# DB を project_db 配下に保存
DB = os.path.join(BASE_DIR, "rover_database.db")

def show_table(conn, table):
    print(f"\n=== {table} ===")
    cur = conn.cursor()
    try:
        cur.execute(f"SELECT * FROM {table}")
        rows = cur.fetchall()

        if not rows:
            print(" → データなし")
            return

        for row in rows:
            print(row)

    except Exception as e:
        print(f"テーブル {table} の取得でエラー:", e)


def main():
    conn = sqlite3.connect(DB)

    print("\n==========================")
    print("   📌 DB 内容確認ツール   ")
    print("==========================\n")

    # 既存テーブル一覧を表示
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [t[0] for t in cur.fetchall()]
    print("■ テーブル一覧：")
    for t in tables:
        print(" -", t)

    # 各テーブルの中身を全部表示
    for t in tables:
        show_table(conn, t)

    conn.close()


if __name__ == "__main__":
    main()
