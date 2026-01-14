# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import timedelta


class WizardKyKhachHang(models.TransientModel):
    _name = 'wizard.ky.khach.hang'
    _description = 'Wizard Ký điện tử Khách hàng'

    yeu_cau_ky_id = fields.Many2one('yeu_cau_ky', string='Yêu cầu ký', required=True)
    van_ban_id = fields.Many2one(related='yeu_cau_ky_id.van_ban_id', string='Văn bản')
    khach_hang_id = fields.Many2one(related='yeu_cau_ky_id.khach_hang_id', string='Khách hàng')
    
    ten_van_ban = fields.Char(related='van_ban_id.ten_van_ban', string='Tên văn bản')
    ten_khach_hang = fields.Char(related='khach_hang_id.ten_khach_hang', string='Tên khách hàng')
    
    # Chữ ký
    chu_ky = fields.Binary('Chữ ký', required=True,
                           help='Vẽ chữ ký của bạn trên canvas')
    
    # OTP
    otp_code = fields.Char('Mã OTP', required=True, size=6,
                           help='Nhập mã OTP đã được gửi qua email')
    
    # Xác nhận
    xac_nhan = fields.Boolean('Tôi đã đọc và đồng ý với nội dung văn bản này', default=False)
    
    def action_gui_otp(self):
        """Gửi lại mã OTP"""
        self.ensure_one()
        
        if not self.yeu_cau_ky_id:
            raise UserError('Không tìm thấy yêu cầu ký!')
        
        # Gửi OTP
        self.yeu_cau_ky_id.action_gui_otp()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Đã gửi OTP'),
                'message': f'Mã OTP đã được gửi đến email {self.yeu_cau_ky_id.email}',
                'type': 'info',
                'sticky': False,
            }
        }
    
    def action_ky(self):
        """Thực hiện ký điện tử"""
        self.ensure_one()
        
        # Kiểm tra xác nhận
        if not self.xac_nhan:
            raise UserError('Bạn phải xác nhận đã đọc và đồng ý với nội dung văn bản!')
        
        # Kiểm tra chữ ký
        if not self.chu_ky:
            raise UserError('Bạn chưa vẽ chữ ký! Vui lòng vẽ chữ ký trên canvas.')
        
        # Kiểm tra OTP
        if not self.otp_code:
            raise UserError('Vui lòng nhập mã OTP!')
        
        # Xác thực OTP
        try:
            self.yeu_cau_ky_id.action_xac_thuc_otp(self.otp_code)
        except UserError as e:
            raise UserError(str(e))
        
        # Lấy IP address
        ip_address = self.env['ir.http']._get_client_address() if hasattr(self.env['ir.http'], '_get_client_address') else 'N/A'
        
        # Thực hiện ký
        self.yeu_cau_ky_id.action_ky(
            chu_ky_data=self.chu_ky,
            ip_address=ip_address
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Ký thành công!'),
                'message': f'Cảm ơn bạn đã ký văn bản "{self.ten_van_ban}"',
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }
