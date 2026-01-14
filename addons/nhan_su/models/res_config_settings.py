# -*- coding: utf-8 -*-

from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    company_currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        readonly=True,
    )

    nhan_su_muc_phat_di_tre = fields.Monetary(
        related='company_id.nhan_su_muc_phat_di_tre',
        readonly=False,
        currency_field='company_currency_id',
    )
    nhan_su_muc_phat_ve_som = fields.Monetary(
        related='company_id.nhan_su_muc_phat_ve_som',
        readonly=False,
        currency_field='company_currency_id',
    )
    nhan_su_so_cong_chuan = fields.Integer(
        related='company_id.nhan_su_so_cong_chuan',
        readonly=False,
    )
