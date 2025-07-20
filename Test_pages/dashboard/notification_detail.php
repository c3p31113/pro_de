<?php
require_once 'config.php';

// ログインチェック
if (!isset($_SESSION['user_id'])) {
    header('Location: login.php');
    exit();
}

$notification_id = $_GET['id'] ?? 0;
if (!$notification_id) {
    die('IDが指定されていません。');
}

// 指定されたIDの通知を取得
$stmt = $pdo->prepare("SELECT * FROM notifications WHERE id = ?");
$stmt->execute([$notification_id]);
$notification = $stmt->fetch(PDO::FETCH_ASSOC);

if (!$notification) {
    die('指定された通知が見つかりません。');
}

$title = '異常通知詳細';
require_once './templates/header.php';
?>

<div class="container" style="margin-top: 80px; padding: 20px;">
    <h2>異常通知詳細</h2>
    <h3><?php echo htmlspecialchars($notification['title'], ENT_QUOTES, 'UTF-8'); ?></h3>
    <p><strong>発生日時:</strong> <?php echo htmlspecialchars($notification['created_at'], ENT_QUOTES, 'UTF-8'); ?></p>
    <p><strong>ステータス:</strong> <?php echo htmlspecialchars($notification['status'], ENT_QUOTES, 'UTF-8'); ?></p>
    <hr>
    <p><strong>内容:</strong></p>
    <p><?php echo nl2br(htmlspecialchars($notification['description'], ENT_QUOTES, 'UTF-8')); ?></p>
</div>

<?php require_once './templates/footer.php'; ?>