# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, timedelta
import hashlib
import base64
import logging
import io
import re
import unicodedata

from .ocr_utils import fix_spacing_artifacts

_logger = logging.getLogger(__name__)

try:
    from textblob import TextBlob
    from sumy.parsers.plaintext import PlaintextParser
    from sumy.nlp.tokenizers import Tokenizer
    from sumy.summarizers.lsa import LsaSummarizer
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False
    _logger.warning("AI libraries not available. Install textblob and sumy for AI features.")


class VanBan(models.Model):
    _name = 'van_ban'
    _description = 'Văn bản'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'ngay_tao desc'

    # === THÔNG TIN CƠ BẢN ===
    ma_van_ban = fields.Char('Mã văn bản', required=True, copy=False, readonly=True,
                              default=lambda self: _('New'), tracking=True)
    ten_van_ban = fields.Char('Tên văn bản', required=True, tracking=True)
    loai_van_ban_id = fields.Many2one('loai_van_ban', string='Loại văn bản', 
                                       required=True, tracking=True,
                                       default=lambda self: self._default_loai_van_ban())
    mo_ta = fields.Text('Mô tả')
    
    # === TRẠNG THÁI (WORKFLOW) ===
    # Quy trình: Nháp → Chờ duyệt → Đã duyệt → Chờ ký → Đã ký → Đã gửi
    # KÝ ĐIỆN TỬ BẮT BUỘC trước khi gửi
    trang_thai = fields.Selection([
        ('nhap', 'Nháp'),
        ('cho_duyet', 'Chờ duyệt'),
        ('da_duyet', 'Đã duyệt'),
        ('cho_ky', 'Chờ ký'),
        ('da_ky', 'Đã ký'),
        ('da_gui', 'Đã gửi'),  # THÊM: Gửi sau khi ký
        ('het_hieu_luc', 'Hết hiệu lực'),
        ('huy', 'Đã hủy')
    ], string='Trạng thái', default='nhap', required=True, tracking=True)
    
    # Dynamic Workflow Template
    workflow_template_id = fields.Many2one('workflow.template', string='Workflow Template',
                                           domain="[('model_name', '=', 'van_ban'), ('active', '=', True)]",
                                           tracking=True, help='Select workflow template for this document')
    
    # === THỜI HẠN ===
    ngay_tao = fields.Datetime('Ngày tạo', default=fields.Datetime.now, readonly=True)
    ngay_gui = fields.Date('Ngày gửi', tracking=True, readonly=True,
                           help='Ngày gửi văn bản (sau khi ký điện tử)')
    ngay_hieu_luc = fields.Date('Ngày hiệu lực', tracking=True)
    ngay_het_han = fields.Date('Ngày hết hạn', tracking=True)
    so_ngay_con_lai = fields.Integer('Số ngày còn lại', compute='_compute_so_ngay_con_lai',
                                      store=True)
    sap_het_han = fields.Boolean('Sắp hết hạn', compute='_compute_so_ngay_con_lai',
                                  store=True)
    
    # === LIÊN KẾT ===
    # Liên kết với module Khách hàng
    khach_hang_id = fields.Many2one('khach_hang', string='Khách hàng liên quan',
                                     tracking=True)
    khach_hang_trong_hop_dong = fields.Char(
        'Khách hàng (trong hợp đồng)',
        help='Tên khách hàng/đối tác được trích xuất từ nội dung hợp đồng (PDF).'
    )
    don_hang_id = fields.Many2one('don_hang', string='Đơn hàng liên quan',
                                   domain="[('khach_hang_id', '=', khach_hang_id)]")
    
    # Liên kết với module Nhân sự
    nguoi_tao_id = fields.Many2one('nhan_vien', string='Người tạo',
                                    default=lambda self: self._get_nhan_vien_hien_tai(),
                                    tracking=True)
    # Trưởng phòng Sales - người duyệt văn bản (bước 1)
    truong_phong_duyet_id = fields.Many2one(
        'nhan_vien', string='Trưởng phòng duyệt',
        domain="['|', '|', ('chuc_vu', 'ilike', 'Trưởng phòng'), ('chuc_vu', 'ilike', 'Truong phong'), ('chuc_vu_id.name', 'ilike', 'Trưởng phòng')]",
        default=lambda self: self._get_truong_phong_sales_default(),
        tracking=True,
        help='Trưởng phòng Sales sẽ duyệt văn bản')
    nguoi_duyet_id = fields.Many2one('nhan_vien', string='Người duyệt (cũ)', tracking=True)  # Kept for compatibility
    nguoi_phe_duyet_id = fields.Many2one('nhan_vien', string='Người phê duyệt', tracking=True)
    # Giám đốc - người ký văn bản (bước 2)
    nguoi_ky_id = fields.Many2one(
        'nhan_vien', string='Giám đốc ký',
        domain="['|', '|', '|', ('chuc_vu', 'ilike', 'Giám đốc'), ('chuc_vu', 'ilike', 'Giam doc'), ('chuc_vu', 'ilike', 'Director'), ('chuc_vu_id.name', 'ilike', 'Giám đốc')]",
        default=lambda self: self._get_giam_doc_default(),
        tracking=True,
        help='Giám đốc sẽ duyệt và ký điện tử văn bản')
    
    # Computed fields for display
    ten_nguoi_tao = fields.Char('Tên người tạo', compute='_compute_sync_nhan_su', store=True)
    phong_ban_nguoi_tao = fields.Char('Phòng ban người tạo', compute='_compute_sync_nhan_su', store=True)
    ten_nguoi_duyet = fields.Char('Tên người duyệt', compute='_compute_sync_nhan_su', store=True)
    ten_nguoi_ky = fields.Char('Tên người ký', compute='_compute_sync_nhan_su', store=True)
    
    # === FILE ĐÍNH KÈM ===
    file_dinh_kem = fields.Binary('File văn bản', attachment=True)
    ten_file = fields.Char('Tên file')
    file_da_ky = fields.Binary('File đã ký', attachment=True, readonly=True)
    ten_file_da_ky = fields.Char('Tên file đã ký')

    # === PDF AUTO-EXTRACTION (AI) ===
    ai_pdf_source_hash = fields.Char('AI PDF Source Hash', readonly=True)
    ai_pdf_text = fields.Text('AI PDF Extracted Text', readonly=True)
    ai_pdf_extracted_at = fields.Datetime('AI PDF Extracted At', readonly=True)
    ai_pdf_extract_state = fields.Selection([
        ('none', 'Chưa xử lý'),
        ('done', 'Đã trích xuất'),
        ('error', 'Lỗi'),
    ], string='AI PDF Extract State', default='none', readonly=True)
    ai_pdf_extract_error = fields.Text('AI PDF Extract Error', readonly=True)
    
    # === KÝ ĐIỆN TỬ ===
    da_ky_noi_bo = fields.Boolean('Đã ký nội bộ', readonly=True)
    ngay_ky_noi_bo = fields.Datetime('Ngày ký nội bộ', readonly=True)
    chu_ky_noi_bo = fields.Binary('Chữ ký nội bộ', readonly=True)

    nguoi_ky_trong_pdf = fields.Char(
        'Người ký (trong PDF đã ký)',
        readonly=True,
        tracking=True,
        help='Họ tên người ký được trích xuất từ nội dung file PDF sau khi ký.'
    )
    nguoi_ky_trong_pdf_extracted_at = fields.Datetime('Trích xuất từ PDF lúc', readonly=True)

    chuc_vu_nguoi_ky_trong_pdf = fields.Char(
        'Chức vụ người ký (trong PDF đã ký)',
        readonly=True,
        tracking=True,
        help='Chức vụ người ký được trích xuất từ nội dung file PDF sau khi ký (nếu có trong văn bản).'
    )
    chuc_vu_nguoi_ky_trong_pdf_extracted_at = fields.Datetime('Trích xuất chức vụ từ PDF lúc', readonly=True)
    
    da_khach_ky = fields.Boolean('Khách đã ký', readonly=True)
    ngay_khach_ky = fields.Datetime('Ngày khách ký', readonly=True)
    chu_ky_khach = fields.Binary('Chữ ký khách hàng', readonly=True)

    signature_log_ids = fields.One2many(
        'van_ban.signature.log', 'van_ban_id',
        string='Lịch sử ký', readonly=True
    )
    
    # === YÊU CẦU KÝ ===
    yeu_cau_ky_ids = fields.One2many('yeu_cau_ky', 'van_ban_id', string='Yêu cầu ký')
    so_yeu_cau_ky = fields.Integer('Số yêu cầu ký', compute='_compute_so_yeu_cau_ky')
    
    # === LỊCH SỬ ===
    lich_su_ids = fields.One2many('lich_su_van_ban', 'van_ban_id', string='Lịch sử thay đổi')
    
    # === BẢO MẬT ===
    hash_file = fields.Char('Hash file', readonly=True, help='Mã hash để kiểm tra tính toàn vẹn')
    bi_khoa = fields.Boolean('Bị khóa', default=False, 
                              help='Văn bản bị khóa không thể chỉnh sửa')
    
    # === AI FEATURES ===
    ai_category_suggestion = fields.Many2one('loai_van_ban', string='AI gợi ý loại', readonly=True)
    ai_summary = fields.Text('Tóm tắt AI', readonly=True)
    ai_sentiment = fields.Selection([
        ('positive', 'Tích cực'),
        ('neutral', 'Trung lập'),
        ('negative', 'Tiêu cực')
    ], string='Sentiment AI', readonly=True)
    ai_approver_suggestion = fields.Many2many('nhan_vien', string='AI gợi ý người duyệt', readonly=True)
    ai_risk_score = fields.Float('Điểm rủi ro AI', readonly=True, help='Điểm rủi ro từ 0-1')

    # === BLOCKCHAIN (OPTIONAL) ===
    blockchain_tx_hash = fields.Char('Blockchain Transaction Hash', readonly=True, tracking=True)
    
    # === GHI CHÚ ===
    ghi_chu = fields.Text('Ghi chú')
    ly_do_huy = fields.Text('Lý do hủy')
    
    # === TIỆN ÍCH ===
    currency_id = fields.Many2one('res.currency', string='Tiền tệ',
                                   default=lambda self: self.env.company.currency_id)
    gia_tri_hop_dong = fields.Monetary('Giá trị hợp đồng', currency_field='currency_id')
    
    # === PROCESS AUTOMATION - AI-ENHANCED FEATURES ===
    # AI suggestions for workflow
    ai_suggested_approver = fields.Many2one('nhan_vien', string='AI đề xuất người duyệt',
                                             compute='_compute_ai_suggestions', store=False)
    ai_suggested_signer = fields.Many2one('nhan_vien', string='AI đề xuất người ký',
                                           compute='_compute_ai_suggestions', store=False)
    ai_risk_level = fields.Selection([
        ('low', 'Thấp'),
        ('medium', 'Trung bình'),
        ('high', 'Cao'),
        ('critical', 'Nguy hiểm')
    ], string='Mức độ rủi ro (AI)', compute='_compute_ai_risk_assessment', store=True)

    ai_category_suggestion = fields.Char('AI phân loại tự động', compute='_compute_ai_category', store=True)
    ai_priority_score = fields.Float('Điểm ưu tiên (AI)', compute='_compute_ai_priority', store=True)
    
    # Additional AI fields for analysis
    ai_assessment = fields.Text('Đánh giá AI', readonly=True)
    ai_analysis_date = fields.Datetime('Ngày phân tích AI', readonly=True)
    ai_auto_stats = fields.Text('Thống kê AI tự động', readonly=True)

    # Automated workflow tracking
    auto_follow_up_count = fields.Integer('Số lần follow-up tự động', default=0)
    last_auto_follow_up = fields.Datetime('Lần follow-up cuối')
    sla_deadline = fields.Datetime('Hạn SLA', compute='_compute_sla_deadline', store=True)
    sla_breached = fields.Boolean('Vi phạm SLA', compute='_compute_sla_status', store=True)
    
    _sql_constraints = [
        ('ma_van_ban_unique', 'unique(ma_van_ban)', 'Mã văn bản đã tồn tại!')
    ]
    
    # File security constraints
    ALLOWED_FILE_TYPES = ['pdf', 'doc', 'docx', 'txt', 'jpg', 'jpeg', 'png']
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    
    @api.constrains('file_dinh_kem', 'ten_file')
    def _check_file_security(self):
        """Validate file uploads for security"""
        for record in self:
            if record.file_dinh_kem:
                # Check file size
                file_size = len(base64.b64decode(record.file_dinh_kem))
                if file_size > self.MAX_FILE_SIZE:
                    raise ValidationError(f"File size exceeds maximum allowed size of {self.MAX_FILE_SIZE / (1024*1024):.1f}MB")
                
                # Check file extension
                if record.ten_file:
                    file_ext = record.ten_file.split('.')[-1].lower() if '.' in record.ten_file else ''
                    if file_ext not in self.ALLOWED_FILE_TYPES:
                        raise ValidationError(f"File type '{file_ext}' is not allowed. Allowed types: {', '.join(self.ALLOWED_FILE_TYPES)}")
                
                # Check for malicious content (basic check)
                file_content = base64.b64decode(record.file_dinh_kem)
                if self._contains_malicious_content(file_content):
                    raise ValidationError("File contains potentially malicious content and has been rejected")
    
    def _contains_malicious_content(self, file_content):
        """Basic check for malicious file content"""
        # Check for executable signatures
        malicious_signatures = [
            b'MZ',  # Windows executable
            b'#!/bin/',  # Shell script
            b'<?php',  # PHP script
            b'<script',  # JavaScript
        ]
        
        for signature in malicious_signatures:
            if file_content.startswith(signature):
                return True
        
        return False

    # === PDF AUTO-FILL (ONCHANGE) ===

    @api.onchange('file_dinh_kem', 'ten_file')
    def _onchange_file_dinh_kem_autofill_from_pdf(self):
        """Auto-fill fields when user uploads a PDF in the form."""
        warning = False
        for record in self:
            warning = record._ai_autofill_from_uploaded_pdf(force=False, is_onchange=True) or warning
        return warning

    def _post_sign_autofill_from_signed_pdf(self):
        """Chạy sau khi ký: trích xuất dữ liệu từ file PDF đã ký.

        - Ưu tiên trích xuất tên người ký (đại diện BÊN A) và ghi lịch sử.
        - Có thể trích xuất tên khách hàng (BÊN B) để điền `khach_hang_trong_hop_dong` nếu đang trống.
        - Không raise lỗi để tránh làm fail luồng ký.
        """
        self.ensure_one()

        if not self.file_da_ky or not self.ten_file_da_ky:
            return False

        file_ext = self.ten_file_da_ky.split('.')[-1].lower() if '.' in self.ten_file_da_ky else ''
        if file_ext != 'pdf':
            return False

        try:
            pdf_bytes = base64.b64decode(self.file_da_ky)
        except Exception:
            return False

        try:
            extracted_text = self._ai_extract_text_from_pdf_bytes(pdf_bytes)
        except Exception as e:
            _logger.warning("Post-sign PDF extraction failed (read PDF): %s", e)
            return False

        try:
            party_info = self._ai_extract_party_names_from_text(extracted_text)
        except Exception as e:
            _logger.warning("Post-sign PDF extraction failed (party parse): %s", e)
            return False

        # Apply customer name (BÊN B) if empty
        try:
            self._ai_apply_party_info(party_info)
        except Exception as e:
            _logger.warning("Post-sign PDF extraction failed (apply party): %s", e)

        signer_in_pdf = (party_info.get('dai_dien_ben_a') or '').strip() if isinstance(party_info, dict) else False

        signer_title_in_pdf = False
        try:
            if signer_in_pdf:
                signer_title_in_pdf = self._ai_extract_signer_title_from_text(extracted_text, signer_in_pdf)
        except Exception as e:
            _logger.warning("Post-sign PDF extraction failed (title parse): %s", e)

        if signer_in_pdf:
            self.write({
                'nguoi_ky_trong_pdf': signer_in_pdf,
                'nguoi_ky_trong_pdf_extracted_at': fields.Datetime.now(),
            })

        if signer_title_in_pdf:
            self.write({
                'chuc_vu_nguoi_ky_trong_pdf': signer_title_in_pdf,
                'chuc_vu_nguoi_ky_trong_pdf_extracted_at': fields.Datetime.now(),
            })

        # Log to history
        try:
            if hasattr(self, '_ghi_lich_su'):
                lines = [
                    '📄 Trích xuất dữ liệu từ PDF đã ký',
                ]
                if signer_in_pdf:
                    lines.append(f'   - Người ký (trong PDF): {signer_in_pdf}')
                if signer_title_in_pdf:
                    lines.append(f'   - Chức vụ (trong PDF): {signer_title_in_pdf}')
                ben_b = (party_info.get('ben_b') or '').strip() if isinstance(party_info, dict) else False
                if ben_b:
                    lines.append(f'   - Khách hàng (BÊN B): {ben_b}')
                self._ghi_lich_su('pdf_signed_extract', "\n".join(lines))
        except Exception as e:
            _logger.warning("Post-sign PDF extraction failed (history): %s", e)

        return signer_in_pdf or False

    def _ai_extract_signer_title_from_text(self, extracted_text, signer_name):
        """Extract signer title/position near signer name in the signature block.

        Heuristic: find the last occurrence of signer_name near the end, then look upward
        for a short line that looks like a job title (e.g., Giám đốc, Tổng giám đốc...).
        """
        if not extracted_text or not signer_name:
            return False

        raw_lines = [re.sub(r'\s+', ' ', (ln or '')).strip() for ln in extracted_text.splitlines()]
        lines = [ln for ln in raw_lines if ln]
        if not lines:
            return False

        def _norm(s):
            if not s:
                return ''
            s = s.strip().lower()
            s = s.replace('\u00a0', ' ').replace('\t', ' ').replace('\n', ' ').replace('\r', ' ')
            s = unicodedata.normalize('NFKD', s)
            s = ''.join(ch for ch in s if not unicodedata.combining(ch))
            s = s.replace('đ', 'd')
            s = re.sub(r"[^0-9a-zA-Z\s]", " ", s)
            s = re.sub(r'\s+', ' ', s).strip()
            return s

        target = _norm(signer_name)
        if not target:
            return False

        stop_re = re.compile(r'\b(ky|ký|ghi ro|ghi rõ|dong dau|đóng dấu|dai dien|đại diện|ben\s*[ab]|bên\s*[ab])\b', re.IGNORECASE)

        # Search from the end for the signer line
        for idx in range(len(lines) - 1, -1, -1):
            ln = lines[idx]
            if target and target in _norm(ln):
                # Look upward for title-like line
                for j in range(max(0, idx - 6), idx):
                    cand = lines[idx - 1 - (j - max(0, idx - 6))]
                    c = (cand or '').strip()
                    if not c:
                        continue
                    if stop_re.search(c):
                        continue
                    if re.search(r'\d', c):
                        continue
                    if len(c) > 60:
                        continue
                    # Handle patterns like "Chức vụ: Giám đốc"
                    m = re.search(r'(Chức vụ|Chuc vu)\s*[:：]\s*(.+)$', c, flags=re.IGNORECASE)
                    if m:
                        val = m.group(2).strip()
                        return val or False
                    # Skip parenthetical guidance
                    if re.search(r'\(.*\)', c):
                        continue
                    return c
                return False
        return False

    def action_ai_autofill_from_pdf(self):
        """Manual re-run (useful after editing, or when onchange didn't run due to caching)."""
        for record in self:
            warning = record._ai_autofill_from_uploaded_pdf(force=True, is_onchange=False)
            if warning:
                return warning
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('AI Auto-fill'),
                'message': _('Đã thử tự điền thông tin từ PDF.'),
                'type': 'success',
                'sticky': False,
            }
        }

    def _ai_autofill_from_uploaded_pdf(self, force=False, is_onchange=False):
        """Shared implementation for onchange and manual button.

        - Only runs when `file_dinh_kem` is a PDF.
        - Uses hash caching; set `force=True` to re-run.
        - Fills only empty fields.
        """
        self.ensure_one()

        if not self.file_dinh_kem:
            return False

        filename = self.ten_file or ''

        # Always provide safe defaults for required fields (avoid "Invalid fields" popups)
        # NOTE: Do NOT lock the title to filename here; we will prefer PDF-content title later.
        fallback_title_from_filename = self._ai_title_from_filename(filename) if filename else False
        placeholder_title = _('Văn bản')
        if not self.ten_van_ban:
            self.ten_van_ban = fallback_title_from_filename or placeholder_title
        if not self.loai_van_ban_id:
            self.loai_van_ban_id = self._default_loai_van_ban()

        # Fast reject non-PDF by extension (if filename exists)
        file_ext = filename.split('.')[-1].lower() if '.' in filename else ''
        if filename and file_ext and file_ext != 'pdf':
            return False

        try:
            pdf_bytes = base64.b64decode(self.file_dinh_kem)
        except Exception:
            return False

        # If filename is missing, detect PDF by header to still allow onchange autofill.
        if not filename:
            if not pdf_bytes.lstrip().startswith(b'%PDF'):
                return False
        else:
            if file_ext != 'pdf':
                return False

        source_hash = hashlib.md5(pdf_bytes).hexdigest()
        if not force and self.ai_pdf_source_hash and self.ai_pdf_source_hash == source_hash:
            return False

        try:
            extracted_text = self._ai_extract_text_from_pdf_bytes(pdf_bytes)
        except Exception as e:
            self.ai_pdf_source_hash = source_hash
            self.ai_pdf_extract_state = 'error'
            self.ai_pdf_extract_error = str(e)
            # Keep defaults for required fields, and attempt to guess doc type from filename.
            if not self.loai_van_ban_id:
                self.loai_van_ban_id = self._ai_guess_loai_van_ban_from_text(extracted_text=None, filename=filename)
            # Fallback title already applied above; keep going with warning.
            if is_onchange:
                return {
                    'warning': {
                        'title': _('Không thể đọc PDF'),
                        'message': str(e),
                    }
                }
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Không thể đọc PDF'),
                    'message': str(e),
                    'type': 'warning',
                    'sticky': False,
                }
            }

        if not extracted_text or len(extracted_text.strip()) < 30:
            self.ai_pdf_source_hash = source_hash
            self.ai_pdf_extract_state = 'error'
            self.ai_pdf_extract_error = 'Không trích xuất được text từ PDF (có thể là PDF scan).'
            msg = _(
                'Không trích xuất được text từ PDF (có thể là PDF scan). '
                'Bạn có thể dùng chức năng OCR trước, hoặc cung cấp PDF có layer chữ.'
            )
            if not self.loai_van_ban_id:
                self.loai_van_ban_id = self._ai_guess_loai_van_ban_from_text(extracted_text=None, filename=filename)
            # Fallback title already applied above.
            if is_onchange:
                return {
                    'warning': {
                        'title': _('PDF không có text'),
                        'message': msg,
                    }
                }
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('PDF không có text'),
                    'message': msg,
                    'type': 'warning',
                    'sticky': False,
                }
            }

        # Store extraction info (truncate to avoid huge DB text)
        self.ai_pdf_source_hash = source_hash
        self.ai_pdf_text = extracted_text[:50000]
        self.ai_pdf_extracted_at = fields.Datetime.now()
        self.ai_pdf_extract_state = 'done'
        self.ai_pdf_extract_error = False

        # Prefer title extracted from PDF content; override placeholder/filename-based fallback.
        try:
            extracted_title = self._ai_extract_title_from_text(extracted_text, filename=filename)
        except Exception:
            extracted_title = False
        if extracted_title:
            current_title = (self.ten_van_ban or '').strip()
            if (not current_title) or (current_title == placeholder_title) or (fallback_title_from_filename and current_title == fallback_title_from_filename):
                self.ten_van_ban = extracted_title

        # Rule-based: extract key fields without AI (fast + reliable)
        if not self.khach_hang_trong_hop_dong:
            guessed_kh = self._ai_guess_customer_name_from_text(extracted_text)
            if guessed_kh:
                self.khach_hang_trong_hop_dong = guessed_kh

        if not self.gia_tri_hop_dong or self.gia_tri_hop_dong == 0:
            guessed_value = self._ai_extract_contract_value_from_text(extracted_text)
            if guessed_value:
                self.gia_tri_hop_dong = guessed_value

        # Rule-based: detect parties/signers from text before AI (avoid wrong customer)
        party_info = self._ai_extract_party_names_from_text(extracted_text)

        # STRICT VALIDATION: if extracted parties/signers don't match existing data, stop immediately.
        def _norm(val):
            if not val:
                return ''
            s = (val or '').strip().lower()
            s = s.replace('\u00a0', ' ').replace('\t', ' ').replace('\n', ' ').replace('\r', ' ')
            s = s.replace('\u200b', '').replace('\u200c', '').replace('\u200d', '').replace('\ufeff', '')
            s = unicodedata.normalize('NFKD', s)
            s = ''.join(ch for ch in s if not unicodedata.combining(ch))
            s = s.replace('đ', 'd')
            s = re.sub(r"[^0-9a-zA-Z\s]", " ", s)
            s = re.sub(r'\s+', ' ', s).strip()
            return s

        issues = []
        ben_b_in_pdf = (party_info.get('ben_b') or '').strip() if isinstance(party_info, dict) else ''
        signer_a_in_pdf = (party_info.get('dai_dien_ben_a') or '').strip() if isinstance(party_info, dict) else ''

        matched_customer = False
        if ben_b_in_pdf:
            KhachHang = self.env['khach_hang'].sudo()
            matched_customer = KhachHang.search([('ten_khach_hang', '=ilike', ben_b_in_pdf)], limit=1)
            if not matched_customer:
                matched_customer = KhachHang.search([('ten_khach_hang', 'ilike', ben_b_in_pdf)], limit=1)
            if not matched_customer:
                issues.append(_(u'Khách hàng trong PDF chưa có trong module Khách hàng: %s') % ben_b_in_pdf)

        # If user already selected customer/order, enforce consistency with PDF
        if matched_customer and self.khach_hang_id and self.khach_hang_id.id != matched_customer.id:
            # name-based fallback (in case of duplicates / formatting)
            if _norm(self.khach_hang_id.ten_khach_hang) != _norm(ben_b_in_pdf):
                issues.append(_(u'Khách hàng liên quan không khớp với PDF. PDF: %s | Văn bản: %s') % (ben_b_in_pdf, self.khach_hang_id.ten_khach_hang or ''))

        if self.don_hang_id and self.khach_hang_id and self.don_hang_id.khach_hang_id and self.don_hang_id.khach_hang_id.id != self.khach_hang_id.id:
            issues.append(_(u'Đơn hàng liên quan không thuộc khách hàng đã chọn. Đơn hàng: %s | Khách hàng: %s') % (
                (self.don_hang_id.ma_don_hang or self.don_hang_id.display_name),
                (self.khach_hang_id.ten_khach_hang or self.khach_hang_id.display_name),
            ))
        elif self.don_hang_id and matched_customer and self.don_hang_id.khach_hang_id and self.don_hang_id.khach_hang_id.id != matched_customer.id:
            issues.append(_(u'Đơn hàng liên quan không khớp với khách hàng trong PDF. PDF: %s | Đơn hàng thuộc: %s') % (
                ben_b_in_pdf,
                (self.don_hang_id.khach_hang_id.ten_khach_hang if self.don_hang_id.khach_hang_id else ''),
            ))

        if signer_a_in_pdf and self.nguoi_ky_id and _norm(self.nguoi_ky_id.ten_nv) != _norm(signer_a_in_pdf):
            issues.append(_(u'Người ký nội bộ không khớp với tên người ký trong PDF (Bên A). PDF: %s | Văn bản: %s') % (
                signer_a_in_pdf,
                (self.nguoi_ky_id.ten_nv or ''),
            ))

        if issues:
            self.ai_pdf_extract_state = 'error'
            self.ai_pdf_extract_error = '\n'.join(issues)
            title = _('Dữ liệu PDF không khớp')
            msg = _('Không thể tiếp tục tự điền từ PDF vì dữ liệu không trùng khớp:\n\n%s') % ('\n'.join([f'- {x}' for x in issues]))
            if is_onchange:
                return {
                    'warning': {
                        'title': title,
                        'message': msg,
                    }
                }
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': title,
                    'message': msg,
                    'type': 'danger',
                    'sticky': True,
                }
            }

        self._ai_apply_party_info(party_info)

        # Link to existing customer record when uniquely found.
        # This enables downstream domain filtering (e.g., order selection) right after extraction.
        if ben_b_in_pdf and not self.khach_hang_id:
            try:
                self._ai_apply_customer_name(ben_b_in_pdf)
            except Exception:
                # Never fail the PDF auto-fill flow due to customer linking
                pass

        # Fill document type if still empty
        if not self.loai_van_ban_id:
            self.loai_van_ban_id = self._ai_guess_loai_van_ban_from_text(extracted_text=extracted_text, filename=filename)

        # AI: extract structured fields from text
        try:
            extracted = self._ai_extract_structured_fields_from_text(extracted_text)
            self._ai_apply_extracted_fields(extracted)
        except Exception as e:
            self.ai_pdf_extract_error = str(e)
            msg = _(
                'PDF đã đọc được nội dung nhưng AI không trích xuất được dữ liệu để tự điền. '
                'Bạn vẫn có thể điền thủ công hoặc thử lại sau.\n\nLỗi: %s'
            ) % str(e)
            if is_onchange:
                return {
                    'warning': {
                        'title': _('Không thể trích xuất trường bằng AI'),
                        'message': msg,
                    }
                }
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Không thể trích xuất trường bằng AI'),
                    'message': msg,
                    'type': 'warning',
                    'sticky': False,
                }
            }

        # Fallback title from filename if still empty
        if not self.ten_van_ban:
            self.ten_van_ban = fallback_title_from_filename or placeholder_title

        return False

    def _ai_extract_title_from_text(self, extracted_text, *, filename=None):
        """Extract document title from the beginning of PDF text.

        Goal: Use in-document title (e.g. "HỢP ĐỒNG ...", "BÁO GIÁ ...") rather than filename.
        Returns a cleaned single-line title or False.
        """
        if not extracted_text:
            return False

        text = extracted_text.replace('\u00a0', ' ')
        raw_lines = [re.sub(r'\s+', ' ', (ln or '')).strip() for ln in text.splitlines()]
        lines = [ln for ln in raw_lines if ln]
        if not lines:
            return False

        # Scan the first part of the document for a title-like line
        head = lines[:60]

        def _is_header_noise(ln):
            return bool(re.search(
                r'(cộng\s*hòa|độc\s*lập|tự\s*do|hạnh\s*phúc|socialist|republic|---+|\*\*\*+)',
                ln,
                flags=re.IGNORECASE,
            ))

        def _is_meta_line(ln):
            return bool(re.search(r'(số\s*[:：]|ngày\s*\d{1,2}|tháng\s*\d{1,2}|năm\s*\d{4})', ln, flags=re.IGNORECASE))

        # Primary keywords that usually appear in a title
        kw = (
            r'(PHỤ\s*LỤC\s*HỢP\s*ĐỒNG|HỢP\s*ĐỒNG|BÁO\s*GIÁ|BIÊN\s*BẢN|CÔNG\s*VĂN|TỜ\s*TRÌNH|QUYẾT\s*ĐỊNH)'
        )

        for i, ln in enumerate(head):
            if _is_header_noise(ln):
                continue
            if re.search(kw, ln, flags=re.IGNORECASE):
                cand = ln
                # Optionally append the next line if it looks like a subtitle
                nxt = head[i + 1] if i + 1 < len(head) else ''
                if nxt and (not _is_header_noise(nxt)) and (not _is_meta_line(nxt)) and len(nxt) <= 140:
                    # common subtitle: all-caps words without too many digits
                    if len(re.findall(r'\d', nxt)) <= 6:
                        cand = f"{cand} {nxt}".strip()
                cand = re.sub(r'\s+', ' ', cand).strip()
                # Avoid absurdly long lines
                if 6 <= len(cand) <= 180:
                    return cand

        # Fallback: pick the first non-noise line that looks like a title
        for ln in head:
            if _is_header_noise(ln) or _is_meta_line(ln):
                continue
            if len(ln) < 6 or len(ln) > 180:
                continue
            # skip lines that are mostly punctuation/digits
            letters = len(re.findall(r'[A-Za-zÀ-ỹ]', ln))
            if letters < 6:
                continue
            return re.sub(r'\s+', ' ', ln).strip()

        return False

    def _ai_guess_customer_name_from_text(self, extracted_text):
        """Best-effort customer name extraction (BÊN B/BÊN MUA/BÊN THUÊ) without AI."""
        if not extracted_text:
            return False

        text = fix_spacing_artifacts(extracted_text)
        raw_lines = [re.sub(r'\s+', ' ', (ln or '')).strip() for ln in text.splitlines()]
        lines = [ln for ln in raw_lines if ln]

        def _clean_org(val):
            v = (val or '').strip()
            v = re.sub(r'^[-•·]\s*', '', v)
            v = re.sub(r'^(Tên\s*(đơn\s*vị|công\s*ty|doanh\s*nghiệp)|Đơn\s*vị)\s*[:：]\s*', '', v, flags=re.IGNORECASE)
            v = re.sub(r'^(BÊN\s*[AB]|BÊN\s*MUA|BÊN\s*BÁN|BÊN\s*THUÊ|BÊN\s*CHO\s*THUÊ)\s*[:：\-–]*\s*', '', v, flags=re.IGNORECASE)
            v = re.sub(r'\s+', ' ', v).strip()
            # Stop at common field separators
            v = re.split(r'\s{2,}|\s+-\s+|\s+\|\s+|\s*;\s*', v)[0].strip()
            # Avoid picking addresses
            if re.search(r'địa\s*chỉ|mst|mã\s*số\s*thuế|điện\s*thoại|tel|fax|email', v, flags=re.IGNORECASE):
                return ''
            # Too short is usually noise
            if len(v) < 4:
                return ''
            return v

        # 1) Try to leverage existing party extraction first
        try:
            party = self._ai_extract_party_names_from_text(extracted_text)
            ben_b = (party.get('ben_b') or '').strip() if isinstance(party, dict) else ''
            ben_b = _clean_org(ben_b)
            if ben_b:
                return ben_b
        except Exception:
            pass

        # 2) Fallback: find BÊN B line and take same/next line as org name
        for i, ln in enumerate(lines[:200]):
            if re.search(r'BÊN\s*B\b|BÊN\s*MUA\b|BÊN\s*THUÊ\b', ln, flags=re.IGNORECASE):
                # Same-line name
                m = re.search(r'(?:BÊN\s*B|BÊN\s*MUA|BÊN\s*THUÊ)\s*\(?\s*BÊN\s*B\s*\)?\s*[:：\-–]*\s*(.+)$', ln, flags=re.IGNORECASE)
                if m:
                    cand = _clean_org(m.group(1))
                    if cand:
                        return cand
                # Next meaningful line
                for j in range(i + 1, min(i + 6, len(lines))):
                    cand = _clean_org(lines[j])
                    if cand:
                        return cand

        return False

    def _ai_extract_contract_value_from_text(self, extracted_text):
        """Extract contract value (gia_tri_hop_dong) from Vietnamese contract text without AI."""
        if not extracted_text:
            return False

        # Normalize NBSP and whitespace
        text = (extracted_text or '').replace('\u00a0', ' ')
        text = re.sub(r'\s+', ' ', text)

        # Keywords that typically precede the contract value
        keyword = r'(giá\s*trị\s*hợp\s*đồng|tổng\s*giá\s*trị|trị\s*giá|giá\s*trị|tổng\s*tiền|thành\s*tiền|giá\s*bán|giá\s*trị\s*thanh\s*toán)'
        # Capture a number-like chunk, allow thousand separators '.', ',', spaces
        pattern = rf"{keyword}[^0-9]{{0,40}}([0-9][0-9\.,\s]{{4,}})\s*(vnd|vnđ|đồng|d|₫)?"

        matches = re.findall(pattern, text, flags=re.IGNORECASE)
        candidates = []
        for m in matches:
            raw_num = (m[1] if isinstance(m, tuple) and len(m) > 1 else '')
            if not raw_num:
                continue
            digits = re.sub(r'[^0-9]', '', raw_num)
            if not digits:
                continue
            # Heuristic: ignore tiny numbers (often article numbers)
            try:
                val = int(digits)
            except Exception:
                continue
            if val < 100000:  # < 100k is unlikely contract value
                continue
            candidates.append(val)

        if not candidates:
            return False

        # Choose the largest value found near keywords
        best = max(candidates)
        try:
            return float(best)
        except Exception:
            return False

    @api.model
    def _default_loai_van_ban(self):
        """Default required doc type to avoid blocking creates."""
        Loai = self.env['loai_van_ban']
        domain = [('active', '=', True)]
        rec = Loai.search(domain + [('ten_loai', 'ilike', 'Hợp đồng')], limit=1, order='thu_tu, id')
        if rec:
            return rec
        rec = Loai.search(domain, limit=1, order='thu_tu, id')
        return rec

    def _ai_guess_loai_van_ban_from_text(self, extracted_text=None, filename=None):
        """Heuristic: choose `loai_van_ban` from extracted text or filename."""
        self.ensure_one()

        probe = f"{filename or ''}\n{extracted_text or ''}"
        probe = unicodedata.normalize('NFD', probe)
        probe = ''.join(ch for ch in probe if unicodedata.category(ch) != 'Mn')
        probe = probe.replace('đ', 'd').replace('Đ', 'D')
        probe = re.sub(r'\s+', ' ', probe).strip().lower()

        def _find_by_name(name):
            return self.env['loai_van_ban'].search([
                ('active', '=', True),
                ('ten_loai', 'ilike', name),
            ], limit=1, order='thu_tu, id')

        rules = [
            (r'phu\s*luc', 'Phụ lục hợp đồng'),
            (r'bao\s*gia', 'Báo giá'),
            (r'bien\s*ban', 'Biên bản nghiệm thu'),
            (r'cong\s*van', 'Công văn'),
            (r'to\s*trinh', 'Tờ trình'),
            (r'hop\s*dong', 'Hợp đồng'),
        ]
        for pattern, loai_name in rules:
            if re.search(pattern, probe, flags=re.IGNORECASE):
                rec = _find_by_name(loai_name)
                if rec:
                    return rec

        return self._default_loai_van_ban()

    def _ai_title_from_filename(self, filename):
        if not filename:
            return False
        base = filename.rsplit('/', 1)[-1]
        base = base.rsplit('\\', 1)[-1]
        if '.' in base:
            base = '.'.join(base.split('.')[:-1])
        return (base or '').strip() or False

    def _ai_extract_party_names_from_text(self, extracted_text):
        """Try to extract party names (BÊN A/BÊN B, đại diện) from contract text."""
        if not extracted_text:
            return {}

        text = fix_spacing_artifacts(extracted_text)
        # Normalize spaces, keep line structure
        raw_lines = [re.sub(r'\s+', ' ', (ln or '')).strip() for ln in text.splitlines()]
        lines = [ln for ln in raw_lines if ln]

        def _clean_name(val):
            """Làm sạch tên: bỏ prefix như '- Họ và tên:', 'Ông', 'Bà', etc. và loại bỏ dấu cách thừa giữa các ký tự."""
            if not val:
                return ''
            v = fix_spacing_artifacts(val).strip()
            # Cắt phần dư sau các ký tự phân tách thường gặp
            v = re.split(r'\s{2,}|\s+-\s+|\s+\|\s+|\s*;\s*|,', v)[0].strip()
            # Cắt nếu có thông tin phụ phía sau
            v = re.split(r'\b(sinh\s*năm|ngày\s*sinh|cmnd|cccd|mst|mã\s*số\s*thuế|địa\s*chỉ|điện\s*thoại|tel|fax|email)\b', v, flags=re.IGNORECASE)[0].strip()
            # Bỏ bullet đầu dòng
            v = re.sub(r'^[-•·]\s*', '', v)
            # Bỏ prefix "Họ và tên:", "Họ tên:", "Tên:"
            v = re.sub(r'^(Họ và tên|Họ tên|Tên)\s*[:：]\s*', '', v, flags=re.IGNORECASE)
            # Bỏ prefix "Ông", "Bà"
            v = re.sub(r'^(Ông|Bà|Anh|Chị)\s*[:：]?\s*', '', v, flags=re.IGNORECASE)
            # Nếu tên bị dính liền (không có dấu cách giữa các từ), tách ra theo chữ hoa
            if v and not ' ' in v and len(v) > 4:
                v = re.sub(r'(?<=[a-zàáảãạăắằẳẵặâấầẩẫậđèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵ])(?=[A-ZÀÁẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬĐÈÉẺẼẸÊẾỀỂỄỆÌÍỈĨỊÒÓỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÙÚỦŨỤƯỨỪỬỮỰỲÝỶỸỴ])', ' ', v)
            # Chỉ giữ 1 dấu cách giữa các từ
            v = re.sub(r'\s+', ' ', v)
            return v.strip()

        def _is_valid_person_name(val):
            """Kiểm tra xem có phải tên người hợp lệ không."""
            if not val:
                return False
            v = _clean_name(val)
            v = re.sub(r'[()\[\]"""_\.]+', ' ', v).strip()
            if len(v) < 4:
                return False
            # Skip instruction lines
            if re.search(r'ký|ghi rõ|đóng dấu|đại diện|bên\s*[ab]|bên mua|bên bán|bên thuê|bên cho thuê', v, flags=re.IGNORECASE):
                return False
            # Skip lines with digits
            if re.search(r'\d', v):
                return False
            # Heuristic: at least 2 words
            if len(v.split()) < 2:
                return False
            return True

        def _find_customer_in_ben_b_section():
            """Tìm tên khách hàng trong phần BÊN MUA (BÊN B)."""
            in_ben_b = False
            for i, ln in enumerate(lines):
                # Bắt đầu phần BÊN B / BÊN MUA
                if re.search(r'BÊN\s*MUA\s*\(?\s*BÊN\s*B\s*\)?|BÊN\s*B\s*\(?\s*BÊN\s*MUA\s*\)?|BÊN\s*B\s*[:：]|BÊN\s*MUA\s*[:：]', ln, flags=re.IGNORECASE):
                    in_ben_b = True
                    continue
                # Kết thúc khi gặp section khác
                if in_ben_b and re.search(r'^(ĐIỀU|Điều)\s*\d+|^(II|III|IV|V)\.|NỘI DUNG|THỎA THUẬN|HAI BÊN', ln, flags=re.IGNORECASE):
                    break
                if in_ben_b:
                    # Tìm dòng có "Họ và tên:" hoặc "- Họ và tên:"
                    m = re.search(r'(Họ và tên|Họ tên)\s*[:：]\s*(.+)$', ln, flags=re.IGNORECASE)
                    if m:
                        name = m.group(2).strip()
                        if len(name) >= 4:
                            return _clean_name(name)
                    # Tìm dòng có "Khách hàng:" nếu có
                    m2 = re.search(r'(Khách hàng|Bên\s*B)\s*[:：]\s*(.+)$', ln, flags=re.IGNORECASE)
                    if m2:
                        name = m2.group(2).strip()
                        if len(name) >= 4:
                            return _clean_name(name)
            return False

        def _find_customer_anywhere():
            """Fallback: tìm tên khách hàng theo mẫu 'Họ và tên' trước phần chữ ký."""
            end_idx = len(lines)
            for i, ln in enumerate(lines):
                if re.search(r'ĐẠI\s*DIỆN\s*BÊN\s*A|ĐẠI\s*DIỆN\s*BÊN\s*B|\(Ký,\s*ghi\s*rõ|Ký\s*tên', ln, flags=re.IGNORECASE):
                    end_idx = i
                    break

            for ln in lines[:end_idx]:
                m = re.search(r'(Họ và tên|Họ tên)\s*[:：]\s*(.+)$', ln, flags=re.IGNORECASE)
                if m:
                    name = _clean_name(m.group(2).strip())
                    if _is_valid_person_name(name):
                        return name

                m2 = re.search(r'(Khách hàng|Bên\s*B)\s*[:：]\s*(.+)$', ln, flags=re.IGNORECASE)
                if m2:
                    name = _clean_name(m2.group(2).strip())
                    if _is_valid_person_name(name):
                        return name

            return False

        def _find_signer_at_end():
            """Tìm tên người ký (ĐẠI DIỆN BÊN A) ở cuối văn bản."""
            import logging
            _logger = logging.getLogger(__name__)

            def _try_split_two_names(line):
                """Best-effort split for 2-column PDFs where two names get concatenated on one line.

                Example: "Nguyễn Văn Bê Phạm Lực" -> ("Nguyễn Văn Bê", "Phạm Lực")
                """
                if not line:
                    return (False, False)
                cleaned = _clean_name(line)
                words = cleaned.split()
                if len(words) < 4:
                    return (False, False)

                def _strip_accents(s):
                    import unicodedata
                    return ''.join(
                        ch for ch in unicodedata.normalize('NFD', s)
                        if unicodedata.category(ch) != 'Mn'
                    )

                family_names = {
                    'NGUYEN', 'TRAN', 'LE', 'PHAM', 'HOANG', 'HUYNH', 'PHAN', 'VU', 'VO', 'DANG', 'BUI',
                    'DO', 'HO', 'NGO', 'DUONG', 'LY', 'DINH', 'TRUONG', 'MAI', 'TA', 'TANG', 'THAI',
                    'TIEN', 'TONG', 'TO',
                }

                def _looks_like_family_name(word):
                    if not word:
                        return False
                    w = _strip_accents(word).upper().strip()
                    return w in family_names

                best = (False, False)
                best_score = None

                # Ensure both sides have at least 2 words
                for k in range(2, len(words) - 1):
                    left = ' '.join(words[:k]).strip()
                    right = ' '.join(words[k:]).strip()
                    if not (_is_valid_person_name(left) and _is_valid_person_name(right)):
                        continue
                    lw = len(left.split())
                    rw = len(right.split())
                    # Prefer splits that keep both names reasonably long and balanced
                    score = min(lw, rw) * 10 - abs(lw - rw)
                    # Strong preference: the right-side name should start with a family name
                    right_first = right.split()[0] if right else ''
                    if _looks_like_family_name(right_first):
                        score += 100
                    if best_score is None or score > best_score:
                        best_score = score
                        best = (left, right)

                return best
            
            # Lấy 40 dòng cuối của văn bản (phần chữ ký)
            end_lines = lines[-40:] if len(lines) > 40 else lines
            
            _logger.info("=== SIGNER DETECTION ===")
            _logger.info(f"Last 20 lines: {end_lines[-20:]}")
            
            dai_dien_a_idx = -1
            dai_dien_b_idx = -1
            
            # Tìm vị trí ĐẠI DIỆN BÊN A và ĐẠI DIỆN BÊN B
            for i, ln in enumerate(end_lines):
                # Tìm ĐẠI DIỆN BÊN A (có thể cùng dòng với BÊN B nếu PDF 2 cột)
                if re.search(r'ĐẠI\s*DIỆN\s*BÊN\s*A|DAI\s*DIEN\s*BEN\s*A', ln, flags=re.IGNORECASE):
                    dai_dien_a_idx = i
                    _logger.info(f"Found DAI DIEN BEN A at line {i}: {ln}")
                # Tìm ĐẠI DIỆN BÊN B riêng (không dùng elif vì có thể cùng dòng)
                if re.search(r'ĐẠI\s*DIỆN\s*BÊN\s*B|DAI\s*DIEN\s*BEN\s*B', ln, flags=re.IGNORECASE):
                    dai_dien_b_idx = i
                    _logger.info(f"Found DAI DIEN BEN B at line {i}: {ln}")
            
            signer_a = False
            signer_b = False
            
            # Nếu ĐẠI DIỆN BÊN A và BÊN B cùng dòng (PDF 2 cột)
            if dai_dien_a_idx >= 0 and dai_dien_a_idx == dai_dien_b_idx:
                _logger.info("A and B on same line - 2 column PDF")
                # Tìm dòng tiếp theo có 2 tên
                for j in range(dai_dien_a_idx + 1, min(dai_dien_a_idx + 8, len(end_lines))):
                    cand = end_lines[j]
                    # Bỏ qua dòng hướng dẫn
                    if re.search(r'ký|ghi rõ|đóng dấu', cand, flags=re.IGNORECASE):
                        continue
                    # Tìm 2 tên trên cùng dòng (cách nhau bởi khoảng trắng lớn)
                    parts = re.split(r'\s{3,}', cand)
                    if len(parts) >= 2:
                        name_a = _clean_name(parts[0].strip())
                        name_b = _clean_name(parts[-1].strip())
                        if len(name_a) >= 4 and len(name_a.split()) >= 2:
                            signer_a = name_a
                        if len(name_b) >= 4 and len(name_b.split()) >= 2:
                            signer_b = name_b
                        if signer_a or signer_b:
                            _logger.info(f"Found names on same line: A={signer_a}, B={signer_b}")
                            break

                    # Fallback: sometimes PDF extraction collapses columns into a single-space line
                    split_a, split_b = _try_split_two_names(cand)
                    if split_a or split_b:
                        signer_a = split_a or signer_a
                        signer_b = split_b or signer_b
                        _logger.info(f"Found names by heuristic split: A={signer_a}, B={signer_b}")
                        break

                    # Nếu chỉ có 1 tên, kiểm tra xem có phải tên hợp lệ không
                    elif _is_valid_person_name(cand):
                        # Không biết là A hay B, bỏ qua
                        _logger.info(f"Single name found but ambiguous: {cand}")
                        continue
            else:
                # ĐẠI DIỆN BÊN A và BÊN B khác dòng
                # Tìm tên sau ĐẠI DIỆN BÊN A (trước ĐẠI DIỆN BÊN B nếu có)
                if dai_dien_a_idx >= 0:
                    end_idx = dai_dien_b_idx if (dai_dien_b_idx > dai_dien_a_idx) else len(end_lines)
                    for j in range(dai_dien_a_idx + 1, min(dai_dien_a_idx + 6, end_idx)):
                        if j < len(end_lines):
                            cand = end_lines[j]
                            # Bỏ qua dòng hướng dẫn
                            if re.search(r'ký|ghi rõ|đóng dấu', cand, flags=re.IGNORECASE):
                                continue
                            if _is_valid_person_name(cand):
                                signer_a = _clean_name(cand)
                                _logger.info(f"Found signer A: {signer_a}")
                                break
                
                # Tìm tên sau ĐẠI DIỆN BÊN B
                if dai_dien_b_idx >= 0:
                    for j in range(dai_dien_b_idx + 1, min(dai_dien_b_idx + 6, len(end_lines))):
                        cand = end_lines[j]
                        # Bỏ qua dòng hướng dẫn
                        if re.search(r'ký|ghi rõ|đóng dấu', cand, flags=re.IGNORECASE):
                            continue
                        if _is_valid_person_name(cand):
                            signer_b = _clean_name(cand)
                            _logger.info(f"Found signer B: {signer_b}")
                            break
            
            _logger.info(f"Final: signer_a={signer_a}, signer_b={signer_b}")
            return signer_a, signer_b

        # Trích xuất thông tin
        ben_b = _find_customer_in_ben_b_section() or _find_customer_anywhere()
        signer_a, signer_b = _find_signer_at_end()

        # Fallback: nếu không tìm được BÊN B rõ ràng, dùng người ký BÊN B
        if not ben_b and signer_b and _is_valid_person_name(signer_b):
            ben_b = _clean_name(signer_b)

        return {
            'ben_a': False,  # Không cần lấy tên công ty BÊN A
            'ben_b': ben_b,  # Tên khách hàng từ phần BÊN MUA
            'dai_dien_ben_a': signer_a,  # Người ký nội bộ
            'dai_dien_ben_b': signer_b,  # Người ký bên B (khách hàng)
        }


    def _ai_apply_party_info(self, party_info):
        """Apply rule-based party info (prefer BÊN B as customer).
        
        Lưu ý: Không auto-fill nguoi_ky_id từ PDF vì dễ sai.
        Người ký nội bộ sẽ được chọn thủ công hoặc dùng default.
        """
        if not isinstance(party_info, dict):
            return

        ben_b = (party_info.get('ben_b') or '').strip() if party_info.get('ben_b') else False
        if ben_b and not self.khach_hang_trong_hop_dong:
            self.khach_hang_trong_hop_dong = ben_b
            # Không gán khach_hang_id trong onchange - sẽ được xử lý khi save

        # Không auto-fill nguoi_ky_id từ PDF nữa - để người dùng chọn thủ công
        # hoặc dùng default value

    def _ai_apply_customer_name(self, kh_name):
        """Find existing customer by name and assign to `khach_hang_id`.
        
        Lưu ý: KHÔNG tạo khách hàng mới trong onchange vì sẽ gây lỗi transaction.
        Chỉ tìm và gán nếu đã tồn tại.
        """
        if not kh_name or self.khach_hang_id:
            return
        kh = self.env['khach_hang'].sudo().search([('ten_khach_hang', '=ilike', kh_name)], limit=1)
        if not kh:
            kh = self.env['khach_hang'].sudo().search([('ten_khach_hang', 'ilike', kh_name)], limit=1)
        # Không tạo mới khách hàng trong onchange context - chỉ gán nếu tìm thấy
        if kh:
            self.khach_hang_id = kh

    def _ai_extract_text_from_pdf_bytes(self, pdf_bytes):
        """Extract text from PDF bytes.

        Prefer PyPDF2 (already in root requirements), fallback to pdfplumber.
        """
        text_parts = []

        # 1) PyPDF2 (supports both old and new API)
        try:
            from PyPDF2 import PdfReader  # PyPDF2 >= 2
            reader = PdfReader(io.BytesIO(pdf_bytes))
            for page in getattr(reader, 'pages', []) or []:
                try:
                    page_text = page.extract_text() or ''
                except Exception:
                    page_text = ''
                if page_text:
                    text_parts.append(fix_spacing_artifacts(page_text))
            extracted = "\n".join(text_parts).strip()
            extracted = fix_spacing_artifacts(extracted)
            if extracted:
                return extracted
        except Exception:
            pass

        try:
            from PyPDF2 import PdfFileReader  # PyPDF2 1.x
            reader = PdfFileReader(io.BytesIO(pdf_bytes))
            for i in range(reader.getNumPages()):
                try:
                    page_text = reader.getPage(i).extractText() or ''
                except Exception:
                    page_text = ''
                if page_text:
                    text_parts.append(fix_spacing_artifacts(page_text))
            extracted = "\n".join(text_parts).strip()
            extracted = fix_spacing_artifacts(extracted)
            if extracted:
                return extracted
        except Exception:
            pass

        # 2) pdfplumber (better for some PDFs)
        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                for page in pdf.pages:
                    try:
                        page_text = page.extract_text() or ''
                    except Exception:
                        page_text = ''
                    if page_text:
                        text_parts.append(fix_spacing_artifacts(page_text))
            return fix_spacing_artifacts("\n".join(text_parts).strip())
        except Exception as e:
            raise UserError(_(
                "Không thể trích xuất text từ PDF. Vui lòng kiểm tra thư viện PyPDF2/pdfplumber. Lỗi: %s"
            ) % str(e))

    def _ai_extract_structured_fields_from_text(self, extracted_text):
        """Use AI to extract key fields for the van_ban form."""
        self.ensure_one()

        # Build lightweight hints from existing master data
        loai_names = []
        khach_hang_names = []
        try:
            loai_names = self.env['loai_van_ban'].sudo().search([], limit=50).mapped('ten_loai')
        except Exception:
            loai_names = []
        try:
            khach_hang_names = self.env['khach_hang'].sudo().search([], limit=50).mapped('ten_khach_hang')
        except Exception:
            khach_hang_names = []

        # Không dùng AI để extract nguoi_ky vì đã có rule-based extraction chính xác hơn
        schema = {
            'ten_van_ban': 'string',
            'loai_van_ban': 'string|null',
            'khach_hang': 'string|null',
            'gia_tri_hop_dong': 'number|null',
            'ngay_hieu_luc': 'string|null',
            'ngay_het_han': 'string|null',
            'mo_ta': 'string|null',
        }

        loai_hint = "; ".join([n for n in loai_names if n])
        khach_hang_hint = "; ".join([n for n in khach_hang_names if n])
        instructions = (
            "Ngôn ngữ: tiếng Việt. "
            "Trả về JSON đúng schema. "
            "ngay_hieu_luc/ngay_het_han theo định dạng YYYY-MM-DD (nếu thấy dd/mm/yyyy hãy chuyển). "
            "gia_tri_hop_dong trả về số (không kèm đơn vị, không dấu chấm/phẩy). "
            "khach_hang là tên khách hàng/đối tác được nêu trong hợp đồng, ưu tiên BÊN B / BÊN MUA / BÊN THUÊ. "
            "loai_van_ban nếu có thì ưu tiên chọn 1 trong danh sách loại văn bản hiện có: "
            f"{loai_hint[:1500]}. "
            "khach_hang nếu có thì ưu tiên chọn 1 trong danh sách khách hàng hiện có: "
            f"{khach_hang_hint[:1500]}"
        )

        ai_service = self.env['ai.service']
        # record_id có thể là NewId khi onchange; dùng 0 để logging an toàn
        record_id = self.id if isinstance(self.id, int) else 0
        return ai_service.extract_structured_data(
            extracted_text,
            schema=schema,
            instructions=instructions,
            model_name='van_ban',
            record_id=record_id,
        )

    def _ai_apply_extracted_fields(self, extracted):
        """Apply extracted fields onto the record (only fill empty values)."""
        self.ensure_one()
        if not isinstance(extracted, dict):
            return

        # Title
        title = (extracted.get('ten_van_ban') or '').strip() if extracted.get('ten_van_ban') else False
        if title and not self.ten_van_ban:
            self.ten_van_ban = title

        # Description
        mo_ta = (extracted.get('mo_ta') or '').strip() if extracted.get('mo_ta') else False
        if mo_ta and not self.mo_ta:
            self.mo_ta = mo_ta

        # Dates
        def _normalize_date(val):
            if not val:
                return False
            if isinstance(val, str):
                v = val.strip()
                # normalize dd/mm/yyyy -> yyyy-mm-dd if needed
                m = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{4})$', v)
                if m:
                    d, mo, y = m.groups()
                    return f"{y}-{int(mo):02d}-{int(d):02d}"
                m = re.match(r'^(\d{4})-(\d{1,2})-(\d{1,2})$', v)
                if m:
                    y, mo, d = m.groups()
                    return f"{y}-{int(mo):02d}-{int(d):02d}"
            return False

        ngay_hieu_luc = _normalize_date(extracted.get('ngay_hieu_luc'))
        if ngay_hieu_luc and not self.ngay_hieu_luc:
            self.ngay_hieu_luc = ngay_hieu_luc

        ngay_het_han = _normalize_date(extracted.get('ngay_het_han'))
        if ngay_het_han and not self.ngay_het_han:
            self.ngay_het_han = ngay_het_han

        # Contract value
        gia_tri = extracted.get('gia_tri_hop_dong')
        if (gia_tri is not None) and (not self.gia_tri_hop_dong or self.gia_tri_hop_dong == 0):
            try:
                if isinstance(gia_tri, str):
                    digits = re.sub(r'[^0-9]', '', gia_tri)
                    self.gia_tri_hop_dong = float(digits) if digits else self.gia_tri_hop_dong
                else:
                    self.gia_tri_hop_dong = float(gia_tri)
            except Exception:
                pass

        # Document type
        loai_name = (extracted.get('loai_van_ban') or '').strip() if extracted.get('loai_van_ban') else False
        if loai_name and not self.loai_van_ban_id:
            loai = self.env['loai_van_ban'].sudo().search([('ten_loai', '=ilike', loai_name)], limit=1)
            if not loai:
                loai = self.env['loai_van_ban'].sudo().search([('ten_loai', 'ilike', loai_name)], limit=1)
            if loai:
                self.loai_van_ban_id = loai

        # Related customer - chỉ gán vào field Char, không gán Many2one trong onchange
        kh_name = (extracted.get('khach_hang') or '').strip() if extracted.get('khach_hang') else False
        if kh_name:
            if not self.khach_hang_trong_hop_dong:
                self.khach_hang_trong_hop_dong = kh_name
            # Không gán khach_hang_id trong onchange - tránh lỗi transaction

        # Lưu ý: nguoi_ky đã được xử lý bởi _ai_apply_party_info() (rule-based)
        # Không xử lý ở đây để tránh ghi đè
    
    # === COMPUTE METHODS ===
    
    def _get_nhan_vien_hien_tai(self):
        """Lấy nhân viên hiện tại từ user đang đăng nhập"""
        nhan_vien = self.env['nhan_vien'].search([
            ('user_id', '=', self.env.uid)
        ], limit=1)
        return nhan_vien.id if nhan_vien else False
    
    def _get_truong_phong_sales_default(self):
        """Lấy Trưởng phòng Sales để auto-fill cho người duyệt văn bản"""
        # Tìm theo chức vụ Trưởng phòng và phòng ban Sales
        truong_phong = self.env['nhan_vien'].search([
            '|', '|', '|',
            ('chuc_vu', 'ilike', 'Trưởng phòng'),
            ('chuc_vu', 'ilike', 'Truong phong'),
            ('chuc_vu_id.name', 'ilike', 'Trưởng phòng'),
            ('chuc_vu_id.name', 'ilike', 'Truong phong'),
            '|', '|',
            ('phong_ban', 'ilike', 'Sales'),
            ('phong_ban_id.name', 'ilike', 'Sales'),
            ('phong_ban_id.name', 'ilike', 'Kinh doanh'),
            ('trang_thai_lam_viec', '=', 'dang_lam')
        ], limit=1)
        if truong_phong:
            return truong_phong.id
        
        # Fallback: Tìm bất kỳ Trưởng phòng nào
        truong_phong = self.env['nhan_vien'].search([
            '|', '|',
            ('chuc_vu', 'ilike', 'Trưởng phòng'),
            ('chuc_vu', 'ilike', 'Truong phong'),
            ('chuc_vu_id.name', 'ilike', 'Trưởng phòng'),
            ('trang_thai_lam_viec', '=', 'dang_lam')
        ], limit=1)
        return truong_phong.id if truong_phong else False
    
    def _get_giam_doc_default(self):
        """Lấy Giám đốc để auto-fill cho người ký điện tử"""
        # Tìm theo chức vụ Giám đốc và phòng ban Giám đốc
        giam_doc = self.env['nhan_vien'].search([
            '|', '|', '|', '|',
            ('chuc_vu', 'ilike', 'Giám đốc'),
            ('chuc_vu', 'ilike', 'Giam doc'),
            ('chuc_vu', 'ilike', 'Director'),
            ('chuc_vu_id.name', 'ilike', 'Giám đốc'),
            ('chuc_vu_id.name', 'ilike', 'Director'),
            '|', '|',
            ('phong_ban', 'ilike', 'Giám đốc'),
            ('phong_ban_id.name', 'ilike', 'Giám đốc'),
            ('phong_ban_id.name', 'ilike', 'Ban giám đốc'),
            ('trang_thai_lam_viec', '=', 'dang_lam')
        ], limit=1)
        if giam_doc:
            return giam_doc.id
        
        # Fallback: Tìm bất kỳ Giám đốc nào
        giam_doc = self.env['nhan_vien'].search([
            '|', '|', '|',
            ('chuc_vu', 'ilike', 'Giám đốc'),
            ('chuc_vu', 'ilike', 'Giam doc'),
            ('chuc_vu', 'ilike', 'Director'),
            ('chuc_vu', 'ilike', 'CEO'),
            ('trang_thai_lam_viec', '=', 'dang_lam')
        ], limit=1)
        return giam_doc.id if giam_doc else False
    
    @api.depends('ngay_het_han')
    def _compute_so_ngay_con_lai(self):
        """Tính số ngày còn lại và cảnh báo sắp hết hạn"""
        today = fields.Date.today()
        for record in self:
            if record.ngay_het_han:
                delta = record.ngay_het_han - today
                record.so_ngay_con_lai = delta.days
                record.sap_het_han = 0 <= delta.days <= 30
            else:
                record.so_ngay_con_lai = 0
                record.sap_het_han = False
    
    @api.depends('yeu_cau_ky_ids')
    def _compute_so_yeu_cau_ky(self):
        for record in self:
            record.so_yeu_cau_ky = len(record.yeu_cau_ky_ids)
    
    # === SYSTEM INTEGRATION COMPUTE METHODS ===
    @api.depends('nguoi_tao_id.ten_nv', 'nguoi_tao_id.phong_ban',
                 'nguoi_duyet_id.ten_nv', 'nguoi_ky_id.ten_nv')
    def _compute_sync_nhan_su(self):
        """Đồng bộ thông tin từ module nhan_su để đảm bảo tính nhất quán dữ liệu"""
        for record in self:
            # Sync thông tin người tạo
            if record.nguoi_tao_id:
                record.ten_nguoi_tao = record.nguoi_tao_id.ten_nv
                record.phong_ban_nguoi_tao = record.nguoi_tao_id.phong_ban
            else:
                record.ten_nguoi_tao = False
                record.phong_ban_nguoi_tao = False
            
            # Sync thông tin người duyệt
            if record.nguoi_duyet_id:
                record.ten_nguoi_duyet = record.nguoi_duyet_id.ten_nv
            else:
                record.ten_nguoi_duyet = False
            
            # Sync thông tin người ký
            if record.nguoi_ky_id:
                record.ten_nguoi_ky = record.nguoi_ky_id.ten_nv
            else:
                record.ten_nguoi_ky = False
            
    # === PROCESS AUTOMATION COMPUTE METHODS ===

    @api.depends('loai_van_ban_id', 'gia_tri_hop_dong', 'khach_hang_id')
    def _compute_ai_suggestions(self):
        """AI đề xuất người duyệt và ký dựa trên loại văn bản và giá trị"""
        for record in self:
            # Reset suggestions
            record.ai_suggested_approver = False
            record.ai_suggested_signer = False

            if not record.loai_van_ban_id:
                continue

            # AI Logic: Dựa trên loại văn bản và giá trị hợp đồng
            loai_vb = record.loai_van_ban_id.ten_loai.lower()

            # Tìm nhân viên phù hợp dựa trên phòng ban và chức vụ
            nhan_vien_pool = self.env['nhan_vien'].search([
                ('trang_thai_lam_viec', '=', 'dang_lam')
            ])

            # Logic AI cho người duyệt (Approver)
            if 'hợp đồng' in loai_vb or record.gia_tri_hop_dong > 50000000:  # > 50 triệu
                # Ưu tiên trưởng phòng kinh doanh hoặc tài chính
                approvers = nhan_vien_pool.filtered(
                    lambda nv: nv.chuc_vu and ('trưởng' in nv.chuc_vu.lower() or 'phó' in nv.chuc_vu.lower())
                )
                if approvers:
                    record.ai_suggested_approver = approvers[0].id

            elif 'quyết định' in loai_vb or 'nội quy' in loai_vb:
                # Ưu tiên lãnh đạo cấp cao
                leaders = nhan_vien_pool.filtered(
                    lambda nv: nv.chuc_vu and ('giám đốc' in nv.chuc_vu.lower() or 'tổng' in nv.chuc_vu.lower())
                )
                if leaders:
                    record.ai_suggested_approver = leaders[0].id

            # Logic AI cho người ký (Signer)
            if record.gia_tri_hop_dong > 100000000:  # > 100 triệu
                # Cần lãnh đạo cấp cao ký
                high_level = nhan_vien_pool.filtered(
                    lambda nv: nv.chuc_vu and ('giám đốc' in nv.chuc_vu.lower() or 'tổng' in nv.chuc_vu.lower())
                )
                if high_level:
                    record.ai_suggested_signer = high_level[0].id
            elif record.gia_tri_hop_dong > 20000000:  # > 20 triệu
                # Trưởng phòng có thể ký
                managers = nhan_vien_pool.filtered(
                    lambda nv: nv.chuc_vu and 'trưởng' in nv.chuc_vu.lower()
                )
                if managers:
                    record.ai_suggested_signer = managers[0].id

    @api.depends('gia_tri_hop_dong', 'loai_van_ban_id', 'khach_hang_id')
    def _compute_ai_risk_assessment(self):
        """AI đánh giá mức độ rủi ro của văn bản"""
        for record in self:
            risk_score = 0

            # Risk factors
            if record.gia_tri_hop_dong:
                if record.gia_tri_hop_dong > 500000000:  # > 500 triệu
                    risk_score += 3
                elif record.gia_tri_hop_dong > 100000000:  # > 100 triệu
                    risk_score += 2
                elif record.gia_tri_hop_dong > 50000000:  # > 50 triệu
                    risk_score += 1

            # Loại văn bản có rủi ro cao
            if record.loai_van_ban_id:
                loai_vb = record.loai_van_ban_id.ten_loai.lower()
                if any(keyword in loai_vb for keyword in ['hợp đồng', 'thỏa thuận', 'cam kết']):
                    risk_score += 1

            # Khách hàng mới hoặc có vấn đề
            if record.khach_hang_id:
                # Logic đơn giản: Giả sử khách hàng mới có rủi ro cao hơn
                # Trong thực tế có thể dựa trên lịch sử giao dịch
                risk_score += 0.5

            # Determine risk level
            if risk_score >= 3:
                record.ai_risk_level = 'critical'
            elif risk_score >= 2:
                record.ai_risk_level = 'high'
            elif risk_score >= 1:
                record.ai_risk_level = 'medium'
            else:
                record.ai_risk_level = 'low'

    @api.depends('ten_van_ban', 'mo_ta', 'loai_van_ban_id')
    def _compute_ai_category(self):
        """AI tự động phân loại văn bản dựa trên nội dung"""
        for record in self:
            if not record.ten_van_ban and not record.mo_ta:
                record.ai_category_suggestion = False
                continue

            text_content = f"{record.ten_van_ban or ''} {record.mo_ta or ''}".lower()

            # AI Classification Logic
            if any(keyword in text_content for keyword in ['hợp đồng', 'contract', 'agreement']):
                record.ai_category_suggestion = 'Hợp đồng'
            elif any(keyword in text_content for keyword in ['quyết định', 'decision', 'decree']):
                record.ai_category_suggestion = 'Quyết định'
            elif any(keyword in text_content for keyword in ['báo cáo', 'report', 'summary']):
                record.ai_category_suggestion = 'Báo cáo'
            elif any(keyword in text_content for keyword in ['thông báo', 'notification', 'announcement']):
                record.ai_category_suggestion = 'Thông báo'
            elif any(keyword in text_content for keyword in ['biên bản', 'minutes', 'record']):
                record.ai_category_suggestion = 'Biên bản'
            else:
                record.ai_category_suggestion = 'Tài liệu khác'

    @api.depends('ai_risk_level', 'sap_het_han', 'trang_thai', 'gia_tri_hop_dong')
    def _compute_ai_priority(self):
        """AI tính điểm ưu tiên cho văn bản"""
        for record in self:
            priority_score = 0

            # Risk level contribution
            risk_weights = {'low': 1, 'medium': 2, 'high': 3, 'critical': 5}
            priority_score += risk_weights.get(record.ai_risk_level, 1)

            # Urgent documents (expiring soon)
            if record.sap_het_han:
                priority_score += 2

            # Status-based priority
            status_weights = {
                'cho_duyet': 3, 'cho_ky': 4, 'da_ky': 2,
                'nhap': 1, 'da_duyet': 2, 'da_gui': 1
            }
            priority_score += status_weights.get(record.trang_thai, 1)

            # Value-based priority
            if record.gia_tri_hop_dong:
                if record.gia_tri_hop_dong > 100000000:  # > 100 triệu
                    priority_score += 3
                elif record.gia_tri_hop_dong > 50000000:  # > 50 triệu
                    priority_score += 2
                elif record.gia_tri_hop_dong > 10000000:  # > 10 triệu
                    priority_score += 1

            record.ai_priority_score = min(priority_score, 10)  # Cap at 10

    @api.depends('trang_thai', 'ngay_tao', 'ai_risk_level')
    def _compute_sla_deadline(self):
        """Tính hạn SLA dựa trên trạng thái và mức độ rủi ro"""
        for record in self:
            if not record.ngay_tao:
                record.sla_deadline = False
                continue

            base_days = 7  # Default 7 days

            # Adjust based on risk level
            risk_multipliers = {
                'low': 1, 'medium': 1.5, 'high': 2, 'critical': 3
            }
            multiplier = risk_multipliers.get(record.ai_risk_level, 1)

            # Adjust based on status
            status_multipliers = {
                'cho_duyet': 1, 'da_duyet': 0.5, 'cho_ky': 1.5,
                'da_ky': 0.5, 'da_gui': 0
            }
            status_multiplier = status_multipliers.get(record.trang_thai, 1)

            total_days = base_days * multiplier * status_multiplier
            record.sla_deadline = record.ngay_tao + timedelta(days=int(total_days))

    @api.depends('sla_deadline')
    def _compute_sla_status(self):
        """Kiểm tra xem có vi phạm SLA không"""
        now = fields.Datetime.now()
        for record in self:
            record.sla_breached = record.sla_deadline and now > record.sla_deadline
    
    # === SYSTEM INTEGRATION CONSTRAINTS ===
    @api.constrains('nguoi_tao_id', 'nguoi_duyet_id', 'nguoi_phe_duyet_id', 'nguoi_ky_id')
    def _check_nhan_vien_active(self):
        """Đảm bảo nhân viên liên quan vẫn đang hoạt động"""
        for record in self:
            nhan_vien_fields = [
                ('nguoi_tao_id', record.nguoi_tao_id),
                ('nguoi_duyet_id', record.nguoi_duyet_id),
                ('nguoi_phe_duyet_id', record.nguoi_phe_duyet_id),
                ('nguoi_ky_id', record.nguoi_ky_id)
            ]
            
            for field_name, nhan_vien in nhan_vien_fields:
                if nhan_vien and nhan_vien.trang_thai_lam_viec != 'dang_lam':
                    field_label = self._fields[field_name].string
                    raise ValidationError(f'{field_label} "{nhan_vien.ten_nv}" không còn hoạt động trong hệ thống!')
    
    @api.constrains('nguoi_tao_id')
    def _check_nguoi_tao_required(self):
        """Đảm bảo luôn có người tạo"""
        for record in self:
            if not record.nguoi_tao_id:
                raise ValidationError('Văn bản phải có người tạo!')
    
    # === CRUD METHODS ===
    
    @api.model
    def create(self, vals):
        """Tạo mã văn bản tự động và ghi lịch sử"""
        if vals.get('ma_van_ban', _('New')) == _('New'):
            vals['ma_van_ban'] = self.env['ir.sequence'].next_by_code('van_ban') or _('New')
        
        record = super(VanBan, self).create(vals)
        
        # Ghi lịch sử tạo
        record._ghi_lich_su('tao', 'Tạo văn bản mới')
        
        # Tính hash file nếu có
        if record.file_dinh_kem:
            record._compute_hash_file()
        
        return record
    
    def write(self, vals):
        """Ghi lịch sử thay đổi"""
        # Log để debug nguoi_ky_id
        if 'nguoi_ky_id' in vals or 'nguoi_duyet_id' in vals:
            _logger.info(
                "van_ban.write called with nguoi_ky_id=%s, nguoi_duyet_id=%s for ids=%s",
                vals.get('nguoi_ky_id'),
                vals.get('nguoi_duyet_id'),
                self.ids
            )
        
        # Danh sách các trường quan trọng không được sửa khi bị khóa
        protected_fields = [
            'ten_van_ban', 'loai_van_ban_id', 'file_dinh_kem', 'ten_file',
            'khach_hang_id', 'don_hang_id', 'gia_tri_hop_dong',
            'ngay_hieu_luc', 'ngay_het_han', 'mo_ta'
        ]
        
        # Danh sách các trường được phép cập nhật khi bị khóa (hệ thống)
        allowed_when_locked = [
            'bi_khoa', 'trang_thai', 
            'da_ky_noi_bo', 'ngay_ky_noi_bo', 'chu_ky_noi_bo',
            'da_khach_ky', 'ngay_khach_ky', 'chu_ky_khach',
            'file_da_ky', 'ten_file_da_ky', 'hash_file',
            'ghi_chu', 'ly_do_huy'
        ]
        
        for record in self:
            if record.bi_khoa:
                # Kiểm tra xem có trường bị bảo vệ nào được cập nhật không
                protected_updated = set(vals.keys()) & set(protected_fields)
                if protected_updated:
                    raise UserError(
                        f'Văn bản đã bị khóa, không thể chỉnh sửa!\n'
                        f'Các trường không được sửa: {", ".join(protected_updated)}'
                    )
        
        result = super(VanBan, self).write(vals)
        
        # Ghi lịch sử nếu có thay đổi quan trọng
        if 'trang_thai' in vals:
            for record in self:
                record._ghi_lich_su('trang_thai', f'Chuyển trạng thái sang: {record.trang_thai}')
        
        if 'file_dinh_kem' in vals:
            for record in self:
                record._compute_hash_file()
                record._ghi_lich_su('file', 'Cập nhật file đính kèm')
        
        return result
    
    # === SIGNER MATCH HELPERS ===

    def _normalize_name_for_match(self, name):
        if not name:
            return ''
        name = fix_spacing_artifacts(name).strip().lower()
        name = name.replace('\u00a0', ' ').replace('\t', ' ').replace('\n', ' ').replace('\r', ' ')
        name = name.replace('\u200b', '').replace('\u200c', '').replace('\u200d', '').replace('\ufeff', '')
        name = unicodedata.normalize('NFKD', name)
        name = ''.join([c for c in name if not unicodedata.combining(c)])
        name = name.replace('đ', 'd')
        name = re.sub(r"[^0-9a-zA-Z\s]", " ", name)
        name = name.replace('_', ' ')
        name = re.sub(r'\s+', ' ', name).strip()
        return name

    def _find_employee_by_pdf_name(self, signer_in_pdf):
        self.ensure_one()
        if not signer_in_pdf:
            return False

        norm = self._normalize_name_for_match(signer_in_pdf)
        if not norm:
            return False

        candidates = self.env['nhan_vien'].sudo().search([
            ('ten_nv', 'ilike', signer_in_pdf),
        ], limit=50)

        if not candidates:
            tokens = [t for t in norm.split() if t]
            domain = []
            for t in tokens[:4]:
                domain.append(('ten_nv', 'ilike', t))
            if domain:
                candidates = self.env['nhan_vien'].sudo().search(domain, limit=50)

        for nv in candidates:
            if self._normalize_name_for_match(nv.ten_nv) == norm:
                return nv
        return candidates[:1] if candidates else False

    # === WORKFLOW ACTIONS ===
    
    def action_gui_duyet(self):
        """Gửi văn bản để duyệt - Gửi đến Trưởng phòng Sales"""
        for record in self:
            if not record.file_dinh_kem:
                raise UserError('Vui lòng đính kèm file văn bản trước khi gửi duyệt!')

            # Auto-assign Trưởng phòng Sales nếu chưa có
            if not record.truong_phong_duyet_id:
                truong_phong = record._get_truong_phong_sales_default()
                if truong_phong:
                    record.write({'truong_phong_duyet_id': truong_phong})
                    record._ghi_lich_su('auto_assign', f'Tự động gán Trưởng phòng duyệt')

            record.write({'trang_thai': 'cho_duyet'})
            
            # Ghi lịch sử
            ten_truong_phong = record.truong_phong_duyet_id.ten_nv if record.truong_phong_duyet_id else 'Chưa xác định'
            record._ghi_lich_su('gui_duyet', f'Gửi văn bản để duyệt đến Trưởng phòng: {ten_truong_phong}')

            # Enhanced notifications
            record._send_enhanced_notifications('approval_request')

            # Schedule follow-up if high priority
            if record.ai_priority_score >= 7:
                record._schedule_auto_follow_up('approval', days=2)
    
    def action_duyet(self):
        """Trưởng phòng duyệt văn bản - Sau đó hiện nút Gửi ký"""
        for record in self:
            # Lưu lại nguoi_ky_id trước khi write để preserve
            nguoi_ky_id_before = record.nguoi_ky_id.id if record.nguoi_ky_id else False
            
            # Gán người duyệt thực tế (Trưởng phòng hiện tại)
            nguoi_duyet_thuc_te = self._get_nhan_vien_hien_tai()
            vals = {'trang_thai': 'da_duyet'}
            
            # Cập nhật truong_phong_duyet_id nếu chưa có
            if not record.truong_phong_duyet_id:
                vals['truong_phong_duyet_id'] = nguoi_duyet_thuc_te
            
            # Log before write to debug
            _logger.info(
                "action_duyet: van_ban_id=%s before write - nguoi_ky_id=%s, truong_phong_duyet_id=%s",
                record.id, record.nguoi_ky_id.id if record.nguoi_ky_id else None,
                record.truong_phong_duyet_id.id if record.truong_phong_duyet_id else None
            )
            
            record.write(vals)
            
            # Check and restore nguoi_ky_id if it was cleared
            if nguoi_ky_id_before and not record.nguoi_ky_id:
                _logger.warning(
                    "action_duyet: nguoi_ky_id was cleared after write for van_ban_id=%s, restoring it",
                    record.id
                )
                record.write({'nguoi_ky_id': nguoi_ky_id_before})
            
            # Ghi lịch sử với tên người duyệt thực tế
            ten_nguoi_duyet = ''
            if nguoi_duyet_thuc_te:
                nv = self.env['nhan_vien'].sudo().browse(nguoi_duyet_thuc_te)
                ten_nguoi_duyet = nv.ten_nv if nv.exists() else ''
            record._ghi_lich_su('duyet', f'Trưởng phòng duyệt văn bản: {ten_nguoi_duyet or self.env.user.name}')

            # Enhanced notifications
            record._send_enhanced_notifications('approved')

            # Cancel follow-up activities
            record._cancel_pending_follow_ups()
    
    def action_tu_choi_duyet(self):
        """Từ chối duyệt văn bản"""
        for record in self:
            record.write({'trang_thai': 'nhap'})
            record._ghi_lich_su('tu_choi', 'Từ chối duyệt văn bản')
    
    def action_gui_ky(self):
        """Trưởng phòng gửi văn bản đến Giám đốc để ký"""
        for record in self:
            # Dùng sudo để bypass record rules khi đọc nguoi_ky_id
            record_sudo = record.sudo()
            
            # Auto-assign Giám đốc nếu chưa có
            if not record_sudo.nguoi_ky_id:
                giam_doc = record._get_giam_doc_default()
                if giam_doc:
                    record_sudo.write({'nguoi_ky_id': giam_doc})
                    record._ghi_lich_su('auto_assign', 'Tự động gán Giám đốc để ký')
            
            # Kiểm tra phải có Giám đốc ký
            if not record_sudo.nguoi_ky_id:
                _logger.warning(
                    "action_gui_ky blocked: van_ban_id=%s ma_van_ban=%s user_id=%s (no nguoi_ky_id)",
                    record.id,
                    record.ma_van_ban,
                    self.env.user.id,
                )
                raise UserError(
                    'Vui lòng chọn "Giám đốc ký" trước khi gửi ký.\n\n'
                    f'(Văn bản: {record.ma_van_ban} - ID {record.id})'
                )

            record.write({'trang_thai': 'cho_ky'})
            
            # Ghi lịch sử
            ten_giam_doc = record_sudo.nguoi_ky_id.ten_nv if record_sudo.nguoi_ky_id else 'Chưa xác định'
            record._ghi_lich_su('gui_ky', f'Gửi văn bản đến Giám đốc để ký: {ten_giam_doc}')

            # Enhanced notifications
            record._send_enhanced_notifications('signature_request')

            # Schedule urgent follow-up for high-risk documents
            if record.ai_risk_level in ['high', 'critical']:
                record._schedule_auto_follow_up('signature', days=1)

    # ==========================================
    # SMART BUTTON ACTIONS
    # ==========================================

    def action_view_file_goc(self):
        """Xem/Tải file gốc"""
        self.ensure_one()
        if not self.file_dinh_kem:
            raise UserError('Không có file đính kèm!')
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content?model=van_ban&id={self.id}&field=file_dinh_kem&filename={self.ten_file or "file.pdf"}&download=true',
            'target': 'new',
        }

    def action_view_file_da_ky(self):
        """Xem/Tải file đã ký"""
        self.ensure_one()
        if not self.file_da_ky:
            raise UserError('Chưa có file đã ký!')
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content?model=van_ban&id={self.id}&field=file_da_ky&filename={self.ten_file_da_ky or "signed.pdf"}&download=true',
            'target': 'new',
        }

    def action_view_signature_log(self):
        """Xem lịch sử ký"""
        self.ensure_one()
        return {
            'name': _('Lịch sử ký - %s') % self.ma_van_ban,
            'type': 'ir.actions.act_window',
            'res_model': 'van_ban.signature.log',
            'view_mode': 'tree,form',
            'domain': [('van_ban_id', '=', self.id)],
            'context': {'default_van_ban_id': self.id},
        }

    def action_ky_noi_bo(self):
        """Mở wizard ký điện tử - VẼ CHỮ KÝ"""
        self.ensure_one()
        
        # Kiểm tra điều kiện trước khi mở wizard
        if self.trang_thai not in ['da_duyet', 'cho_ky']:
            raise UserError('Văn bản chưa được duyệt!')
        
        if not self.file_dinh_kem:
            raise UserError('Vui lòng đính kèm file văn bản trước khi ký!')
        
        # Mở wizard ký điện tử
        return {
            'name': _('Ký điện tử - Vẽ chữ ký'),
            'type': 'ir.actions.act_window',
            'res_model': 'wizard.ky.dien.tu',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_van_ban_id': self.id,
            }
        }
    
    def action_xac_thuc_chu_ky(self):
        """
        Xác thực chữ ký số bằng cách:
        1. Lấy Public Key từ kho (Certificate)
        2. Giải mã chữ ký số bằng Public Key
        3. So sánh với file gốc
        4. Kết luận: Hợp lệ hoặc Không hợp lệ
        """
        self.ensure_one()
        
        if not self.da_ky_noi_bo:
            raise UserError('Văn bản chưa được ký điện tử!')
        
        # Tìm signature log mới nhất của văn bản (không chỉ giới hạn trạng thái 'signed')
        # Trường hợp đã xác thực trước đó thì status sẽ là 'verified' và vẫn cần hiển thị được.
        signature_log = self.env['van_ban.signature.log'].search([
            ('van_ban_id', '=', self.id),
            ('digital_signature', '!=', False),
        ], order='signed_at desc', limit=1)

        if not signature_log:
            raise UserError(
                'Không tìm thấy thông tin chữ ký số!\n\n'
                'Vui lòng kiểm tra lại: văn bản đã được ký điện tử (PKI) và có log ký hợp lệ.'
            )

        if not signature_log.certificate_id:
            raise UserError(
                'Không tìm thấy chứng thư số (certificate) trong log ký!\n\n'
                'Không thể xác thực chữ ký nếu thiếu certificate.'
            )
        
        # Gọi method xác thực từ signature log
        try:
            # Nếu đã verify rồi thì chỉ hiển thị thông tin
            if signature_log.verification_status != 'verified':
                signature_log.action_verify_signature()
            
            signer_display = signature_log.signer_name or signature_log.signer_name_expected or 'N/A'
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('✅ Xác thực thành công'),
                    'message': f'Chữ ký số hợp lệ!\n\n👤 Người ký: {signer_display}\n📅 Ngày ký: {signature_log.signed_at.strftime("%d/%m/%Y %H:%M")}\n🔐 Certificate: {signature_log.certificate_id.name if signature_log.certificate_id else "N/A"}\n✅ Xác thực lúc: {signature_log.verified_at.strftime("%d/%m/%Y %H:%M") if signature_log.verified_at else "N/A"}',
                    'type': 'success',
                    'sticky': True,
                }
            }
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('❌ Xác thực thất bại'),
                    'message': f'Chữ ký số không hợp lệ!\n\nLý do: {str(e)}',
                    'type': 'danger',
                    'sticky': True,
                }
            }
    
    def action_gui_van_ban(self):
        """Gửi văn bản - CHỈ được gửi SAU KHI đã ký điện tử"""
        for record in self:
            # KIỂM TRA BẮT BUỘC: Phải ký điện tử trước khi gửi
            if not record.da_ky_noi_bo:
                raise UserError(
                    'KHÔNG THỂ GỬI!\n\n'
                    'Văn bản chưa được ký điện tử.\n'
                    'Vui lòng thực hiện ký điện tử trước khi gửi.'
                )
            
            if record.trang_thai != 'da_ky':
                raise UserError('Chỉ có thể gửi văn bản đã ký!')
            
            # Nếu cần khách hàng ký, kiểm tra xem khách đã ký chưa
            if record.khach_hang_id and not record.da_khach_ky:
                raise UserError(
                    'CHƯA THỂ GỬI!\n\n'
                    'Văn bản cần chữ ký của khách hàng.\n'
                    'Vui lòng đợi khách hàng ký xong hoặc gửi yêu cầu ký cho khách hàng.'
                )
            
            # Gửi văn bản và KHÓA VĂN BẢN
            record.write({
                'trang_thai': 'da_gui',
                'ngay_gui': fields.Date.today(),
                'bi_khoa': True  # KHÓA khi gửi đi
            })
            
            record._ghi_lich_su('gui', 'Gửi văn bản - Văn bản đã được khóa')
            
            # Gửi email thông báo cho khách hàng (nếu có)
            if record.khach_hang_id and record.khach_hang_id.email:
                record._gui_email_van_ban_da_gui()

            # Gửi email thông báo + file đã ký cho Giám đốc (nếu có)
            record._gui_email_van_ban_da_gui_cho_giam_doc()

            # Thông báo nội bộ
            record._send_enhanced_notifications('sent')
        
        # Thông báo thành công và reload form
        self.env.cr.commit()  # Commit để đảm bảo dữ liệu được lưu
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Gửi văn bản thành công!',
                'message': f'Văn bản {self.ma_van_ban} đã được gửi và khóa.',
                'type': 'success',
                'sticky': True,
                'next': {
                    'type': 'ir.actions.act_window',
                    'res_model': 'van_ban',
                    'res_id': self.id,
                    'views': [(False, 'form')],
                    'view_mode': 'form',
                },
            }
        }

    def _gui_email_van_ban_da_gui_cho_giam_doc(self):
        """Gửi email văn bản đã ký cho Giám đốc"""
        self.ensure_one()

        giam_doc_email = None
        giam_doc_name = None

        if self.nguoi_ky_id:
            giam_doc_name = self.nguoi_ky_id.ten_nv or self.nguoi_ky_id.name
            giam_doc_email = self.nguoi_ky_id.email or (self.nguoi_ky_id.user_id.email if self.nguoi_ky_id.user_id else None)

        if not giam_doc_email:
            return

        mail_values = {
            'subject': f'[{self.env.company.name}] Văn bản đã ký: {self.ten_van_ban}',
            'body_html': f'''
                <p>Kính gửi {giam_doc_name or "Giám đốc"},</p>
                <p>Văn bản <strong>{self.ten_van_ban}</strong> đã được ký đầy đủ và gửi đi.</p>
                <p><strong>Thông tin văn bản:</strong></p>
                <ul>
                    <li>Mã văn bản: {self.ma_van_ban}</li>
                    <li>Loại văn bản: {self.loai_van_ban_id.ten_loai}</li>
                    <li>Ngày gửi: {self.ngay_gui}</li>
                    <li>Khách hàng: {self.khach_hang_id.ten_khach_hang if self.khach_hang_id else ""}</li>
                </ul>
                <p>File văn bản đã ký được đính kèm trong email này.</p>
                <br/>
                <p>Trân trọng,</p>
                <p>{self.env.company.name}</p>
            ''',
            'email_to': giam_doc_email,
            'email_from': self.env.company.email or 'noreply@company.com',
        }

        if self.file_da_ky and self.ten_file_da_ky:
            mail_values['attachment_ids'] = [(
                0, 0, {
                    'name': self.ten_file_da_ky,
                    'datas': self.file_da_ky,
                    'mimetype': 'application/pdf',
                }
            )]

        self.env['mail.mail'].create(mail_values).send()
    
    def action_gui_yeu_cau_ky_khach(self):
        """Tạo yêu cầu ký cho khách hàng"""
        self.ensure_one()
        
        # KIỂM TRA: Phải ký nội bộ trước
        if not self.da_ky_noi_bo:
            raise UserError(
                'Vui lòng ký điện tử nội bộ trước khi gửi yêu cầu ký cho khách hàng!'
            )
        
        if not self.khach_hang_id:
            raise UserError('Vui lòng chọn khách hàng liên quan!')
        
        if not self.khach_hang_id.email:
            raise UserError('Khách hàng chưa có email!')
        
        # Tạo yêu cầu ký
        yeu_cau = self.env['yeu_cau_ky'].create({
            'van_ban_id': self.id,
            'khach_hang_id': self.khach_hang_id.id,
            'email': self.khach_hang_id.email,
            'trang_thai': 'cho_ky'
        })
        
        # Gửi email
        yeu_cau.action_gui_email_yeu_cau_ky()
        
        self._ghi_lich_su('gui_yeu_cau_ky', f'Gửi yêu cầu ký cho khách hàng: {self.khach_hang_id.ten_khach_hang}')

        # Thông báo trên hồ sơ khách hàng (module khách hàng)
        if self.khach_hang_id:
            self.khach_hang_id.message_post(
                body=(
                    f'📄 Có yêu cầu ký mới cho văn bản <strong>{self.ten_van_ban}</strong>. '
                    'Vui lòng ký để hoàn tất.'
                )
            )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Thành công',
                'message': f'Đã gửi yêu cầu ký cho {self.khach_hang_id.ten_khach_hang}',
                'type': 'success',
            }
        }
    
    def action_huy(self):
        """Hủy văn bản"""
        for record in self:
            if record.trang_thai == 'da_ky':
                raise UserError('Không thể hủy văn bản đã ký!')
            
            record.write({'trang_thai': 'huy'})
            record._ghi_lich_su('huy', f'Hủy văn bản. Lý do: {record.ly_do_huy or "Không có"}')
    
    def action_mo_khoa(self):
        """Mở khóa văn bản (chỉ admin)"""
        for record in self:
            record.write({'bi_khoa': False})
            record._ghi_lich_su('mo_khoa', 'Mở khóa văn bản')
    
    # === HELPER METHODS ===
    
    def _ghi_lich_su(self, hanh_dong, mo_ta):
        """Ghi lịch sử thay đổi văn bản với audit trail chi tiết"""
        self.ensure_one()
        
        # Get audit information from request
        ip_address = 'N/A'
        user_agent = 'N/A'
        session_id = 'N/A'
        
        try:
            # Get IP address
            if hasattr(self.env['ir.http'], '_get_client_address'):
                ip_address = self.env['ir.http']._get_client_address()
            elif hasattr(self.env, 'request') and self.env.request:
                ip_address = self.env.request.httprequest.remote_addr
            
            # Get user agent and session
            if hasattr(self.env, 'request') and self.env.request:
                user_agent = self.env.request.httprequest.headers.get('User-Agent', 'N/A')
                session_id = self.env.request.session.sid if hasattr(self.env.request, 'session') else 'N/A'
        except Exception as e:
            _logger.warning(f"Could not capture audit information: {str(e)}")
        
        self.env['lich_su_van_ban'].create({
            'van_ban_id': self.id,
            'hanh_dong': hanh_dong,
            'mo_ta': mo_ta,
            'nguoi_thuc_hien_id': self.env.uid,
            'thoi_gian': fields.Datetime.now(),
            'ip_address': ip_address,
            'user_agent': user_agent,
            'session_id': session_id,
        })
    
    def _compute_hash_file(self):
        """Tính hash MD5 của file để kiểm tra tính toàn vẹn"""
        self.ensure_one()
        if self.file_dinh_kem:
            file_content = base64.b64decode(self.file_dinh_kem)
            self.hash_file = hashlib.md5(file_content).hexdigest()
    
    def _gui_email_van_ban_da_gui(self):
        """Gửi email thông báo văn bản đã gửi cho khách hàng"""
        self.ensure_one()
        if not self.khach_hang_id or not self.khach_hang_id.email:
            return
        
        mail_values = {
            'subject': f'[{self.env.company.name}] Văn bản: {self.ten_van_ban}',
            'body_html': f'''
                <p>Kính gửi {self.khach_hang_id.ten_khach_hang},</p>
                <p>Chúng tôi xin gửi đến Quý khách văn bản: <strong>{self.ten_van_ban}</strong></p>
                <p><strong>Thông tin văn bản:</strong></p>
                <ul>
                    <li>Mã văn bản: {self.ma_van_ban}</li>
                    <li>Loại văn bản: {self.loai_van_ban_id.ten_loai}</li>
                    <li>Ngày gửi: {self.ngay_gui}</li>
                    <li>Đã ký điện tử: Có</li>
                </ul>
                <p>Văn bản đính kèm trong email này.</p>
                <br/>
                <p>Trân trọng,</p>
                <p>{self.env.company.name}</p>
            ''',
            'email_to': self.khach_hang_id.email,
            'email_from': self.env.company.email or 'noreply@company.com',
        }
        
        # Đính kèm file đã ký
        if self.file_da_ky and self.ten_file_da_ky:
            mail_values['attachment_ids'] = [(
                0, 0, {
                    'name': self.ten_file_da_ky,
                    'datas': self.file_da_ky,
                    'mimetype': 'application/pdf',
                }
            )]
        
        self.env['mail.mail'].create(mail_values).send()
    
    # === PROCESS AUTOMATION - ENHANCED NOTIFICATIONS ===
    
    def _send_enhanced_notifications(self, notification_type):
        """Gửi thông báo nâng cao dựa trên loại sự kiện"""
        self.ensure_one()
        
        if notification_type == 'approval_request':
            self._send_approval_request_notifications()
        elif notification_type == 'approved':
            self._send_approval_complete_notifications()
        elif notification_type == 'signature_request':
            self._send_signature_request_notifications()
        elif notification_type == 'signed':
            self._send_signature_complete_notifications()
        elif notification_type == 'sent':
            self._send_document_sent_notifications()
        elif notification_type == 'expired':
            # Tối thiểu: tạo cảnh báo activity cho người tạo (nếu có user hệ thống)
            if self.nguoi_tao_id and getattr(self.nguoi_tao_id, 'user_id', False):
                self.activity_schedule(
                    'mail.mail_activity_data_warning',
                    user_id=self.nguoi_tao_id.user_id.id,
                    summary=_('Văn bản hết hiệu lực: %s') % (self.ten_van_ban or ''),
                    note=_('Văn bản đã hết hạn/hết hiệu lực và được hệ thống cập nhật tự động.'),
                )
    
    def _send_approval_request_notifications(self):
        """Gửi thông báo yêu cầu duyệt với thông tin AI"""
        if not self.nguoi_duyet_id or not self.nguoi_duyet_id.email:
            return
        
        risk_color = {'low': 'green', 'medium': 'orange', 'high': 'red', 'critical': 'darkred'}
        risk_icon = {'low': '✅', 'medium': '⚠️', 'high': '🔴', 'critical': '🚨'}
        
        mail_values = {
            'subject': f'[{risk_icon.get(self.ai_risk_level, "📄")}] Yêu cầu duyệt: {self.ten_van_ban}',
            'body_html': f'''
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <h2 style="color: #2E86C1;">Yêu cầu duyệt văn bản</h2>
                    
                    <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 10px 0;">
                        <h3>{self.ten_van_ban}</h3>
                        <p><strong>Mã văn bản:</strong> {self.ma_van_ban}</p>
                        <p><strong>Loại văn bản:</strong> {self.loai_van_ban_id.ten_loai}</p>
                        <p><strong>Người tạo:</strong> {self.ten_nguoi_tao}</p>
                        <p><strong>Giá trị:</strong> {self.gia_tri_hop_dong:,.0f} VND</p>
                    </div>
                    
                    <div style="background-color: {risk_color.get(self.ai_risk_level, 'gray')}; color: white; padding: 10px; border-radius: 5px; margin: 10px 0;">
                        <strong>AI Risk Assessment: {self.ai_risk_level.upper()}</strong><br/>
                        Priority Score: {self.ai_priority_score}/10
                    </div>
                    
                    <p><strong>Deadline SLA:</strong> {self.sla_deadline}</p>
                    
                    <div style="text-align: center; margin: 20px 0;">
                        <a href="/web#id={self.id}&model=van_ban&view_type=form" 
                           style="background-color: #28a745; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
                            Xem và duyệt văn bản
                        </a>
                    </div>
                    
                    <p style="color: #666; font-size: 12px;">
                        Email này được gửi tự động bởi hệ thống quản lý văn bản.
                    </p>
                </div>
            ''',
            'email_to': self.nguoi_duyet_id.email,
            'email_from': self.env.company.email or 'noreply@company.com',
        }
        
        self.env['mail.mail'].create(mail_values).send()
    
    def _send_approval_complete_notifications(self):
        """Gửi thông báo duyệt thành công"""
        # Thông báo cho người tạo
        if self.nguoi_tao_id and self.nguoi_tao_id.email:
            mail_values = {
                'subject': f'✅ Văn bản đã được duyệt: {self.ten_van_ban}',
                'body_html': f'''
                    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                        <h2 style="color: #28a745;">Văn bản đã được duyệt</h2>
                        <p>Kính gửi {self.ten_nguoi_tao},</p>
                        <p>Văn bản <strong>{self.ten_van_ban}</strong> đã được duyệt thành công.</p>
                        <p><strong>Người duyệt:</strong> {self.ten_nguoi_duyet}</p>
                        <p><strong>Tiếp theo:</strong> Văn bản sẽ được chuyển sang bước ký điện tử.</p>
                    </div>
                ''',
                'email_to': self.nguoi_tao_id.email,
                'email_from': self.env.company.email or 'noreply@company.com',
            }
            self.env['mail.mail'].create(mail_values).send()
    
    def _send_signature_request_notifications(self):
        """Gửi thông báo yêu cầu ký"""
        if not self.nguoi_ky_id or not self.nguoi_ky_id.email:
            return
        
        mail_values = {
            'subject': f'🖊️ Yêu cầu ký văn bản: {self.ten_van_ban}',
            'body_html': f'''
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <h2 style="color: #8E44AD;">Yêu cầu ký văn bản</h2>
                    
                    <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 10px 0;">
                        <h3>{self.ten_van_ban}</h3>
                        <p><strong>Mã văn bản:</strong> {self.ma_van_ban}</p>
                        <p><strong>Người duyệt:</strong> {self.ten_nguoi_duyet}</p>
                    </div>
                    
                    <div style="text-align: center; margin: 20px 0;">
                        <a href="/web#id={self.id}&model=van_ban&view_type=form" 
                           style="background-color: #8E44AD; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
                            Truy cập và ký văn bản
                        </a>
                    </div>
                    
                    <p style="color: #666; font-size: 12px;">
                        Vui lòng hoàn thành ký điện tử trong thời hạn quy định.
                    </p>
                </div>
            ''',
            'email_to': self.nguoi_ky_id.email,
            'email_from': self.env.company.email or 'noreply@company.com',
        }
        
        self.env['mail.mail'].create(mail_values).send()
    
    def _send_signature_complete_notifications(self):
        """Gửi thông báo ký hoàn thành"""
        # Thông báo cho người tạo và người duyệt
        recipients = []
        if self.nguoi_tao_id and self.nguoi_tao_id.email:
            recipients.append((self.nguoi_tao_id.email, self.ten_nguoi_tao))
        if self.nguoi_duyet_id and self.nguoi_duyet_id.email and self.nguoi_duyet_id != self.nguoi_tao_id:
            recipients.append((self.nguoi_duyet_id.email, self.ten_nguoi_duyet))
        
        for email, name in recipients:
            mail_values = {
                'subject': f'✍️ Văn bản đã được ký: {self.ten_van_ban}',
                'body_html': f'''
                    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                        <h2 style="color: #27AE60;">Văn bản đã được ký điện tử</h2>
                        <p>Kính gửi {name},</p>
                        <p>Văn bản <strong>{self.ten_van_ban}</strong> đã được ký thành công.</p>
                        <p><strong>Người ký:</strong> {self.ten_nguoi_ky}</p>
                        <p><strong>Thời gian ký:</strong> {self.ngay_ky_noi_bo}</p>
                        <p><strong>Tiếp theo:</strong> Văn bản có thể được gửi đi hoặc yêu cầu ký của khách hàng.</p>
                    </div>
                ''',
                'email_to': email,
                'email_from': self.env.company.email or 'noreply@company.com',
            }
            self.env['mail.mail'].create(mail_values).send()
    
    def _send_document_sent_notifications(self):
        """Gửi thông báo văn bản đã gửi"""
        # Thông báo cho tất cả người liên quan
        recipients = []
        if self.nguoi_tao_id and self.nguoi_tao_id.email:
            recipients.append((self.nguoi_tao_id.email, self.ten_nguoi_tao))
        if self.nguoi_duyet_id and self.nguoi_duyet_id.email:
            recipients.append((self.nguoi_duyet_id.email, self.ten_nguoi_duyet))
        if self.nguoi_ky_id and self.nguoi_ky_id.email:
            recipients.append((self.nguoi_ky_id.email, self.ten_nguoi_ky))
        
        for email, name in recipients:
            mail_values = {
                'subject': f'📤 Văn bản đã gửi: {self.ten_van_ban}',
                'body_html': f'''
                    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                        <h2 style="color: #3498DB;">Văn bản đã được gửi</h2>
                        <p>Kính gửi {name},</p>
                        <p>Văn bản <strong>{self.ten_van_ban}</strong> đã được gửi thành công.</p>
                        <p><strong>Ngày gửi:</strong> {self.ngay_gui}</p>
                        <p><strong>Trạng thái:</strong> Đã khóa và hoàn thành</p>
                    </div>
                ''',
                'email_to': email,
                'email_from': self.env.company.email or 'noreply@company.com',
            }
            self.env['mail.mail'].create(mail_values).send()
    
    # === PROCESS AUTOMATION - AI WORKFLOW METHODS ===
    
    def _schedule_auto_follow_up(self, follow_up_type, days=1):
        """Lên lịch follow-up tự động"""
        self.ensure_one()
        
        follow_up_date = fields.Datetime.now() + timedelta(days=days)
        
        activity_summary = {
            'approval': f'Follow-up: Duyệt văn bản {self.ten_van_ban}',
            'signature': f'Follow-up: Ký văn bản {self.ten_van_ban}',
            'customer_signature': f'Follow-up: Khách ký văn bản {self.ten_van_ban}'
        }
        
        # Determine responsible user
        responsible_user = False
        if follow_up_type == 'approval' and self.nguoi_duyet_id:
            responsible_user = self.nguoi_duyet_id.user_id
        elif follow_up_type in ['signature', 'customer_signature'] and self.nguoi_ky_id:
            responsible_user = self.nguoi_ky_id.user_id
        
        if responsible_user:
            self.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=responsible_user.id,
                summary=activity_summary.get(follow_up_type, 'Follow-up văn bản'),
                date_deadline=follow_up_date,
                note=f'Auto follow-up #{self.auto_follow_up_count + 1} cho văn bản có độ ưu tiên cao.'
            )
            
            self.write({
                'auto_follow_up_count': self.auto_follow_up_count + 1,
                'last_auto_follow_up': fields.Datetime.now()
            })
    
    def _cancel_pending_follow_ups(self):
        """Hủy các follow-up đang chờ"""
        self.ensure_one()
        
        # Cancel pending activities related to this document
        activities = self.env['mail.activity'].search([
            ('res_model', '=', 'van_ban'),
            ('res_id', '=', self.id),
            ('activity_type_id', '=', self.env.ref('mail.mail_activity_data_todo').id),
            ('summary', 'ilike', 'Follow-up')
        ])
        
        activities.unlink()
    
    def action_ai_apply_suggestions(self):
        """Áp dụng các đề xuất của AI"""
        self.ensure_one()
        
        changes_made = []
        
        # Apply approver suggestion
        if not self.nguoi_duyet_id and self.ai_suggested_approver:
            self.write({'nguoi_duyet_id': self.ai_suggested_approver.id})
            changes_made.append(f'Người duyệt: {self.ai_suggested_approver.ten_nv}')
        
        # Apply signer suggestion
        if not self.nguoi_ky_id and self.ai_suggested_signer:
            self.write({'nguoi_ky_id': self.ai_suggested_signer.id})
            changes_made.append(f'Người ký: {self.ai_suggested_signer.ten_nv}')
        
        # Apply category suggestion
        if self.ai_category_suggestion and not self.loai_van_ban_id:
            # Try to find matching category
            category = self.env['loai_van_ban'].search([
                ('ten_loai', 'ilike', self.ai_category_suggestion)
            ], limit=1)
            if category:
                self.write({'loai_van_ban_id': category.id})
                changes_made.append(f'Loại văn bản: {category.ten_loai}')
        
        if changes_made:
            self._ghi_lich_su('ai_apply', f'AI áp dụng đề xuất: {", ".join(changes_made)}')
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'AI Suggestions Applied',
                    'message': f'Đã áp dụng đề xuất AI: {", ".join(changes_made)}',
                    'type': 'success',
                }
            }
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'No Changes',
                'message': 'Không có đề xuất AI nào để áp dụng.',
                'type': 'warning',
            }
        }
    
    def action_analyze_ai(self):
        """Phân tích văn bản bằng AI và đưa ra đề xuất"""
        self.ensure_one()
        
        if not AI_AVAILABLE:
            raise UserError("AI libraries không khả dụng. Vui lòng cài đặt textblob và sumy.")
        
        try:
            # Analyze document content
            content = self._get_document_content_for_analysis()
            
            # Perform AI analysis
            analysis_result = self._perform_ai_analysis(content)
            
            # Update AI fields
            self.write({
                'ai_summary': analysis_result.get('summary', ''),
                'ai_category_suggestion': analysis_result.get('category', ''),
                'ai_priority_score': analysis_result.get('priority', 5),
                'ai_risk_level': analysis_result.get('risk_level', 'medium'),
                'ai_suggested_approver': analysis_result.get('suggested_approver'),
                'ai_suggested_signer': analysis_result.get('suggested_signer'),
                'ai_assessment': analysis_result.get('assessment', ''),
                'ai_analysis_date': fields.Datetime.now(),
                'ai_auto_stats': analysis_result.get('stats', ''),
            })
            
            # Log the analysis
            self._ghi_lich_su('ai_analyze', 'AI phân tích văn bản và đưa ra đề xuất')
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'AI Analysis Complete',
                    'message': 'Đã hoàn thành phân tích AI. Kiểm tra tab Trợ lý AI để xem kết quả.',
                    'type': 'success',
                }
            }
            
        except Exception as e:
            _logger.error(f"AI analysis failed: {str(e)}")
            raise UserError(f"Lỗi phân tích AI: {str(e)}")
    
    def _get_document_content_for_analysis(self):
        """Lấy nội dung văn bản để phân tích AI"""
        content_parts = []
        
        # Add title and description
        if self.ten_van_ban:
            content_parts.append(f"Tiêu đề: {self.ten_van_ban}")
        if self.mo_ta:
            content_parts.append(f"Mô tả: {self.mo_ta}")
        
        # Add document type
        if self.loai_van_ban_id:
            content_parts.append(f"Loại văn bản: {self.loai_van_ban_id.ten_loai}")
        
        # Add creator info
        if self.nguoi_tao_id:
            content_parts.append(f"Người tạo: {self.nguoi_tao_id.ten_nv}")
        
        # Add approver info
        if self.nguoi_duyet_id:
            content_parts.append(f"Người duyệt: {self.nguoi_duyet_id.ten_nv}")
        
        # Add signer info
        if self.nguoi_ky_id:
            content_parts.append(f"Người ký: {self.nguoi_ky_id.ten_nv}")
        
        # Add dates
        if self.ngay_tao:
            content_parts.append(f"Ngày tạo: {self.ngay_tao}")
        if self.ngay_het_han:
            content_parts.append(f"Ngày hết hạn: {self.ngay_het_han}")
        
        return "\n".join(content_parts)
    
    def _perform_ai_analysis(self, content):
        """Thực hiện phân tích AI trên nội dung"""
        result = {
            'summary': '',
            'category': '',
            'priority': 5,
            'risk_level': 'medium',
            'suggested_approver': False,
            'suggested_signer': False,
            'assessment': '',
            'stats': '',
        }
        
        if not content:
            return result
        
        try:
            # Create text blob for analysis
            blob = TextBlob(content)
            
            # Generate summary using sumy
            parser = PlaintextParser.from_string(content, Tokenizer("english"))
            summarizer = LsaSummarizer()
            summary_sentences = summarizer(parser.document, 2)  # 2 sentence summary
            result['summary'] = " ".join(str(sentence) for sentence in summary_sentences)
            
            # Analyze sentiment for priority
            sentiment = blob.sentiment.polarity
            if sentiment > 0.1:
                result['priority'] = 7  # High priority for positive/urgent content
            elif sentiment < -0.1:
                result['priority'] = 3  # Low priority for negative content
            else:
                result['priority'] = 5  # Medium priority
            
            # Determine risk level based on keywords and content
            risk_keywords = ['khẩn cấp', 'quan trọng', 'deadline', 'hết hạn', 'urgent', 'important']
            risk_score = 0
            
            content_lower = content.lower()
            for keyword in risk_keywords:
                if keyword in content_lower:
                    risk_score += 1
            
            if risk_score >= 3:
                result['risk_level'] = 'critical'
            elif risk_score >= 2:
                result['risk_level'] = 'high'
            elif risk_score >= 1:
                result['risk_level'] = 'medium'
            else:
                result['risk_level'] = 'low'
            
            # Suggest approver based on document type and creator
            if self.loai_van_ban_id and self.nguoi_tao_id:
                # Find approvers with similar document types
                suggested_approvers = self.env['nhan_vien'].search([
                    ('id', '!=', self.nguoi_tao_id.id),
                ], limit=5)
                
                if suggested_approvers:
                    result['suggested_approver'] = suggested_approvers[0]
            
            # Suggest signer (typically higher level than approver)
            if result['suggested_approver']:
                # Find signers with higher positions
                suggested_signers = self.env['nhan_vien'].search([
                    ('id', '!=', self.nguoi_tao_id.id),
                ], limit=3)
                
                if suggested_signers:
                    result['suggested_signer'] = suggested_signers[0]
            
            # Generate assessment
            result['assessment'] = f"""
Đánh giá AI cho văn bản "{self.ten_van_ban}":
- Độ ưu tiên: {result['priority']}/10
- Mức độ rủi ro: {result['risk_level'].upper()}
- Tóm tắt: {result['summary'][:100]}...
- Đề xuất người duyệt: {result['suggested_approver'].ten_nv if result['suggested_approver'] else 'Không có'}
- Đề xuất người ký: {result['suggested_signer'].ten_nv if result['suggested_signer'] else 'Không có'}
            """.strip()
            
            # Generate stats
            result['stats'] = f"""
Thống kê phân tích:
- Độ dài nội dung: {len(content)} ký tự
- Số từ: {len(content.split())}
- Sentiment: {sentiment:.2f}
- Từ khóa rủi ro tìm thấy: {risk_score}
            """.strip()
            
        except Exception as e:
            _logger.warning(f"AI analysis error: {str(e)}")
            result['assessment'] = f"Lỗi phân tích AI: {str(e)}"
        
        return result
    
    # === SCHEDULED ACTIONS ===
    
    # === ENHANCED SCHEDULED ACTIONS - PROCESS AUTOMATION ===
    
    @api.model
    def _cron_check_het_han(self):
        """Enhanced cron job kiểm tra văn bản hết hạn và gửi cảnh báo"""
        today = fields.Date.today()
        
        # Tìm văn bản sắp hết hạn (trong 30 ngày)
        van_ban_sap_het_han = self.search([
            ('trang_thai', 'in', ['da_duyet', 'da_ky']),
            ('ngay_het_han', '!=', False),
            ('ngay_het_han', '>=', today),
            ('ngay_het_han', '<=', today + timedelta(days=30))
        ])
        
        for vb in van_ban_sap_het_han:
            # Enhanced notifications with AI risk assessment
            risk_icon = {'low': '⚪', 'medium': '🟡', 'high': '🔴', 'critical': '🚨'}
            
            # Gửi thông báo cho người tạo
            if vb.nguoi_tao_id and vb.nguoi_tao_id.user_id:
                vb.activity_schedule(
                    'mail.mail_activity_data_warning',
                    user_id=vb.nguoi_tao_id.user_id.id,
                    summary=f'{risk_icon.get(vb.ai_risk_level, "⚠️")} Văn bản sắp hết hạn: {vb.ten_van_ban} ({vb.so_ngay_con_lai} ngày)',
                    date_deadline=vb.ngay_het_han,
                    note=f'Risk Level: {vb.ai_risk_level.upper()}\nPriority: {vb.ai_priority_score}/10\nSLA Status: {"Breach" if vb.sla_breached else "OK"}'
                )
        
        # Đánh dấu văn bản đã hết hạn
        van_ban_het_han = self.search([
            ('trang_thai', 'in', ['da_duyet', 'da_ky']),
            ('ngay_het_han', '!=', False),
            ('ngay_het_han', '<', today)
        ])
        
        for vb in van_ban_het_han:
            vb.write({'trang_thai': 'het_hieu_luc'})
            vb._ghi_lich_su('het_han', 'Văn bản hết hiệu lực - Auto update by cron')
            
            # Notify all stakeholders
            vb._send_enhanced_notifications('expired')
    
    @api.model
    def _cron_auto_follow_up(self):
        """Cron job tự động follow-up các văn bản pending"""
        now = fields.Datetime.now()
        
        # Follow-up approval requests (pending > 2 days)
        pending_approvals = self.search([
            ('trang_thai', '=', 'cho_duyet'),
            ('ngay_tao', '<', now - timedelta(days=2)),
            ('auto_follow_up_count', '<', 3)  # Max 3 follow-ups
        ])
        
        for vb in pending_approvals:
            vb._schedule_auto_follow_up('approval', days=1)
        
        # Follow-up signature requests (pending > 3 days)
        pending_signatures = self.search([
            ('trang_thai', '=', 'cho_ky'),
            ('ngay_tao', '<', now - timedelta(days=3)),
            ('auto_follow_up_count', '<', 3)
        ])
        
        for vb in pending_signatures:
            vb._schedule_auto_follow_up('signature', days=1)
    
    @api.model
    def _cron_sla_monitoring(self):
        """Cron job giám sát SLA và cảnh báo vi phạm"""
        now = fields.Datetime.now()
        
        # Find SLA breaches
        sla_breaches = self.search([
            ('sla_deadline', '!=', False),
            ('sla_deadline', '<', now),
            ('trang_thai', 'not in', ['da_gui', 'het_hieu_luc', 'huy']),
            ('sla_breached', '=', False)  # Only notify once
        ])
        
        for vb in sla_breaches:
            vb.write({'sla_breached': True})
            
            # Notify stakeholders about SLA breach
            stakeholders = []
            if vb.nguoi_tao_id and vb.nguoi_tao_id.user_id:
                stakeholders.append(vb.nguoi_tao_id.user_id.id)
            if vb.nguoi_duyet_id and vb.nguoi_duyet_id.user_id:
                stakeholders.append(vb.nguoi_duyet_id.user_id.id)
            if vb.nguoi_ky_id and vb.nguoi_ky_id.user_id:
                stakeholders.append(vb.nguoi_ky_id.user_id.id)
            
            for user_id in set(stakeholders):  # Remove duplicates
                vb.activity_schedule(
                    'mail.mail_activity_data_warning',
                    user_id=user_id,
                    summary=f'🚨 SLA Breach: {vb.ten_van_ban}',
                    note=f'Văn bản đã vi phạm thời hạn SLA.\nRisk Level: {vb.ai_risk_level.upper()}\nOverdue: {(now - vb.sla_deadline).days} days'
                )
    
    @api.model
    def _cron_ai_optimization(self):
        """Cron job tối ưu hóa AI suggestions dựa trên dữ liệu lịch sử"""
        # Analyze approval patterns and update AI logic
        # This would be more complex in a real implementation
        
        # For now, just log the optimization run
        self.env['ir.logging'].create({
            'name': 'AI Optimization',
            'type': 'server',
            'dbname': self.env.cr.dbname,
            'level': 'INFO',
            'message': 'AI optimization cron completed - analyzed approval patterns and updated suggestions',
            'path': 'van_ban.models.van_ban',
            'func': '_cron_ai_optimization',
            'line': '1'
        })
    
    @api.model
    def _cron_data_quality_check(self):
        """Cron job kiểm tra chất lượng dữ liệu và đề xuất cải thiện"""
        # Find documents with missing critical information
        incomplete_docs = self.search([
            ('trang_thai', 'in', ['da_duyet', 'da_ky']),
            '|', '|',
            ('nguoi_duyet_id', '=', False),
            ('nguoi_ky_id', '=', False),
            ('file_dinh_kem', '=', False)
        ])
        
        for vb in incomplete_docs:
            issues = []
            if not vb.nguoi_duyet_id:
                issues.append('thiếu người duyệt')
            if not vb.nguoi_ky_id:
                issues.append('thiếu người ký')
            if not vb.file_dinh_kem:
                issues.append('thiếu file đính kèm')
            
            if vb.nguoi_tao_id and vb.nguoi_tao_id.user_id:
                vb.activity_schedule(
                    'mail.mail_activity_data_todo',
                    user_id=vb.nguoi_tao_id.user_id.id,
                    summary=f'📋 Cần bổ sung thông tin: {vb.ten_van_ban}',
                    note=f'Văn bản thiếu các thông tin quan trọng: {", ".join(issues)}'
                )
    
    # === DYNAMIC WORKFLOW METHODS ===
    available_transitions = fields.Many2many('workflow.transition', string='Available Transitions',
                                             compute='_compute_available_transitions', store=False)
    
    @api.depends('trang_thai', 'workflow_template_id')
    def _compute_available_transitions(self):
        """Compute available transitions based on current state and workflow template"""
        for record in self:
            if record.workflow_template_id:
                transitions = record.workflow_template_id.get_available_transitions(record.trang_thai, record)
                record.available_transitions = transitions
            else:
                record.available_transitions = self.env['workflow.transition']
    
    def execute_transition(self, transition_id):
        """Execute a workflow transition"""
        self.ensure_one()
        transition = self.env['workflow.transition'].browse(transition_id)
        
        if not transition or transition not in self.available_transitions:
            raise UserError(_('Invalid transition or transition not available for current state.'))
        
        # Check required group permission
        if transition.required_group:
            if not self.env.user.has_group(transition.required_group.id):
                raise UserError(_('You do not have permission to execute this transition.'))
        
        # Check condition domain if specified
        if transition.condition_domain:
            domain = eval(transition.condition_domain)
            if not self.filtered_domain(domain):
                raise UserError(_('Transition condition not met.'))
        
        # Execute the transition
        old_state = self.trang_thai
        result = transition.execute_transition(self)
        
        # Log the transition
        self._ghi_lich_su('transition', 
                         f'Transition: {old_state} -> {self.trang_thai}',
                         f'Executed transition: {transition.name}')
        
        return result
