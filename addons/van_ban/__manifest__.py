# -*- coding: utf-8 -*-
{
    'name': 'Quản lý Văn bản',
    'version': '15.0.2.0.0',
    'summary': 'Quản lý văn bản với ký điện tử - Phiên bản nâng cấp',
    'description': """
        Module Quản lý Văn bản với Ký Điện tử
        =====================================
        
        Tính năng chính:
        - Tạo và quản lý văn bản (Hợp đồng, Báo giá, Phụ lục)
        - Quy trình duyệt văn bản (Workflow)
        - Ký điện tử nội bộ và khách hàng
        - Phân quyền và bảo mật văn bản
        - Theo dõi lịch sử và Audit Trail
        - Nhắc hạn và cảnh báo tự động
        - Báo cáo và Dashboard
        
        Tích hợp với:
        - Module Quản lý Nhân sự
        - Module Quản lý Khách hàng
    """,
    'author': 'FIT-DNU',
    'category': 'Document Management',
    'depends': ['base', 'mail', 'nhan_su', 'khach_hang', 'ai_integration'],
    'data': [
        'security/van_ban_security.xml',
        'security/ir.model.access.csv',
        'data/loai_van_ban_data.xml',
        'data/workflow_template_data.xml',
        'data/sequence_data.xml',
        'data/cron.xml',
        'data/cron_advanced.xml',  # Cron cho Certificate Rotation, Archive
        'data/cron_reminder.xml',  # Cron nhắc nhở hạn xử lý
        'views/res_config_settings_views.xml',
        'wizard/wizard_ky_dien_tu_views.xml',
        'wizard/wizard_ky_khach_hang_views.xml',
        'views/loai_van_ban_views.xml',
        'views/yeu_cau_ky_views.xml',
        'views/lich_su_van_ban_views.xml',
        'views/van_ban_signature_log_views.xml',
        'views/pki_certificate_views.xml',  # Thêm views cho PKI
        'views/pki_advanced_views.xml',  # Views cho CRL, Rotation, External Storage
        'views/workflow_template_views.xml',
        'views/van_ban_views.xml',
        'views/van_ban_fields_extension_views.xml',  # Views cho Độ mật, Độ khẩn, Phiên bản
        'views/van_ban_den_views.xml',
        'views/van_ban_di_views.xml',
        'views/van_ban_ocr_views.xml',
        'views/dashboard_views.xml',
        'views/van_ban_ai_views.xml',
        'views/technical_menu.xml',
        'views/menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'van_ban/static/src/css/signature_pad.css',
            'van_ban/static/src/css/menu_icons.css',
        ],
    },
    'external_dependencies': {
        'python': [
            'pytesseract',
            'Pillow',
            'pdfplumber',
            'docx',
            'requests',
            'web3',
            'eth_account',
            'textblob',
            'sumy',
            'sklearn',
            'pandas',
            'numpy',
            'openai',
            'tiktoken',
            'cryptography',  # Thêm cryptography cho PKI
            # PAdES signing dependencies (optional):
            # 'pyhanko',
            # 'pyhanko_certvalidator',
            # 'boto3',  # Thêm boto3 cho External Storage (S3/MinIO) - Optional, comment nếu chưa cài
        ],
        'bin': [
            'tesseract',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
