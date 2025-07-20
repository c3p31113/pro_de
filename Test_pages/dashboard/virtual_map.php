<?php
require_once 'config.php';

// ログインチェック
if (!isset($_SESSION['user_id'])) {
    header('Location: login.php');
    exit();
}

$title = '仮想マップ';
// このページ専用のCSSがあればここで指定します。
// $css_file = 'map.css';
require_once './templates/header.php';
?>

<div class="container" style="margin-top: 80px; padding: 20px;">
    <h2>仮想マップ</h2>
    <p>指定されたエリアの仮想マップを表示します。</p>
    <div id="virtual-map" style="width: 100%; height: 400px; background-color: #e0e0e0; border: 1px solid #ccc; text-align: center; line-height: 400px; font-size: 1.2em; color: #666;">
        仮想マップ表示エリア
    </div>
</div>

<?php require_once './templates/footer.php'; ?>
