# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class PKICertificateRevocation(models.Model):
    """
    Danh sách chứng thư số bị thu hồi (CRL)
    Quản lý danh sách chứng thư số bị thu hồi
    Theo chuẩn RFC 5280 - X.509 PKI Certificate and CRL Profile
    """
    _name = 'pki.certificate.revocation'
    _description = 'Danh sách chứng thư số bị thu hồi (CRL)'
    _inherit = ['mail.thread']
    _order = 'revoked_at desc'
    
    # === THÔNG TIN CƠ BẢN ===
    name = fields.Char('Tên', compute='_compute_name', store=True)
    certificate_id = fields.Many2one('pki.certificate', string='Chứng thư số bị thu hồi',
                                    required=True, ondelete='cascade', tracking=True)
    
    # === THÔNG TIN THU HỒI ===
    revoked_at = fields.Datetime('Thời gian thu hồi', 
                                 default=fields.Datetime.now, 
                                 required=True, readonly=True, tracking=True)
    revoked_by = fields.Many2one('res.users', string='Người thu hồi',
                                 default=lambda self: self.env.user,
                                 required=True, readonly=True)
    
    reason_code = fields.Selection([
        ('unspecified', 'Không xác định'),
        ('key_compromise', 'Khóa riêng bị lộ'),
        ('ca_compromise', 'Tổ chức cấp phát bị xâm nhập'),
        ('affiliation_changed', 'Thay đổi tổ chức'),
        ('superseded', 'Được thay thế bởi chứng thư mới'),
        ('cessation_of_operation', 'Ngừng hoạt động'),
        ('certificate_hold', 'Tạm đình chỉ'),
        ('remove_from_crl', 'Gỡ khỏi danh sách thu hồi (kích hoạt lại)'),
        ('privilege_withdrawn', 'Thu hồi đặc quyền'),
        ('aa_compromise', 'Cơ quan xác thực bị xâm nhập'),
    ], string='Lý do thu hồi', required=True, default='unspecified',
       tracking=True, help='Mã lý do theo RFC 5280')
    
    reason_description = fields.Text('Chi tiết lý do', tracking=True)
    
    # === TRẠNG THÁI ===
    state = fields.Selection([
        ('active', 'Đang có hiệu lực'),
        ('removed', 'Đã gỡ khỏi danh sách thu hồi'),
    ], string='Trạng thái', default='active', required=True, tracking=True)
    
    # === THÔNG TIN LIÊN QUAN ===
    user_id = fields.Many2one(related='certificate_id.user_id', 
                              string='User', store=True, readonly=True)
    certificate_name = fields.Char(related='certificate_id.name',
                                   string='Tên chứng thư số', store=True, readonly=True)
    
    # === AUDIT ===
    removed_at = fields.Datetime('Thời gian gỡ khỏi danh sách thu hồi', readonly=True)
    removed_by = fields.Many2one('res.users', string='Người gỡ', readonly=True)
    removed_reason = fields.Text('Lý do gỡ khỏi danh sách thu hồi')
    
    # === CRL SERIAL ===
    crl_entry_number = fields.Integer('Số thứ tự trong danh sách', readonly=True,
                                     help='Số thứ tự trong danh sách thu hồi')
    
    
    @api.depends('certificate_id', 'revoked_at')
    def _compute_name(self):
        """Tạo tên tự động"""
        for record in self:
            if record.certificate_id:
                record.name = f"CRL-{record.certificate_id.name}-{record.id or 'New'}"
            else:
                record.name = f"CRL-{record.id or 'New'}"
    
    @api.model
    def create(self, vals):
        """Override create để gán CRL entry number"""
        record = super(PKICertificateRevocation, self).create(vals)
        
        # Gán entry number (tăng dần)
        last_entry = self.search([], order='crl_entry_number desc', limit=1)
        record.crl_entry_number = (last_entry.crl_entry_number + 1) if last_entry else 1
        
        # Cập nhật trạng thái certificate
        if record.certificate_id and record.certificate_id.state != 'revoked':
            record.certificate_id.write({
                'state': 'revoked',
                'revoked_at': record.revoked_at,
                'revoked_reason': record.reason_description,
            })
        
        # Post message
        record.message_post(
            body=f'''
                <p><strong>🚫 Certificate đã bị thu hồi</strong></p>
                <ul>
                    <li><strong>Lý do:</strong> {dict(record._fields['reason_code'].selection)[record.reason_code]}</li>
                    <li><strong>Người thu hồi:</strong> {record.revoked_by.name}</li>
                    <li><strong>Thời gian:</strong> {record.revoked_at}</li>
                </ul>
            '''
        )
        
        return record
    
    def action_remove_from_crl(self):
        """
        Gỡ certificate khỏi CRL (Reactivate)
        Chỉ áp dụng cho trường hợp 'certificate_hold' (tạm đình chỉ)
        """
        self.ensure_one()
        
        if self.state != 'active':
            raise UserError('Entry này đã được gỡ khỏi CRL rồi!')
        
        if self.reason_code != 'certificate_hold':
            raise UserError(
                'Chỉ có thể reactivate certificate bị "tạm đình chỉ" (certificate_hold)!\n'
                'Các lý do khác là vĩnh viễn và không thể reactivate.'
            )
        
        self.write({
            'state': 'removed',
            'removed_at': fields.Datetime.now(),
            'removed_by': self.env.uid,
        })
        
        # Reactivate certificate
        if self.certificate_id:
            self.certificate_id.write({
                'state': 'active',
                'revoked_at': False,
                'revoked_reason': False,
            })
        
        self.message_post(
            body=f'''
                <p><strong>✅ Certificate đã được reactivate</strong></p>
                <p>Người thực hiện: {self.env.user.name}</p>
            '''
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('✅ Đã reactivate'),
                'message': 'Certificate đã được gỡ khỏi CRL và reactivate thành công',
                'type': 'success',
            }
        }
    
    @api.model
    def check_certificate_revoked(self, certificate_id):
        """
        Kiểm tra certificate có bị thu hồi không
        Return: (is_revoked, reason)
        """
        if not certificate_id:
            return (False, None)
        
        revocation = self.search([
            ('certificate_id', '=', certificate_id),
            ('state', '=', 'active'),
        ], limit=1)
        
        if revocation:
            reason = dict(revocation._fields['reason_code'].selection)[revocation.reason_code]
            return (True, reason)
        
        return (False, None)
    
    def action_export_crl(self):
        """
        Export CRL ra file text
        Format: CRL entry theo RFC 5280
        """
        self.ensure_one()
        
        crl_content = f"""
===============================================
CERTIFICATE REVOCATION LIST (CRL)
===============================================

Issuer: {self.env.company.name}
This Update: {fields.Datetime.now()}
Next Update: {fields.Datetime.now() + timedelta(days=7)}

Revoked Certificates:
-----------------------------------------------

Entry #{self.crl_entry_number}
Certificate: {self.certificate_name}
Serial Number: {self.certificate_id.id}
Revocation Date: {self.revoked_at}
Reason Code: {dict(self._fields['reason_code'].selection)[self.reason_code]}
Issuer: {self.revoked_by.name}

===============================================
        """
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/?model=pki.certificate.revocation&id={self.id}&field=crl_content&filename=CRL_{self.id}.txt',
            'target': 'new',
        }


