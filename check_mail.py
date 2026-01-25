#!/usr/bin/env python3
import psycopg2
conn = psycopg2.connect(dbname='ngoc', user='odoo', password='odoo', host='localhost')
cur = conn.cursor()
cur.execute('SELECT name, smtp_host, smtp_port, smtp_user, active FROM ir_mail_server')
print('=== MAIL SERVERS ===')
servers = cur.fetchall()
if servers:
    for r in servers: print(r)
else:
    print('No mail server configured')
cur.execute('SELECT id, login, email FROM res_users WHERE active=true LIMIT 5')
print('\n=== USERS ===')
for r in cur.fetchall(): print(r)
conn.close()
