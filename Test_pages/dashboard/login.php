<?php
$title = 'ログイン画面';
$css_file = 'LogIn.css';
require_once './templates/header.php';
?>

<div class="container">
    <form action="login_process.php" method="post">
        <div class="menu">
            <input type="text" name="username" placeholder="ログインID" class="item" required>
            <input type="password" name="password" placeholder="パスワード" class="item" required>
        </div>
        <div class="LogIn">
            <button type="submit">ログインする</button>
        </div>
    </form>
</div>

<?php require_once './templates/footer.php'; ?>