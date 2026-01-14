# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError


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

    is_valid = fields.Boolean('Hợp lệ', default=False)
    invalid_reason = fields.Char('Lý do không hợp lệ')

    signed_at = fields.Datetime('Thời gian', required=True, default=fields.Datetime.now)
    ip_address = fields.Char('IP')

    signature_image = fields.Binary('Chữ ký (ảnh)')

    file_sha256 = fields.Char('SHA256 file')
    blockchain_tx_hash = fields.Char('Blockchain TX Hash')

    @api.constrains('van_ban_id', 'van_ban_di_id', 'van_ban_den_id')
    def _check_one_target(self):
        for rec in self:
            targets = [bool(rec.van_ban_id), bool(rec.van_ban_di_id), bool(rec.van_ban_den_id)]
            if sum(targets) != 1:
                raise ValidationError('Lịch sử ký phải gắn đúng 1 văn bản (đến/đi/nội bộ).')
