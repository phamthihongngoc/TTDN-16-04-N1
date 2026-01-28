# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class HoaDon(models.Model):
    _name = 'hoa_don'
    _description = 'Hóa đơn'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'ngay_hoa_don desc, id desc'

    ma_hoa_don = fields.Char(
        'Mã hóa đơn',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        tracking=True,
    )
    don_hang_id = fields.Many2one('don_hang', string='Đơn hàng', required=True, ondelete='cascade')
    khach_hang_id = fields.Many2one(related='don_hang_id.khach_hang_id', string='Khách hàng', store=True)
    ngay_hoa_don = fields.Date('Ngày hóa đơn', default=fields.Date.context_today, required=True)

    line_ids = fields.One2many('hoa_don.line', 'hoa_don_id', string='Chi tiết hóa đơn', copy=True)

    currency_id = fields.Many2one('res.currency', string='Đơn vị tiền tệ',
                                  default=lambda self: self.env.company.currency_id)
    tong_tien = fields.Monetary('Tổng tiền', compute='_compute_tong_tien', store=True,
                                currency_field='currency_id', tracking=True)

    trang_thai = fields.Selection([
        ('nhap', 'Nháp'),
        ('da_gui', 'Đã gửi'),
        ('da_thanh_toan', 'Đã thanh toán'),
    ], string='Trạng thái', default='nhap', tracking=True)

    _sql_constraints = [
        ('ma_hoa_don_unique', 'unique(ma_hoa_don)', 'Mã hóa đơn đã tồn tại!')
    ]

    def _is_placeholder_ma_hoa_don(self, value):
        return not value or value in {'New', 'Mới', _('New')}

    def _generate_unique_ma_hoa_don(self):
        for _i in range(100):
            candidate = self.env['ir.sequence'].next_by_code('hoa_don')
            if self._is_placeholder_ma_hoa_don(candidate):
                continue
            if not self.sudo().search_count([('ma_hoa_don', '=', candidate)]):
                return candidate
        return self.env['ir.sequence'].next_by_code('hoa_don') or 'New'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            ma_hoa_don = vals.get('ma_hoa_don')
            if self._is_placeholder_ma_hoa_don(ma_hoa_don):
                vals['ma_hoa_don'] = self._generate_unique_ma_hoa_don()
        return super().create(vals_list)

    @api.depends('line_ids', 'line_ids.thanh_tien')
    def _compute_tong_tien(self):
        for record in self:
            record.tong_tien = sum(record.line_ids.mapped('thanh_tien'))

    def action_gui_hoa_don(self):
        for record in self:
            record._send_invoice_email()
            record.trang_thai = 'da_gui'
        return True

    def action_thanh_toan(self):
        for record in self:
            if record.trang_thai == 'da_thanh_toan':
                continue
            record.trang_thai = 'da_thanh_toan'
            if record.don_hang_id:
                record.don_hang_id.trang_thai_thanh_toan = 'da_thanh_toan'
                record.don_hang_id.message_post(
                    body=_('Đơn hàng đã được thanh toán qua hóa đơn %s.') % (record.ma_hoa_don or ''),
                    subtype_xmlid='mail.mt_note'
                )
        return True

    def _send_invoice_email(self):
        self.ensure_one()
        khach_hang = self.khach_hang_id
        if not khach_hang or not khach_hang.email:
            return False

        subject = _('Hóa đơn %s cho đơn hàng %s') % (self.ma_hoa_don, self.don_hang_id.ma_don_hang)
        body_html = (
            f"<p>Xin chào {khach_hang.ten_khach_hang},</p>"
            f"<p>Hóa đơn <strong>{self.ma_hoa_don}</strong> cho đơn hàng "
            f"<strong>{self.don_hang_id.ma_don_hang}</strong> đã được tạo.</p>"
            f"<p>Tổng tiền: <strong>{self.tong_tien:,.0f} {self.currency_id.name}</strong></p>"
            f"<p>Vui lòng đăng nhập hệ thống để xem và thanh toán hóa đơn.</p>"
        )

        email_record = self.env['email_khach_hang'].create({
            'chu_de': subject,
            'noi_dung': body_html,
            'khach_hang_ids': [(6, 0, [khach_hang.id])],
        })
        email_record.action_gui_email()
        return True


class HoaDonLine(models.Model):
    _name = 'hoa_don.line'
    _description = 'Chi tiết hóa đơn'
    _order = 'hoa_don_id, id'

    hoa_don_id = fields.Many2one('hoa_don', string='Hóa đơn', required=True, ondelete='cascade')
    san_pham_id = fields.Many2one('san_pham', string='Sản phẩm', required=True)
    so_luong = fields.Integer('Số lượng', required=True, default=1)
    don_gia = fields.Monetary('Đơn giá', required=True, currency_field='currency_id')
    thanh_tien = fields.Monetary('Thành tiền', compute='_compute_thanh_tien', store=True,
                                  currency_field='currency_id')

    currency_id = fields.Many2one(related='hoa_don_id.currency_id', store=True)

    @api.depends('so_luong', 'don_gia')
    def _compute_thanh_tien(self):
        for record in self:
            record.thanh_tien = record.so_luong * record.don_gia
