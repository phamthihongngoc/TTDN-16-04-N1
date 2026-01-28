# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class PhieuXuatKho(models.Model):
    _name = 'phieu_xuat_kho'
    _description = 'Phiếu xuất kho'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'ngay_xuat desc, id desc'

    ma_phieu = fields.Char(
        'Mã phiếu',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        tracking=True,
    )
    don_hang_id = fields.Many2one('don_hang', string='Đơn hàng', required=True, ondelete='cascade')
    khach_hang_id = fields.Many2one(related='don_hang_id.khach_hang_id', string='Khách hàng', store=True)
    ngay_xuat = fields.Date('Ngày xuất', default=fields.Date.context_today, required=True)

    line_ids = fields.One2many('phieu_xuat_kho.line', 'phieu_xuat_kho_id', string='Chi tiết xuất kho', copy=True)

    trang_thai = fields.Selection([
        ('moi', 'Mới'),
        ('da_xuat', 'Đã xuất kho'),
    ], string='Trạng thái', default='moi', tracking=True)

    _sql_constraints = [
        ('ma_phieu_unique', 'unique(ma_phieu)', 'Mã phiếu xuất kho đã tồn tại!')
    ]

    def _is_placeholder_ma_phieu(self, value):
        return not value or value in {'New', 'Mới', _('New')}

    def _generate_unique_ma_phieu(self):
        for _i in range(100):
            candidate = self.env['ir.sequence'].next_by_code('phieu_xuat_kho')
            if self._is_placeholder_ma_phieu(candidate):
                continue
            if not self.sudo().search_count([('ma_phieu', '=', candidate)]):
                return candidate
        return self.env['ir.sequence'].next_by_code('phieu_xuat_kho') or 'New'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            ma_phieu = vals.get('ma_phieu')
            if self._is_placeholder_ma_phieu(ma_phieu):
                vals['ma_phieu'] = self._generate_unique_ma_phieu()
        return super().create(vals_list)

    def action_xuat_kho(self):
        for record in self:
            if record.trang_thai == 'da_xuat':
                continue
            if not record.line_ids:
                raise ValidationError('Phiếu xuất kho không có dòng sản phẩm!')

            for line in record.line_ids:
                if line.san_pham_id and line.so_luong:
                    line.san_pham_id.so_luong_ton_kho -= line.so_luong

            record.trang_thai = 'da_xuat'
            if record.don_hang_id and record.don_hang_id.trang_thai not in ['hoan_thanh', 'huy']:
                record.don_hang_id.trang_thai = 'dang_giao'
        return True


class PhieuXuatKhoLine(models.Model):
    _name = 'phieu_xuat_kho.line'
    _description = 'Chi tiết phiếu xuất kho'
    _order = 'phieu_xuat_kho_id, id'

    phieu_xuat_kho_id = fields.Many2one('phieu_xuat_kho', string='Phiếu xuất kho', required=True, ondelete='cascade')
    san_pham_id = fields.Many2one('san_pham', string='Sản phẩm', required=True)
    so_luong = fields.Integer('Số lượng', required=True, default=1)
    ghi_chu = fields.Char('Ghi chú')
