# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class PKICertificateRotation(models.Model):
    """
    Key Rotation Policy
    Quản lý chính sách xoay vòng khóa và gia hạn certificate
    """
    _name = 'pki.certificate.rotation'
    _description = 'Certificate Rotation Policy'
    _inherit = ['mail.thread']
    _order = 'rotation_date desc'
    
    name = fields.Char('Tên', compute='_compute_name', store=True)
    
    # === CERTIFICATE CŨ & MỚI ===
    old_certificate_id = fields.Many2one('pki.certificate', 
                                        string='Certificate cũ',
                                        required=True, ondelete='cascade')
    new_certificate_id = fields.Many2one('pki.certificate',
                                        string='Certificate mới',
                                        ondelete='set null')
    
    # === THÔNG TIN ROTATION ===
    rotation_date = fields.Datetime('Ngày rotation', 
                                   default=fields.Datetime.now,
                                   readonly=True)
    rotation_type = fields.Selection([
        ('manual', 'Manual'),
        ('auto_expiring', 'Tự động - Sắp hết hạn'),
        ('auto_policy', 'Tự động - Theo chính sách'),
        ('revocation', 'Do thu hồi'),
    ], string='Loại rotation', required=True, default='manual')
    
    rotation_reason = fields.Text('Lý do rotation')
    
    # === TRẠNG THÁI ===
    state = fields.Selection([
        ('pending', 'Chờ thực hiện'),
        ('in_progress', 'Đang thực hiện'),
        ('completed', 'Hoàn thành'),
        ('failed', 'Thất bại'),
        ('cancelled', 'Đã hủy'),
    ], string='Trạng thái', default='pending', tracking=True)
    
    # === USER ===
    user_id = fields.Many2one(related='old_certificate_id.user_id',
                             string='User', store=True, readonly=True)
    
    # === METADATA ===
    created_by = fields.Many2one('res.users', string='Người tạo',
                                default=lambda self: self.env.user,
                                readonly=True)
    completed_at = fields.Datetime('Hoàn thành lúc', readonly=True)
    error_message = fields.Text('Thông báo lỗi', readonly=True)
    
    
    @api.depends('old_certificate_id', 'rotation_date')
    def _compute_name(self):
        for record in self:
            if record.old_certificate_id:
                date_str = fields.Datetime.to_string(record.rotation_date)[:10]
                record.name = f"Rotation-{record.old_certificate_id.name}-{date_str}"
            else:
                record.name = f"Rotation-{record.id or 'New'}"
    
    @api.model
    def create(self, vals):
        """Override create để post message"""
        record = super(PKICertificateRotation, self).create(vals)
        
        record.message_post(
            body=f'''
                <p><strong>🔄 Key Rotation được tạo</strong></p>
                <ul>
                    <li>Certificate cũ: {record.old_certificate_id.name}</li>
                    <li>Loại: {dict(record._fields['rotation_type'].selection)[record.rotation_type]}</li>
                    <li>Lý do: {record.rotation_reason or 'N/A'}</li>
                </ul>
            '''
        )
        
        return record
    
    def action_execute_rotation(self):
        """
        Thực hiện rotation: Tạo certificate mới, revoke certificate cũ
        """
        self.ensure_one()
        
        if self.state not in ['pending', 'failed']:
            raise UserError('Chỉ có thể thực hiện rotation ở trạng thái Pending hoặc Failed!')
        
        try:
            self.write({'state': 'in_progress'})
            
            # Bước 1: Tạo certificate mới
            _logger.info("Creating new certificate for rotation...")
            new_cert = self.env['pki.certificate'].create({
                'name': f"{self.old_certificate_id.name} (Renewed)",
                'user_id': self.old_certificate_id.user_id.id,
                'subject_common_name': self.old_certificate_id.subject_common_name,
                'subject_organization': self.old_certificate_id.subject_organization,
                'subject_email': self.old_certificate_id.subject_email,
                'key_size': self.old_certificate_id.key_size,
                'hash_algorithm': self.old_certificate_id.hash_algorithm,
                'valid_from': fields.Datetime.now(),
                'valid_to': fields.Datetime.now() + timedelta(days=365),
                'state': 'draft',
            })
            
            # Bước 2: Generate keypair cho certificate mới
            _logger.info("Generating new keypair...")
            new_cert.action_generate_keypair()
            
            # Bước 3: Revoke certificate cũ (nếu chưa revoke)
            if self.old_certificate_id.state == 'active':
                _logger.info("Revoking old certificate...")
                self.old_certificate_id.action_revoke(
                    reason_code='superseded',
                    reason_description=f'Superseded by new certificate: {new_cert.name}'
                )
            
            # Bước 4: Cập nhật rotation record
            self.write({
                'new_certificate_id': new_cert.id,
                'state': 'completed',
                'completed_at': fields.Datetime.now(),
            })
            
            # Bước 5: Thông báo user
            self._notify_user_rotation_completed(new_cert)
            
            self.message_post(
                body=f'''
                    <p><strong>✅ Key Rotation hoàn thành</strong></p>
                    <ul>
                        <li>Certificate mới: {new_cert.name}</li>
                        <li>Hoàn thành lúc: {self.completed_at}</li>
                    </ul>
                '''
            )
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('✅ Rotation thành công!'),
                    'message': f'Certificate mới đã được tạo: {new_cert.name}',
                    'type': 'success',
                    'sticky': True,
                }
            }
            
        except Exception as e:
            _logger.error("Key rotation failed: %s", e)
            self.write({
                'state': 'failed',
                'error_message': str(e),
            })
            raise UserError(f'Lỗi khi thực hiện key rotation: {str(e)}')
    
    def _notify_user_rotation_completed(self, new_cert):
        """Gửi email thông báo rotation hoàn thành"""
        if not self.user_id or not self.user_id.email:
            return
        
        try:
            mail_values = {
                'subject': f'[{self.env.company.name}] Certificate đã được gia hạn',
                'body_html': f'''
                    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                        <h2 style="color: #2c3e50;">🔄 Certificate Rotation thành công</h2>
                        <p>Xin chào <strong>{self.user_id.name}</strong>,</p>
                        <p>Certificate của bạn đã được gia hạn tự động:</p>
                        
                        <div style="background-color: #f8f9fa; padding: 15px; border-left: 4px solid #3498db; margin: 20px 0;">
                            <h3 style="margin-top: 0;">Certificate cũ (đã revoke)</h3>
                            <ul>
                                <li>Tên: {self.old_certificate_id.name}</li>
                                <li>Hết hạn: {self.old_certificate_id.valid_to}</li>
                            </ul>
                            
                            <h3>Certificate mới</h3>
                            <ul>
                                <li>Tên: {new_cert.name}</li>
                                <li>Có hiệu lực đến: {new_cert.valid_to}</li>
                                <li>Key Size: {new_cert.key_size} bits</li>
                                <li>Hash Algorithm: {new_cert.hash_algorithm}</li>
                            </ul>
                        </div>
                        
                        <p style="color: #e74c3c; font-weight: bold;">
                            ⚠️ Lưu ý: Certificate cũ không còn sử dụng được. Vui lòng sử dụng certificate mới cho các giao dịch ký.
                        </p>
                        
                        <hr style="border: none; border-top: 1px solid #ecf0f1; margin: 30px 0;"/>
                        <p style="color: #95a5a6; font-size: 12px;">
                            Email này được gửi tự động từ hệ thống {self.env.company.name}
                        </p>
                    </div>
                ''',
                'email_to': self.user_id.email,
                'email_from': self.env.company.email or 'noreply@company.com',
            }
            self.env['mail.mail'].sudo().create(mail_values).send()
        except Exception as e:
            _logger.error("Failed to send rotation notification email: %s", e)
    
    @api.model
    def cron_check_expiring_certificates(self):
        """
        Cron job: Kiểm tra các certificate sắp hết hạn và tạo rotation
        Chạy hàng ngày
        """
        _logger.info("=== Checking expiring certificates for rotation ===")
        
        # Lấy certificates sắp hết hạn trong 30 ngày
        threshold_date = fields.Datetime.now() + timedelta(days=30)
        expiring_certs = self.env['pki.certificate'].search([
            ('state', '=', 'active'),
            ('valid_to', '<=', threshold_date),
        ])
        
        rotation_count = 0
        for cert in expiring_certs:
            # Kiểm tra đã có rotation chưa
            existing_rotation = self.search([
                ('old_certificate_id', '=', cert.id),
                ('state', 'in', ['pending', 'in_progress', 'completed']),
            ])
            
            if existing_rotation:
                _logger.info(f"Certificate {cert.name} already has rotation")
                continue
            
            # Tạo rotation
            days_until_expiry = (cert.valid_to - fields.Datetime.now()).days
            rotation = self.create({
                'old_certificate_id': cert.id,
                'rotation_type': 'auto_expiring',
                'rotation_reason': f'Certificate sắp hết hạn trong {days_until_expiry} ngày',
                'state': 'pending',
            })
            
            _logger.info(f"Created rotation for certificate {cert.name}")
            rotation_count += 1
            
            # Nếu còn ít hơn 7 ngày, tự động execute rotation
            if days_until_expiry <= 7:
                try:
                    rotation.action_execute_rotation()
                    _logger.info(f"Auto-executed rotation for {cert.name}")
                except Exception as e:
                    _logger.error(f"Auto-rotation failed for {cert.name}: {e}")
        
        _logger.info(f"=== Created {rotation_count} rotations ===")
        return rotation_count
    
    def action_cancel(self):
        """Hủy rotation"""
        self.ensure_one()
        if self.state not in ['pending', 'failed']:
            raise UserError('Chỉ có thể hủy rotation ở trạng thái Pending hoặc Failed!')
        
        self.write({'state': 'cancelled'})
        return True


