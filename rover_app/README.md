・app.py:ローカルサーバーで起動するためのコード。こちらを実行でローカルサーバーを立ち上げwebページを開く。

・setup_db.py:動作確認のために使用するデータベースを作成するためのプログラム。sample_imagesに格納されている画像をデータベースに登録して作成している。あくまで試験的に使用しているため本来は使用しない。解析をしてしまうとデータベースから画像が抜き取られるため再度画像解析を行う場合はこちらのコードをもう一度実行する必要がある。

・rober_database.db：上記で作成されたデータベース

・check_db.py:データベースの中身を確認するプログラム。デバック用。

・abstract-aloe-474205-q4-c90961f66caf.json：GoogleAPIを使用するためのJSONキー(現在Vision APIは実装していないので使用はしていない)

以下app.py起動により使用されるプログラム
・kensyou_run_vision.py：画像解析用プログラム
・database.py：データベース関係のプログラム
・pdf_create.py：pdf作成用プログラム
・network_handler.py：ローバー操作用プログラム

以下画像解析用学習ラベル
・plant_health_cnn_labels.txt
・plant_health_cnn_model.h5

・templates：htmlを格納しているファイル

・login.html：ログインページ
・top.html：トップページ
・index.html：画像解析ページ
・result_list.html：解析結果ページ
・image_view.html：画像ページ
・notifications.html：異常通知ページ（病害のみ表示ページ）
・select_route.html：仮想マップページ
・control.html：ローバー操作ページ
・location.html：現在位置表示ページ
・settings.html：設定ページ

以下static内の説明

・css：html装飾のstyle.cssがある
・images：装飾用画像(icon)がある
・js：ローバー操作用のcontrol.jsがある
・results：解析後の注釈付き画像を保存しているフォルダ