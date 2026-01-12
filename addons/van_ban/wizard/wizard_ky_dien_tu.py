# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import base64


class WizardKyDienTu(models.TransientModel):
    _name = 'wizard.ky.dien.tu'
    _description = 'Wizard Ký điện tử'

    van_ban_id = fields.Many2one('van_ban', string='Văn bản', required=True)
    ten_van_ban = fields.Char(related='van_ban_id.ten_van_ban', string='Tên văn bản')
    loai_van_ban = fields.Char(related='van_ban_id.loai_van_ban_id.ten_loai', string='Loại văn bản')
    
    # Chữ ký
    chu_ky = fields.Binary('Chữ ký', required=True, 
                           help='Vẽ chữ ký của bạn trên canvas')
    
    # Thông tin người ký
    nguoi_ky_id = fields.Many2one('nhan_vien', string='Người ký',
                                   default=lambda self: self._get_nhan_vien_hien_tai(),
                                   readonly=True)
    ten_nguoi_ky = fields.Char(related='nguoi_ky_id.ten_nv', string='Họ tên')
    chuc_vu = fields.Char(related='nguoi_ky_id.chuc_vu', string='Chức vụ')
    
    # Xác nhận
    xac_nhan = fields.Boolean('Tôi xác nhận đã đọc và đồng ý với nội dung văn bản này', 
                               default=False)
    
    def _get_nhan_vien_hien_tai(self):
        """Lấy nhân viên hiện tại"""
        nhan_vien = self.env['nhan_vien'].search([
            ('user_id', '=', self.env.uid)
        ], limit=1)
        return nhan_vien.id if nhan_vien else False
    
    @api.model
    def default_get(self, fields_list):
        """Khởi tạo giá trị mặc định"""
        res = super(WizardKyDienTu, self).default_get(fields_list)
        
        # Lấy văn bản từ context
        active_id = self.env.context.get('active_id')
        if active_id:
            van_ban = self.env['van_ban'].browse(active_id)
            res['van_ban_id'] = van_ban.id
            
            # Kiểm tra điều kiện ký
            if van_ban.trang_thai not in ['da_duyet', 'cho_ky']:
                raise UserError('Văn bản chưa được duyệt! Không thể ký.')
            
            if not van_ban.file_dinh_kem:
                raise UserError('Văn bản chưa có file đính kèm! Vui lòng upload file trước khi ký.')
        
        return res
    
    def action_ky(self):
        """Thực hiện ký điện tử"""
        self.ensure_one()
        
        # Kiểm tra xác nhận
        if not self.xac_nhan:
            raise UserError('Bạn phải xác nhận đã đọc và đồng ý với nội dung văn bản!')
        
        # Kiểm tra chữ ký
        if not self.chu_ky:
            raise UserError('Bạn chưa vẽ chữ ký! Vui lòng vẽ chữ ký trên canvas.')
        
        # Lấy IP address
        ip_address = self.env['ir.http']._get_client_address() if hasattr(self.env['ir.http'], '_get_client_address') else 'N/A'
        
        # Cập nhật văn bản
        self.van_ban_id.write({
            'da_ky_noi_bo': True,
            'ngay_ky_noi_bo': fields.Datetime.now(),
            'nguoi_ky_id': self.nguoi_ky_id.id,
            'chu_ky_noi_bo': self.chu_ky,
            'trang_thai': 'da_ky',
            'bi_khoa': False  # Chưa khóa, đợi gửi
        })
        
        # Copy file gốc thành file đã ký
        if self.van_ban_id.file_dinh_kem:
            self.van_ban_id.file_da_ky = self.van_ban_id.file_dinh_kem
            self.van_ban_id.ten_file_da_ky = f"SIGNED_{self.van_ban_id.ten_file}" if self.van_ban_id.ten_file else "SIGNED_document.pdf"
        
        # Ghi lịch sử
        self.van_ban_id._ghi_lich_su(
            'ky', 
            f'Ký điện tử văn bản bởi {self.nguoi_ky_id.ten_nv} ({self.chuc_vu or "N/A"}) từ IP: {ip_address}'
        )
        
        # Gửi thông báo
        self.van_ban_id.message_post(
            body=f'''
                <p><strong>Văn bản đã được ký điện tử</strong></p>
                <p>Người ký: {self.nguoi_ky_id.ten_nv} - {self.chuc_vu or "N/A"}</p>
                <p>Thời gian: {fields.Datetime.now()}</p>
                <p>IP: {ip_address}</p>
            '''
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Ký thành công!'),
                'message': f'Văn bản "{self.van_ban_id.ten_van_ban}" đã được ký điện tử.',
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }
    
    def action_cancel(self):
        """Hủy ký"""
        return {'type': 'ir.actions.act_window_close'}
