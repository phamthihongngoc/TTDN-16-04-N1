# -*- coding: utf-8 -*-

from odoo import models, fields


class NhanSuPhongBan(models.Model):
    _name = 'nhan_su.phong_ban'
    _description = 'Phòng ban'
    _order = 'name'

    name = fields.Char('Tên phòng ban', required=True, index=True)
    code = fields.Char('Mã phòng ban', index=True)
    company_id = fields.Many2one(
        'res.company',
        string='Công ty',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('name_company_unique', 'unique(name, company_id)', 'Phòng ban đã tồn tại trong công ty!'),
    ]
