-- SQL Script để thêm Gmail SMTP Server vào Odoo
-- Chạy: psql postgresql://odoo:odoo@localhost/ngoc -f add_gmail_smtp.sql

-- Kiểm tra mail server hiện tại
SELECT 'CURRENT MAIL SERVERS:' as info;
SELECT id, name, smtp_host, smtp_user, active FROM ir_mail_server;

-- Kiểm tra user email
SELECT 'USER EMAIL:' as info;
SELECT id, login, email FROM res_users WHERE id = 2;

-- Kiểm tra company email  
SELECT 'COMPANY EMAIL:' as info;
SELECT id, name, email FROM res_company LIMIT 1;

-- Kiểm tra mail queue
SELECT 'MAIL QUEUE STATUS:' as info;
SELECT state, count(*) FROM mail_mail GROUP BY state;

-- ====================================
-- THÊM GMAIL SMTP SERVER
-- QUAN TRỌNG: Thay YOUR_APP_PASSWORD bằng App Password thực
-- Tạo App Password tại: https://myaccount.google.com/apppasswords
-- ====================================

-- Xóa mail server cũ (nếu có)
-- DELETE FROM ir_mail_server WHERE smtp_host = 'smtp.gmail.com';

-- Thêm Gmail SMTP Server
-- INSERT INTO ir_mail_server (name, smtp_host, smtp_port, smtp_user, smtp_pass, smtp_encryption, active, sequence, smtp_debug, create_date, write_date, create_uid, write_uid)
-- VALUES (
--     'Gmail SMTP',
--     'smtp.gmail.com',
--     587,
--     'phamnogc887@gmail.com',
--     'YOUR_APP_PASSWORD',  -- << THAY BẰNG APP PASSWORD 16 KÝ TỰ
--     'starttls',
--     true,
--     10,
--     false,
--     NOW(),
--     NOW(),
--     1,
--     1
-- );

SELECT 'Done! If you added mail server, restart Odoo.' as info;
