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
    $email_notification = isset($_POST['email_notification']) ? (bool)$_POST['email_notification'] : 0;
    $email_address = $_POST['email_address'] ?? '';

    // データベースを更新
    $stmt = $pdo->prepare(
        "UPDATE user_settings SET email_notification = ?, email_address = ? WHERE user_id = ?"
    );
    $stmt->execute([$email_notification, $email_address, $user_id]);

    $message = "設定を保存しました。";
}

// 現在の設定をデータベースから読み込む
$stmt = $pdo->prepare("SELECT email_notification, email_address FROM user_settings WHERE user_id = ?");
$stmt->execute([$user_id]);
$current_settings = $stmt->fetch(PDO::FETCH_ASSOC);

// もし設定が存在しない場合(新規ユーザーなど)は、デフォルト値を用意
if (!$current_settings) {
    $current_settings = [
        'email_notification' => true,
        'email_address' => ''
    ];
}

$title = '通知設定';
require_once './templates/header.php';
?>

<div class="container" style="margin-top: 80px; padding: 20px;">
    <h2>通知設定</h2>

    <?php if (isset($message)): ?>
        <p style="color: green; font-weight: bold;"><?php echo $message; ?></p>
    <?php endif; ?>

    <form action="notification_settings.php" method="post" style="border: 1px solid #ccc; padding: 20px; border-radius: 8px;">
        <div class="form-group" style="margin-bottom: 15px;">
            <label for="email_notification" style="display: inline-block; width: 150px;">メール通知</label>
            <select name="email_notification" id="email_notification" style="padding: 5px;">
                <option value="1" <?php echo $current_settings['email_notification'] ? 'selected' : ''; ?>>有効</option>
                <option value="0" <?php echo !$current_settings['email_notification'] ? 'selected' : ''; ?>>無効</option>
            </select>
        </div>
        <div class="form-group" style="margin-bottom: 15px;">
            <label for="email_address" style="display: inline-block; width: 150px;">通知先メールアドレス</label>
            <input type="email" name="email_address" id="email_address" value="<?php echo htmlspecialchars($current_settings['email_address'], ENT_QUOTES, 'UTF-8'); ?>" style="padding: 5px; width: 250px;">
        </div>
        <hr>
        <button type="submit" style="padding: 10px 20px; cursor: pointer;">設定を保存</button>
    </form>
</div>

<?php require_once './templates/footer.php'; ?>
