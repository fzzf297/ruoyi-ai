CREATE TABLE admin_page_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    page_id INTEGER NOT NULL,
    version INTEGER NOT NULL,
    action TEXT NOT NULL,
    snapshot_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(page_id, version)
);

CREATE INDEX idx_admin_page_versions_page_id
    ON admin_page_versions(page_id);

CREATE TABLE app_interface_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    interface_id INTEGER NOT NULL,
    version INTEGER NOT NULL,
    action TEXT NOT NULL,
    snapshot_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(interface_id, version)
);

CREATE INDEX idx_app_interface_versions_interface_id
    ON app_interface_versions(interface_id);
