<?php
require_once 'config.php';

// ログインチェック
if (!isset($_SESSION['user_id'])) {
    header('Location: login.php');
    exit();
}

$user_id = $_SESSION['user_id'];

// フォームが送信された場合の保存処理
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    // 送信された値を取得
    $operation_mode = $_POST['operation_mode'] ?? 'auto';
    $max_speed = $_POST['max_speed'] ?? 5;

    // データベースを更新
    $stmt = $pdo->prepare(
        "UPDATE user_settings SET operation_mode = ?, max_speed = ? WHERE user_id = ?"
    );
    $stmt->execute([$operation_mode, $max_speed, $user_id]);

    $message = "設定を保存しました。";
}

// 現在の設定をデータベースから読み込む
$stmt = $pdo->prepare("SELECT operation_mode, max_speed FROM user_settings WHERE user_id = ?");
$stmt->execute([$user_id]);
$current_settings = $stmt->fetch(PDO::FETCH_ASSOC);

// もし設定が存在しない場合(新規ユーザーなど)は、デフォルト値を用意
if (!$current_settings) {
    $current_settings = [
        'operation_mode' => 'auto',
        'max_speed' => 5
    ];
}

$title = 'ローバ設定';
require_once './templates/header.php';
?>

<div class="container" style="margin-top: 80px; padding: 20px;">
    <h2>ローバ設定</h2>

    <?php if (isset($message)): ?>
        <p style="color: green; font-weight: bold;"><?php echo $message; ?></p>
    <?php endif; ?>

    <form action="rover_settings.php" method="post" style="border: 1px solid #ccc; padding: 20px; border-radius: 8px;">
        <div class="form-group" style="margin-bottom: 15px;">
            <label for="operation_mode" style="display: inline-block; width: 150px;">動作モード</label>
            <select name="operation_mode" id="operation_mode" style="padding: 5px;">
                <option value="auto" <?php echo $current_settings['operation_mode'] === 'auto' ? 'selected' : ''; ?>>自動運転</option>
                <option value="manual" <?php echo $current_settings['operation_mode'] === 'manual' ? 'selected' : ''; ?>>手動操作</option>
            </select>
        </div>
        <div class="form-group" style="margin-bottom: 15px;">
            <label for="max_speed" style="display: inline-block; width: 150px;">最高速度 (km/h)</label>
            <input type="number" name="max_speed" id="max_speed" value="<?php echo htmlspecialchars($current_settings['max_speed'], ENT_QUOTES, 'UTF-8'); ?>" min="1" max="20" style="padding: 5px; width: 80px;">
        </div>
        <hr>
        <button type="submit" style="padding: 10px 20px; cursor: pointer;">設定を保存</button>
    </form>
</div>

<?php require_once './templates/footer.php'; ?>
