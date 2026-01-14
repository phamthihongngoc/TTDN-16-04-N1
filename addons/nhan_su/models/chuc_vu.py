# -*- coding: utf-8 -*-

from odoo import models, fields


class NhanSuChucVu(models.Model):
    _name = 'nhan_su.chuc_vu'
    _description = 'Chức vụ'
    _order = 'name'

    name = fields.Char('Tên chức vụ', required=True, index=True)
    code = fields.Char('Mã chức vụ', index=True)
    company_id = fields.Many2one(
        'res.company',
        string='Công ty',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('name_company_unique', 'unique(name, company_id)', 'Chức vụ đã tồn tại trong công ty!'),
    ]