class PKICertificate(models.Model):
    """Extend PKICertificate với CRL checking"""
    _inherit = 'pki.certificate'
    
    revocation_id = fields.Many2one('pki.certificate.revocation', 
                                    string='CRL Entry',
                                    compute='_compute_revocation_id',
                                    store=False)
    is_revoked = fields.Boolean('Đã bị thu hồi', 
                                compute='_compute_is_revoked',
                                store=True)
    
    @api.depends('state')
    def _compute_revocation_id(self):
        """Tìm CRL entry nếu có"""
        for record in self:
            revocation = self.env['pki.certificate.revocation'].search([
                ('certificate_id', '=', record.id),
                ('state', '=', 'active'),
            ], limit=1)
            record.revocation_id = revocation.id if revocation else False
    
    @api.depends('state')
    def _compute_is_revoked(self):
        """Check revocation status"""
        for record in self:
            record.is_revoked = (record.state == 'revoked')
    
    def action_revoke(self, reason_code='unspecified', reason_description=''):
        """
        Thu hồi certificate với CRL
        """
        self.ensure_one()
        
        if self.state == 'revoked':
            raise UserError('Certificate này đã bị thu hồi rồi!')
        
        # Tạo CRL entry
        crl_entry = self.env['pki.certificate.revocation'].create({
            'certificate_id': self.id,
            'reason_code': reason_code,
            'reason_description': reason_description,
        })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('🚫 Đã thu hồi'),
                'message': f'Certificate đã bị thu hồi với lý do: {reason_code}',
                'type': 'warning',
                'sticky': True,
            }
        }
    
    def check_revocation_status(self):
        """
        Kiểm tra CRL trước khi sử dụng certificate
        """
        self.ensure_one()
        
        is_revoked, reason = self.env['pki.certificate.revocation'].check_certificate_revoked(self.id)
        
        if is_revoked:
            raise UserError(
                f'❌ Certificate đã bị thu hồi!\n\n'
                f'Lý do: {reason}\n'
                f'Certificate này không còn có giá trị pháp lý.'
            )
        
        return True
