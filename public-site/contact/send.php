<?php
session_start();
header('Content-Type: application/json');

// Only accept POST
if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    echo json_encode(['success' => false, 'error' => 'Method not allowed']);
    exit;
}

// Honeypot: bots fill hidden field "website"
if (!empty($_POST['website'])) {
    echo json_encode(['success' => true]);
    exit;
}

// CSRF validation
if (
    empty($_POST['csrf_token']) ||
    empty($_SESSION['csrf_token']) ||
    !hash_equals($_SESSION['csrf_token'], $_POST['csrf_token'])
) {
    http_response_code(403);
    echo json_encode(['success' => false, 'error' => 'Invalid session. Please reload the page.']);
    exit;
}

// Rate limiting: max 3 submissions per IP per 10 minutes
$ip      = $_SERVER['REMOTE_ADDR'] ?? 'unknown';
$rf      = sys_get_temp_dir() . '/beagle_cl_' . md5($ip);
$now     = time();
$history = file_exists($rf) ? (json_decode(file_get_contents($rf), true) ?: []) : [];
$history = array_values(array_filter($history, fn($t) => $now - $t < 600));
if (count($history) >= 3) {
    http_response_code(429);
    echo json_encode(['success' => false, 'error' => 'Too many requests. Please try again in a few minutes.']);
    exit;
}

// Sanitize inputs
$name      = trim(strip_tags($_POST['name']      ?? ''));
$company   = trim(strip_tags($_POST['company']   ?? ''));
$email_raw = trim($_POST['email'] ?? '');
$endpoints = intval($_POST['endpoints'] ?? 0);
$message   = trim(strip_tags($_POST['message']   ?? ''));

$email = filter_var($email_raw, FILTER_VALIDATE_EMAIL);

if (!$name || !$email || !$message) {
    http_response_code(400);
    echo json_encode(['success' => false, 'error' => 'Please fill in all required fields.']);
    exit;
}
if (strlen($name) > 120 || strlen($company) > 250 || strlen($message) > 5000) {
    http_response_code(400);
    echo json_encode(['success' => false, 'error' => 'Input exceeds maximum allowed length.']);
    exit;
}

// Build email  — recipient is server-side only, never exposed to the browser
$to      = 'dennis.wicht@web.de';
$subject = '=?UTF-8?B?' . base64_encode('Beagle OS: Commercial License Request') . '?=';

$body  = "New commercial license request received via beagle-os.com/contact/\n";
$body .= "=================================================================\n\n";
$body .= "Name:          {$name}\n";
if ($company !== '') {
    $body .= "Company:       {$company}\n";
}
$body .= "E-Mail:        {$email}\n";
if ($endpoints > 0) {
    $body .= "Endpoints:     {$endpoints}\n";
}
$body .= "\nMessage:\n--------\n{$message}\n\n";
$body .= "---\nSource IP : {$ip}\nTimestamp : " . date('Y-m-d H:i:s T') . "\n";

$headers  = "From: noreply@beagle-os.com\r\n";
$headers .= "Reply-To: {$email}\r\n";
$headers .= "X-Mailer: BeagleOS-Contact/1.0\r\n";
$headers .= "MIME-Version: 1.0\r\n";
$headers .= "Content-Type: text/plain; charset=UTF-8\r\n";
$headers .= "Content-Transfer-Encoding: 8bit\r\n";

$sent = mail($to, $subject, $body, $headers);

if ($sent) {
    $history[] = $now;
    file_put_contents($rf, json_encode($history));
    unset($_SESSION['csrf_token']); // one-time token
    echo json_encode(['success' => true]);
} else {
    http_response_code(500);
    echo json_encode(['success' => false, 'error' => 'Could not send message. Please try again later.']);
}
