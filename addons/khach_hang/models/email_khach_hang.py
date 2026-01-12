# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class EmailKhachHang(models.Model):
    _name = 'email_khach_hang'
    _description = 'Email khách hàng'
    _inherit = ['mail.thread']
    _order = 'ngay_gui desc'

    # Thông tin email
    chu_de = fields.Char('Chủ đề email', required=True, tracking=True)
    noi_dung = fields.Html('Nội dung email', required=True)
    
    # Người nhận
    khach_hang_ids = fields.Many2many('khach_hang', string='Khách hàng nhận', required=True)
    danh_sach_email = fields.Text('Danh sách email', compute='_compute_danh_sach_email', store=True)
    so_nguoi_nhan = fields.Integer('Số người nhận', compute='_compute_danh_sach_email', store=True)
    
    # Trạng thái
    trang_thai = fields.Selection([
        ('nhap', 'Nháp'),
        ('da_gui', 'Đã gửi')
    ], string='Trạng thái', default='nhap', required=True, tracking=True)
    
    # Thời gian
    ngay_tao = fields.Datetime('Ngày tạo', default=fields.Datetime.now, readonly=True)
    ngay_gui = fields.Datetime('Ngày gửi', readonly=True, tracking=True)
    
    # Người tạo
    nguoi_tao_id = fields.Many2one('res.users', string='Người tạo', 
                                     default=lambda self: self.env.user, readonly=True)
    
    # File đính kèm
    attachment_ids = fields.Many2many('ir.attachment', string='File đính kèm')
    
    @api.depends('khach_hang_ids')
    def _compute_danh_sach_email(self):
        """Lấy danh sách email khách hàng"""
        for record in self:
            emails = record.khach_hang_ids.filtered(lambda k: k.email).mapped('email')
            record.danh_sach_email = ', '.join(emails) if emails else ''
            record.so_nguoi_nhan = len(emails)
    
    def action_gui_email(self):
        """Gửi email cho khách hàng"""
        for record in self:
            if not record.khach_hang_ids:
                raise UserError('Vui lòng chọn ít nhất một khách hàng!')
            
            emails_hop_le = record.khach_hang_ids.filtered(lambda k: k.email)
            if not emails_hop_le:
                raise UserError('Không có khách hàng nào có email hợp lệ!')
            
            # Gửi email thông qua mail template
            for khach_hang in emails_hop_le:
                mail_values = {
                    'subject': record.chu_de,
                    'body_html': record.noi_dung,
                    'email_to': khach_hang.email,
                    'email_from': self.env.user.email or self.env.company.email,
                    'author_id': self.env.user.partner_id.id,
                    'attachment_ids': [(6, 0, record.attachment_ids.ids)],
                }
                mail = self.env['mail.mail'].create(mail_values)
                mail.send()
            
            # Cập nhật trạng thái
            record.write({
                'trang_thai': 'da_gui',
                'ngay_gui': fields.Datetime.now()
            })
            
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Thành công'),
                'message': _('Đã gửi email đến %s khách hàng!') % len(emails_hop_le),
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_xem_truoc(self):
        """Xem trước email"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'target': 'new',
            'url': '/web/content/email_khach_hang/%s/preview' % self.id,
        }
    
    def action_sao_chep(self):
        """Sao chép email"""
        self.ensure_one()
        new_email = self.copy({
            'chu_de': _('%s (Copy)') % self.chu_de,
            'trang_thai': 'nhap',
            'ngay_gui': False
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'email_khach_hang',
            'res_id': new_email.id,
            'view_mode': 'form',
            'target': 'current',
        }
