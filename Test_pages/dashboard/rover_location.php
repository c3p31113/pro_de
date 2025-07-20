<?php
require_once 'config.php';

// ログインチェック
if (!isset($_SESSION['user_id'])) {
    header('Location: login.php');
    exit();
}

$title = 'ローバ現在位置';
// このページ専用のCSSがあればここで指定します。
// $css_file = 'location.css';
require_once './templates/header.php';
?>

<div class="container" style="margin-top: 80px; padding: 20px;">
    <h2>ローバ現在位置</h2>
    <div style="border: 1px solid #ccc; padding: 20px; border-radius: 8px;">
        <p>ローバーの現在位置情報を表示します。</p>
        <ul>
            <li><strong>緯度:</strong> 35.6895</li>
            <li><strong>経度:</strong> 139.6917</li>
            <li><strong>最終更新日時:</strong> <?php echo date('Y-m-d H:i:s'); ?></li>
        </ul>
        <!-- 将来的にはここに地図などを埋め込むことができます -->
        <div id="map-placeholder" style="width: 100%; height: 300px; background-color: #eee; text-align: center; line-height: 300px; margin-top: 20px;">
            地図表示エリア
        </div>
    </div>
</div>

<?php require_once './templates/footer.php'; ?>
