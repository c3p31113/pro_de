<?php
require_once 'config.php';

// セッション変数をすべて解除する
$_SESSION = array();

// セッションを破壊する
session_destroy();

// ログインページにリダイレクトする
header('Location: login.php');
exit();