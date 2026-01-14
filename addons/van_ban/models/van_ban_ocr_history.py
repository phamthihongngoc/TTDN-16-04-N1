# -*- coding: utf-8 -*-

import base64
import hashlib

from odoo import api, fields, models, _


class VanBanOCRHistory(models.Model):
    _name = 'van_ban_ocr_history'
    _description = 'OCR - Lịch sử trích xuất'
    _order = 'create_date desc, id desc'

    ocr_id = fields.Many2one('van_ban_ocr', string='OCR', required=True, ondelete='cascade', index=True)

    name = fields.Char('Tên lịch sử', required=True, default=lambda self: _('Lần trích xuất'))
    user_id = fields.Many2one('res.users', string='Người thực hiện', required=True, default=lambda self: self.env.user, index=True)

    file_dinh_kem = fields.Binary('File', attachment=True)
    ten_file = fields.Char('Tên file')

    loai_file = fields.Selection(
        [('docx', 'DOCX'), ('image', 'Ảnh'), ('unknown', 'Không xác định')],
        string='Loại file',
        readonly=True,
    )

    checksum_sha1 = fields.Char('SHA1', readonly=True, index=True)
    lang = fields.Char('Ngôn ngữ OCR', readonly=True)
    tesseract_config = fields.Char('Tesseract config', readonly=True)

    noi_dung_trich_xuat = fields.Text('Nội dung trích xuất')
    loi_xu_ly = fields.Text('Lỗi xử lý')

    @api.model
    def compute_sha1_from_b64(self, file_b64):
        if not file_b64:
            return False
        try:
            raw = base64.b64decode(file_b64)
        except Exception:
            return False
        return hashlib.sha1(raw).hexdigest()
