# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import base64
import logging
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)

try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa, padding
    from cryptography.hazmat.backends import default_backend
    from cryptography import x509
    from cryptography.x509.oid import NameOID
except ImportError as e:
    _logger.warning("Missing cryptography library: %s. Please install: pip install cryptography", e)


class PKICertificate(models.Model):
    """
    Quản lý chứng thư số (PKI Certificate) cho từng người dùng
    Thực hiện quy trình chữ ký số chuẩn PKI:
    1. Private Key: Dùng để mã hóa hash của văn bản (tạo chữ ký số)
    2. Public Key: Dùng để giải mã và xác thực chữ ký số
    3. Certificate: Chứng thư số xác thực danh tính người ký
    """
    _name = 'pki.certificate'
    _description = 'Chứng thư số PKI'
    _inherit = ['mail.thread']
    _order = 'created_at desc'

    # === THÔNG TIN CƠ BẢN ===
    name = fields.Char('Tên chứng thư', required=True, tracking=True)
    user_id = fields.Many2one('res.users', string='Người dùng', required=True, 
                              ondelete='cascade', tracking=True)
    nhan_vien_id = fields.Many2one('nhan_vien', string='Nhân viên', 
                                    compute='_compute_nhan_vien', store=True)
    
    # === PRIVATE KEY (BẢO MẬT) ===
    private_key = fields.Binary('Private Key (Encrypted)', 
                                help='Khóa riêng tư - Dùng để ký văn bản. KHÔNG BAO GIỜ chia sẻ!',
                                groups='base.group_system')
    private_key_password = fields.Char('Password bảo vệ Private Key',
                                      groups='base.group_system',
                                      help='Password để mở khóa private key khi ký')
    
    # === PUBLIC KEY (CÔNG KHAI) ===
    public_key = fields.Binary('Public Key', 
                              help='Khóa công khai - Dùng để xác thực chữ ký. Có thể chia sẻ công khai.')
    public_key_pem = fields.Text('Public Key (PEM format)', 
                                 help='Public key ở định dạng văn bản PEM')
    
    # === CERTIFICATE (CHỨNG THƯ SỐ) ===
    certificate = fields.Binary('Certificate (X.509)', 
                               help='Chứng thư số X.509 xác thực danh tính người ký')
    certificate_pem = fields.Text('Certificate (PEM format)',
                                  help='Certificate ở định dạng văn bản PEM')
    
    # === THÔNG TIN CERTIFICATE ===
    subject_common_name = fields.Char('Common Name (CN)', tracking=True,
                                     help='Tên người ký trong certificate')
    subject_organization = fields.Char('Organization (O)', tracking=True,
                                      help='Tổ chức/Công ty')
    subject_email = fields.Char('Email', tracking=True)
    
    issuer_name = fields.Char('Issuer', readonly=True,
                             help='Tổ chức cấp chứng thư số')
    
    # === THỜI HẠN ===
    valid_from = fields.Datetime('Có hiệu lực từ', required=True, 
                                 default=fields.Datetime.now, tracking=True)
    valid_to = fields.Datetime('Có hiệu lực đến', required=True,
                              default=lambda self: fields.Datetime.now() + timedelta(days=365),
                              tracking=True)
    
    # === TRẠNG THÁI ===
    state = fields.Selection([
        ('draft', 'Nháp'),
        ('active', 'Đang hoạt động'),
        ('expired', 'Hết hạn'),
        ('revoked', 'Đã thu hồi'),
    ], string='Trạng thái', default='draft', required=True, tracking=True)
    
    is_valid = fields.Boolean('Còn hiệu lực', compute='_compute_is_valid', store=True)
    
    # === THUẬT TOÁN ===
    key_size = fields.Integer('Key Size (bits)', default=2048, required=True,
                             help='Độ dài khóa: 2048, 3072, 4096 bits')
    hash_algorithm = fields.Selection([
        ('SHA256', 'SHA-256 (Khuyến nghị)'),
        ('SHA384', 'SHA-384'),
        ('SHA512', 'SHA-512'),
    ], string='Thuật toán Hash', default='SHA256', required=True,
       help='Thuật toán hash sử dụng khi ký văn bản')
    
    # === AUDIT TRAIL ===
    created_at = fields.Datetime('Ngày tạo', default=fields.Datetime.now, readonly=True)
    created_by = fields.Many2one('res.users', string='Người tạo', 
                                 default=lambda self: self.env.user, readonly=True)
    revoked_at = fields.Datetime('Ngày thu hồi', readonly=True)
    revoked_reason = fields.Text('Lý do thu hồi')
    
    # === THỐNG KÊ ===
    signature_count = fields.Integer('Số lần đã ký', compute='_compute_signature_count')
    
    # === RELATED ===
    user_name = fields.Char(related='user_id.name', string='Tên người dùng', store=True)
    
    
    @api.depends('user_id')
    def _compute_nhan_vien(self):
        """Tự động liên kết với nhân viên"""
        for record in self:
            if record.user_id:
                nhan_vien = self.env['nhan_vien'].search([
                    ('user_id', '=', record.user_id.id)
                ], limit=1)
                record.nhan_vien_id = nhan_vien.id if nhan_vien else False
            else:
                record.nhan_vien_id = False
    
    @api.depends('valid_from', 'valid_to', 'state')
    def _compute_is_valid(self):
        """Kiểm tra certificate còn hiệu lực không"""
        now = fields.Datetime.now()
        for record in self:
            if record.state == 'active' and record.valid_from <= now <= record.valid_to:
                record.is_valid = True
            else:
                record.is_valid = False
    
    def _compute_signature_count(self):
        """Đếm số lần đã ký bằng certificate này"""
        for record in self:
            record.signature_count = self.env['van_ban.signature.log'].search_count([
                ('certificate_id', '=', record.id),
                ('is_valid', '=', True)
            ])
    
    @api.constrains('key_size')
    def _check_key_size(self):
        """Kiểm tra key size hợp lệ"""
        for record in self:
            if record.key_size not in [2048, 3072, 4096]:
                raise ValidationError('Key size phải là 2048, 3072 hoặc 4096 bits')
    
    @api.constrains('valid_from', 'valid_to')
    def _check_validity_dates(self):
        """Kiểm tra ngày hiệu lực hợp lệ"""
        for record in self:
            if record.valid_to <= record.valid_from:
                raise ValidationError('Ngày hết hạn phải sau ngày bắt đầu!')
    
    def action_generate_keypair(self):
        """
        Tạo cặp khóa Private/Public Key và Certificate
        Đây là bước đầu tiên trong quy trình PKI
        """
        self.ensure_one()
        
        try:
            # Bước 1: Tạo Private Key
            _logger.info("Generating RSA key pair (size: %s bits)...", self.key_size)
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=self.key_size,
                backend=default_backend()
            )
            
            # Bước 2: Lấy Public Key từ Private Key
            public_key = private_key.public_key()
            
            # Bước 3: Mã hóa Private Key với password (nếu có)
            encryption_algorithm = serialization.BestAvailableEncryption(
                self.private_key_password.encode() if self.private_key_password 
                else b'odoo_default_password'
            )
            
            private_key_pem = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=encryption_algorithm
            )
            
            # Bước 4: Export Public Key (không mã hóa - dùng để xác thực)
            public_key_pem = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
            
            # Bước 5: Tạo Certificate X.509 (Self-signed)
            subject = issuer = x509.Name([
                x509.NameAttribute(NameOID.COMMON_NAME, 
                                 self.subject_common_name or self.user_id.name),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, 
                                 self.subject_organization or self.env.company.name),
                x509.NameAttribute(NameOID.EMAIL_ADDRESS, 
                                 self.subject_email or self.user_id.email or 'no-email@example.com'),
            ])
            
            cert = x509.CertificateBuilder().subject_name(
                subject
            ).issuer_name(
                issuer
            ).public_key(
                public_key
            ).serial_number(
                x509.random_serial_number()
            ).not_valid_before(
                self.valid_from
            ).not_valid_after(
                self.valid_to
            ).sign(private_key, hashes.SHA256(), default_backend())
            
            certificate_pem = cert.public_bytes(serialization.Encoding.PEM)
            
            # Bước 6: Lưu vào database
            self.write({
                'private_key': base64.b64encode(private_key_pem),
                'public_key': base64.b64encode(public_key_pem),
                'public_key_pem': public_key_pem.decode('utf-8'),
                'certificate': base64.b64encode(certificate_pem),
                'certificate_pem': certificate_pem.decode('utf-8'),
                'issuer_name': f'Self-signed by {self.env.company.name}',
                'state': 'active',
            })
            
            self.message_post(
                body=f'''
                    <p><strong>✅ Đã tạo chứng thư số thành công!</strong></p>
                    <ul>
                        <li>Key Size: {self.key_size} bits</li>
                        <li>Hash Algorithm: {self.hash_algorithm}</li>
                        <li>Valid From: {self.valid_from}</li>
                        <li>Valid To: {self.valid_to}</li>
                    </ul>
                '''
            )
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Thành công!'),
                    'message': f'Đã tạo chứng thư số cho {self.user_id.name}',
                    'type': 'success',
                }
            }
            
        except Exception as e:
            _logger.error("Error generating certificate: %s", e)
            raise UserError(f'Lỗi khi tạo chứng thư số: {str(e)}')
    
    def get_private_key_object(self):
        """
        Lấy Private Key object để ký văn bản
        Cần password để giải mã
        """
        self.ensure_one()
        
        if not self.private_key:
            raise UserError('Certificate chưa có private key!')
        
        if not self.is_valid:
            raise UserError('Certificate không còn hiệu lực hoặc đã bị thu hồi!')
        
        try:
            private_key_pem = base64.b64decode(self.private_key)
            password = self.private_key_password.encode() if self.private_key_password else b'odoo_default_password'
            
            private_key = serialization.load_pem_private_key(
                private_key_pem,
                password=password,
                backend=default_backend()
            )
            
            return private_key
            
        except Exception as e:
            _logger.error("Error loading private key: %s", e)
            raise UserError(f'Không thể load private key: {str(e)}')
    
    def get_public_key_object(self):
        """
        Lấy Public Key object để xác thực chữ ký
        Public key là công khai, không cần password
        """
        self.ensure_one()
        
        if not self.public_key:
            raise UserError('Certificate chưa có public key!')
        
        try:
            public_key_pem = base64.b64decode(self.public_key)
            public_key = serialization.load_pem_public_key(
                public_key_pem,
                backend=default_backend()
            )
            
            return public_key
            
        except Exception as e:
            _logger.error("Error loading public key: %s", e)
            raise UserError(f'Không thể load public key: {str(e)}')
    
    def get_hash_algorithm(self):
        """Trả về hash algorithm object"""
        hash_map = {
            'SHA256': hashes.SHA256(),
            'SHA384': hashes.SHA384(),
            'SHA512': hashes.SHA512(),
        }
        return hash_map.get(self.hash_algorithm, hashes.SHA256())
    
    def action_revoke(self):
        """Thu hồi certificate"""
        self.ensure_one()
        
        return {
            'name': 'Thu hồi chứng thư số',
            'type': 'ir.actions.act_window',
            'res_model': 'pki.certificate.revoke.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_certificate_id': self.id}
        }
    
    def action_download_public_key(self):
        """Download public key để chia sẻ"""
        self.ensure_one()
        
        if not self.public_key_pem:
            raise UserError('Chứa có public key để download!')
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/pki.certificate/{self.id}/public_key_pem/PublicKey_{self.user_id.login}.pem?download=true',
            'target': 'new',
        }
    
    def action_view_signatures(self):
        """Xem các văn bản đã ký bằng certificate này"""
        self.ensure_one()
        
        return {
            'name': f'Văn bản đã ký bằng {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'van_ban.signature.log',
            'view_mode': 'tree,form',
            'domain': [('certificate_id', '=', self.id)],
        }
    
    @api.model
    def cron_check_expiring_certificates(self):
        """
        Cron job: Kiểm tra certificate sắp hết hạn
        Chạy hàng ngày, thông báo trước 30 ngày
        """
        warning_date = fields.Datetime.now() + timedelta(days=30)
        
        expiring_certs = self.search([
            ('state', '=', 'active'),
            ('valid_to', '<=', warning_date),
            ('valid_to', '>=', fields.Datetime.now())
        ])
        
        for cert in expiring_certs:
            days_left = (cert.valid_to - fields.Datetime.now()).days
            cert.message_post(
                body=f'⚠️ Cảnh báo: Chứng thư số sẽ hết hạn sau {days_left} ngày!',
                subject='Chứng thư số sắp hết hạn',
                message_type='notification',
                subtype_xmlid='mail.mt_comment',
            )
    
    @api.model
    def cron_expire_certificates(self):
        """
        Cron job: Tự động đánh dấu certificate hết hạn
        Chạy hàng ngày
        """
        expired_certs = self.search([
            ('state', '=', 'active'),
            ('valid_to', '<', fields.Datetime.now())
        ])
        
        for cert in expired_certs:
            cert.write({
                'state': 'expired',
            })
            cert.message_post(
                body='❌ Chứng thư số đã hết hạn tự động.',
                subject='Chứng thư số hết hạn'
            )
