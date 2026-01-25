# -*- coding: utf-8 -*-
{
    'name': 'AI Integration - OpenAI',
    'version': '15.0.2.0.0',
    'summary': 'Tích hợp OpenAI ChatGPT API cho hệ thống Odoo',
    'description': """
AI Integration - OpenAI
=======================

Tính năng chính:

* Kết nối OpenAI ChatGPT API (GPT-4, GPT-3.5-turbo)
* Service dùng chung cho tất cả modules  
* Tóm tắt văn bản tự động
* Trích xuất thông tin có cấu trúc
* Phân loại và gắn nhãn tự động
* Chat hỏi đáp theo ngữ cảnh (RAG)
* Soạn thảo nội dung chuẩn hóa
* Lưu log và audit trail
* Quản lý chi phí token

CHATBOT THÔNG MINH:

* AI Assistant với function calling
* Context-aware cho từng module
* Thực thi hành động có xác nhận
* Chat panel tích hợp sẵn

Tích hợp với: Văn bản, Nhân sự, Khách hàng
    """,
    'author': 'FIT-DNU',
    'category': 'Technical',
    'depends': ['base', 'mail'],
    'data': [
        'security/ai_security.xml',
        'security/ir.model.access.csv',
        'data/ai_config_data.xml',
        'data/ai_chat_tools_data.xml',
        'views/ai_config_settings_views.xml',
        'views/ai_job_views.xml',
        'views/ai_log_views.xml',
        'views/ai_chat_views.xml',
        'wizard/ai_assistant_wizard_views.xml',
        'views/menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'ai_integration/static/src/scss/ai_chat.scss',
            'ai_integration/static/src/js/ai_chat_widget.js',
            'ai_integration/static/src/js/ai_chat_systray.js',
        ],
        'web.assets_qweb': [
            'ai_integration/static/src/xml/ai_chat_templates.xml',
        ],
    },
    'external_dependencies': {
        'python': ['openai', 'tiktoken'],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
