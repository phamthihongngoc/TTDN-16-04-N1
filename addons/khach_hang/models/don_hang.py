# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class DonHang(models.Model):
    _name = 'don_hang'
    _description = 'Đơn hàng'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'ngay_dat_hang desc'

    # Thông tin cơ bản
    ma_don_hang = fields.Char('Mã đơn hàng', required=True, copy=False, readonly=True,
                                default=lambda self: _('New'))
    khach_hang_id = fields.Many2one('khach_hang', string='Khách hàng', required=True,
                                      ondelete='cascade', tracking=True)
    ngay_dat_hang = fields.Date('Ngày đặt hàng', required=True, default=fields.Date.context_today,
                                  tracking=True)
    
    # Trạng thái
    trang_thai = fields.Selection([
        ('moi', 'Mới'),
        ('dang_xu_ly', 'Đang xử lý'),
        ('dang_giao', 'Đang giao'),
        ('hoan_thanh', 'Hoàn thành'),
        ('huy', 'Hủy')
    ], string='Trạng thái', default='moi', required=True, tracking=True)
    
    # Chi tiết đơn hàng
    line_ids = fields.One2many('don_hang.line', 'don_hang_id', string='Chi tiết đơn hàng',
                                 copy=True)
    
    # Tổng tiền
    tong_tien = fields.Monetary('Tổng tiền', compute='_compute_tong_tien', store=True,
                                 currency_field='currency_id', tracking=True)
    thanh_tien = fields.Monetary('Thành tiền', compute='_compute_tong_tien', store=True,
                                  currency_field='currency_id')
    
    # Ghi chú
    ghi_chu = fields.Text('Ghi chú')
    
    # Nhân viên xử lý
    nhan_vien_xu_ly_id = fields.Many2one('nhan_vien', string='Nhân viên xử lý', tracking=True)
    
    # Tiện ích
    currency_id = fields.Many2one('res.currency', string='Đơn vị tiền tệ',
                                    default=lambda self: self.env.company.currency_id)
    
    _sql_constraints = [
        ('ma_don_hang_unique', 'unique(ma_don_hang)', 'Mã đơn hàng đã tồn tại!')
    ]
    
    @api.model
    def create(self, vals):
        """Tự động tạo mã đơn hàng"""
        if vals.get('ma_don_hang', _('New')) == _('New'):
            vals['ma_don_hang'] = self.env['ir.sequence'].next_by_code('don_hang') or _('New')
        return super(DonHang, self).create(vals)
    
    @api.depends('line_ids', 'line_ids.thanh_tien')
    def _compute_tong_tien(self):
        """Tính tổng tiền đơn hàng"""
        for record in self:
            record.tong_tien = sum(record.line_ids.mapped('thanh_tien'))
            record.thanh_tien = record.tong_tien
    
    def action_xac_nhan(self):
        """Xác nhận đơn hàng"""
        for record in self:
            if not record.line_ids:
                raise ValidationError('Vui lòng thêm sản phẩm vào đơn hàng!')
            record.trang_thai = 'dang_xu_ly'
    
    def action_giao_hang(self):
        """Chuyển trạng thái đang giao"""
        for record in self:
            record.trang_thai = 'dang_giao'
    
    def action_hoan_thanh(self):
        """Hoàn thành đơn hàng"""
        for record in self:
            record.trang_thai = 'hoan_thanh'
            # Cập nhật tồn kho
            for line in record.line_ids:
                if line.san_pham_id:
                    line.san_pham_id.so_luong_ton_kho -= line.so_luong
    
    def action_huy(self):
        """Hủy đơn hàng"""
        for record in self:
            record.trang_thai = 'huy'


class DonHangLine(models.Model):
    _name = 'don_hang.line'
    _description = 'Chi tiết đơn hàng'
    _order = 'don_hang_id, sequence, id'

    sequence = fields.Integer('Thứ tự', default=10)
    don_hang_id = fields.Many2one('don_hang', string='Đơn hàng', required=True, ondelete='cascade')
    san_pham_id = fields.Many2one('san_pham', string='Sản phẩm', required=True)
    ten_san_pham = fields.Char('Tên sản phẩm', related='san_pham_id.ten_san_pham', store=True)
    so_luong = fields.Integer('Số lượng', required=True, default=1)
    don_gia = fields.Monetary('Đơn giá', required=True, currency_field='currency_id')
    thanh_tien = fields.Monetary('Thành tiền', compute='_compute_thanh_tien', store=True,
                                  currency_field='currency_id')
    ghi_chu = fields.Char('Ghi chú')
    
    currency_id = fields.Many2one(related='don_hang_id.currency_id', store=True)
    
    _sql_constraints = [
        ('check_so_luong', 'CHECK(so_luong > 0)', 'Số lượng phải lớn hơn 0!'),
        ('check_don_gia', 'CHECK(don_gia >= 0)', 'Đơn giá không được âm!')
    ]
    
    @api.depends('so_luong', 'don_gia')
    def _compute_thanh_tien(self):
        """Tính thành tiền"""
        for record in self:
            record.thanh_tien = record.so_luong * record.don_gia
    
    @api.onchange('san_pham_id')
    def _onchange_san_pham(self):
        """Tự động điền đơn giá khi chọn sản phẩm"""
        if self.san_pham_id:
            self.don_gia = self.san_pham_id.don_gia
