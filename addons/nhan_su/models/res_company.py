# -*- coding: utf-8 -*-

from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    nhan_su_muc_phat_di_tre = fields.Monetary(
        string='Mức phạt đi trễ/lần (mặc định)',
        currency_field='currency_id',
        default=50000.0,
    )
    nhan_su_muc_phat_ve_som = fields.Monetary(
        string='Mức phạt về sớm/lần (mặc định)',
        currency_field='currency_id',
        default=50000.0,
    )
    nhan_su_so_cong_chuan = fields.Integer(
        string='Số công chuẩn/tháng (mặc định)',
        default=26,
    )
