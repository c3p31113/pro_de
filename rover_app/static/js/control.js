document.addEventListener('DOMContentLoaded', () => {
    // 修正点①: ブラウザ専用のポート「8889」に接続
    const ws = new WebSocket(`ws://${window.location.hostname}:8889`);

    const videoElement = document.getElementById('video-stream');
    const buttons = {
        forward: document.getElementById('btn-forward'),
        backward: document.getElementById('btn-backward'),
        left: document.getElementById('btn-left'),
        right: document.getElementById('btn-right'),
        record: document.getElementById('btn-record'),
        photo: document.getElementById('btn-photo'),
        replay: document.getElementById('btn-replay')
    };

    let isRecording = false;

    // メッセージ送信関数 (元のコードをそのまま利用)
    const sendMessage = (command) => {
        if (ws.readyState === WebSocket.OPEN) {
            const message = {
                command: command,
                route_id: routeId // HTMLから渡されたルートID
            };
            ws.send(JSON.stringify(message));
            console.log('Sent:', message);
        }
    };

    // --- 各ボタンのイベントリスナー (元のコードをそのまま利用) ---
    // 移動ボタン
    ['forward', 'backward', 'left', 'right'].forEach(direction => {
        buttons[direction].addEventListener('mousedown', () => sendMessage(direction));
        buttons[direction].addEventListener('mouseup', () => sendMessage('stop'));
        buttons[direction].addEventListener('mouseleave', () => sendMessage('stop'));
        buttons[direction].addEventListener('touchstart', (e) => { e.preventDefault(); sendMessage(direction); });
        buttons[direction].addEventListener('touchend', (e) => { e.preventDefault(); sendMessage('stop'); });
    });

    // 経路記憶ボタン
    buttons.record.addEventListener('click', () => {
        isRecording = !isRecording;
        if (isRecording) {
            sendMessage('start_recording');
            buttons.record.textContent = '記憶中...';
            buttons.record.classList.add('recording');
        } else {
            sendMessage('stop_recording');
            buttons.record.textContent = '経路記憶';
            buttons.record.classList.remove('recording');
        }
    });

    // 写真撮影ボタン
    buttons.photo.addEventListener('click', () => {
        sendMessage('take_photo');
    });

    //経路再生ボタン
    buttons.replay.addEventListener('click', () => {
        // 再生コマンドを送信
        sendMessage('replay_path');
        alert('経路再生を開始します');
    });


    // --- WebSocketイベント (ここを修正) ---
    ws.onopen = () => {
        console.log('WebSocket connection established');
        videoElement.alt = "Waiting for video stream...";
    };

    // 修正点② & ③: サーバーからのメッセージ受信処理を更新
    ws.onmessage = (event) => {
        // メッセージがBlob（バイナリデータ）の場合、それはビデオフレーム
        if (event.data instanceof Blob) {
            // BlobをURLに変換してimg要素のsrcに設定
            videoElement.src = URL.createObjectURL(event.data);
        } else {
            // テキストデータ(JSON)の場合
            try {
                const data = JSON.parse(event.data);
                console.log('Received:', data);
                if(data.command === 'take_photo' && data.status === 'ok') {
                    alert(`写真を撮影しました: ${data.filename}`);
                }
            } catch (e) {
                console.error("Failed to parse JSON message:", event.data);
            }
        }
    };

    ws.onclose = () => {
        console.log('WebSocket connection closed');
        videoElement.alt = "Connection closed. Please reload.";
    };
    
    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        videoElement.alt = "Connection error.";
    };
});