document.addEventListener('DOMContentLoaded', () => {
    // WebSocketサーバーに接続
    const ws = new WebSocket(`ws://${window.location.hostname}:8888`);

    const buttons = {
        forward: document.getElementById('btn-forward'),
        backward: document.getElementById('btn-backward'),
        left: document.getElementById('btn-left'),
        right: document.getElementById('btn-right'),
        record: document.getElementById('btn-record'),
        photo: document.getElementById('btn-photo')
    };

    let isRecording = false;

    // メッセージ送信関数
    const sendMessage = (command) => {
        if (ws.readyState === WebSocket.OPEN) {
            const message = {
                command: command,
                route_id: currentRouteId // HTMLから渡されたルートID
            };
            ws.send(JSON.stringify(message));
            console.log('Sent:', message);
        }
    };

    // 移動ボタンのイベントリスナー
    ['forward', 'backward', 'left', 'right'].forEach(direction => {
        buttons[direction].addEventListener('mousedown', () => sendMessage(direction));
        buttons[direction].addEventListener('mouseup', () => sendMessage('stop'));
        buttons[direction].addEventListener('mouseleave', () => sendMessage('stop')); // ボタンからカーソルが離れた場合も停止
        buttons[direction].addEventListener('touchstart', (e) => { e.preventDefault(); sendMessage(direction); });
        buttons[direction].addEventListener('touchend', (e) => { e.preventDefault(); sendMessage('stop'); });
    });

    // 経路記憶ボタンのイベントリスナー
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

    // 写真撮影ボタンのイベントリスナー
    buttons.photo.addEventListener('click', () => {
        sendMessage('take_photo');
    });

    // WebSocketイベント
    ws.onopen = () => console.log('WebSocket connection established');
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        console.log('Received:', data);
        if(data.command === 'take_photo' && data.status === 'ok') {
            alert(`写真を撮影しました: ${data.filename}`);
        }
    };
    ws.onclose = () => console.log('WebSocket connection closed');
    ws.onerror = (error) => console.log('WebSocket error:', error);
});