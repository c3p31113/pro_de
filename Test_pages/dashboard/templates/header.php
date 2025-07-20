<?php
// ログインしているユーザー名を取得 (セッションにない場合は 'ゲスト')
$username = isset($_SESSION['username']) ? htmlspecialchars($_SESSION['username'], ENT_QUOTES, 'UTF-8') : 'ゲスト';
?>
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <title><?php echo $title ?? 'ダッシュボード'; ?></title>
    <link rel="stylesheet" href="./Css/style.css">
    <?php if (isset($css_file)): ?>
        <link rel="stylesheet" href="./Css/<?php echo $css_file; ?>">
    <?php endif; ?>
</head>
<body>
    <header>
        <div class="header-content">
            <div class="user-name">ログインユーザ：<?php echo $username; ?></div>
        </div>
    </header>