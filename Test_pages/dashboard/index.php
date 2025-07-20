<?php
require_once 'config.php';

// ログインチェック
if (!isset($_SESSION['user_id'])) {
    header('Location: login.php');
    exit();
}

$title = 'メニュー画面';
$css_file = 'Top.css';
require_once './templates/header.php';
?>

<div class="Top_container">
    <div class="menu">
        <a href="notification_list.php" class="item">1 異常通知</a>
        <a href="virtual_map.php" class="item">3 仮想マップ</a>
        <a href="rover_location.php" class="item">2 現在位置</a>
        <a href="settings.php" class="item">4 設定</a>
    </div>
</div>
<div style="text-align: center; margin-top: 20px;">
    <a href="logout.php">ログアウト</a>
</div>

<?php require_once './templates/footer.php'; ?>