# -*- coding: utf-8 -*-

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    van_ban_ocr_provider = fields.Selection(
        selection=[
            ('local', 'Local (Tesseract)'),
            ('ocrspace', 'OCR API (OCR.Space)'),
        ],
        string='OCR Provider',
        config_parameter='van_ban.ocr_provider',
        default='local',
    )

    van_ban_ocrspace_api_key = fields.Char(
        string='OCR.Space API Key',
        config_parameter='van_ban.ocrspace_api_key',
    )

    van_ban_ocrspace_language = fields.Char(
        string='OCR.Space Language',
        help="Mã ngôn ngữ theo OCR.Space (vd: vie, eng).",
        config_parameter='van_ban.ocrspace_language',
        default='vie',
    )

    van_ban_ocrspace_engine = fields.Selection(
        selection=[('1', 'Engine 1'), ('2', 'Engine 2')],
        string='OCR.Space Engine',
        help='Engine 2 thường cho chất lượng tốt hơn (tùy gói API).',
        config_parameter='van_ban.ocrspace_engine',
        default='2',
    )

    van_ban_ocr_docx_images = fields.Boolean(
        string='OCR ảnh trong file DOCX',
        help='Nếu DOCX có ảnh scan/ảnh chụp, hệ thống sẽ OCR thêm phần ảnh và ghép vào kết quả.',
        config_parameter='van_ban.ocr_docx_images',
        default=True,
    )

    van_ban_ocr_docx_max_images = fields.Integer(
        string='Giới hạn số ảnh OCR/DOCX',
        help='Giới hạn để tránh DOCX nhiều ảnh làm chậm hệ thống.',
        config_parameter='van_ban.ocr_docx_max_images',
        default=10,
    )
