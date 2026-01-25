#!/usr/bin/env python3
"""
Script để thêm Gmail SMTP server vào Odoo.
Chạy: python3 add_mail_server.py

QUAN TRỌNG: 
- Cần tạo App Password cho Gmail: https://myaccount.google.com/apppasswords
- Bật 2FA trên tài khoản Google trước khi tạo App Password
"""
import psycopg2
from datetime import datetime

# === CẤU HÌNH SMTP ===
SMTP_CONFIG = {
    'name': 'Gmail SMTP',
    'smtp_host': 'smtp.gmail.com',
    'smtp_port': 587,
    'smtp_user': 'phamnogc887@gmail.com',  # Email của bạn
    'smtp_pass': '',  # << THAY BẰNG APP PASSWORD CỦA BẠN >>
    'smtp_encryption': 'starttls',
    'active': True,
}

def main():
    conn = psycopg2.connect(dbname='ngoc', user='odoo', password='odoo', host='localhost')
    cur = conn.cursor()
    
    # Check existing mail servers
    cur.execute('SELECT id, name, smtp_host, smtp_user, active FROM ir_mail_server')
    servers = cur.fetchall()
    print('=== MAIL SERVERS HIỆN TẠI ===')
    if servers:
        for s in servers:
            print(f"ID: {s[0]}, Name: {s[1]}, Host: {s[2]}, User: {s[3]}, Active: {s[4]}")
    else:
        print('(Chưa có mail server nào)')
    
    # Check users
    cur.execute('SELECT id, login, email FROM res_users WHERE active=true LIMIT 5')
    users = cur.fetchall()
    print('\n=== USERS ===')
    for u in users:
        print(f"ID: {u[0]}, Login: {u[1]}, Email: {u[2]}")
    
    # Thêm mail server nếu chưa có
    if not servers and SMTP_CONFIG['smtp_pass']:
        print('\n=== THÊM MAIL SERVER ===')
        cur.execute('''
            INSERT INTO ir_mail_server (name, smtp_host, smtp_port, smtp_user, smtp_pass, smtp_encryption, active, create_date, write_date, create_uid, write_uid)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 1, 1)
        ''', (
            SMTP_CONFIG['name'],
            SMTP_CONFIG['smtp_host'],
            SMTP_CONFIG['smtp_port'],
            SMTP_CONFIG['smtp_user'],
            SMTP_CONFIG['smtp_pass'],
            SMTP_CONFIG['smtp_encryption'],
            SMTP_CONFIG['active'],
            datetime.now(),
            datetime.now()
        ))
        conn.commit()
        print(f"✓ Đã thêm mail server: {SMTP_CONFIG['name']}")
    elif not SMTP_CONFIG['smtp_pass']:
        print('\n⚠️  Chưa cấu hình smtp_pass! Hãy sửa file và thêm App Password.')
    else:
        print('\n✓ Mail server đã tồn tại.')
    
    conn.close()

if __name__ == '__main__':
    main()
