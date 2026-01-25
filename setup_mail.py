#!/usr/bin/env python3
"""
Script kiểm tra và cấu hình Mail Server cho Odoo
Chạy: python3 setup_mail.py
"""
import psycopg2
from datetime import datetime

def main():
    conn = psycopg2.connect(dbname='ngoc', user='odoo', password='odoo', host='localhost')
    cur = conn.cursor()
    
    print("=" * 60)
    print("KIỂM TRA CẤU HÌNH EMAIL ODOO")
    print("=" * 60)
    
    # 1. Kiểm tra mail server
    cur.execute("SELECT id, name, smtp_host, smtp_port, smtp_user, smtp_encryption, active FROM ir_mail_server")
    servers = cur.fetchall()
    print("\n📧 OUTGOING MAIL SERVERS:")
    if servers:
        for s in servers:
            print(f"  ✓ ID={s[0]}, Name={s[1]}, Host={s[2]}, Port={s[3]}, User={s[4]}, Encryption={s[5]}, Active={s[6]}")
    else:
        print("  ❌ KHÔNG CÓ MAIL SERVER - CẦN CẤU HÌNH!")
    
    # 2. Kiểm tra user email
    cur.execute("SELECT id, login, email FROM res_users WHERE id=2")
    user = cur.fetchone()
    print(f"\n👤 USER HIỆN TẠI (ID=2):")
    if user:
        print(f"  Login: {user[1]}")
        print(f"  Email: {user[2] or '❌ CHƯA CÓ EMAIL'}")
    
    # 3. Kiểm tra company email
    cur.execute("SELECT id, name, email FROM res_company LIMIT 1")
    company = cur.fetchone()
    print(f"\n🏢 COMPANY:")
    if company:
        print(f"  Name: {company[1]}")
        print(f"  Email: {company[2] or '❌ CHƯA CÓ EMAIL'}")
    
    # 4. Kiểm tra mail queue
    cur.execute("SELECT id, subject, email_to, state, failure_reason FROM mail_mail ORDER BY id DESC LIMIT 5")
    mails = cur.fetchall()
    print(f"\n📬 MAIL QUEUE (5 gần nhất):")
    if mails:
        for m in mails:
            subj = (m[1][:50] + '...') if m[1] and len(m[1]) > 50 else (m[1] or 'N/A')
            status = '✓' if m[3] == 'sent' else '⏳' if m[3] == 'outgoing' else '❌'
            print(f"  {status} ID={m[0]}, To={m[2]}, State={m[3]}")
            if m[4]:
                print(f"     Error: {m[4]}")
    else:
        print("  (Không có email nào)")
    
    # 5. Thêm mail server nếu chưa có
    if not servers:
        print("\n" + "=" * 60)
        print("THÊM GMAIL SMTP SERVER")
        print("=" * 60)
        
        # Hỏi App Password
        print("""
⚠️  Để gửi email qua Gmail, bạn cần tạo App Password:
   1. Vào https://myaccount.google.com/apppasswords
   2. Bật 2FA nếu chưa bật
   3. Tạo App Password cho 'Mail' 
   4. Copy mã 16 ký tự (ví dụ: abcd efgh ijkl mnop)
""")
        
        app_password = input("Nhập App Password Gmail (16 ký tự, bỏ dấu cách): ").strip().replace(' ', '')
        
        if len(app_password) >= 16:
            try:
                cur.execute("""
                    INSERT INTO ir_mail_server 
                    (name, smtp_host, smtp_port, smtp_user, smtp_pass, smtp_encryption, active, 
                     sequence, smtp_debug, create_date, write_date, create_uid, write_uid)
                    VALUES 
                    (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    'Gmail SMTP - phamnogc887@gmail.com',
                    'smtp.gmail.com',
                    587,
                    'phamnogc887@gmail.com',
                    app_password,
                    'starttls',
                    True,
                    10,
                    False,
                    datetime.now(),
                    datetime.now(),
                    1,
                    1
                ))
                server_id = cur.fetchone()[0]
                conn.commit()
                print(f"\n✅ Đã thêm mail server thành công! ID={server_id}")
                print("   Vui lòng khởi động lại Odoo để áp dụng.")
            except Exception as e:
                conn.rollback()
                print(f"\n❌ Lỗi: {e}")
        else:
            print("❌ App Password không hợp lệ (cần 16 ký tự)")
    
    conn.close()
    
    print("\n" + "=" * 60)
    print("HƯỚNG DẪN CẤU HÌNH QUA GIAO DIỆN ODOO")
    print("=" * 60)
    print("""
1. Settings → Technical → Email → Outgoing Mail Servers
2. Click 'Create'
3. Điền:
   - Description: Gmail SMTP
   - SMTP Server: smtp.gmail.com
   - SMTP Port: 587
   - Connection Security: TLS (STARTTLS)
   - Username: phamnogc887@gmail.com
   - Password: <App Password 16 ký tự>
4. Click 'Test Connection' → Save
""")

if __name__ == '__main__':
    main()
