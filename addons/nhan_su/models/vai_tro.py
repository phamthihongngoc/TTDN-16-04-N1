# -*- coding: utf-8 -*-

from odoo import models, fields, api


class VaiTro(models.Model):
    _name = 'vai_tro'
    _description = 'Vai trò nhân sự trong quy trình văn bản'
    _order = 'thu_tu, ten_vai_tro'

    ten_vai_tro = fields.Char('Tên vai trò', required=True, 
                               help='VD: Nhân viên kinh doanh, Trưởng phòng, Giám đốc')
    ma_vai_tro = fields.Char('Mã vai trò', required=True, copy=False,
                              help='Mã định danh duy nhất cho vai trò')
    mo_ta = fields.Text('Mô tả', help='Mô tả chi tiết về vai trò và trách nhiệm')
    thu_tu = fields.Integer('Thứ tự', default=10, 
                             help='Thứ tự ưu tiên trong workflow (số càng nhỏ càng ưu tiên)')
    color = fields.Integer('Màu sắc', default=0, 
                           help='Màu sắc hiển thị cho vai trò trong giao diện')
    active = fields.Boolean('Hoạt động', default=True)
    
    # Phân quyền xử lý văn bản
    quyen_soan_thao = fields.Boolean('Quyền soạn thảo', default=True,
                                      help='Được phép tạo và soạn thảo văn bản mới')
    quyen_duyet = fields.Boolean('Quyền duyệt', default=False,
                                  help='Được phép duyệt văn bản (cấp trưởng phòng)')
    quyen_phe_duyet = fields.Boolean('Quyền phê duyệt', default=False,
                                      help='Được phép phê duyệt cuối cùng (cấp giám đốc)')
    quyen_huy = fields.Boolean('Quyền hủy', default=False,
                                help='Được phép hủy bỏ văn bản đã được duyệt')
    quyen_xem_tat_ca = fields.Boolean('Quyền xem tất cả', default=False,
                                       help='Được xem tất cả văn bản trong hệ thống')
    
    # Quyền quản lý khách hàng
    quyen_them_khach_hang = fields.Boolean('Quyền thêm khách hàng', default=True,
                                            help='Được phép tạo mới khách hàng')
    quyen_phan_cong_khach_hang = fields.Boolean('Quyền phân công', default=False,
                                                  help='Được phép phân công khách hàng cho nhân viên khác')
    quyen_xem_khach_hang_tat_ca = fields.Boolean('Xem tất cả khách hàng', default=False,
                                                   help='Xem được tất cả khách hàng, không chỉ của mình')
    
    # Quyền quản lý nhân sự
    quyen_quan_ly_nhan_su = fields.Boolean('Quyền quản lý nhân sự', default=False,
                                            help='Được phép thêm/sửa/xóa nhân viên')
    quyen_phan_quyen = fields.Boolean('Quyền phân quyền', default=False,
                                       help='Được phép gán vai trò cho nhân viên khác')
    
    # Mối quan hệ
    nhan_vien_ids = fields.Many2many('nhan_vien', string='Nhân viên',
                                      help='Danh sách nhân viên có vai trò này')
    so_nhan_vien = fields.Integer('Số nhân viên', compute='_compute_so_nhan_vien', store=True)
    
    # Security group liên kết
    group_id = fields.Many2one('res.groups', string='Nhóm quyền hệ thống',
                                help='Liên kết với nhóm quyền của Odoo')
    
    _sql_constraints = [
        ('ma_vai_tro_unique', 'unique(ma_vai_tro)', 'Mã vai trò đã tồn tại!')
    ]
    
    @api.depends('nhan_vien_ids')
    def _compute_so_nhan_vien(self):
        """Tính số nhân viên có vai trò này"""
        for record in self:
            record.so_nhan_vien = len(record.nhan_vien_ids)
    
    def name_get(self):
        """Hiển thị tên vai trò kèm số nhân viên"""
        result = []
        for record in self:
            name = f"{record.ten_vai_tro} ({record.so_nhan_vien} NV)"
            result.append((record.id, name))
        return result
    
    @api.model
    def create_default_roles(self):
        """Tạo các vai trò mặc định cho hệ thống"""
        default_roles = [
            {
                'ten_vai_tro': 'Nhân viên kinh doanh',
                'ma_vai_tro': 'NVKD',
                'mo_ta': 'Nhân viên kinh doanh - Soạn thảo văn bản, quản lý khách hàng được phân công',
                'thu_tu': 30,
                'quyen_soan_thao': True,
                'quyen_duyet': False,
                'quyen_phe_duyet': False,
                'quyen_them_khach_hang': True,
                'quyen_phan_cong_khach_hang': False,
                'quyen_xem_khach_hang_tat_ca': False,
            },
            {
                'ten_vai_tro': 'Trưởng phòng',
                'ma_vai_tro': 'TP',
                'mo_ta': 'Trưởng phòng - Duyệt văn bản, phân công nhân viên',
                'thu_tu': 20,
                'quyen_soan_thao': True,
                'quyen_duyet': True,
                'quyen_phe_duyet': False,
                'quyen_huy': False,
                'quyen_xem_tat_ca': True,
                'quyen_them_khach_hang': True,
                'quyen_phan_cong_khach_hang': True,
                'quyen_xem_khach_hang_tat_ca': True,
            },
            {
                'ten_vai_tro': 'Giám đốc',
                'ma_vai_tro': 'GD',
                'mo_ta': 'Giám đốc - Phê duyệt cuối cùng, toàn quyền quản lý',
                'thu_tu': 10,
                'quyen_soan_thao': True,
                'quyen_duyet': True,
                'quyen_phe_duyet': True,
                'quyen_huy': True,
                'quyen_xem_tat_ca': True,
                'quyen_them_khach_hang': True,
                'quyen_phan_cong_khach_hang': True,
                'quyen_xem_khach_hang_tat_ca': True,
                'quyen_quan_ly_nhan_su': True,
                'quyen_phan_quyen': True,
            },
        ]
        
        for role_data in default_roles:
            existing = self.search([('ma_vai_tro', '=', role_data['ma_vai_tro'])], limit=1)
            if not existing:
                self.create(role_data)
        
        return True
