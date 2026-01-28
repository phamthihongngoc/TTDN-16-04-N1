# -*- coding: utf-8 -*-

from odoo import models, fields, api


class LoaiPhuCap(models.Model):
    _name = 'loai_phu_cap'
    _description = 'Loại phụ cấp'
    _order = 'sequence, name'

    name = fields.Char('Tên phụ cấp', required=True)
    code = fields.Char('Mã', required=True)
    sequence = fields.Integer('Thứ tự', default=10)
    active = fields.Boolean('Hoạt động', default=True)
    
    loai_tinh = fields.Selection([
        ('co_dinh', 'Cố định hàng tháng'),
        ('theo_cong', 'Theo ngày công'),
        ('theo_gio', 'Theo giờ làm')
    ], string='Cách tính', default='co_dinh', required=True)
    
    so_tien = fields.Monetary('Số tiền mặc định', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    
    tinh_vao_bhxh = fields.Boolean('Tính vào BHXH', default=False,
                                    help='Có tính phụ cấp này vào lương đóng BHXH không')
    tinh_vao_thue = fields.Boolean('Tính vào thuế TNCN', default=True,
                                    help='Có tính phụ cấp này vào thu nhập chịu thuế không')
    
    ghi_chu = fields.Text('Ghi chú')
    
    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Mã phụ cấp đã tồn tại!')
    ]


