# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import base64
import hashlib
import logging
import re
import unicodedata
from datetime import timedelta

_logger = logging.getLogger(__name__)

try:
    from web3 import Web3
    from eth_account import Account
except ImportError as e:
    _logger.warning("Missing blockchain libraries: %s", e)

try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.backends import default_backend
except ImportError as e:
    _logger.warning("Missing cryptography library: %s. Please install: pip install cryptography", e)


class WizardKyDienTu(models.TransientModel):
    _name = 'wizard.ky.dien.tu'
    _description = 'Wizard Ký điện tử'

    van_ban_id = fields.Many2one('van_ban', string='Văn bản')
    van_ban_di_id = fields.Many2one('van_ban_di', string='Văn bản đi')
    van_ban_den_id = fields.Many2one('van_ban_den', string='Văn bản đến')

    document_display_name = fields.Char(string='Tên văn bản', compute='_compute_document_info', readonly=True)
    document_display_type = fields.Char(string='Loại', compute='_compute_document_info', readonly=True)

    ten_van_ban = fields.Char(related='van_ban_id.ten_van_ban', string='Tên văn bản (nội bộ)')
    loai_van_ban = fields.Char(related='van_ban_id.loai_van_ban_id.ten_loai', string='Loại văn bản')
    
    # Chữ ký - UPLOAD ẢNH CÓ SẴN
    chu_ky = fields.Binary('Ảnh chữ ký', required=True, 
                           help='Upload ảnh chữ ký có sẵn của bạn (JPG/PNG)')
    chu_ky_filename = fields.Char('Tên file chữ ký')
    
    # Private/Public Key (Tự động sinh khi upload ảnh chữ ký)
    private_key_generated = fields.Text('Private Key (tự sinh)', readonly=True,
                                       help='Private key được sinh tự động từ ảnh chữ ký')
    public_key_generated = fields.Text('Public Key (tự sinh)', readonly=True,
                                      help='Public key được sinh tự động và lưu vào kho')
    keys_generated = fields.Boolean('Đã sinh khóa', default=False, readonly=True)
    
    # Thông tin người ký - có thể chọn thủ công nếu user không có nhân viên liên kết
    nguoi_ky_id = fields.Many2one('nhan_vien', string='Người ký',
                                   default=lambda self: self._get_nhan_vien_hien_tai(),
                                   required=True)
    ten_nguoi_ky = fields.Char(related='nguoi_ky_id.ten_nv', string='Họ tên')
    chuc_vu = fields.Char(related='nguoi_ky_id.chuc_vu', string='Chức vụ')

    ho_ten_xac_nhan = fields.Char('Xác minh họ và tên',
                                 help='Nhập đúng họ và tên của bạn để xác minh trước khi ký.')
    
    # Xác nhận
    xac_nhan = fields.Boolean('Tôi xác nhận đã đọc và đồng ý với nội dung văn bản này', 
                               default=False)
    
    # Blockchain
    ky_blockchain = fields.Boolean('Ký trên Blockchain', default=True,
                                   help='Lưu hash chữ ký lên blockchain để đảm bảo tính toàn vẹn')
    blockchain_tx_hash = fields.Char('Blockchain Transaction Hash', readonly=True)
    
    # === PKI CERTIFICATE ===
    certificate_id = fields.Many2one('pki.certificate', string='Chứng thư số PKI',
                                    compute='_compute_certificate_id', store=True,
                                    help='Chứng thư số được sử dụng để ký văn bản')
    certificate_info = fields.Char('Thông tin chứng thư', compute='_compute_certificate_info')
    
    # === OTP/2FA (XÁC THỰC 2 LỚP) ===
    require_otp = fields.Boolean('Yêu cầu OTP', default=True,
                                 help='Bật xác thực 2 lớp bằng OTP trước khi ký')
    otp_code = fields.Char('Mã OTP', help='Nhập mã OTP đã được gửi qua email')
    otp_sent = fields.Boolean('Đã gửi OTP', default=False)
    otp_verified = fields.Boolean('Đã xác thực OTP', default=False)
    otp_sent_code = fields.Char('OTP đã gửi', help='Mã OTP đã gửi (lưu tạm)')
    otp_sent_at = fields.Datetime('Thời gian gửi OTP', help='Thời gian gửi OTP')
    user_email = fields.Char('Email người dùng', compute='_compute_user_email', store=False)
    
    def _get_nhan_vien_hien_tai(self):
        """Mặc định chọn đúng Giám đốc được phép ký (nếu có)."""
        # Ưu tiên theo đúng tên để tránh chọn nhầm
        giam_doc = self.env['nhan_vien'].search([('ten_nv', '=', 'Phạm Thị Hồng Ngọc')], limit=1)
        if giam_doc:
            return giam_doc.id

        # Fallback: tìm theo chức vụ
        giam_doc = self.env['nhan_vien'].search([
            '|', '|', '|',
            ('chuc_vu', 'ilike', 'Giám đốc'),
            ('chuc_vu', 'ilike', 'Giam doc'),
            ('chuc_vu', 'ilike', 'Director'),
            ('chuc_vu', 'ilike', 'CEO')
        ], limit=1)
        if giam_doc:
            return giam_doc.id

        # Nếu chưa cấu hình được giám đốc, fallback về nhân viên theo user
        nhan_vien = self.env['nhan_vien'].search([('user_id', '=', self.env.uid)], limit=1)
        if nhan_vien:
            return nhan_vien.id

        any_nv = self.env['nhan_vien'].search([], limit=1)
        return any_nv.id if any_nv else False
    
    @api.depends_context('uid')
    def _compute_user_email(self):
        """Lấy email của user hiện tại"""
        for wizard in self:
            wizard.user_email = self.env.user.email or 'Chưa có email'
    
    def _generate_keys_from_image(self):
        """Phương thức sinh Private/Public Key từ ảnh chữ ký"""
        if not self.chu_ky or self.keys_generated:
            return
            
        try:
            from cryptography.hazmat.primitives.asymmetric import rsa
            from cryptography.hazmat.primitives import serialization
            from cryptography.hazmat.backends import default_backend
            
            _logger.info("Sinh Private/Public Key từ ảnh chữ ký...")
            
            # Sinh cặp khóa RSA 2048-bit
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
                backend=default_backend()
            )
            
            # Export Private Key (mã hóa bằng password từ ảnh chữ ký)
            image_hash = hashlib.sha256(base64.b64decode(self.chu_ky)).hexdigest()
            password = image_hash[:32].encode()  # Dùng hash của ảnh làm password
            
            private_pem = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.BestAvailableEncryption(password)
            )
            
            # Export Public Key
            public_key = private_key.public_key()
            public_pem = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
            
            self.private_key_generated = private_pem.decode('utf-8')
            self.public_key_generated = public_pem.decode('utf-8')
            self.keys_generated = True
            
            _logger.info("✓ Đã sinh Private/Public Key thành công")
            
        except Exception as e:
            _logger.error("Lỗi khi sinh Private/Public Key: %s", e)
            raise UserError(f'Lỗi khi sinh khóa: {str(e)}')
    
    @api.onchange('chu_ky')
    def _onchange_chu_ky(self):
        """Tự động sinh Private/Public Key khi upload ảnh chữ ký"""
        if self.chu_ky and not self.keys_generated:
            self._generate_keys_from_image()
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('✓ Đã sinh khóa'),
                    'message': 'Private/Public Key đã được sinh tự động từ ảnh chữ ký',
                    'type': 'success',
                }
            }
    
    @api.model
    def create(self, vals):
        """Override create để tự động sinh keys khi tạo record"""
        record = super(WizardKyDienTu, self).create(vals)
        if record.chu_ky and not record.keys_generated:
            record._generate_keys_from_image()
        return record
    
    def write(self, vals):
        """Override write để tự động sinh keys khi update ảnh chữ ký"""
        res = super(WizardKyDienTu, self).write(vals)
        if 'chu_ky' in vals and self.chu_ky and not self.keys_generated:
            self._generate_keys_from_image()
        return res

    @api.depends('van_ban_id', 'van_ban_di_id', 'van_ban_den_id')
    def _compute_document_info(self):
        for wizard in self:
            if wizard.van_ban_id:
                wizard.document_display_type = 'Văn bản'
                wizard.document_display_name = wizard.van_ban_id.ten_van_ban
            elif wizard.van_ban_di_id:
                wizard.document_display_type = 'Văn bản đi'
                wizard.document_display_name = wizard.van_ban_di_id.name or wizard.van_ban_di_id.trich_yeu
            elif wizard.van_ban_den_id:
                wizard.document_display_type = 'Văn bản đến'
                wizard.document_display_name = wizard.van_ban_den_id.name or wizard.van_ban_den_id.trich_yeu
            else:
                wizard.document_display_type = False
                wizard.document_display_name = False
    
    @api.depends('nguoi_ky_id')
    def _compute_certificate_id(self):
        """Tự động lấy certificate còn hiệu lực của người ký"""
        for wizard in self:
            if wizard.nguoi_ky_id and wizard.nguoi_ky_id.user_id:
                cert = self.env['pki.certificate'].search([
                    ('user_id', '=', wizard.nguoi_ky_id.user_id.id),
                    ('state', '=', 'active'),
                    ('is_valid', '=', True)
                ], order='created_at desc', limit=1)
                wizard.certificate_id = cert.id if cert else False
            else:
                wizard.certificate_id = False
    
    @api.depends('certificate_id')
    def _compute_certificate_info(self):
        """Hiển thị thông tin certificate"""
        for wizard in self:
            if wizard.certificate_id:
                cert = wizard.certificate_id
                wizard.certificate_info = f"{cert.name} (Hết hạn: {cert.valid_to.strftime('%d/%m/%Y') if cert.valid_to else 'N/A'})"
            else:
                wizard.certificate_info = 'Chưa có chứng thư số'

    def _normalize_name(self, name):
        if not name:
            return ''
        name = name.strip().lower()
        # normalize common unicode whitespace
        name = name.replace('\u00a0', ' ').replace('\t', ' ').replace('\n', ' ').replace('\r', ' ')
        # loại ký tự zero-width thường gây "nhìn giống" nhưng so sánh fail
        name = name.replace('\u200b', '').replace('\u200c', '').replace('\u200d', '').replace('\ufeff', '')
        name = unicodedata.normalize('NFKD', name)
        name = ''.join([c for c in name if not unicodedata.combining(c)])
        # Vietnamese special letter (not decomposed by NFKD)
        name = name.replace('đ', 'd')
        # chuẩn hoá các ký tự lạ/punctuation thành khoảng trắng
        name = re.sub(r"[^0-9a-zA-Z\s]", " ", name)
        name = name.replace('_', ' ')
        name = re.sub(r'\s+', ' ', name).strip()
        return name

    @api.onchange('nguoi_ky_id')
    def _onchange_nguoi_ky_id_fill_confirm_name(self):
        for wizard in self:
            if wizard.nguoi_ky_id and wizard.nguoi_ky_id.ten_nv:
                wizard.ho_ten_xac_nhan = wizard.nguoi_ky_id.ten_nv

    def _get_target_document(self):
        self.ensure_one()
        if self.van_ban_id:
            return ('van_ban', self.van_ban_id)
        if self.van_ban_di_id:
            return ('van_ban_di', self.van_ban_di_id)
        if self.van_ban_den_id:
            return ('van_ban_den', self.van_ban_den_id)
        return (None, None)

    def _check_can_sign(self, model_name, document):
        """Enforce that only authorized users can sign, and (when configured) only the assigned signer can sign."""
        self.ensure_one()

        if not self.env.user.has_group('van_ban.group_giam_doc_ky') and not self.env.user.has_group('van_ban.group_quan_tri_van_ban') and not self.env.user.has_group('base.group_system'):
            raise UserError('Bạn không có quyền ký điện tử. Vui lòng liên hệ quản trị để cấp quyền.')

        expected_nv = False
        if model_name == 'van_ban':
            expected_nv = document.nguoi_ky_id
        elif model_name == 'van_ban_di':
            expected_nv = document.nguoi_ky_id
        elif model_name == 'van_ban_den':
            expected_nv = document.nguoi_ky_id

        # If document has an assigned signer with a linked user, enforce it (admins can override)
        if expected_nv and expected_nv.user_id and expected_nv.user_id.id != self.env.uid:
            if not self.env.user.has_group('van_ban.group_quan_tri_van_ban') and not self.env.user.has_group('base.group_system'):
                raise UserError('Bạn không phải là người được phân công ký cho văn bản này.')

        # Enforce a single allowed signer (Giám đốc Phạm Thị Hồng Ngọc), unless admin override
        if not self.env.user.has_group('van_ban.group_quan_tri_van_ban') and not self.env.user.has_group('base.group_system'):
            director_nv = self.env['nhan_vien'].search([('ten_nv', '=', 'Phạm Thị Hồng Ngọc')], limit=1)
            if not director_nv or not director_nv.user_id:
                raise UserError('Chưa cấu hình người ký Giám đốc (Phạm Thị Hồng Ngọc) hoặc chưa liên kết user.')
            if director_nv.user_id.id != self.env.uid:
                raise UserError('Chỉ Giám đốc Phạm Thị Hồng Ngọc (đúng tài khoản) được phép ký điện tử.')

    def _log_signature_attempt(self, model_name, document, *, is_valid, invalid_reason=False, tx_hash=False, file_sha256=False, digital_signature=False, certificate_id=False, public_key_snapshot=False, public_key_pem_snapshot=False):
        self.ensure_one()
        
        # Lấy họ tên người ký
        ten_nguoi_ky = self.nguoi_ky_id.ten_nv if self.nguoi_ky_id else self.env.user.name
        chuc_vu = self.chuc_vu or 'N/A'
        
        vals = {
            'user_id': self.env.uid,
            'nhan_vien_id': self.nguoi_ky_id.id if self.nguoi_ky_id else False,
            'signer_name_entered': self.ho_ten_xac_nhan,
            'signer_name_expected': ten_nguoi_ky,  # Họ tên đầy đủ người ký
            'is_valid': bool(is_valid),
            'invalid_reason': invalid_reason or False,
            'ip_address': self.env['ir.http']._get_client_address() if hasattr(self.env['ir.http'], '_get_client_address') else 'N/A',
            'signature_image': self.chu_ky or False,
            'file_sha256': file_sha256 or False,
            'blockchain_tx_hash': tx_hash or False,
            'digital_signature': digital_signature or False,  # PKI signature
            'certificate_id': certificate_id or False,  # PKI certificate used
            'public_key_snapshot': public_key_snapshot or False,
            'public_key_pem_snapshot': public_key_pem_snapshot or False,
            'hash_algorithm': self.certificate_id.hash_algorithm if self.certificate_id else False,
            'verification_status': 'signed' if is_valid else 'failed',
        }
        if model_name == 'van_ban':
            vals['van_ban_id'] = document.id
        elif model_name == 'van_ban_di':
            vals['van_ban_di_id'] = document.id
        elif model_name == 'van_ban_den':
            vals['van_ban_den_id'] = document.id
        self.env['van_ban.signature.log'].sudo().create(vals)
    
    @api.model
    def default_get(self, fields_list):
        """Khởi tạo giá trị mặc định"""
        res = super(WizardKyDienTu, self).default_get(fields_list)

        # Prefer explicit defaults
        if res.get('van_ban_id') or res.get('van_ban_di_id') or res.get('van_ban_den_id'):
            pass
        else:
            active_model = self.env.context.get('active_model')
            active_id = self.env.context.get('active_id')
            if active_model and active_id:
                if active_model == 'van_ban':
                    res['van_ban_id'] = active_id
                elif active_model == 'van_ban_di':
                    res['van_ban_di_id'] = active_id
                elif active_model == 'van_ban_den':
                    res['van_ban_den_id'] = active_id

        # Default full-name confirmation: ưu tiên theo Người ký đang chọn để tránh mismatch
        if 'ho_ten_xac_nhan' in fields_list:
            nv_id = res.get('nguoi_ky_id')
            if nv_id:
                nv = self.env['nhan_vien'].browse(nv_id)
                res['ho_ten_xac_nhan'] = (nv.ten_nv or '')
            else:
                nhan_vien = self.env['nhan_vien'].search([('user_id', '=', self.env.uid)], limit=1)
                res['ho_ten_xac_nhan'] = (nhan_vien.ten_nv if nhan_vien else self.env.user.name) or ''

        return res
    
    def action_ky(self):
        """
        Thực hiện ký điện tử theo quy trình PKI chuẩn:
        
        Bước 1: Xác thực người ký (2FA/OTP nếu bật)
        Bước 2: Tạo hash của file PDF
        Bước 3: Mã hóa hash bằng private key (tạo chữ ký số)
        Bước 4: Gắn chữ ký số vào văn bản kèm public key
        Bước 5: Lưu log và blockchain (tùy chọn)
        """
        self.ensure_one()

        model_name, document = self._get_target_document()
        if not model_name or not document:
            raise UserError('Thiếu thông tin văn bản để ký.')

        # === BƯỚC 1: XÁC THỰC NGƯỜI KÝ ===
        # Kiểm tra quyền
        self._check_can_sign(model_name, document)
        
        # Kiểm tra xác nhận đọc văn bản
        if not self.xac_nhan:
            raise UserError('Bạn phải xác nhận đã đọc và đồng ý với nội dung văn bản!')
        
        # Kiểm tra ảnh chữ ký đã upload
        if not self.chu_ky:
            raise UserError('Bạn chưa upload ảnh chữ ký! Vui lòng upload ảnh chữ ký có sẵn.')
        
        # Sinh keys nếu chưa có (đảm bảo keys luôn được sinh)
        if not self.keys_generated or not self.private_key_generated or not self.public_key_generated:
            _logger.info("Sinh keys trong action_ky vì chưa có keys...")
            self._generate_keys_from_image()
        
        # Kiểm tra lại sau khi sinh
        if not self.keys_generated or not self.private_key_generated or not self.public_key_generated:
            raise UserError('Không thể sinh Private/Public Key! Vui lòng kiểm tra ảnh chữ ký.')
        
        # Xác thực OTP (Xác thực 2 lớp)
        if self.require_otp and not self.otp_verified:
            raise UserError('Bạn phải xác thực OTP trước khi ký! Click "Gửi OTP" và nhập mã OTP.')
        
        # Xác thực họ tên
        if not self.ho_ten_xac_nhan:
            raise UserError('Vui lòng nhập họ tên để xác minh trước khi ký.')
        expected_name = (self.nguoi_ky_id.ten_nv if self.nguoi_ky_id else self.env.user.name) or ''
        entered_norm = self._normalize_name(self.ho_ten_xac_nhan)
        expected_norm = self._normalize_name(expected_name)
        if entered_norm != expected_norm:
            self._log_signature_attempt(
                model_name, document,
                is_valid=False,
                invalid_reason='Họ tên xác minh không khớp.'
            )
            raise UserError(
                'Họ tên xác minh không khớp với tài khoản ký.\n'
                f'Bạn cần nhập đúng: "{expected_name}"'
            )
        
        # === BƯỚC 2: LƯU PUBLIC KEY VÀO KHO ===
        # Tạo hoặc cập nhật certificate với public key vừa sinh
        certificate = self.certificate_id
        if not certificate:
            # Tạo certificate mới để lưu public key
            public_key_pem = self.public_key_generated or ''
            # Binary field cần base64 string (decoded từ bytes)
            public_key_b64 = base64.b64encode(public_key_pem.encode('utf-8')).decode('utf-8') if public_key_pem else False
            certificate = self.env['pki.certificate'].create({
                'name': f'Certificate - {self.ten_nguoi_ky} - {fields.Date.today()}',
                'user_id': self.nguoi_ky_id.user_id.id if self.nguoi_ky_id and self.nguoi_ky_id.user_id else self.env.uid,
                'public_key': public_key_b64,
                'public_key_pem': public_key_pem,
                'state': 'active',
                'valid_from': fields.Date.today(),
                'valid_to': fields.Date.today() + timedelta(days=365),
                'key_size': 2048,
                'hash_algorithm': 'SHA256',  # Phải viết hoa theo Selection field
            })
            self.certificate_id = certificate.id
            _logger.info("✓ Đã lưu Public Key vào kho (Certificate ID: %s)", certificate.id)
        
        # === BƯỚC 3: TẠO HASH CỦA FILE PDF ===
        file_sha256 = False
        file_data = None
        try:
            file_field = getattr(document, 'file_dinh_kem', False)
            if not file_field:
                raise UserError('Văn bản chưa có file đính kèm! Vui lòng upload file trước khi ký.')
            
            file_data = base64.b64decode(file_field)
            file_sha256 = hashlib.sha256(file_data).hexdigest()
            _logger.info("File SHA256 hash: %s", file_sha256)
        except Exception as e:
            _logger.error("Error creating file hash: %s", e)
            raise UserError(f'Lỗi khi tạo hash file: {str(e)}')
        
        # === BƯỚC 4: KÝ ĐIỆN TỬ (MÃ HÓA HASH BẰNG PRIVATE KEY TỰ SINH) ===
        digital_signature = False
        try:
            # Load private key từ string (đã được mã hóa bằng password từ ảnh)
            image_hash = hashlib.sha256(base64.b64decode(self.chu_ky)).hexdigest()
            password = image_hash[:32].encode()
            
            private_key = serialization.load_pem_private_key(
                self.private_key_generated.encode('utf-8'),
                password=password,
                backend=default_backend()
            )
            
            # Tạo chữ ký số: Mã hóa file data bằng private key
            # Đây là bước cốt lõi - chỉ private key owner mới tạo được chữ ký này
            digital_signature = private_key.sign(
                file_data,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            
            # Convert sang base64 để lưu database
            digital_signature_b64 = base64.b64encode(digital_signature).decode('utf-8')
            _logger.info("✓ Chữ ký số đã được tạo (length: %d bytes)", len(digital_signature))
            
        except Exception as e:
            _logger.error("Lỗi tạo chữ ký số: %s", e)
            self._log_signature_attempt(
                model_name, document,
                is_valid=False,
                invalid_reason=f'Lỗi tạo chữ ký số: {str(e)}',
                file_sha256=file_sha256,
            )
            raise UserError(f'Lỗi khi tạo chữ ký số: {str(e)}')
        
        # Lấy IP address
        ip_address = self.env['ir.http']._get_client_address() if hasattr(self.env['ir.http'], '_get_client_address') else 'N/A'
        
        # === BƯỚC 5: LƯU CHỮ KÝ LÊN BLOCKCHAIN (TÙY CHỌN) ===
        tx_hash = False
        if self.ky_blockchain and model_name == 'van_ban':
            tx_hash = self._sign_on_blockchain(file_sha256, digital_signature_b64)

        # === BƯỚC 6: LƯU KẾT QUẢ VÀO VĂN BẢN ===
        now = fields.Datetime.now()
        
        # Đảm bảo có người ký
        if not self.nguoi_ky_id:
            raise UserError('Vui lòng chọn Người ký trước khi xác nhận!')
        
        # Tùy theo model, gán đúng trường
        if model_name == 'van_ban':
            signature_data = {
                'da_ky_noi_bo': True,
                'ngay_ky_noi_bo': now,
                'nguoi_ky_id': self.nguoi_ky_id.id,
                'chu_ky_noi_bo': self.chu_ky,
                'trang_thai': 'da_ky',
                'bi_khoa': False,  # Chưa khóa, đợi gửi
            }
        elif model_name == 'van_ban_di':
            signature_data = {
                'da_ky_dien_tu': True,
                'ngay_ky_dien_tu': now,
                'nguoi_ky_id': self.nguoi_ky_id.id,
                'chu_ky_dien_tu': self.chu_ky,
                'trang_thai': 'da_ky',
                'ngay_ky': fields.Date.context_today(self),
            }
        elif model_name == 'van_ban_den':
            signature_data = {
                'da_ky_dien_tu': True,
                'ngay_ky_dien_tu': now,
                'nguoi_ky_id': self.nguoi_ky_id.id,
                'chu_ky_dien_tu': self.chu_ky,
            }
        else:
            signature_data = {}
        
        # Thêm blockchain tx hash cho van_ban
        if model_name == 'van_ban' and tx_hash:
            signature_data['blockchain_tx_hash'] = tx_hash
        
        document.write(signature_data)

        # Copy file đã ký
        if document.file_dinh_kem:
            document.file_da_ky = document.file_dinh_kem
            document.ten_file_da_ky = f"SIGNED_{document.ten_file}" if hasattr(document, 'ten_file') and document.ten_file else "SIGNED_document.pdf"

        # === POST-SIGN: TRÍCH XUẤT TỪ PDF ĐÃ KÝ (nếu có) ===
        extracted_signer_in_pdf = False
        if model_name == 'van_ban' and hasattr(document, '_post_sign_autofill_from_signed_pdf'):
            try:
                extracted_signer_in_pdf = document._post_sign_autofill_from_signed_pdf()
            except Exception as e:
                # Không chặn luồng ký nếu trích xuất thất bại
                _logger.warning('Post-sign PDF extraction error: %s', e)

        # Lấy thông tin người ký để ghi log
        ten_nguoi_ky = self.nguoi_ky_id.ten_nv if self.nguoi_ky_id else self.env.user.name
        chuc_vu = self.chuc_vu or 'N/A'
        thoi_gian_ky = now.strftime('%d/%m/%Y %H:%M:%S')

        # Ghi log lịch sử (nếu có method) - ghi đầy đủ họ tên và thời gian
        if hasattr(document, '_ghi_lich_su'):
            document._ghi_lich_su(
                'ky',
                f'✅ Ký điện tử PKI thành công\n'
                f'   - Người ký: {ten_nguoi_ky}\n'
                f'   - Chức vụ: {chuc_vu}\n'
                f'   - Thời gian: {thoi_gian_ky}\n'
                f'   - IP: {ip_address}'
            )

        # Post message với họ tên đầy đủ
        message_body = f'''
            <p><strong>✅ Văn bản đã được ký điện tử (PKI)</strong></p>
            <p><strong>Người ký:</strong> {ten_nguoi_ky}</p>
            <p><strong>Chức vụ:</strong> {chuc_vu}</p>
            <p><strong>Thời gian:</strong> {thoi_gian_ky}</p>
            <p><strong>IP:</strong> {ip_address}</p>
            <p><strong>Chứng thư số:</strong> {self.certificate_id.name if self.certificate_id else 'N/A'}</p>
            <p><strong>Hash Algorithm:</strong> {self.certificate_id.hash_algorithm if self.certificate_id else 'N/A'}</p>
            <p><strong>File SHA256:</strong> <code>{file_sha256[:16]}...{file_sha256[-16:]}</code></p>
        '''
        if extracted_signer_in_pdf:
            message_body += f'<p><strong>Người ký (trích xuất từ PDF đã ký):</strong> {extracted_signer_in_pdf}</p>'
        if tx_hash:
            message_body += f'<p><strong>Blockchain TX:</strong> <code>{tx_hash}</code></p>'
        
        document.message_post(body=message_body)

        # === BƯỚC 7: GHI LOG AUDIT TRAIL ===
        public_key_snapshot_b64 = False
        try:
            if self.public_key_generated:
                public_key_snapshot_b64 = base64.b64encode(self.public_key_generated.encode('utf-8')).decode('utf-8')
        except Exception:
            public_key_snapshot_b64 = False
        self._log_signature_attempt(
            model_name, document,
            is_valid=True,
            tx_hash=tx_hash,
            file_sha256=file_sha256,
            digital_signature=digital_signature_b64,
            certificate_id=self.certificate_id.id,
            public_key_snapshot=public_key_snapshot_b64,
            public_key_pem_snapshot=self.public_key_generated or False,
        )
        
        # === BƯỚC 8: RELOAD FORM VĂN BẢN ĐỂ HIỂN THỊ THÔNG TIN NGƯỜI KÝ ===
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('✅ Ký thành công!'),
                'message': f'Đã ký điện tử bởi {ten_nguoi_ky} ({chuc_vu}) lúc {thoi_gian_ky}',
                'type': 'success',
                'sticky': False,
                'next': {
                    'type': 'ir.actions.act_window',
                    'res_model': model_name,
                    'res_id': document.id,
                    'views': [[False, 'form']],
                    'target': 'current',
                }
            }
        }
    
    def action_send_otp(self):
        """
        Gửi mã OTP qua email cho xác thực 2 lớp
        Đây là bước xác thực bổ sung trước khi cho phép ký
        """
        self.ensure_one()
        
        user_email = self.env.user.email
        if not user_email:
            raise UserError('Tài khoản của bạn chưa có email! Vui lòng cập nhật email trước.')
        
        # Tạo mã OTP 6 số
        import secrets
        import string
        otp = ''.join(secrets.choice(string.digits) for _ in range(6))
        
        # Gửi email OTP TRƯỚC để tránh lỗi concurrent
        try:
            mail_values = {
                'subject': f'[{self.env.company.name}] Mã OTP xác thực ký văn bản',
                'body_html': f'''
                    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                        <h2 style="color: #2c3e50;">🔐 Xác thực ký điện tử</h2>
                        <p>Xin chào <strong>{self.env.user.name}</strong>,</p>
                        <p>Bạn đang thực hiện ký điện tử văn bản: <strong>{self.document_display_name}</strong></p>
                        <p>Mã OTP của bạn là:</p>
                        <div style="background-color: #f8f9fa; padding: 20px; text-align: center; font-size: 32px; font-weight: bold; letter-spacing: 5px; color: #e74c3c; border-radius: 5px; margin: 20px 0;">
                            {otp}
                        </div>
                        <p style="color: #7f8c8d; font-size: 14px;">
                            ⚠️ Mã OTP này có hiệu lực trong <strong>5 phút</strong>.<br/>
                            ⚠️ Không chia sẻ mã này với bất kỳ ai.
                        </p>
                        <hr style="border: none; border-top: 1px solid #ecf0f1; margin: 30px 0;"/>
                        <p style="color: #95a5a6; font-size: 12px;">
                            Email này được gửi tự động từ hệ thống {self.env.company.name}.<br/>
                            Nếu bạn không thực hiện hành động này, vui lòng liên hệ quản trị viên ngay lập tức.
                        </p>
                    </div>
                ''',
                'email_to': user_email,
                'email_from': self.env.company.email or 'noreply@company.com',
            }
            mail = self.env['mail.mail'].sudo().create(mail_values)
            mail.send()
            
            _logger.info("OTP email sent successfully to %s", user_email)
            
        except Exception as e:
            _logger.error("Error sending OTP email: %s", e)
            raise UserError(f'Lỗi khi gửi email OTP: {str(e)}')
        
        # Lưu OTP vào wizard SAU KHI gửi thành công
        try:
            self.write({
                'otp_sent_code': otp,
                'otp_sent': True,
                'otp_verified': False,
                'otp_sent_at': fields.Datetime.now(),
            })
        except Exception as e:
            _logger.warning("Could not update wizard otp state: %s", e)
        
        # Reload wizard để hiện ô nhập OTP
        return {
            'type': 'ir.actions.act_window',
            'name': 'Ký điện tử',
            'res_model': 'wizard.ky.dien.tu',
            'res_id': self.id,
            'view_mode': 'form',
            'view_type': 'form',
            'target': 'new',
            'context': dict(self.env.context, otp_just_sent=True),
        }
    
    def action_verify_otp(self):
        """
        Xác thực mã OTP
        Xác thực 2 lớp: Password (đăng nhập) + OTP (email)
        """
        self.ensure_one()
        
        if not self.otp_sent:
            raise UserError('Vui lòng gửi OTP trước khi xác thực!')
        
        if not self.otp_code:
            raise UserError('Vui lòng nhập mã OTP!')
        
        # Kiểm tra timeout (5 phút)
        from datetime import datetime, timedelta
        if self.otp_sent_at:
            now = fields.Datetime.now()
            time_diff = now - self.otp_sent_at
            if time_diff > timedelta(minutes=5):
                raise UserError('Mã OTP đã hết hạn! Vui lòng gửi lại OTP mới.')
        
        # Kiểm tra OTP có khớp không
        if self.otp_code.strip() != self.otp_sent_code:
            raise UserError('Mã OTP không chính xác! Vui lòng kiểm tra lại email.')
        
        # Xác thực thành công
        self.write({'otp_verified': True})
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('✅ Xác thực thành công'),
                'message': 'Mã OTP hợp lệ. Bạn có thể tiến hành ký văn bản.',
                'type': 'success',
            }
        }
    
    def _sign_on_blockchain(self, file_hash, digital_signature):
        """
        Lưu hash chữ ký lên blockchain
        Tham số:
        - file_hash: SHA256 hash của file PDF gốc
        - digital_signature: Chữ ký số PKI (đã mã hóa bằng private key)
        """
        try:
            # Tạo combined hash: file + signature
            combined_data = f"{file_hash}_{digital_signature[:64]}"  # Lấy 64 ký tự đầu
            combined_hash = hashlib.sha256(combined_data.encode()).hexdigest()
            
            # Kết nối đến Ethereum network (Infura)
            infura_url = self.env['ir.config_parameter'].sudo().get_param('blockchain.infura_url')
            private_key = self.env['ir.config_parameter'].sudo().get_param('blockchain.private_key')
            
            if not infura_url or not private_key:
                _logger.warning("Blockchain config missing")
                return False
            
            w3 = Web3(Web3.HTTPProvider(infura_url))
            
            # web3 v5 compatibility
            if hasattr(w3, 'isConnected'):
                connected = w3.isConnected()
            else:
                connected = w3.is_connected()

            if not connected:
                _logger.error("Cannot connect to blockchain")
                return False
            
            # Tạo transaction để lưu hash
            account = Account.from_key(private_key)
            
            # Gửi transaction đơn giản (có thể thay bằng smart contract)
            chain_id = self.env['ir.config_parameter'].sudo().get_param('blockchain.chain_id')
            try:
                chain_id = int(chain_id) if chain_id else None
            except Exception:
                chain_id = None

            tx_data = '0x' + combined_hash

            transaction = {
                'to': '0x0000000000000000000000000000000000000000',  # Burn address
                'value': 0,
                'gasPrice': w3.eth.gas_price,
                'nonce': w3.eth.get_transaction_count(account.address),
                'data': tx_data  # Hash trong data field
            }

            if chain_id:
                transaction['chainId'] = chain_id

            # Gas must include intrinsic cost for data; estimate it.
            try:
                transaction['gas'] = w3.eth.estimate_gas(transaction)
            except Exception as e:
                _logger.warning("estimate_gas failed, using safe fallback gas: %s", e)
                transaction['gas'] = 50000
            
            signed_tx = w3.eth.account.sign_transaction(transaction, private_key)
            raw_tx = getattr(signed_tx, 'rawTransaction', None) or getattr(signed_tx, 'raw_transaction', None)
            tx_hash = w3.eth.send_raw_transaction(raw_tx)
            
            return w3.to_hex(tx_hash)
            
        except Exception as e:
            _logger.error("Blockchain signing error: %s", e)
            return False
    
    def action_cancel(self):
        """Hủy ký"""
        return {'type': 'ir.actions.act_window_close'}
