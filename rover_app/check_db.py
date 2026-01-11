"""
DB内容確認スクリプト(ターミナル表示)。

- SQLite(rover_database.db)に接続してテーブル一覧/内容を表示する
- 画像(BLOB)等がある場合は表示を短縮する(必要ならbase64で扱う前提)
"""
import sqlite3
import base64

# DB: 主要な設定値（パス/閾値など）。
DB = "rover_database.db"


# --------------------------------------------------------
# 指定テーブルの内容をSELECTして整形表示する。
# --------------------------------------------------------
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



# --------------------------------------------------------
# エントリポイント。表示したいテーブルを順番に出力する。
# --------------------------------------------------------
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
