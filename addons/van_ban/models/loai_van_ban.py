# -*- coding: utf-8 -*-

from odoo import models, fields, api


class LoaiVanBan(models.Model):
    _name = 'loai_van_ban'
    _description = 'Loại văn bản'
    _order = 'thu_tu, ten_loai'

    ten_loai = fields.Char('Tên loại văn bản', required=True)
    ma_loai = fields.Char('Mã loại', required=True)
    mo_ta = fields.Text('Mô tả')
    thu_tu = fields.Integer('Thứ tự', default=10)
    active = fields.Boolean('Active', default=True)
    
    # Cấu hình workflow
    yeu_cau_duyet = fields.Boolean('Yêu cầu duyệt', default=True,
                                    help='Văn bản loại này cần được duyệt trước khi ký')
    yeu_cau_ky = fields.Boolean('Yêu cầu ký', default=True,
                                 help='Văn bản loại này cần được ký điện tử')
    cho_phep_khach_ky = fields.Boolean('Cho phép khách hàng ký', default=False,
                                        help='Cho phép gửi yêu cầu ký cho khách hàng')
    
    # Template
    mau_van_ban = fields.Binary('Mẫu văn bản', attachment=True)
    ten_file_mau = fields.Char('Tên file mẫu')
    
    # Thống kê
    so_van_ban = fields.Integer('Số văn bản', compute='_compute_so_van_ban')
    
    _sql_constraints = [
        ('ma_loai_unique', 'unique(ma_loai)', 'Mã loại văn bản đã tồn tại!')
    ]
    
    @api.depends()
    def _compute_so_van_ban(self):
        for record in self:
            record.so_van_ban = self.env['van_ban'].search_count([
                ('loai_van_ban_id', '=', record.id)
            ])
