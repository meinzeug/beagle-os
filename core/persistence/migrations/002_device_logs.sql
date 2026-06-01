CREATE TABLE IF NOT EXISTS device_logs (
    entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT '',
    level TEXT NOT NULL DEFAULT 'info',
    captured_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    content TEXT NOT NULL DEFAULT '',
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_device_logs_device_id ON device_logs(device_id);
CREATE INDEX IF NOT EXISTS idx_device_logs_device_captured_at ON device_logs(device_id, captured_at DESC);
CREATE INDEX IF NOT EXISTS idx_device_logs_source ON device_logs(source);