class PKICertificate(models.Model):
    """Extend PKICertificate với rotation tracking"""
    _inherit = 'pki.certificate'
    
    rotation_ids = fields.One2many('pki.certificate.rotation', 
                                   'old_certificate_id',
                                   string='Lịch sử rotation')
    rotation_count = fields.Integer('Số lần rotation', 
                                   compute='_compute_rotation_count')
    has_pending_rotation = fields.Boolean('Có rotation đang chờ',
                                         compute='_compute_has_pending_rotation')
    days_until_expiry = fields.Integer('Số ngày đến khi hết hạn',
                                      compute='_compute_days_until_expiry')
    
    @api.depends('rotation_ids')
    def _compute_rotation_count(self):
        for record in self:
            record.rotation_count = len(record.rotation_ids)
    
    @api.depends('rotation_ids.state')
    def _compute_has_pending_rotation(self):
        for record in self:
            pending = record.rotation_ids.filtered(lambda r: r.state in ['pending', 'in_progress'])
            record.has_pending_rotation = bool(pending)
    
    @api.depends('valid_to')
    def _compute_days_until_expiry(self):
        now = fields.Datetime.now()
        for record in self:
            if record.valid_to:
                delta = record.valid_to - now
                record.days_until_expiry = delta.days
            else:
                record.days_until_expiry = 0
    
    def action_rotate_certificate(self):
        """Tạo rotation mới cho certificate này"""
        self.ensure_one()
        
        if self.state != 'active':
            raise UserError('Chỉ có thể rotate certificate đang active!')
        
        # Kiểm tra đã có rotation pending chưa
        if self.has_pending_rotation:
            raise UserError('Certificate này đã có rotation đang chờ xử lý!')
        
        # Tạo rotation
        rotation = self.env['pki.certificate.rotation'].create({
            'old_certificate_id': self.id,
            'rotation_type': 'manual',
            'rotation_reason': 'Manual rotation request',
            'state': 'pending',
        })
        
        # Mở form rotation
        return {
            'type': 'ir.actions.act_window',
            'name': 'Certificate Rotation',
            'res_model': 'pki.certificate.rotation',
            'res_id': rotation.id,
            'view_mode': 'form',
            'target': 'current',
        }
