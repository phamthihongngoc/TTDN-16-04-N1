# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import base64
import hashlib
import logging
import re
import unicodedata
import io
import time
import tempfile
from datetime import timedelta

try:
    from ..models.ocr_utils import fix_spacing_artifacts
except Exception:
    def fix_spacing_artifacts(text):
        return text

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

    # Thông tin người ký lấy trực tiếp từ PDF (để đối chiếu)
    pdf_ten_nguoi_ky = fields.Char(string='Họ tên (trong PDF)', readonly=True)
    pdf_chuc_vu = fields.Char(string='Chức vụ (trong PDF)', readonly=True)

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
        name = (fix_spacing_artifacts(name) or '').strip().lower()
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

    def _is_pdf_file(self, filename, file_bytes):
        if file_bytes and file_bytes[:4] == b'%PDF':
            return True
        if filename and isinstance(filename, str) and filename.lower().endswith('.pdf'):
            return True
        return False

    def _extract_signer_info_from_pdf(self, model_name, document):
        """Extract signer name/title from the attached PDF for display & permission matching."""
        self.ensure_one()

        if model_name != 'van_ban':
            return (False, False)

        file_field = getattr(document, 'file_dinh_kem', False)
        filename = getattr(document, 'ten_file', False)
        if not file_field:
            return (False, False)
        try:
            pdf_bytes = base64.b64decode(file_field)
        except Exception:
            return (False, False)
        if not pdf_bytes or not self._is_pdf_file(filename, pdf_bytes):
            return (False, False)

        if not hasattr(document, '_ai_extract_text_from_pdf_bytes') or not hasattr(document, '_ai_extract_party_names_from_text'):
            return (False, False)

        extracted_text = document._ai_extract_text_from_pdf_bytes(pdf_bytes)
        party_info = document._ai_extract_party_names_from_text(extracted_text) or {}
        signer_in_pdf = (party_info.get('dai_dien_ben_a') or '').strip() if isinstance(party_info, dict) else False
        signer_title = False
        if signer_in_pdf and hasattr(document, '_ai_extract_signer_title_from_text'):
            signer_title = document._ai_extract_signer_title_from_text(extracted_text, signer_in_pdf)
        return (signer_in_pdf or False, signer_title or False)

    def _find_employee_by_pdf_name(self, signer_in_pdf):
        self.ensure_one()
        if not signer_in_pdf:
            return False

        norm = self._normalize_name(signer_in_pdf)
        if not norm:
            return False

        # Fast candidates first
        candidates = self.env['nhan_vien'].sudo().search([
            ('ten_nv', 'ilike', signer_in_pdf),
        ], limit=50)
        # If none, try token-based fuzzy query
        if not candidates:
            tokens = [t for t in norm.split() if t]
            domain = []
            for t in tokens[:4]:
                domain.append(('ten_nv', 'ilike', t))
            if domain:
                candidates = self.env['nhan_vien'].sudo().search(domain, limit=50)

        for nv in candidates:
            if self._normalize_name(nv.ten_nv) == norm:
                return nv
        return candidates[:1] if candidates else False

    def _pre_sign_validate_pdf_consistency(self, model_name, document, *, pdf_bytes):
        """Block signing if PDF content doesn't match HR/customer/order links.

        Rules (strict):
        - Must extract signer name (Bên A) from PDF and match assigned internal signer.
        - Must extract customer name (Bên B) from PDF and match a customer record.
        - Document must have customer + related order selected and consistent with extracted customer.
        """
        self.ensure_one()

        if model_name != 'van_ban':
            return
        if not pdf_bytes or not self._is_pdf_file(getattr(document, 'ten_file', False), pdf_bytes):
            return

        if not hasattr(document, '_ai_extract_text_from_pdf_bytes') or not hasattr(document, '_ai_extract_party_names_from_text'):
            return

        try:
            extracted_text = document._ai_extract_text_from_pdf_bytes(pdf_bytes)
            party_info = document._ai_extract_party_names_from_text(extracted_text) or {}
        except Exception as e:
            raise UserError(f'Không thể đọc/trích xuất thông tin từ PDF để đối chiếu trước khi ký. Lỗi: {str(e)}')

        signer_in_pdf = (party_info.get('dai_dien_ben_a') or '').strip()
        customer_in_pdf = (party_info.get('ben_b') or '').strip()

        expected_signer_name = False
        if hasattr(document, 'nguoi_ky_id') and document.nguoi_ky_id and getattr(document.nguoi_ky_id, 'ten_nv', False):
            expected_signer_name = document.nguoi_ky_id.ten_nv
        else:
            expected_signer_name = (self.nguoi_ky_id.ten_nv if self.nguoi_ky_id else self.env.user.name) or ''

        if not signer_in_pdf:
            raise UserError(
                'Không trích xuất được tên người ký (ĐẠI DIỆN BÊN A) trong PDF để đối chiếu.\n'
                'Vui lòng kiểm tra lại file PDF (phần chữ ký có “ĐẠI DIỆN BÊN A/B” và “Họ và tên”).'
            )

        # If mismatch, try to auto-fix assigned signer (only when safe):
        # - PDF signer maps to an employee
        # - Current user is that employee (or admin)
        # This prevents false blocks when the document's signer wasn't persisted correctly.
        if self._normalize_name(signer_in_pdf) != self._normalize_name(expected_signer_name):
            try:
                matched_nv = self._find_employee_by_pdf_name(signer_in_pdf)
                if matched_nv and hasattr(document, 'nguoi_ky_id'):
                    is_admin = self.env.user.has_group('van_ban.group_quan_tri_van_ban') or self.env.user.has_group('base.group_system')
                    is_owner = bool(matched_nv.user_id and matched_nv.user_id.id == self.env.uid)
                    if is_admin or is_owner:
                        if (not document.nguoi_ky_id) or (document.nguoi_ky_id.id != matched_nv.id):
                            document.sudo().write({'nguoi_ky_id': matched_nv.id})
                            if hasattr(document, '_ghi_lich_su'):
                                document._ghi_lich_su('nguoi_ky_sync', f'Auto-fix Người ký nội bộ theo PDF trước khi ký: {matched_nv.ten_nv}')
                        expected_signer_name = matched_nv.ten_nv or expected_signer_name
            except Exception:
                pass

            # Still mismatch after auto-fix => block.
            if self._normalize_name(signer_in_pdf) != self._normalize_name(expected_signer_name):
                raise UserError(
                    'Tên người ký trong PDF KHÔNG khớp với Người ký nội bộ được phân công.\n\n'
                    f'- Trong PDF (Bên A): {signer_in_pdf}\n'
                    f'- Trong hệ thống (Người ký nội bộ): {expected_signer_name}\n\n'
                    'Vui lòng sửa lại file PDF hoặc cập nhật “Người ký nội bộ” trên văn bản trước khi ký.'
                )

        if not customer_in_pdf:
            raise UserError(
                'Không trích xuất được tên khách hàng (Bên B) trong PDF để đối chiếu.\n'
                'Vui lòng kiểm tra lại file PDF (phần BÊN B/BÊN MUA).'
            )

        KhachHang = self.env['khach_hang'].sudo()
        customer_pdf_norm = self._normalize_name(customer_in_pdf)

        # Find best match: prefer exact normalized name match to avoid picking wrong records
        candidate_domain = [('ten_khach_hang', 'ilike', customer_in_pdf)]
        candidate_count = KhachHang.search_count(candidate_domain)
        candidates = KhachHang.search(candidate_domain, limit=50)
        exact_matches = candidates.filtered(lambda c: self._normalize_name(c.ten_khach_hang or '') == customer_pdf_norm)
        matched_customer_exact = exact_matches[:1] if exact_matches else False
        matched_customer_fuzzy = candidates[:1] if candidates else False
        matched_customer = matched_customer_exact or matched_customer_fuzzy

        if not matched_customer:
            raise UserError(
                'Khách hàng trong PDF chưa có trong module Khách hàng, không thể ký.\n\n'
                f'- Khách hàng (Bên B) trong PDF: {customer_in_pdf}\n\n'
                'Vui lòng tạo khách hàng trong module Khách hàng và gán “Khách hàng liên quan” + “Đơn hàng liên quan” cho văn bản, rồi ký lại.'
            )

        if not getattr(document, 'khach_hang_id', False):
            # If we have exactly one exact match, auto-assign to reduce friction.
            # Otherwise, block with a clearer message.
            if matched_customer_exact and len(exact_matches) == 1:
                document.sudo().write({'khach_hang_id': matched_customer_exact.id})
            else:
                suggestions = '\n'.join([
                    f"- #{c.id}: {c.ten_khach_hang}" for c in (exact_matches or candidates)[:5]
                ])
                raise UserError(
                    'Văn bản chưa chọn “Khách hàng liên quan”, không thể ký.\n\n'
                    f'- Hệ thống đọc từ PDF (Bên B): {customer_in_pdf}\n'
                    f'- Có {candidate_count} khách hàng gần giống trong hệ thống.\n'
                    f'{suggestions}\n\n'
                    'Vui lòng chọn đúng “Khách hàng liên quan” trên văn bản trước khi ký.'
                )

        selected_customer = document.khach_hang_id
        if self._normalize_name(selected_customer.ten_khach_hang or '') != self._normalize_name(customer_in_pdf):
            raise UserError(
                'Khách hàng trên văn bản KHÔNG khớp với khách hàng trong PDF, không thể ký.\n\n'
                f'- Trong PDF (Bên B): {customer_in_pdf}\n'
                f'- Trên văn bản (Khách hàng liên quan): {selected_customer.ten_khach_hang or ""}\n\n'
                'Vui lòng chọn đúng “Khách hàng liên quan” hoặc sửa lại file PDF.'
            )

        if not getattr(document, 'don_hang_id', False):
            DonHang = self.env['don_hang'].sudo()
            order_domain = [('khach_hang_id', '=', selected_customer.id)]
            order_count = DonHang.search_count(order_domain)

            if order_count == 1:
                only_order = DonHang.search(order_domain, order='ngay_dat_hang desc, id desc', limit=1)
                document.sudo().write({'don_hang_id': only_order.id})
            elif order_count == 0:
                raise UserError(
                    'Khách hàng trên văn bản chưa có đơn hàng nào, không thể ký.\n\n'
                    f'- Khách hàng: {selected_customer.ten_khach_hang or ""}\n\n'
                    'Vui lòng tạo đơn hàng cho khách hàng này, hoặc chọn đúng khách hàng/đơn hàng rồi ký lại.'
                )
            else:
                orders = DonHang.search(order_domain, order='ngay_dat_hang desc, id desc', limit=5)
                preview = '\n'.join([
                    f"- {o.ma_don_hang or ('#%s' % o.id)} | {o.ngay_dat_hang or ''} | {o.trang_thai or ''}" for o in orders
                ])
                raise UserError(
                    'Văn bản chưa chọn “Đơn hàng liên quan”, không thể ký.\n\n'
                    f'- Khách hàng: {selected_customer.ten_khach_hang or ""}\n'
                    f'- Tìm thấy {order_count} đơn hàng. 5 đơn gần nhất:\n{preview}\n\n'
                    'Vui lòng chọn đúng “Đơn hàng liên quan” trên văn bản trước khi ký.'
                )

        selected_order = document.don_hang_id
        if not getattr(selected_order, 'khach_hang_id', False) or selected_order.khach_hang_id.id != selected_customer.id:
            raise UserError(
                'Đơn hàng liên quan KHÔNG thuộc khách hàng đã chọn, không thể ký.\n\n'
                f'- Khách hàng trên văn bản: {selected_customer.ten_khach_hang or ""}\n'
                f'- Khách hàng của đơn hàng: {(selected_order.khach_hang_id.ten_khach_hang if selected_order.khach_hang_id else "")}\n\n'
                'Vui lòng chọn đúng đơn hàng thuộc khách hàng này.'
            )

    def _stamp_signature_on_pdf(self, pdf_bytes, *, signature_image_b64, signer_name, signer_title, signed_at, stamp_all_pages=False):
        """Return a new PDF with a visible signature stamp.

        This is a visual overlay only. Cryptographic signature is handled separately.
        """
        if not pdf_bytes or not signature_image_b64:
            return pdf_bytes

        # PyPDF2 API compatibility:
        # - v1/v2: PdfFileReader/PdfFileWriter + mergePage/addPage
        # - v3+:   PdfReader/PdfWriter + merge_page/add_page
        PdfReader = None
        PdfWriter = None
        PdfFileReader = None
        PdfFileWriter = None
        pypdf2_api = None

        try:
            from PyPDF2 import PdfReader, PdfWriter
            pypdf2_api = 'new'
        except Exception:
            PdfReader = None
            PdfWriter = None

        if not pypdf2_api:
            try:
                from PyPDF2 import PdfFileReader, PdfFileWriter
                pypdf2_api = 'old'
            except Exception:
                PdfFileReader = None
                PdfFileWriter = None

        try:
            from reportlab.pdfgen import canvas
            from reportlab.lib.utils import ImageReader
        except Exception:
            canvas = None
            ImageReader = None

        if (not pypdf2_api) or (not canvas) or (not ImageReader):
            return pdf_bytes

        try:
            img_bytes = base64.b64decode(signature_image_b64)

            # Prefer using the uploaded image as-is to preserve fidelity.
            try:
                img_reader = ImageReader(io.BytesIO(img_bytes))
                img_w, img_h = (300, 120)
            except Exception:
                try:
                    from PIL import Image
                except Exception:
                    Image = None

                if not Image:
                    return pdf_bytes

                img = Image.open(io.BytesIO(img_bytes))
                # Keep alpha if present (common for signature PNGs)
                if img.mode not in ('RGB', 'RGBA'):
                    img = img.convert('RGBA')
                img_reader = ImageReader(img)
                img_w, img_h = img.size

            if pypdf2_api == 'new':
                reader = PdfReader(io.BytesIO(pdf_bytes), strict=False)
                if getattr(reader, 'is_encrypted', False):
                    try:
                        reader.decrypt('')
                    except Exception:
                        return pdf_bytes

                writer = PdfWriter()
                pages = list(getattr(reader, 'pages', []) or [])
                total_pages = len(pages)
                target_pages = range(total_pages) if stamp_all_pages else [max(total_pages - 1, 0)]
            else:
                reader = PdfFileReader(io.BytesIO(pdf_bytes), strict=False)
                if reader.isEncrypted:
                    try:
                        reader.decrypt('')
                    except Exception:
                        return pdf_bytes

                writer = PdfFileWriter()
                total_pages = reader.getNumPages()
                target_pages = range(total_pages) if stamp_all_pages else [max(total_pages - 1, 0)]

            # Best-effort: try to locate the signer's printed name on the last page
            # so the signature image is placed exactly like the sample (above the name).
            name_bbox_last_page = None
            try:
                import re
                import pdfplumber

                if signer_name and not stamp_all_pages:
                    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                        if pdf.pages:
                            last = pdf.pages[-1]
                            words = last.extract_words(use_text_flow=True) or []
                            parts = [p for p in re.split(r"\s+", (signer_name or '').strip()) if p]

                            def _norm(s: str) -> str:
                                # Reuse the same normalization logic as name verification
                                # (accent-insensitive, whitespace/punctuation tolerant).
                                try:
                                    return self._normalize_name(s or '')
                                except Exception:
                                    return (s or '').strip().lower()

                            # Find the longest contiguous match of signer_name parts in the extracted word stream.
                            best = None
                            best_len = 0
                            lower_words = [_norm(w.get('text', '')) for w in words]
                            lower_parts = [_norm(p) for p in parts]

                            if lower_parts and lower_words:
                                for i in range(len(lower_words)):
                                    if lower_words[i] != lower_parts[0]:
                                        continue
                                    j = 0
                                    while (i + j) < len(lower_words) and j < len(lower_parts) and lower_words[i + j] == lower_parts[j]:
                                        j += 1
                                    if j > best_len:
                                        best_len = j
                                        best = (i, i + j - 1)

                            if best and best_len >= max(2, min(3, len(lower_parts))):
                                i0, i1 = best
                                xs0 = [float(words[k].get('x0', 0.0)) for k in range(i0, i1 + 1)]
                                xs1 = [float(words[k].get('x1', 0.0)) for k in range(i0, i1 + 1)]
                                tops = [float(words[k].get('top', 0.0)) for k in range(i0, i1 + 1)]
                                bottoms = [float(words[k].get('bottom', 0.0)) for k in range(i0, i1 + 1)]
                                if xs0 and xs1 and tops and bottoms:
                                    name_bbox_last_page = {
                                        'x0': min(xs0),
                                        'x1': max(xs1),
                                        'top': min(tops),
                                        'bottom': max(bottoms),
                                    }
            except Exception:
                name_bbox_last_page = None

            for page_index in range(total_pages):
                page = pages[page_index] if pypdf2_api == 'new' else reader.getPage(page_index)
                if page_index in target_pages:
                    try:
                        if pypdf2_api == 'new':
                            page_w = float(page.mediabox.width)
                            page_h = float(page.mediabox.height)
                        else:
                            page_w = float(page.mediaBox.getWidth())
                            page_h = float(page.mediaBox.getHeight())
                    except Exception:
                        page_w, page_h = (595.0, 842.0)

                    overlay_buf = io.BytesIO()
                    c = canvas.Canvas(overlay_buf, pagesize=(page_w, page_h))

                    # Stamp only the signature image (no border/text) to avoid covering PDF content.
                    # Place into the Bên A signature area on typical contract templates.
                    # If we can find the printed name, place the signature right above it (like the sample).
                    margin = 36.0
                    gap = 10.0

                    target_w = float(page_w * 0.35)  # Width similar to sample
                    target_h = float(page_h * 0.10)  # Height to avoid covering content
                    target_w = max(160.0, min(target_w, float(page_w) - margin * 2.0))
                    target_h = max(70.0, min(target_h, float(page_h) - margin * 2.0))

                    x0 = float(margin)
                    y0 = float(page_h * 0.18)  # fallback default

                    if (not stamp_all_pages) and (page_index == max(total_pages - 1, 0)) and name_bbox_last_page:
                        try:
                            name_x0 = float(name_bbox_last_page.get('x0', 0.0))
                            name_x1 = float(name_bbox_last_page.get('x1', 0.0))
                            name_top = float(name_bbox_last_page.get('top', 0.0))

                            # Convert pdfplumber top-origin coordinates to reportlab bottom-origin.
                            name_y_top_rl = float(page_h) - name_top

                            # Center the signature in the same column as the name.
                            name_x_center = (name_x0 + name_x1) / 2.0
                            x0 = name_x_center - (target_w / 2.0)

                            # Keep in left half (Bên A) by default.
                            left_max = (float(page_w) / 2.0) - margin - target_w
                            x0 = max(margin, min(x0, left_max))

                            # Put signature above the name line with a small gap.
                            y0 = name_y_top_rl + gap
                        except Exception:
                            pass

                    y0 = max(margin, min(y0, float(page_h) - margin - target_h))

                    img_area_x = x0
                    img_area_y = y0
                    img_area_w = target_w
                    img_area_h = target_h

                    scale = min(img_area_w / float(img_w or 1), img_area_h / float(img_h or 1))
                    draw_w = float(img_w) * scale
                    draw_h = float(img_h) * scale
                    draw_x = img_area_x + (img_area_w - draw_w) / 2.0
                    draw_y = img_area_y + (img_area_h - draw_h) / 2.0
                    c.drawImage(img_reader, draw_x, draw_y, width=draw_w, height=draw_h, mask='auto')

                    c.showPage()
                    c.save()
                    overlay_buf.seek(0)

                    if pypdf2_api == 'new':
                        overlay_reader = PdfReader(overlay_buf, strict=False)
                        overlay_page = overlay_reader.pages[0]
                        page.merge_page(overlay_page)
                        writer.add_page(page)
                    else:
                        overlay_reader = PdfFileReader(overlay_buf, strict=False)
                        overlay_page = overlay_reader.getPage(0)
                        page.mergePage(overlay_page)
                        writer.addPage(page)
                else:
                    if pypdf2_api == 'new':
                        writer.add_page(page)
                    else:
                        writer.addPage(page)

            out_buf = io.BytesIO()
            writer.write(out_buf)
            return out_buf.getvalue()
        except Exception as e:
            _logger.warning('Không thể đóng dấu chữ ký lên PDF: %s', e)
            return pdf_bytes

    def _ensure_pki_keypair_for_pades(self, certificate, *, signer_name=False):
        """Ensure the certificate has private key + X.509 cert for PAdES signing.

        Uses sudo because private key fields are admin-only in UI.
        """
        if not certificate:
            raise UserError('Chưa có chứng thư số PKI để ký PAdES.')

        cert = certificate.sudo()
        if cert.private_key and cert.certificate:
            return cert

        # Populate minimal subject fields for the self-signed cert generation.
        vals = {}
        if signer_name and not cert.subject_common_name:
            vals['subject_common_name'] = signer_name
        if self.env.user.email and not cert.subject_email:
            vals['subject_email'] = self.env.user.email
        if vals:
            cert.write(vals)

        # Generate keypair + certificate (self-signed) if missing.
        cert.action_generate_keypair()
        return cert

    def _pades_sign_pdf(self, pdf_bytes, *, certificate, field_name, page_index=0, box=None, reason=None, location=None):
        """Sign a PDF using PAdES (Acrobat-compatible) via pyHanko."""
        try:
            from pyhanko.sign import signers
            from pyhanko.sign import fields as pyh_fields
            from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
            from pyhanko.pdf_utils.images import PdfImage
            from pyhanko.pdf_utils.layout import SimpleBoxLayoutRule, Margins, AxisAlignment, InnerScaling
            from pyhanko.stamp import StaticStampStyle
        except Exception as e:
            raise UserError(
                'Thiếu thư viện ký số PDF chuẩn (PAdES).\n'
                'Vui lòng cài: pip install "pyhanko==0.25.0" "pyhanko-certvalidator==0.26.2"\n'
                f'Chi tiết: {e}'
            )

        cert = certificate.sudo()
        if not cert.private_key or not cert.certificate:
            raise UserError('Chứng thư số PKI chưa có private key/certificate để ký PAdES.')

        key_pem = base64.b64decode(cert.private_key)
        cert_pem = base64.b64decode(cert.certificate)
        key_passphrase = (cert.private_key_password or 'odoo_default_password').encode('utf-8')

        # Keep temporary key/cert files alive until after signing.
        # Some signer backends lazily read these files, so deleting them too early can lead to
        # hard-to-diagnose runtime errors.
        with tempfile.NamedTemporaryFile(suffix='.pem', delete=True) as key_f, tempfile.NamedTemporaryFile(suffix='.pem', delete=True) as cert_f:
            key_f.write(key_pem)
            key_f.flush()
            cert_f.write(cert_pem)
            cert_f.flush()

            signer = signers.SimpleSigner.load(
                key_file=key_f.name,
                cert_file=cert_f.name,
                key_passphrase=key_passphrase,
            )

            # Some PDFs (often exported by Office/scanners) contain hybrid xref sections.
            # pyHanko refuses to sign hybrid-xref PDFs in strict mode.
            writer = IncrementalPdfFileWriter(io.BytesIO(pdf_bytes), strict=False)

            signature_meta = signers.PdfSignatureMetadata(
                field_name=field_name,
                md_algorithm='sha256',
                reason=reason or 'Ký số PAdES (PKI)',
                location=location or (self.env.company.name or None),
            )

            new_field_spec = pyh_fields.SigFieldSpec(
                sig_field_name=field_name,
                on_page=int(page_index or 0),
                box=box,
            )

            # Custom visible appearance: use the uploaded signature image (avoid pyHanko default icon/text)
            stamp_style = None
            try:
                if self.chu_ky:
                    try:
                        from PIL import Image
                        img = Image.open(io.BytesIO(base64.b64decode(self.chu_ky)))
                        if img.mode not in ('RGB', 'RGBA'):
                            img = img.convert('RGBA')
                        pdf_img = PdfImage(img)
                        stamp_style = StaticStampStyle(
                            border_width=0,
                            background=pdf_img,
                            background_layout=SimpleBoxLayoutRule(
                                x_align=AxisAlignment.ALIGN_MID,
                                y_align=AxisAlignment.ALIGN_MID,
                                margins=Margins(0, 0, 0, 0),
                                inner_content_scaling=InnerScaling.SHRINK_TO_FIT,
                            ),
                            background_opacity=1.0,
                        )
                    except Exception as e:
                        _logger.info('Không thể dùng ảnh chữ ký làm appearance PAdES, fallback default: %s', e)
            except Exception:
                stamp_style = None

            pdf_signer = signers.PdfSigner(
                signature_meta=signature_meta,
                signer=signer,
                stamp_style=stamp_style,
                new_field_spec=new_field_spec,
            )

            out = io.BytesIO()
            pdf_signer.sign_pdf(writer, existing_fields_only=False, output=out)
            return out.getvalue()

    def _can_use_pades(self):
        """Return True if the runtime crypto stack is compatible with pyHanko signing.

        In this environment, we frequently see a mismatch between `pyhanko` and `cryptography`
        where key loading fails (e.g. missing/required `backend` argument). In that case, we
        disable PAdES and fall back to visual stamping + internal signature.
        """
        try:
            import inspect
            from cryptography.hazmat.primitives.serialization import load_pem_private_key

            # If cryptography requires a backend argument, but the installed pyHanko expects a
            # backend-less API, signing will fail. Disable PAdES in that case.
            params = inspect.signature(load_pem_private_key).parameters
            if 'backend' in params:
                return False

            # Also require pyHanko to be importable.
            from pyhanko.sign import signers  # noqa: F401
            return True
        except Exception:
            return False

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

        # Prefill signer info from PDF and enforce HR permission matching (early feedback)
        try:
            tmp = self.new(res)
            model_name, document = tmp._get_target_document()
            if model_name and document:
                signer_in_pdf, title_in_pdf = tmp._extract_signer_info_from_pdf(model_name, document)
                if 'pdf_ten_nguoi_ky' in fields_list:
                    res['pdf_ten_nguoi_ky'] = signer_in_pdf or False
                if 'pdf_chuc_vu' in fields_list:
                    res['pdf_chuc_vu'] = title_in_pdf or False

                if signer_in_pdf:
                    nv = tmp._find_employee_by_pdf_name(signer_in_pdf)
                    if nv:
                        # Enforce that signer matches the current user (unless admin override)
                        if nv.user_id and nv.user_id.id != self.env.uid:
                            if not self.env.user.has_group('van_ban.group_quan_tri_van_ban') and not self.env.user.has_group('base.group_system'):
                                raise UserError(
                                    'Tên người ký trong PDF không thuộc quyền ký của tài khoản này.\n\n'
                                    f'- Trong PDF (Bên A): {signer_in_pdf}\n'
                                    f'- Nhân sự khớp trong hệ thống: {nv.ten_nv}\n\n'
                                    'Vui lòng đăng nhập đúng tài khoản người ký hoặc liên hệ quản trị.'
                                )
                        # Sync signer on wizard
                        if 'nguoi_ky_id' in fields_list:
                            res['nguoi_ky_id'] = nv.id
                        # Confirmation name should follow PDF signer to avoid confusion
                        if 'ho_ten_xac_nhan' in fields_list:
                            res['ho_ten_xac_nhan'] = signer_in_pdf
        except Exception:
            # Do not block wizard if extraction fails; strict checks remain in action_ky
            pass

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

        # Đồng bộ "Người ký nội bộ" trên văn bản theo dữ liệu trích xuất từ PDF (nếu hợp lệ).
        # LƯU Ý: Không được ghi đè lựa chọn thủ công của người dùng.
        # Chỉ auto-fill khi văn bản chưa có Người ký nội bộ.
        try:
            if model_name == 'van_ban' and hasattr(document, 'nguoi_ky_id'):
                is_admin = self.env.user.has_group('van_ban.group_quan_tri_van_ban') or self.env.user.has_group('base.group_system')

                # Always re-extract signer from PDF at signing-time to avoid stale wizard state
                signer_in_pdf, _title_in_pdf = self._extract_signer_info_from_pdf(model_name, document)
                signer_in_pdf = (signer_in_pdf or self.pdf_ten_nguoi_ky or '').strip() or False
                if signer_in_pdf:
                    matched_nv = self._find_employee_by_pdf_name(signer_in_pdf)
                    if matched_nv:
                        is_owner = bool(matched_nv.user_id and matched_nv.user_id.id == self.env.uid)
                        if is_admin or is_owner:
                            # Keep wizard signer in sync too (even if hidden)
                            self.nguoi_ky_id = matched_nv.id
                            if not document.nguoi_ky_id:
                                document.sudo().write({'nguoi_ky_id': matched_nv.id})
                                if hasattr(document, '_ghi_lich_su'):
                                    document._ghi_lich_su('nguoi_ky_sync', f'Auto-fill Người ký nội bộ theo PDF: {matched_nv.ten_nv}')
        except Exception:
            # Không block luồng ký; đối chiếu strict bên dưới vẫn quyết định cuối.
            pass
        
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

        # === KIỂM TRA ĐỐI CHIẾU PDF (STRICT) TRƯỚC KHI TẠO CERT/THỰC HIỆN KÝ ===
        file_data_for_validation = None
        file_field_for_validation = getattr(document, 'file_dinh_kem', False)
        if not file_field_for_validation:
            raise UserError('Văn bản chưa có file đính kèm! Vui lòng upload file trước khi ký.')
        try:
            file_data_for_validation = base64.b64decode(file_field_for_validation)
        except Exception:
            raise UserError('File đính kèm không hợp lệ (không decode được). Vui lòng upload lại PDF.')
        self._pre_sign_validate_pdf_consistency(model_name, document, pdf_bytes=file_data_for_validation)
        
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
        
        # Timestamp dùng xuyên suốt (đóng dấu + ghi log)
        now = fields.Datetime.now()

        # === BƯỚC 3: CHUẨN HOÁ FILE ĐẦU VÀO (ĐÓNG DẤU + PAdES) + TẠO HASH ===
        file_sha256 = False
        file_data = None
        final_file_data = None
        final_file_b64 = None
        can_store_signed_file = hasattr(document, 'file_da_ky') and hasattr(document, 'ten_file_da_ky')
        pades_applied = False
        pades_field_name = False
        try:
            file_field = getattr(document, 'file_dinh_kem', False)
            if not file_field:
                raise UserError('Văn bản chưa có file đính kèm! Vui lòng upload file trước khi ký.')

            # Reuse decoded bytes from strict validation to avoid decoding twice
            file_data = file_data_for_validation or base64.b64decode(file_field)

            final_file_data = file_data

            is_pdf = self._is_pdf_file(getattr(document, 'ten_file', False), file_data)
            signer_name = (self.nguoi_ky_id.ten_nv if self.nguoi_ky_id else self.env.user.name)
            signer_title = (self.chuc_vu or '')

            # Always apply a visible stamp (best-effort) before hashing/signing.
            # This is independent from PAdES and should not block signing.
            if is_pdf and self.chu_ky:
                try:
                    final_file_data = self._stamp_signature_on_pdf(
                        final_file_data,
                        signature_image_b64=self.chu_ky,
                        signer_name=signer_name,
                        signer_title=signer_title,
                        signed_at=now,
                        stamp_all_pages=False,
                    )
                except Exception as e:
                    _logger.warning('Không thể đóng dấu chữ ký lên PDF (bỏ qua): %s', e)

            # PAdES cryptographic signature (Acrobat-compatible) - optional
            # Use getattr for safety in case of partial reload/upgrade.
            if can_store_signed_file and is_pdf and getattr(self, '_can_use_pades', lambda: False)():
                cert_for_pades = self._ensure_pki_keypair_for_pades(self.certificate_id, signer_name=signer_name)

                # Compute a signature field position near bottom-right (within the same stamp area)
                try:
                    from PyPDF2 import PdfFileReader
                    reader = PdfFileReader(io.BytesIO(final_file_data), strict=False)
                    total_pages = reader.getNumPages()
                    page_index = max(total_pages - 1, 0)
                    page = reader.getPage(page_index)
                    page_w = float(page.mediaBox.getWidth())
                    page_h = float(page.mediaBox.getHeight())
                except Exception:
                    page_index = 0
                    page_w, page_h = (595.0, 842.0)

                margin = 36.0
                # Default to Bên A (left side). Đặt chữ ký CAO HƠN để không đè lên họ tên người ký
                box_w = 200.0  # Thu nhỏ chiều rộng
                box_h = 80.0   # Thu nhỏ chiều cao
                x0 = int(margin)
                # Tăng y0 lên để chữ ký nằm cao hơn (18% từ đáy thay vì 13%)
                y0 = int(max(margin, min(page_h * 0.18, page_h - margin - box_h)))
                box = (x0, y0, int(x0 + box_w), int(y0 + box_h))

                pades_field_name = f"SIG_{model_name}_{document.id}_{int(time.time())}"
                try:
                    final_file_data = self._pades_sign_pdf(
                        final_file_data,
                        certificate=cert_for_pades,
                        field_name=pades_field_name,
                        page_index=page_index,
                        box=box,
                        reason=f'Ký số PAdES - {signer_name}',
                    )
                    pades_applied = True
                except Exception as e:
                    # PAdES is optional; keep the stamped PDF and continue.
                    _logger.warning('PAdES signing failed, fallback to stamped PDF only: %s', e)
                    pades_applied = False
                    pades_field_name = False

            final_file_b64 = base64.b64encode(final_file_data)
            file_sha256 = hashlib.sha256(final_file_data).hexdigest()
            _logger.info("File SHA256 hash: %s", file_sha256)
        except Exception as e:
            _logger.error("Error preparing file for signing/hash: %s", e)
            raise UserError(f'Lỗi khi chuẩn bị file để ký/tạo hash: {str(e)}')
        
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
                final_file_data,
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

        # Lưu file đã ký (PDF đã đóng dấu nếu có)
        if can_store_signed_file and final_file_b64:
            ten_goc = getattr(document, 'ten_file', False) or 'document.pdf'
            document.file_da_ky = final_file_b64
            document.ten_file_da_ky = f"SIGNED_{ten_goc}"

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
        if can_store_signed_file and self._is_pdf_file(getattr(document, 'ten_file', False), final_file_data or b''):
            message_body += '<p><strong>Đóng dấu chữ ký lên PDF:</strong> Có</p>'
        if pades_applied:
            message_body += '<p><strong>Ký số chuẩn (PAdES/Acrobat):</strong> Có</p>'
            if pades_field_name:
                message_body += f'<p><strong>PAdES Field:</strong> <code>{pades_field_name}</code></p>'
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
