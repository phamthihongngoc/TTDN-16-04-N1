# -*- coding: utf-8 -*-
{
    'name': 'Quản lý Khách hàng (CRM)',
    'version': '1.0',
    'category': 'Sales/CRM',
    'summary': 'Quản lý khách hàng, hỗ trợ, đơn hàng và email marketing',
    'description': """
        Module Quản lý Khách hàng (CRM)
        ================================
        
        Chức năng chính:
        - Quản lý thông tin khách hàng và phân loại
        - Hỗ trợ và chăm sóc khách hàng
        - Quản lý đơn hàng và sản phẩm
        - Gửi email thông báo khách hàng
        - Thống kê và xếp hạng khách hàng
        - Tích hợp với module Nhân sự để phân công
        
        Tính năng nổi bật:
        - Phân loại khách hàng (Tiềm năng cao/thấp)
        - Trạng thái khách hàng (Mới/Đang giao dịch/Cũ)
        - Đánh giá mức độ hài lòng (1-5 sao)
        - Bảng xếp hạng theo doanh thu
        - Email marketing tích hợp
    """,
    'author': 'FitDNU',
    'website': 'https://www.fitdnu.com',
    'depends': ['base', 'mail', 'nhan_su', 'ai_integration'],
    'data': [
        'security/khach_hang_security.xml',
        'security/ir.model.access.csv',
        'data/sequence_data.xml',
        'data/san_pham_data.xml',
        'data/cron.xml',
        'views/khach_hang_views.xml',
        'views/ho_tro_khach_hang_views.xml',
        'views/don_hang_views.xml',
        'views/phieu_xuat_kho_views.xml',
        'views/hoa_don_views.xml',
        'views/san_pham_views.xml',
        'views/email_khach_hang_views.xml',
        'views/dashboard_views.xml',
        'views/dashboard_chart_views.xml',
        'views/dashboard_advanced_views.xml',
        'views/dashboard_modern_views.xml',
        'views/kanban_advanced_views.xml',
        'views/khach_hang_ai_views.xml',
        'views/menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'khach_hang/static/src/css/dashboard.css',
            'khach_hang/static/src/css/khach_hang_modern.css',
        ],
    },
    'demo': [],
    'external_dependencies': {
        'python': [
            'pandas',
            'numpy',
            'sklearn',  # scikit-learn
            # 'stripe',  # Optional payment gateways
            # 'paypalrestsdk',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
