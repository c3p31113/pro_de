<?php
require_once 'config.php';

// ログインチェック
if (!isset($_SESSION['user_id'])) {
    header('Location: login.php');
    exit();
}

// 異常通知をデータベースから取得
$stmt = $pdo->query("SELECT id, title, status, created_at FROM notifications ORDER BY created_at DESC");
$notifications = $stmt->fetchAll(PDO::FETCH_ASSOC);

$title = '異常通知一覧';
// このページ専用のCSSがあればここで指定します。
// $css_file = 'notification.css';
require_once './templates/header.php';
?>

<div class="container" style="margin-top: 80px; padding: 20px;">
    <h2>異常通知一覧</h2>
    <table border="1" style="width: 100%; border-collapse: collapse;">
        <thead>
            <tr>
                <th style="padding: 8px;">発生日時</th>
                <th style="padding: 8px;">タイトル</th>
                <th style="padding: 8px;">ステータス</th>
                <th style="padding: 8px;">詳細</th>
            </tr>
        </thead>
        <tbody>
            <?php foreach ($notifications as $notification): ?>
                <tr>
                    <td style="padding: 8px;"><?php echo htmlspecialchars($notification['created_at'], ENT_QUOTES, 'UTF-8'); ?></td>
                    <td style="padding: 8px;"><?php echo htmlspecialchars($notification['title'], ENT_QUOTES, 'UTF-8'); ?></td>
                    <td style="padding: 8px;"><?php echo htmlspecialchars($notification['status'], ENT_QUOTES, 'UTF-8'); ?></td>
                    <td style="padding: 8px; text-align: center;">
                        <a href="notification_detail.php?id=<?php echo $notification['id']; ?>">詳細表示</a>
                    </td>
                </tr>
            <?php endforeach; ?>
        </tbody>
    </table>
</div>

<?php require_once './templates/footer.php'; ?>