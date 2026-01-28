# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class CaLamViec(models.Model):
    _name = 'ca_lam_viec'
    _description = 'Ca làm việc'
    _order = 'sequence, name'

    name = fields.Char('Tên ca', required=True)
    code = fields.Char('Mã ca', required=True)
    sequence = fields.Integer('Thứ tự', default=10)
    active = fields.Boolean('Hoạt động', default=True)
    
    # Thời gian làm việc
    gio_bat_dau = fields.Float('Giờ bắt đầu', required=True, default=8.0, 
                                help='Ví dụ: 8.0 = 8h00, 8.5 = 8h30')
    gio_ket_thuc = fields.Float('Giờ kết thúc', required=True, default=17.0)
    
    # Giờ nghỉ trưa
    nghi_trua = fields.Boolean('Có nghỉ trưa', default=True)
    gio_nghi_trua_bat_dau = fields.Float('Nghỉ trưa từ', default=12.0)
    gio_nghi_trua_ket_thuc = fields.Float('Nghỉ trưa đến', default=13.0)
    
    # Tính toán
    so_gio_lam_chuan = fields.Float('Số giờ làm chuẩn', compute='_compute_so_gio_lam', store=True)
    
    # Quy định đi trễ/về sớm
    cho_phep_tre_phut = fields.Integer('Cho phép trễ (phút)', default=15,
                                        help='Số phút trễ được phép mà không bị tính đi trễ')
    cho_phep_som_phut = fields.Integer('Cho phép về sớm (phút)', default=0)
    
    # Tăng ca
    he_so_tang_ca = fields.Float('Hệ số tăng ca', default=1.5,
                                  help='Hệ số nhân lương cho giờ tăng ca')
    he_so_tang_ca_dem = fields.Float('Hệ số tăng ca đêm', default=2.0,
                                      help='Hệ số nhân lương cho tăng ca ban đêm (22h-6h)')
    he_so_nghi_le = fields.Float('Hệ số ngày lễ', default=3.0,
                                  help='Hệ số nhân lương cho ngày lễ/chủ nhật')
    
    # Ghi chú
    ghi_chu = fields.Text('Ghi chú')
    
    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Mã ca đã tồn tại!')
    ]
    
    @api.depends('gio_bat_dau', 'gio_ket_thuc', 'nghi_trua', 'gio_nghi_trua_bat_dau', 'gio_nghi_trua_ket_thuc')
    def _compute_so_gio_lam(self):
        for rec in self:
            tong_gio = rec.gio_ket_thuc - rec.gio_bat_dau
            if rec.nghi_trua:
                gio_nghi = rec.gio_nghi_trua_ket_thuc - rec.gio_nghi_trua_bat_dau
                tong_gio -= gio_nghi
            rec.so_gio_lam_chuan = max(0, tong_gio)
    
    @api.constrains('gio_bat_dau', 'gio_ket_thuc')
    def _check_gio(self):
        for rec in self:
            if rec.gio_bat_dau >= rec.gio_ket_thuc:
                raise ValidationError('Giờ bắt đầu phải nhỏ hơn giờ kết thúc!')
            if rec.gio_bat_dau < 0 or rec.gio_ket_thuc > 24:
                raise ValidationError('Giờ phải trong khoảng 0-24!')
    
    @api.constrains('gio_nghi_trua_bat_dau', 'gio_nghi_trua_ket_thuc', 'nghi_trua')
    def _check_gio_nghi_trua(self):
        for rec in self:
            if rec.nghi_trua:
                if rec.gio_nghi_trua_bat_dau >= rec.gio_nghi_trua_ket_thuc:
                    raise ValidationError('Giờ nghỉ trưa bắt đầu phải nhỏ hơn giờ kết thúc!')
