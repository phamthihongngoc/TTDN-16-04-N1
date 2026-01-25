# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.backends import default_backend
except Exception:
    serialization = None
    default_backend = None


class VanBanSignatureLog(models.Model):
    _name = 'van_ban.signature.log'
    _description = 'Lịch sử ký điện tử'
    _order = 'signed_at desc, id desc'

    # Target document (exactly one must be set)
    van_ban_id = fields.Many2one('van_ban', string='Văn bản')
    van_ban_di_id = fields.Many2one('van_ban_di', string='Văn bản đi')
    van_ban_den_id = fields.Many2one('van_ban_den', string='Văn bản đến')

    user_id = fields.Many2one('res.users', string='User ký', required=True, ondelete='restrict')
    nhan_vien_id = fields.Many2one('nhan_vien', string='Nhân viên', ondelete='set null')

    signer_name_entered = fields.Char('Họ tên xác minh (nhập)')
    signer_name_expected = fields.Char('Họ tên kỳ vọng')
    
    # Computed field for display
    signer_name = fields.Char('Tên người ký', compute='_compute_signer_name', store=True)

    is_valid = fields.Boolean('Hợp lệ', default=False)
    invalid_reason = fields.Char('Lý do không hợp lệ')

    signed_at = fields.Datetime('Thời gian', required=True, default=fields.Datetime.now)
    ip_address = fields.Char('IP')

    signature_image = fields.Binary('Chữ ký (ảnh vẽ tay)')

    # === PKI FIELDS ===
    certificate_id = fields.Many2one('pki.certificate', string='Chứng thư số PKI',
                                    help='Certificate được sử dụng để ký văn bản')
    digital_signature = fields.Text('Chữ ký số (Digital Signature)',
                                   help='Chữ ký số được tạo bằng cách mã hóa hash file bằng private key')
    hash_algorithm = fields.Char('Thuật toán Hash',
                                 help='SHA256, SHA384, SHA512')
    file_sha256 = fields.Char('SHA256 file',
                              help='Hash của file PDF gốc - dùng để xác minh toàn vẹn')

    # Snapshot public key used at signing time (avoid certificate mismatch issues)
    public_key_snapshot = fields.Binary(
        'Public Key (snapshot)',
        help='Public key tại thời điểm ký (snapshot) - ưu tiên dùng để xác thực để tránh lệch certificate.'
    )
    public_key_pem_snapshot = fields.Text(
        'Public Key PEM (snapshot)',
        help='Public key PEM tại thời điểm ký (snapshot).'
    )
    
    # === VERIFICATION ===
    verification_status = fields.Selection([
        ('signed', 'Đã ký'),
        ('verified', 'Đã xác thực'),
        ('failed', 'Thất bại'),
        ('invalid', 'Không hợp lệ'),
    ], string='Trạng thái xác thực', default='signed',
       help='Trạng thái xác thực chữ ký số')
    verified_at = fields.Datetime('Thời gian xác thực')
    verified_by = fields.Many2one('res.users', string='Người xác thực')
    verification_result = fields.Text('Kết quả xác thực')
    
    # === BLOCKCHAIN ===
    blockchain_tx_hash = fields.Char('Blockchain TX Hash',
                                    help='Transaction hash trên blockchain (nếu có)')

    @api.depends('signer_name_expected', 'nhan_vien_id', 'user_id')
    def _compute_signer_name(self):
        """Lấy tên người ký để hiển thị"""
        for rec in self:
            if rec.signer_name_expected:
                rec.signer_name = rec.signer_name_expected
            elif rec.nhan_vien_id:
                rec.signer_name = rec.nhan_vien_id.ten_nv
            elif rec.user_id:
                rec.signer_name = rec.user_id.name
            else:
                rec.signer_name = 'N/A'

    @api.constrains('van_ban_id', 'van_ban_di_id', 'van_ban_den_id')
    def _check_one_target(self):
        for rec in self:
            targets = [bool(rec.van_ban_id), bool(rec.van_ban_di_id), bool(rec.van_ban_den_id)]
            if sum(targets) != 1:
                raise ValidationError('Lịch sử ký phải gắn đúng 1 văn bản (đến/đi/nội bộ).')
    
    def action_verify_signature(self):
        """
        Xác thực chữ ký số theo quy trình PKI:
        1. Lấy public key từ certificate
        2. Giải mã digital signature bằng public key
        3. Tạo lại hash từ file gốc
        4. So sánh hai hash
        """
        self.ensure_one()
        
        if not self.certificate_id:
            raise UserError('Log này không có thông tin certificate PKI!')
        
        if not self.digital_signature:
            raise UserError('Log này không có chữ ký số!')
        
        # Lấy file gốc để verify
        document = self.van_ban_id or self.van_ban_di_id or self.van_ban_den_id
        if not document:
            raise UserError('Không tìm thấy văn bản để xác thực!')

        # Ưu tiên file đã ký (được snapshot tại thời điểm ký) để tránh trường hợp file gốc bị thay đổi
        file_field = getattr(document, 'file_da_ky', False) or getattr(document, 'file_dinh_kem', False)
        if not file_field:
            raise UserError('Không tìm thấy file để xác thực (file đã ký / file gốc)!')
        
        try:
            import base64
            import hashlib
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.asymmetric import padding
            from cryptography.exceptions import InvalidSignature
            
            # Bước 1: Lấy file data
            file_data = base64.b64decode(file_field)
            current_sha256 = hashlib.sha256(file_data).hexdigest()
            
            # Bước 2: Lấy public key (ưu tiên snapshot tại thời điểm ký)
            public_key = False
            if self.public_key_snapshot:
                snap_pem = base64.b64decode(self.public_key_snapshot)
                public_key = serialization.load_pem_public_key(
                    snap_pem,
                    backend=default_backend()
                )
            elif self.public_key_pem_snapshot:
                public_key = serialization.load_pem_public_key(
                    (self.public_key_pem_snapshot or '').encode('utf-8'),
                    backend=default_backend()
                )
            else:
                public_key = self.certificate_id.get_public_key_object()
            
            # Bước 3: Lấy digital signature
            digital_sig_bytes = base64.b64decode(self.digital_signature)
            
            # Bước 4: Lấy hash algorithm
            hash_algo = self.certificate_id.get_hash_algorithm()
            
            # Bước 5: Xác thực chữ ký
            # Nếu chữ ký hợp lệ, hàm này sẽ không raise exception
            # Nếu không hợp lệ, sẽ raise InvalidSignature
            public_key.verify(
                digital_sig_bytes,
                file_data,
                padding.PSS(
                    mgf=padding.MGF1(hash_algo),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hash_algo
            )
            
            # Xác thực thành công!
            self.write({
                'verification_status': 'verified',
                'verified_at': fields.Datetime.now(),
                'verified_by': self.env.uid,
                'verification_result': f'''
✅ XÁC THỰC THÀNH CÔNG

1. Chữ ký số hợp lệ
2. File không bị thay đổi sau khi ký
3. Người ký: {self.signer_name_expected}
4. Chứng thư số: {self.certificate_id.name}
5. Thời gian ký: {self.signed_at}
6. IP: {self.ip_address}

→ Văn bản này có tính pháp lý và không thể chối bỏ.
                '''
            })
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('✅ Chữ ký hợp lệ!'),
                    'message': 'Chữ ký số đã được xác thực thành công. Văn bản không bị thay đổi.',
                    'type': 'success',
                    'sticky': True,
                }
            }
            
        except InvalidSignature:
            # Phân biệt nguyên nhân thường gặp: file đã đổi vs sai certificate/log
            if self.file_sha256 and current_sha256 != self.file_sha256:
                reason = (
                    '❌ Chữ ký số KHÔNG HỢP LỆ!\n\n'
                    'Nguyên nhân: File dùng để xác thực KHÔNG TRÙNG với file tại thời điểm ký.\n'
                    f'- SHA256 lúc ký: {self.file_sha256}\n'
                    f'- SHA256 hiện tại: {current_sha256}\n\n'
                    'Cách xử lý: dùng đúng "File đã ký" để xác thực, hoặc khôi phục lại file gốc đúng phiên bản đã ký rồi xác thực lại.'
                )
            else:
                reason = (
                    '❌ Chữ ký số KHÔNG HỢP LỆ!\n\n'
                    'Nguyên nhân có thể:\n'
                    '- Certificate (Public Key) không khớp với Private Key đã dùng để ký\n'
                    '- Dữ liệu chữ ký số (digital_signature) bị sai/thiếu\n\n'
                    'Cách xử lý: kiểm tra lại log ký điện tử và chứng thư số PKI được gắn trong log.'
                )

            # Chữ ký không hợp lệ
            self.write({
                'verification_status': 'invalid',
                'verified_at': fields.Datetime.now(),
                'verified_by': self.env.uid,
                'verification_result': reason,
            })

            raise UserError(reason)
            
        except Exception as e:
            self.write({
                'verification_status': 'failed',
                'verified_at': fields.Datetime.now(),
                'verified_by': self.env.uid,
                'verification_result': f'Lỗi xác thực: {str(e)}'
            })
            raise UserError(f'Lỗi khi xác thực chữ ký: {str(e)}')
