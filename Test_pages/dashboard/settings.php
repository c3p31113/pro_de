<?php
require_once 'config.php';

// ログインチェック
if (!isset($_SESSION['user_id'])) {
    header('Location: login.php');
    exit();
}

$title = '設定';
// トップページと同じCSSを流用します
$css_file = 'Top.css';
require_once './templates/header.php';
?>

<div class="Top_container">
    <h2 style="text-align: center; margin-bottom: 30px;">設定メニュー</h2>
    <div class="menu">
        <a href="notification_settings.php" class="item" style="text-decoration: none; color: inherit;">通知設定</a>
        <a href="rover_settings.php" class="item" style="text-decoration: none; color: inherit;">ローバ設定</a>
    </div>
</div>

<?php require_once './templates/footer.php'; ?>
