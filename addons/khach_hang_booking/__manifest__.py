# -*- coding: utf-8 -*-
{
    'name': 'Đặt lịch hẹn Khách hàng - Google Calendar & Zoom',
    'version': '15.0.1.0.0',
    'category': 'Sales/CRM',
    'summary': 'Tích hợp đặt lịch hẹn khách hàng với Google Calendar và Zoom Meeting',
    'description': """
Module Đặt lịch hẹn Khách hàng
================================

Tính năng chính:

* Đặt lịch hẹn trực tiếp từ hồ sơ khách hàng
* Tích hợp Zoom Meeting (Server-to-Server OAuth)
* Đồng bộ Google Calendar (OAuth 2.0 + Refresh Token)
* Quản lý lịch hẹn với trạng thái và nhắc nhở
* Tự động tạo link Zoom khi chọn hẹn trực tuyến
* Đồng bộ 2 chiều với Google Calendar

Luồng tích hợp:

1. Zoom: Server-to-Server OAuth, tự động refresh token
2. Google Calendar: OAuth 2.0 với refresh token, admin authorize 1 lần
    """,
    'author': 'FitDNU',
    'website': 'https://www.fitdnu.com',
    'depends': ['base', 'mail', 'calendar', 'khach_hang'],
    'data': [
        'security/booking_security.xml',
        'security/ir.model.access.csv',
        'data/sequence_data.xml',
        'wizard/booking_quick_create_wizard_views.xml',
        'views/zoom_integration_views.xml',
        'views/google_calendar_integration_views.xml',
        'views/customer_booking_views.xml',
        'views/khach_hang_views_extend.xml',
        'views/menu.xml',
    ],
    'external_dependencies': {
        'python': ['requests'],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
