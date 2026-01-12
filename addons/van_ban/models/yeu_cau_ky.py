# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import secrets
import string
from datetime import datetime, timedelta


class YeuCauKy(models.Model):
    _name = 'yeu_cau_ky'
    _description = 'Yêu cầu ký điện tử'
    _inherit = ['mail.thread']
    _order = 'ngay_tao desc'

    # === THÔNG TIN CƠ BẢN ===
    van_ban_id = fields.Many2one('van_ban', string='Văn bản', required=True, 
                                  ondelete='cascade')
    khach_hang_id = fields.Many2one('khach_hang', string='Khách hàng', required=True)
    email = fields.Char('Email', required=True)
    
    # === TRẠNG THÁI ===
    trang_thai = fields.Selection([
        ('nhap', 'Nháp'),
        ('cho_ky', 'Chờ ký'),
        ('da_ky', 'Đã ký'),
        ('tu_choi', 'Từ chối'),
        ('het_han', 'Hết hạn')
    ], string='Trạng thái', default='nhap', tracking=True)
    
    # === THỜI GIAN ===
    ngay_tao = fields.Datetime('Ngày tạo', default=fields.Datetime.now, readonly=True)
    ngay_gui = fields.Datetime('Ngày gửi', readonly=True)
    ngay_ky = fields.Datetime('Ngày ký', readonly=True)
    ngay_het_han = fields.Date('Ngày hết hạn yêu cầu', 
                                default=lambda self: fields.Date.today() + timedelta(days=7))
    
    # === XÁC THỰC ===
    token = fields.Char('Token xác thực', readonly=True, copy=False)
    otp_code = fields.Char('Mã OTP', readonly=True, copy=False)
    otp_het_han = fields.Datetime('OTP hết hạn', readonly=True)
    so_lan_nhap_sai = fields.Integer('Số lần nhập sai', default=0)
    
    # === CHỮ KÝ ===
    chu_ky = fields.Binary('Chữ ký', readonly=True)
    ip_ky = fields.Char('IP khi ký', readonly=True)
    
    # === GHI CHÚ ===
    ly_do_tu_choi = fields.Text('Lý do từ chối')
    ghi_chu = fields.Text('Ghi chú')
    
    # === RELATED FIELDS ===
    ten_van_ban = fields.Char(related='van_ban_id.ten_van_ban', string='Tên văn bản')
    ten_khach_hang = fields.Char(related='khach_hang_id.ten_khach_hang', string='Tên khách hàng')
    
    # === METHODS ===
    
    def _generate_token(self):
        """Tạo token ngẫu nhiên cho link ký"""
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(32))
    
    def _generate_otp(self):
        """Tạo mã OTP 6 số"""
        return ''.join(secrets.choice(string.digits) for _ in range(6))
    
    def action_gui_email_yeu_cau_ky(self):
        """Gửi email yêu cầu ký cho khách hàng"""
        for record in self:
            # Tạo token
            record.token = record._generate_token()
            record.ngay_gui = fields.Datetime.now()
            record.trang_thai = 'cho_ky'
            
            # Gửi email
            template = self.env.ref('van_ban.email_template_yeu_cau_ky', raise_if_not_found=False)
            if template:
                template.send_mail(record.id, force_send=True)
            else:
                # Gửi email đơn giản nếu không có template
                mail_values = {
                    'subject': f'Yêu cầu ký văn bản: {record.van_ban_id.ten_van_ban}',
                    'body_html': f'''
                        <p>Kính gửi {record.khach_hang_id.ten_khach_hang},</p>
                        <p>Bạn có một văn bản cần ký: <strong>{record.van_ban_id.ten_van_ban}</strong></p>
                        <p>Vui lòng truy cập link sau để ký văn bản:</p>
                        <p><a href="/van_ban/ky/{record.token}">Ký văn bản</a></p>
                        <p>Link này có hiệu lực đến: {record.ngay_het_han}</p>
                        <br/>
                        <p>Trân trọng,</p>
                        <p>{self.env.company.name}</p>
                    ''',
                    'email_to': record.email,
                    'email_from': self.env.company.email or 'noreply@company.com',
                }
                self.env['mail.mail'].create(mail_values).send()
            
            record.message_post(body=f'Đã gửi email yêu cầu ký đến {record.email}')
    
    def action_gui_otp(self):
        """Gửi mã OTP xác thực"""
        for record in self:
            record.otp_code = record._generate_otp()
            record.otp_het_han = fields.Datetime.now() + timedelta(minutes=5)
            
            # Gửi email OTP
            mail_values = {
                'subject': f'Mã OTP xác thực ký văn bản',
                'body_html': f'''
                    <p>Mã OTP của bạn là: <strong style="font-size: 24px;">{record.otp_code}</strong></p>
                    <p>Mã này có hiệu lực trong 5 phút.</p>
                    <p>Nếu bạn không yêu cầu mã này, vui lòng bỏ qua email này.</p>
                ''',
                'email_to': record.email,
                'email_from': self.env.company.email or 'noreply@company.com',
            }
            self.env['mail.mail'].create(mail_values).send()
    
    def action_xac_thuc_otp(self, otp_nhap):
        """Xác thực mã OTP"""
        self.ensure_one()
        
        if self.so_lan_nhap_sai >= 5:
            raise UserError('Bạn đã nhập sai quá 5 lần. Vui lòng yêu cầu mã OTP mới.')
        
        if fields.Datetime.now() > self.otp_het_han:
            raise UserError('Mã OTP đã hết hạn. Vui lòng yêu cầu mã mới.')
        
        if otp_nhap != self.otp_code:
            self.so_lan_nhap_sai += 1
            raise UserError(f'Mã OTP không đúng. Bạn còn {5 - self.so_lan_nhap_sai} lần thử.')
        
        return True
    
    def action_ky(self, chu_ky_data=None, ip_address=None):
        """Thực hiện ký văn bản"""
        self.ensure_one()
        
        if self.trang_thai != 'cho_ky':
            raise UserError('Yêu cầu ký không hợp lệ!')
        
        if fields.Date.today() > self.ngay_het_han:
            self.trang_thai = 'het_han'
            raise UserError('Yêu cầu ký đã hết hạn!')
        
        self.write({
            'trang_thai': 'da_ky',
            'ngay_ky': fields.Datetime.now(),
            'chu_ky': chu_ky_data,
            'ip_ky': ip_address or 'N/A',
            'otp_code': False  # Xóa OTP sau khi ký
        })
        
        # Cập nhật văn bản - CHƯA khóa, chờ đến khi GỬI mới khóa
        self.van_ban_id.write({
            'da_khach_ky': True,
            'ngay_khach_ky': fields.Datetime.now(),
            'chu_ky_khach': chu_ky_data,
            'bi_khoa': False  # CHƯA khóa - chờ đến khi gửi mới khóa
        })
        
        # Gửi email xác nhận
        self._gui_email_xac_nhan_ky()
        
        # Ghi lịch sử
        self.van_ban_id._ghi_lich_su('khach_ky', 
            f'Khách hàng {self.khach_hang_id.ten_khach_hang} đã ký văn bản - Sẵn sàng gửi đi')
    
    def _gui_email_xac_nhan_ky(self):
        """Gửi email xác nhận đã ký thành công"""
        self.ensure_one()
        mail_values = {
            'subject': f'Xác nhận ký văn bản thành công: {self.van_ban_id.ten_van_ban}',
            'body_html': f'''
                <p>Kính gửi {self.khach_hang_id.ten_khach_hang},</p>
                <p>Bạn đã ký thành công văn bản: <strong>{self.van_ban_id.ten_van_ban}</strong></p>
                <p>Thời gian ký: {self.ngay_ky}</p>
                <p>Bản sao văn bản đã ký sẽ được gửi đến bạn qua email riêng.</p>
                <br/>
                <p>Trân trọng,</p>
                <p>{self.env.company.name}</p>
            ''',
            'email_to': self.email,
            'email_from': self.env.company.email or 'noreply@company.com',
        }
        self.env['mail.mail'].create(mail_values).send()
    
    def action_tu_choi(self):
        """Từ chối ký văn bản"""
        for record in self:
            record.trang_thai = 'tu_choi'
            record.van_ban_id._ghi_lich_su('khach_tu_choi', 
                f'Khách hàng {record.khach_hang_id.ten_khach_hang} từ chối ký. Lý do: {record.ly_do_tu_choi or "Không có"}')
    
    def action_gui_lai(self):
        """Gửi lại yêu cầu ký"""
        for record in self:
            record.so_lan_nhap_sai = 0
            record.ngay_het_han = fields.Date.today() + timedelta(days=7)
            record.action_gui_email_yeu_cau_ky()
