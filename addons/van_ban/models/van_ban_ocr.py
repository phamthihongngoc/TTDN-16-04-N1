# -*- coding: utf-8 -*-

import base64
import hashlib
import io
import os
import shutil

from odoo import api, fields, models, _
from odoo.exceptions import UserError

try:
    from PIL import Image
except Exception:
    Image = None

try:
    from PIL import ImageOps, ImageFilter
except Exception:
    ImageOps = None
    ImageFilter = None

try:
    import pytesseract
except Exception:
    pytesseract = None

try:
    from docx import Document
except Exception:
    Document = None

from .ocr_utils import ocr_image_bytes


class VanBanOCR(models.Model):
    _name = 'van_ban_ocr'
    _description = 'OCR - Trích xuất nội dung từ file'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Tên OCR', required=True, default=lambda self: _('OCR'), tracking=True)
    file_dinh_kem = fields.Binary('File', attachment=True, tracking=True)
    ten_file = fields.Char('Tên file', tracking=True)

    history_ids = fields.One2many('van_ban_ocr_history', 'ocr_id', string='Lịch sử', readonly=True)

    loai_file = fields.Selection(
        [('docx', 'DOCX'), ('image', 'Ảnh'), ('unknown', 'Không xác định')],
        string='Loại file',
        compute='_compute_loai_file',
        store=True,
        readonly=True,
    )

    noi_dung_trich_xuat = fields.Text('Nội dung trích xuất', tracking=True)
    loi_xu_ly = fields.Text('Lỗi xử lý', readonly=True)

    def action_clear_file(self):
        for record in self:
            record.write({'file_dinh_kem': False, 'ten_file': False})

    @api.onchange('ten_file')
    def _onchange_ten_file_suggest_name(self):
        for record in self:
            if record.ten_file and (not record.name or record.name == _('OCR')):
                base_name = os.path.splitext(record.ten_file)[0]
                record.name = base_name or _('OCR')

    @api.depends('file_dinh_kem', 'ten_file')
    def _compute_loai_file(self):
        for record in self:
            record.loai_file = record._detect_file_type() if record.file_dinh_kem else 'unknown'

    def _detect_file_type(self):
        self.ensure_one()
        file_data = base64.b64decode(self.file_dinh_kem) if self.file_dinh_kem else b''
        file_name = (self.ten_file or '').lower()
        header = file_data[:16] if file_data else b''

        is_docx = file_name.endswith('.docx') or header.startswith(b'PK')
        is_image = file_name.endswith(('.png', '.jpg', '.jpeg')) or (
            header.startswith(b'\x89PNG\r\n\x1a\n') or
            header.startswith(b'\xff\xd8\xff') or
            header.startswith(b'GIF87a') or
            header.startswith(b'GIF89a') or
            header[:2] == b'BM'
        )

        if is_docx:
            return 'docx'
        if is_image:
            return 'image'
        return 'unknown'

    def _compute_sha1(self, raw_bytes):
        if not raw_bytes:
            return False
        return hashlib.sha1(raw_bytes).hexdigest()

    def _ensure_ocr_dependencies(self):
        missing_python = []
        if pytesseract is None:
            missing_python.append('pytesseract')
        if Image is None:
            missing_python.append('Pillow')

        if missing_python:
            raise UserError(_(
                'Thiếu thư viện OCR (%s). Cài bằng: pip install -r addons/van_ban/requirements.txt'
            ) % ', '.join(missing_python))

        if not shutil.which('tesseract'):
            raise UserError(_(
                'Thiếu chương trình "tesseract" trên hệ điều hành. Trên Ubuntu/Debian: '
                'sudo apt-get install -y tesseract-ocr tesseract-ocr-vie'
            ))

    def _ensure_docx_dependencies(self):
        if Document is None:
            raise UserError(_(
                'Thiếu thư viện đọc DOCX (python-docx). Cài bằng: pip install -r addons/van_ban/requirements.txt'
            ))

    def action_trich_xuat(self):
        for record in self:
            if not record.file_dinh_kem:
                raise UserError(_('Vui lòng upload file trước khi trích xuất.'))
            record._run_extract()

    def _run_extract(self):
        self.ensure_one()

        self.loi_xu_ly = False
        self.noi_dung_trich_xuat = False

        loai = self._detect_file_type()
        file_data = base64.b64decode(self.file_dinh_kem) if self.file_dinh_kem else b''
        checksum = self._compute_sha1(file_data)
        lang_used = False
        tesseract_config = False

        try:
            if loai == 'docx':
                self._ensure_docx_dependencies()
                doc = Document(io.BytesIO(file_data))
                parts = []

                for p in doc.paragraphs:
                    text = (p.text or '').strip()
                    if text:
                        parts.append(text)

                for table in doc.tables:
                    for row in table.rows:
                        row_text = []
                        for cell in row.cells:
                            cell_text = (cell.text or '').strip()
                            if cell_text:
                                row_text.append(cell_text)
                        if row_text:
                            parts.append(' | '.join(row_text))

                self.noi_dung_trich_xuat = ('\n'.join(parts)).strip() or False

            elif loai == 'image':
                self._ensure_ocr_dependencies()
                if ImageOps is None or ImageFilter is None:
                    raise UserError(_('Thiếu thư viện Pillow để xử lý ảnh OCR. Cài bằng: pip install -r addons/van_ban/requirements.txt'))
                lang_used = 'vie+eng'
                tesseract_config = '--oem 3 --psm 6 -c preserve_interword_spaces=1'
                text = ocr_image_bytes(
                    Image,
                    ImageOps,
                    ImageFilter,
                    pytesseract,
                    file_data,
                    lang=lang_used,
                    config=tesseract_config,
                )
                self.noi_dung_trich_xuat = (text or '').strip() or False

            else:
                raise UserError(_('Chỉ hỗ trợ .docx, .png, .jpg/.jpeg.'))

        except UserError:
            raise
        except Exception as e:
            self.loi_xu_ly = str(e)
            self.noi_dung_trich_xuat = False

        self.env['van_ban_ocr_history'].sudo().create({
            'ocr_id': self.id,
            'name': _('Trích xuất %s') % (fields.Datetime.now() or ''),
            'user_id': self.env.user.id,
            'file_dinh_kem': self.file_dinh_kem,
            'ten_file': self.ten_file,
            'loai_file': loai,
            'checksum_sha1': checksum,
            'lang': lang_used,
            'tesseract_config': tesseract_config,
            'noi_dung_trich_xuat': self.noi_dung_trich_xuat,
            'loi_xu_ly': self.loi_xu_ly,
        })

    @api.model_create_multi
    def create(self, vals_list):
        records = super(VanBanOCR, self).create(vals_list)
        for record in records:
            if record.file_dinh_kem:
                record._run_extract()
        return records

    def write(self, vals):
        res = super(VanBanOCR, self).write(vals)
        if 'file_dinh_kem' in vals or 'ten_file' in vals:
            for record in self:
                if record.file_dinh_kem:
                    record._run_extract()
                else:
                    record.noi_dung_trich_xuat = False
                    record.loi_xu_ly = False
        return res
