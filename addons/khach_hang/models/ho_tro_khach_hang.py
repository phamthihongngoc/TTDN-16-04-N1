# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class HoTroKhachHang(models.Model):
    _name = 'ho_tro_khach_hang'
    _description = 'Hỗ trợ khách hàng'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'ngay_tao desc'

    # Thông tin cơ bản
    ten_yeu_cau = fields.Char('Tiêu đề yêu cầu', required=True, tracking=True)
    khach_hang_id = fields.Many2one('khach_hang', string='Khách hàng', required=True, 
                                     ondelete='cascade', tracking=True)
    mo_ta = fields.Text('Mô tả chi tiết')
    
    # Phương thức liên lạc
    phuong_thuc = fields.Selection([
        ('email', 'Email'),
        ('dien_thoai', 'Điện thoại'),
        ('truc_tiep', 'Trực tiếp')
    ], string='Phương thức', default='email', tracking=True)
    
    # Thời gian
    ngay_tao = fields.Datetime('Ngày tạo', default=fields.Datetime.now, required=True)
    ngay_hoan_thanh = fields.Datetime('Ngày hoàn thành', tracking=True)
    
    # Trạng thái
    trang_thai = fields.Selection([
        ('moi', 'Mới'),
        ('dang_xu_ly', 'Đang xử lý'),
        ('hoan_thanh', 'Hoàn thành'),
        ('huy', 'Hủy')
    ], string='Trạng thái', default='moi', required=True, tracking=True)
    
    # Nhân viên
    nhan_vien_id = fields.Many2one('nhan_vien', string='Nhân viên xử lý', tracking=True)
    
    # Đánh giá
    danh_gia = fields.Selection([
        ('1', '⭐'),
        ('2', '⭐⭐'),
        ('3', '⭐⭐⭐'),
        ('4', '⭐⭐⭐⭐'),
        ('5', '⭐⭐⭐⭐⭐')
    ], string='Đánh giá', tracking=True)
    
    nhan_xet = fields.Text('Nhận xét')
    
    # Tính toán
    thoi_gian_xu_ly = fields.Float('Thời gian xử lý (giờ)', compute='_compute_thoi_gian_xu_ly', store=True)
    
    # Tiện ích
    active = fields.Boolean('Active', default=True)
    
    @api.depends('ngay_tao', 'ngay_hoan_thanh')
    def _compute_thoi_gian_xu_ly(self):
        """Tính thời gian xử lý tính bằng giờ"""
        for record in self:
            if record.ngay_tao and record.ngay_hoan_thanh:
                delta = record.ngay_hoan_thanh - record.ngay_tao
                record.thoi_gian_xu_ly = delta.total_seconds() / 3600
            else:
                record.thoi_gian_xu_ly = 0.0
    
    def name_get(self):
        """Hiển thị tên yêu cầu"""
        result = []
        for record in self:
            name = f"#{record.id} - {record.ten_yeu_cau}"
            result.append((record.id, name))
        return result
    
    def action_xu_ly(self):
        """Bắt đầu xử lý"""
        self.write({'trang_thai': 'dang_xu_ly'})
    
    def action_hoan_thanh(self):
        """Hoàn thành"""
        self.write({
            'trang_thai': 'hoan_thanh',
            'ngay_hoan_thanh': fields.Datetime.now()
        })
    
    def action_huy(self):
        """Hủy yêu cầu"""
        self.write({'trang_thai': 'huy'})
