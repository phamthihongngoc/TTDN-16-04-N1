# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import secrets
import string
import base64
import io
import logging
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)


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

    def action_open_wizard_ky_khach(self):
        """Mở wizard ký điện tử cho khách hàng"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Ký điện tử - Khách hàng',
            'res_model': 'wizard.ky.khach.hang',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_yeu_cau_ky_id': self.id,
            }
        }
    
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
        
        # Embed chữ ký khách hàng vào file PDF văn bản
        signed_pdf = self._embed_customer_signature_to_pdf(chu_ky_data)
        
        # Cập nhật văn bản - CHƯA khóa, chờ đến khi GỬI mới khóa
        update_vals = {
            'da_khach_ky': True,
            'ngay_khach_ky': fields.Datetime.now(),
            'chu_ky_khach': chu_ky_data,
            'bi_khoa': False  # CHƯA khóa - chờ đến khi gửi mới khóa
        }
        
        # Nếu embed thành công, cập nhật file đã ký
        if signed_pdf:
            update_vals['file_da_ky'] = base64.b64encode(signed_pdf).decode('utf-8')
        
        self.van_ban_id.write(update_vals)
        
        # Gửi email xác nhận
        self._gui_email_xac_nhan_ky()
        
        # Ghi lịch sử
        self.van_ban_id._ghi_lich_su('khach_ky', 
            f'Khách hàng {self.khach_hang_id.ten_khach_hang} đã ký văn bản - Sẵn sàng gửi đi')

        # Thông báo cho admin/QL văn bản
        self._notify_admin_khach_ky()

    def _notify_admin_khach_ky(self):
        """Thông báo admin khi khách hàng ký xong"""
        self.ensure_one()

        # Post vào chatter của văn bản
        if self.van_ban_id:
            self.van_ban_id.message_post(
                body=(
                    f'✅ Khách hàng <strong>{self.khach_hang_id.ten_khach_hang}</strong> '
                    f'đã ký văn bản <strong>{self.van_ban_id.ten_van_ban}</strong>. '
                    'Vui lòng kiểm tra và gửi văn bản.'
                )
            )

        # Tạo activity cho nhóm quản trị văn bản
        admin_group = self.env.ref('van_ban.group_quan_tri_van_ban', raise_if_not_found=False)
        if admin_group:
            for user in admin_group.users:
                if user and user.active:
                    self.van_ban_id.activity_schedule(
                        'mail.mail_activity_data_todo',
                        user_id=user.id,
                        summary=_('Khách hàng đã ký văn bản'),
                        note=(
                            f'Văn bản: {self.van_ban_id.ten_van_ban}<br/>'
                            f'Khách hàng: {self.khach_hang_id.ten_khach_hang}<br/>'
                            f'Thời gian ký: {self.ngay_ky or ""}'
                        ),
                    )
    
    def _embed_customer_signature_to_pdf(self, signature_data):
        """
        Embed ảnh chữ ký khách hàng vào file PDF văn bản.
        Chỉ thêm ảnh chữ ký thuần túy, không thêm icon hay text mặc định.
        
        Args:
            signature_data: Dữ liệu chữ ký dạng base64
            
        Returns:
            bytes: PDF data đã được embed chữ ký, hoặc None nếu lỗi
        """
        self.ensure_one()
        
        if not signature_data:
            _logger.warning("Không có dữ liệu chữ ký để embed")
            return None
            
        van_ban = self.van_ban_id
        if not van_ban:
            _logger.warning("Không tìm thấy văn bản liên kết")
            return None
        
        # Lấy file PDF hiện tại (ưu tiên file_da_ky nếu đã có, không thì dùng file_dinh_kem)
        pdf_data = van_ban.file_da_ky or van_ban.file_dinh_kem
        if not pdf_data:
            _logger.warning("Văn bản không có file PDF đính kèm")
            return None
        
        try:
            pdf_bytes = base64.b64decode(pdf_data)
        except Exception as e:
            _logger.warning(f"Không thể decode PDF: {e}")
            return None
        
        # Import các thư viện cần thiết
        try:
            from reportlab.pdfgen import canvas
            from reportlab.lib.utils import ImageReader
        except ImportError as e:
            _logger.warning(f"Thiếu thư viện reportlab: {e}")
            return None

        # Optional: use pdfplumber to locate the real signature area (better placement)
        pdfplumber = None
        try:
            import pdfplumber as _pdfplumber
            pdfplumber = _pdfplumber
        except Exception:
            pdfplumber = None
        
        # PyPDF2 compatibility
        PdfReader = None
        PdfWriter = None
        pypdf2_api = None
        
        try:
            from PyPDF2 import PdfReader, PdfWriter
            pypdf2_api = 'new'
        except ImportError:
            pass
        
        if not pypdf2_api:
            try:
                from PyPDF2 import PdfFileReader as PdfReader, PdfFileWriter as PdfWriter
                pypdf2_api = 'old'
            except ImportError:
                _logger.warning("Thiếu thư viện PyPDF2")
                return None
        
        try:
            # Decode ảnh chữ ký
            sig_bytes = base64.b64decode(signature_data)
            
            # Xử lý ảnh chữ ký
            try:
                from PIL import Image
                sig_img = Image.open(io.BytesIO(sig_bytes))
                if sig_img.mode not in ('RGB', 'RGBA'):
                    sig_img = sig_img.convert('RGBA')
                img_reader = ImageReader(sig_img)
                img_w, img_h = sig_img.size
            except Exception:
                img_reader = ImageReader(io.BytesIO(sig_bytes))
                img_w, img_h = (200, 80)  # Default size
            
            # Đọc PDF
            if pypdf2_api == 'new':
                reader = PdfReader(io.BytesIO(pdf_bytes), strict=False)
                if getattr(reader, 'is_encrypted', False):
                    try:
                        reader.decrypt('')
                    except Exception:
                        return None
                writer = PdfWriter()
                pages = list(reader.pages)
                total_pages = len(pages)
            else:
                reader = PdfReader(io.BytesIO(pdf_bytes), strict=False)
                if reader.isEncrypted:
                    try:
                        reader.decrypt('')
                    except Exception:
                        return None
                writer = PdfWriter()
                total_pages = reader.getNumPages()
            
            # Vị trí chữ ký khách hàng (bên phải - Bên B)
            # Thường ở trang cuối, góc phải dưới
            last_page_idx = max(total_pages - 1, 0)
            
            for page_idx in range(total_pages):
                if pypdf2_api == 'new':
                    page = pages[page_idx]
                    page_w = float(page.mediabox.width)
                    page_h = float(page.mediabox.height)
                else:
                    page = reader.getPage(page_idx)
                    page_w = float(page.mediaBox.getWidth())
                    page_h = float(page.mediaBox.getHeight())
                
                # Chỉ thêm chữ ký vào trang cuối
                if page_idx == last_page_idx:
                    # Tạo overlay với chữ ký
                    overlay_buf = io.BytesIO()
                    c = canvas.Canvas(overlay_buf, pagesize=(page_w, page_h))
                    
                    # === TÍNH TOÁN VỊ TRÍ CHỮ KÝ KHÁCH HÀNG (BÊN B) ===
                    # Ưu tiên tìm đúng vùng ký bằng pdfplumber (tọa độ text), fallback sang heuristic.

                    # Kích thước vùng chữ ký (box). Ảnh sẽ được scale giữ tỉ lệ trong box này.
                    sig_width = min(170.0, page_w * 0.22)
                    sig_height = min(70.0, page_h * 0.085)

                    # Defaults (fallback)
                    center_x = page_w * 0.75
                    y_pos = page_h * 0.22

                    def _strip_accents(s):
                        import unicodedata
                        s = unicodedata.normalize('NFKD', s or '')
                        s = ''.join(ch for ch in s if unicodedata.category(ch) != 'Mn')
                        return s

                    def _norm_word(s):
                        import re as _re
                        s = _strip_accents(s or '')
                        s = _re.sub(r"[^0-9A-Za-z]+", "", s)
                        return (s or '').upper()

                    def _find_phrase_bbox(words, phrase_tokens):
                        if not words or not phrase_tokens:
                            return None
                        toks = [_norm_word(t) for t in phrase_tokens if _norm_word(t)]
                        if not toks:
                            return None
                        wnorm = [_norm_word(w.get('text', '')) for w in words]
                        n = len(toks)
                        for i in range(0, max(len(wnorm) - n + 1, 0)):
                            if wnorm[i:i + n] == toks:
                                chunk = words[i:i + n]
                                x0 = min(w.get('x0', 0.0) for w in chunk)
                                x1 = max(w.get('x1', 0.0) for w in chunk)
                                top = min(w.get('top', 0.0) for w in chunk)
                                bottom = max(w.get('bottom', 0.0) for w in chunk)
                                return {'x0': x0, 'x1': x1, 'top': top, 'bottom': bottom}
                        return None

                    # Try anchor-based placement on last page
                    if pdfplumber:
                        try:
                            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                                if 0 <= last_page_idx < len(pdf.pages):
                                    p = pdf.pages[last_page_idx]
                                    words = p.extract_words(keep_blank_chars=False, use_text_flow=True)

                                    # Prefer centering on customer's printed name if found
                                    kh_name = (self.khach_hang_id and self.khach_hang_id.ten_khach_hang) or ''
                                    name_bbox = None
                                    if kh_name:
                                        name_bbox = _find_phrase_bbox(words, (kh_name or '').split())

                                    ky_bbox = _find_phrase_bbox(words, ['Ký', 'ghi', 'rõ', 'họ', 'tên'])
                                    benb_bbox = _find_phrase_bbox(words, ['ĐẠI', 'DIỆN', 'BÊN', 'B'])

                                    ref_bbox = name_bbox or ky_bbox or benb_bbox
                                    if ref_bbox:
                                        center_x = (ref_bbox['x0'] + ref_bbox['x1']) / 2.0

                                    # Convert from pdfplumber (top-origin) to reportlab (bottom-origin)
                                    pad = page_h * 0.012
                                    if ky_bbox:
                                        ky_y0 = page_h - float(ky_bbox['bottom'])  # bottom of text
                                    else:
                                        ky_y0 = None
                                    if name_bbox:
                                        name_y1 = page_h - float(name_bbox['top'])  # top of name text
                                    else:
                                        name_y1 = None

                                    # Place signature between the '(Ký...)' line and the name line
                                    if ky_y0 is not None and name_y1 is not None:
                                        max_top = ky_y0 - pad
                                        min_bottom = name_y1 + pad
                                        available = max_top - min_bottom
                                        if available > 20:
                                            sig_height = min(sig_height, available)
                                            y_pos = min_bottom
                                            if y_pos + sig_height > max_top:
                                                y_pos = max_top - sig_height
                                    elif ky_y0 is not None:
                                        y_pos = max(ky_y0 - sig_height - pad, page_h * 0.12)
                                    elif name_y1 is not None:
                                        y_pos = min(name_y1 + pad, page_h * 0.30)
                        except Exception as _e:
                            # Fallback to heuristic
                            pass

                    x_pos = center_x - (sig_width / 2.0)
                    # Clamp inside page bounds
                    x_pos = max(min(x_pos, page_w - sig_width - 5.0), 5.0)
                    y_pos = max(min(y_pos, page_h - sig_height - 5.0), 5.0)
                    
                    # Scale ảnh giữ nguyên tỷ lệ
                    scale = min(sig_width / float(img_w or 1), sig_height / float(img_h or 1))
                    draw_w = float(img_w) * scale
                    draw_h = float(img_h) * scale
                    
                    # Căn giữa ảnh trong vùng target
                    draw_x = x_pos + (sig_width - draw_w) / 2.0
                    draw_y = y_pos + (sig_height - draw_h) / 2.0
                    
                    # Vẽ CHỈ ảnh chữ ký - KHÔNG thêm text, border hay icon
                    c.drawImage(img_reader, draw_x, draw_y, 
                               width=draw_w, height=draw_h, mask='auto')
                    
                    c.showPage()
                    c.save()
                    overlay_buf.seek(0)
                    
                    # Merge overlay vào page
                    if pypdf2_api == 'new':
                        overlay_reader = PdfReader(overlay_buf, strict=False)
                        overlay_page = overlay_reader.pages[0]
                        page.merge_page(overlay_page)
                        writer.add_page(page)
                    else:
                        from PyPDF2 import PdfFileReader as PdfFileReaderOld
                        overlay_reader = PdfFileReaderOld(overlay_buf, strict=False)
                        overlay_page = overlay_reader.getPage(0)
                        page.mergePage(overlay_page)
                        writer.addPage(page)
                else:
                    # Các trang khác giữ nguyên
                    if pypdf2_api == 'new':
                        writer.add_page(page)
                    else:
                        writer.addPage(page)
            
            # Xuất PDF mới
            out_buf = io.BytesIO()
            writer.write(out_buf)
            result = out_buf.getvalue()
            
            _logger.info(f"Đã embed chữ ký khách hàng vào PDF văn bản {van_ban.ten_van_ban}")
            return result
            
        except Exception as e:
            _logger.warning(f"Lỗi khi embed chữ ký khách hàng vào PDF: {e}")
            return None

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

    def action_open_wizard_ky_khach(self):
        """Mở wizard ký điện tử cho khách hàng"""
        self.ensure_one()

        wizard = self.env['wizard.ky.khach.hang'].create({
            'yeu_cau_ky_id': self.id,
        })

        return {
            'type': 'ir.actions.act_window',
            'name': 'Ký điện tử - Khách hàng',
            'res_model': 'wizard.ky.khach.hang',
            'view_mode': 'form',
            'res_id': wizard.id,
            'target': 'new',
        }
