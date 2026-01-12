# -*- coding: utf-8 -*-
{
    'name': "Quản lý nhân sự",

    'summary': """
        Module quản lý nhân sự với phân quyền và vai trò trong quy trình văn bản""",

    'description': """
        Module Quản lý Nhân sự (HR)
        ============================
        
        Chức năng chính:
        - Quản lý hồ sơ nhân viên (thông tin cá nhân, công việc, trạng thái)
        - Phân quyền và vai trò nhân sự (Nhân viên, Trưởng phòng, Giám đốc)
        - Quản lý chấm công
        - Quản lý bảng lương
        - Phân công và xử lý khách hàng
        - Quy trình duyệt văn bản (Soạn thảo - Duyệt - Phê duyệt)
        
        Vai trò và quyền hạn:
        - Nhân viên kinh doanh: Soạn thảo, quản lý khách hàng được phân công
        - Trưởng phòng: Duyệt văn bản, phân công nhân viên
        - Giám đốc: Phê duyệt cuối cùng, toàn quyền quản lý
    """,

    'author': "FitDNU",
    'website': "https://www.fitdnu.com",
    'category': 'Human Resources',
    'version': '1.0',

    # any module necessary for this one to work correctly
    'depends': ['base', 'mail'],

    # always loaded
    'data': [
        'security/nhan_su_security.xml',
        'security/ir.model.access.csv',
        'data/vai_tro_data.xml',
        'views/nhan_vien.xml',
        'views/vai_tro.xml',
        'views/cham_cong.xml',
        'views/bang_luong.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
