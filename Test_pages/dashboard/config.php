<?php
// データベース接続設定
define('DB_HOST', 'localhost');
define('DB_USER', 'root');
define('DB_PASS', ''); // XAMPPのデフォルトは空パスワード
define('DB_NAME', 'dashboard_db');

// データベース接続
try {
    $pdo = new PDO("mysql:host=" . DB_HOST . ";dbname=" . DB_NAME . ";charset=utf8mb4", DB_USER, DB_PASS);
    // エラー発生時に例外をスローするように設定
    $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
} catch (PDOException $e) {
    die("データベースに接続できませんでした: " . $e->getMessage());
}

// セッションを開始
if (session_status() == PHP_SESSION_NONE) {
    session_start();
}