class PhuCapNhanVien(models.Model):
    _name = 'phu_cap_nhan_vien'
    _description = 'Phụ cấp nhân viên'
    _order = 'nhan_vien_id, loai_phu_cap_id'

    nhan_vien_id = fields.Many2one('nhan_vien', string='Nhân viên', required=True, 
                                    ondelete='cascade', index=True)
    loai_phu_cap_id = fields.Many2one('loai_phu_cap', string='Loại phụ cấp', 
                                       required=True, ondelete='restrict')
    
    so_tien = fields.Monetary('Số tiền', required=True, currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    
    ngay_bat_dau = fields.Date('Ngày bắt đầu', default=fields.Date.today)
    ngay_ket_thuc = fields.Date('Ngày kết thúc', help='Để trống nếu không có thời hạn')
    
    con_hieu_luc = fields.Boolean('Còn hiệu lực', compute='_compute_con_hieu_luc', store=True)
    ghi_chu = fields.Text('Ghi chú')
    
    @api.depends('ngay_bat_dau', 'ngay_ket_thuc')
    def _compute_con_hieu_luc(self):
        today = fields.Date.today()
        for rec in self:
            if rec.ngay_ket_thuc:
                rec.con_hieu_luc = rec.ngay_bat_dau <= today <= rec.ngay_ket_thuc
            else:
                rec.con_hieu_luc = rec.ngay_bat_dau <= today
    
    _sql_constraints = [
        ('unique_nhan_vien_phu_cap', 'unique(nhan_vien_id, loai_phu_cap_id)', 
         'Mỗi nhân viên chỉ có một phụ cấp cùng loại!')
    ]


class CauHinhBHXH(models.Model):
    _name = 'cau_hinh_bhxh'
    _description = 'Cấu hình bảo hiểm xã hội'
    _order = 'ngay_ap_dung desc'
    _rec_name = 'ten'

    ten = fields.Char('Tên cấu hình', required=True)
    ngay_ap_dung = fields.Date('Ngày áp dụng', required=True, default=fields.Date.today)
    active = fields.Boolean('Hoạt động', default=True)
    
    # Tỷ lệ đóng của người lao động
    ty_le_bhxh_nld = fields.Float('BHXH - NLĐ (%)', default=8.0, 
                                   help='Bảo hiểm xã hội người lao động đóng')
    ty_le_bhyt_nld = fields.Float('BHYT - NLĐ (%)', default=1.5,
                                   help='Bảo hiểm y tế người lao động đóng')
    ty_le_bhtn_nld = fields.Float('BHTN - NLĐ (%)', default=1.0,
                                   help='Bảo hiểm thất nghiệp người lao động đóng')
    
    # Tỷ lệ đóng của doanh nghiệp
    ty_le_bhxh_dn = fields.Float('BHXH - DN (%)', default=17.5,
                                  help='Bảo hiểm xã hội doanh nghiệp đóng')
    ty_le_bhyt_dn = fields.Float('BHYT - DN (%)', default=3.0,
                                  help='Bảo hiểm y tế doanh nghiệp đóng')
    ty_le_bhtn_dn = fields.Float('BHTN - DN (%)', default=1.0,
                                  help='Bảo hiểm thất nghiệp doanh nghiệp đóng')
    
    # Tổng
    tong_ty_le_nld = fields.Float('Tổng NLĐ (%)', compute='_compute_tong', store=True)
    tong_ty_le_dn = fields.Float('Tổng DN (%)', compute='_compute_tong', store=True)
    
    # Mức lương tối thiểu/tối đa đóng BHXH
    luong_co_so = fields.Monetary('Lương cơ sở', default=1800000, currency_field='currency_id',
                                   help='Mức lương cơ sở để tính BHXH')
    luong_toi_da_bhxh = fields.Monetary('Mức lương tối đa đóng BHXH', 
                                         compute='_compute_luong_toi_da', store=True,
                                         currency_field='currency_id',
                                         help='20 lần mức lương cơ sở')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    
    # Giảm trừ gia cảnh (thuế TNCN)
    giam_tru_ban_than = fields.Monetary('Giảm trừ bản thân', default=11000000,
                                         currency_field='currency_id')
    giam_tru_nguoi_phu_thuoc = fields.Monetary('Giảm trừ người phụ thuộc', default=4400000,
                                                currency_field='currency_id')
    
    ghi_chu = fields.Text('Ghi chú')
    
    @api.depends('ty_le_bhxh_nld', 'ty_le_bhyt_nld', 'ty_le_bhtn_nld',
                 'ty_le_bhxh_dn', 'ty_le_bhyt_dn', 'ty_le_bhtn_dn')
    def _compute_tong(self):
        for rec in self:
            rec.tong_ty_le_nld = rec.ty_le_bhxh_nld + rec.ty_le_bhyt_nld + rec.ty_le_bhtn_nld
            rec.tong_ty_le_dn = rec.ty_le_bhxh_dn + rec.ty_le_bhyt_dn + rec.ty_le_bhtn_dn
    
    @api.depends('luong_co_so')
    def _compute_luong_toi_da(self):
        for rec in self:
            rec.luong_toi_da_bhxh = rec.luong_co_so * 20
    
    @api.model
    def get_current_config(self):
        """Lấy cấu hình BHXH hiện tại"""
        today = fields.Date.today()
        config = self.search([
            ('active', '=', True),
            ('ngay_ap_dung', '<=', today)
        ], order='ngay_ap_dung desc', limit=1)
        return config


class BangThueTNCN(models.Model):
    _name = 'bang_thue_tncn'
    _description = 'Bảng thuế thu nhập cá nhân lũy tiến'
    _order = 'thu_nhap_tu'

    thu_nhap_tu = fields.Monetary('Thu nhập từ', required=True, currency_field='currency_id')
    thu_nhap_den = fields.Monetary('Thu nhập đến', currency_field='currency_id',
                                    help='Để trống nếu là mức cao nhất')
    ty_le_thue = fields.Float('Tỷ lệ thuế (%)', required=True)
    so_tien_tru = fields.Monetary('Số tiền trừ nhanh', currency_field='currency_id',
                                   help='Số tiền trừ để tính nhanh')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    
    @api.model
    def tinh_thue_tncn(self, thu_nhap_chiu_thue):
        """Tính thuế TNCN theo biểu lũy tiến"""
        if thu_nhap_chiu_thue <= 0:
            return 0
        
        # Tìm bậc thuế phù hợp
        bac_thue = self.search([
            ('thu_nhap_tu', '<=', thu_nhap_chiu_thue),
            '|',
            ('thu_nhap_den', '>=', thu_nhap_chiu_thue),
            ('thu_nhap_den', '=', False)
        ], order='thu_nhap_tu desc', limit=1)
        
        if bac_thue:
            # Tính theo công thức nhanh
            thue = thu_nhap_chiu_thue * bac_thue.ty_le_thue / 100 - bac_thue.so_tien_tru
            return max(0, thue)
        return 0
