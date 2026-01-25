# -*- coding: utf-8 -*-
"""
Script thiết lập API key cho OpenAI
Chạy script này sau khi cài đặt module ai_integration

Sử dụng:
    python3 setup_ai_api_key.py

Hoặc trong Odoo shell:
    ./odoo-bin shell -c odoo.conf
    >>> env['ir.config_parameter'].sudo().set_param('ai_integration.openai_api_key', 'YOUR_API_KEY')
"""

import os
import sys

# Thêm đường dẫn Odoo vào sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def setup_api_key():
    """Thiết lập API key trong database"""
    try:
        import odoo
        from odoo import api, SUPERUSER_ID
        from odoo.tools import config
        
        # Load config
        config.parse_config(['--config', 'odoo.conf'])
        
        # Kết nối database
        db_name = config['db_name']
        if not db_name:
            print("Lỗi: Không tìm thấy database name trong odoo.conf")
            return
        
        registry = odoo.registry(db_name)
        with registry.cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            
            # Thiết lập API key
            api_key = os.environ.get('OPENAI_API_KEY', '')
            if not api_key:
                api_key = input("Nhập OpenAI API Key: ").strip()
            
            if api_key:
                env['ir.config_parameter'].sudo().set_param(
                    'ai_integration.openai_api_key', 
                    api_key
                )
                print(f"✓ Đã thiết lập API key thành công!")
                
                # Thiết lập các config mặc định khác
                defaults = {
                    'ai_integration.default_model': 'gpt-4o-mini',
                    'ai_integration.max_tokens': '4096',
                    'ai_integration.temperature': '0.7',
                    'ai_integration.cache_enabled': 'True',
                    'ai_integration.cache_ttl': '3600',
                }
                
                for key, value in defaults.items():
                    existing = env['ir.config_parameter'].sudo().get_param(key)
                    if not existing:
                        env['ir.config_parameter'].sudo().set_param(key, value)
                        print(f"  ✓ Thiết lập {key} = {value}")
                
                cr.commit()
                print("\n✓ Hoàn tất thiết lập AI Integration!")
            else:
                print("Lỗi: API key không được cung cấp")
                
    except ImportError as e:
        print(f"Lỗi import: {e}")
        print("Hãy chạy script này từ thư mục gốc của Odoo")
    except Exception as e:
        print(f"Lỗi: {e}")

if __name__ == '__main__':
    setup_api_key()
