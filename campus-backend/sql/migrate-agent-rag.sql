-- Agent+RAG menu migration for an existing campus_qa database.
-- Safe to run more than once. It grants the bot management page to admin only.

INSERT IGNORE INTO sys_menu
    (menu_id, menu_name, parent_id, order_num, path, component, menu_type, perms, icon, visible, status)
VALUES
    (33, 'Bot management', 3, 4, '/system/bot', 'system/bot/index', 'C', 'system:bot:manage', 'Connection', '1', '1');

INSERT IGNORE INTO sys_role_menu (role_id, menu_id) VALUES (1, 33);
