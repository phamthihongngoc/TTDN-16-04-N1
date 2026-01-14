# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class SanPham(models.Model):
    _name = 'san_pham'
    _description = 'Sản phẩm'
    _rec_name = 'ten_san_pham'
    _order = 'ten_san_pham'

    # Thông tin sản phẩm
    ten_san_pham = fields.Char('Tên sản phẩm', required=True)
    ma_san_pham = fields.Char('Mã sản phẩm', copy=False)
    loai_san_pham = fields.Selection([
        ('headphone', 'Headphone'),
        ('iphone', 'Iphone'),
        ('laptop', 'Laptop'),
        ('samsung', 'Samsung'),
        ('vivo', 'Vivo')
    ], string='Loại sản phẩm', required=True)
    thuong_hieu = fields.Char('Thương hiệu')
    mo_ta = fields.Text('Mô tả')
    
    # Giá và kho
    don_gia = fields.Monetary('Đơn giá', required=True, currency_field='currency_id')
    so_luong_ton_kho = fields.Integer('Số lượng tồn kho', default=0)
    tong_gia_tri_kho = fields.Monetary('Tổng giá trị kho', compute='_compute_tong_gia_tri_kho',
                                        store=True, currency_field='currency_id')
    
    # Bảo hành
    thoi_gian_bao_hanh = fields.Integer('Thời gian bảo hành (tháng)', default=12,
                                          help='Thời gian bảo hành tính theo tháng')
    
    # Quan hệ
    don_hang_line_ids = fields.One2many('don_hang.line', 'san_pham_id', string='Dòng đơn hàng')
    
    # Thống kê
    so_luong_da_ban = fields.Integer('Số lượng đã bán', compute='_compute_thong_ke', store=True)
    doanh_thu = fields.Monetary('Doanh thu', compute='_compute_thong_ke', store=True,
                                 currency_field='currency_id')
    
    # Tiện ích
    currency_id = fields.Many2one('res.currency', string='Đơn vị tiền tệ',
                                    default=lambda self: self.env.company.currency_id)
    active = fields.Boolean('Active', default=True)
    hinh_anh = fields.Binary('Hình ảnh')
    
    @api.onchange('loai_san_pham')
    def _onchange_loai_san_pham(self):
        """Tự sinh mã sản phẩm khi chọn loại"""
        if self.loai_san_pham and not self.ma_san_pham:
            sequence_code = f"san_pham.{self.loai_san_pham}"
            self.ma_san_pham = self.env['ir.sequence'].next_by_code(sequence_code)
    
    @api.depends('don_gia', 'so_luong_ton_kho')
    def _compute_tong_gia_tri_kho(self):
        """Tính tổng giá trị kho"""
        for record in self:
            record.tong_gia_tri_kho = record.don_gia * record.so_luong_ton_kho
    
    @api.depends('don_hang_line_ids', 'don_hang_line_ids.so_luong', 'don_hang_line_ids.thanh_tien')
    def _compute_thong_ke(self):
        """Tính thống kê bán hàng"""
        for record in self:
            lines = record.don_hang_line_ids.filtered(
                lambda l: l.don_hang_id.trang_thai == 'hoan_thanh'
            )
            record.so_luong_da_ban = sum(lines.mapped('so_luong'))
            record.doanh_thu = sum(lines.mapped('thanh_tien'))
    
    def name_get(self):
        """Hiển thị tên sản phẩm kèm mã"""
        result = []
        for record in self:
            if record.ma_san_pham:
                name = f"[{record.ma_san_pham}] {record.ten_san_pham}"
            else:
                name = record.ten_san_pham
            result.append((record.id, name))
        return result
    
    def action_nhap_kho(self):
        """Nhập kho sản phẩm"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Nhập kho',
            'res_model': 'san_pham.nhap_kho.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_san_pham_id': self.id}
        }
    
    def action_xuat_kho(self):
        """Xuất kho sản phẩm"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Xuất kho',
            'res_model': 'san_pham.xuat_kho.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_san_pham_id': self.id}
        }
