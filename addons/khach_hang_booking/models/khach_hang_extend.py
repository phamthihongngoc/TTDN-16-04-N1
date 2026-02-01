# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class KhachHangExtend(models.Model):
    """Mở rộng model khach_hang để thêm tính năng booking"""
    _inherit = 'khach_hang'

    booking_ids = fields.One2many('customer.booking', 'khach_hang_id', string='Lịch hẹn')
    booking_count = fields.Integer('Số lịch hẹn', compute='_compute_booking_count')
    next_booking_id = fields.Many2one('customer.booking', string='Lịch hẹn tiếp theo',
                                       compute='_compute_next_booking')
    next_booking_date = fields.Datetime('Ngày hẹn tiếp theo', 
                                         related='next_booking_id.start_datetime')

    def _compute_booking_count(self):
        for record in self:
            record.booking_count = self.env['customer.booking'].search_count([
                ('khach_hang_id', '=', record.id)
            ])

    def _compute_next_booking(self):
        for record in self:
            next_booking = self.env['customer.booking'].search([
                ('khach_hang_id', '=', record.id),
                ('state', '=', 'confirmed'),
                ('start_datetime', '>=', fields.Datetime.now())
            ], order='start_datetime asc', limit=1)
            record.next_booking_id = next_booking.id if next_booking else False

    def action_view_bookings(self):
        """Xem tất cả lịch hẹn của khách hàng"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Lịch hẹn - %s') % self.ten_khach_hang,
            'res_model': 'customer.booking',
            'view_mode': 'tree,form,calendar',
            'domain': [('khach_hang_id', '=', self.id)],
            'context': {
                'default_khach_hang_id': self.id,
                'default_title': _('Hẹn gặp %s') % self.ten_khach_hang
            }
        }

    def action_create_booking(self):
        """Mở wizard đặt lịch hẹn nhanh với calendar picker"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Đặt lịch hẹn - %s') % self.ten_khach_hang,
            'res_model': 'booking.quick.create.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_khach_hang_id': self.id,
                'default_title': _('Hẹn gặp %s') % self.ten_khach_hang,
            }
        }
