#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os

# Add Odoo to path
sys.path.append('/home/hongngoc/odoo-fitdnu')
os.chdir('/home/hongngoc/odoo-fitdnu')

import odoo
from odoo import registry, SUPERUSER_ID, api

# Load config
odoo.tools.config['db_host'] = False
odoo.tools.config['db_port'] = False
odoo.tools.config['db_user'] = 'ngoc'
odoo.tools.config['db_password'] = False
odoo.tools.config['addons_path'] = '/home/hongngoc/odoo-fitdnu/odoo/addons,/home/hongngoc/odoo-fitdnu/addons'

db = registry('ngoc')
with db.cursor() as cr:
    env = api.Environment(cr, SUPERUSER_ID, {})
    
    # Kiểm tra xem models đã tồn tại chưa
    models_to_check = [
        'ai.chat.session',
        'ai.chat.message', 
        'ai.chat.tool',
        'ai.chat.orchestrator',
        'ai.context.khach.hang',
        'ai.context.van.ban',
        'ai.chat.tool.khach.hang',
        'ai.chat.tool.van.ban'
    ]
    
    print("=== KIỂM TRA CÁC MODEL CHATBOT ===")
    for model_name in models_to_check:
        try:
            model = env[model_name]
            print(f"✓ {model_name}: OK")
        except KeyError:
            print(f"✗ {model_name}: KHÔNG TỒN TẠI")
    
    # Kiểm tra tools đã được tạo chưa
    print("\n=== KIỂM TRA TOOLS ===")
    try:
        tools = env['ai.chat.tool'].search([])
        print(f"Số lượng tools: {len(tools)}")
        for tool in tools:
            print(f"  - {tool.name} ({tool.module})")
    except Exception as e:
        print(f"Lỗi: {e}")
    
    # Kiểm tra session
    print("\n=== KIỂM TRA SESSIONS ===")
    try:
        sessions = env['ai.chat.session'].search([])
        print(f"Số lượng sessions: {len(sessions)}")
    except Exception as e:
        print(f"Lỗi: {e}")
