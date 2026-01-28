# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ChamCong(models.Model):
    _name = 'cham_cong'
    _description = 'Cham cong nhan vien'
    _order = 'ngay_cham_cong desc'

    nhan_vien_id = fields.Many2one('nhan_vien', string='Nhan vien', required=True, ondelete='cascade')
    ngay_cham_cong = fields.Date('Ngay cham cong', required=True, default=fields.Date.context_today)
    
    # Ca lam viec
    ca_lam_viec_id = fields.Many2one('ca_lam_viec', string='Ca lam viec',
                                      help='Chon ca lam viec, de trong se dung gio mac dinh')
    
    gio_vao = fields.Float('Gio vao', help='Vi du: 7.5 = 7h30')
    gio_ra = fields.Float('Gio ra', help='Vi du: 17.5 = 17h30')
    so_gio_lam = fields.Float('So gio lam', compute='_compute_so_gio_lam', store=True)
    
    # Tang ca
    so_gio_tang_ca = fields.Float('Gio tang ca', compute='_compute_tang_ca', store=True)
    he_so_tang_ca = fields.Float('He so tang ca', compute='_compute_tang_ca', store=True)
    
    trang_thai = fields.Selection([
        ('co_mat', 'Co mat'),
        ('vang_mat', 'Vang mat'),
        ('nghi_phep', 'Nghi phep'),
        ('di_tre', 'Di tre'),
        ('ve_som', 'Ve som'),
        ('nghi_le', 'Nghi le'),
        ('nghi_bu', 'Nghi bu')
    ], string='Trang thai', default='co_mat')
    ghi_chu = fields.Text('Ghi chu')

    _sql_constraints = [
        ('unique_nhan_vien_ngay', 'unique(nhan_vien_id, ngay_cham_cong)', 
         'Mot nhan vien chi co mot ban ghi cham cong moi ngay!')
    ]

    @api.depends('gio_vao', 'gio_ra', 'ca_lam_viec_id', 'trang_thai')
    def _compute_so_gio_lam(self):
        """Tinh so gio lam viec, tru gio nghi trua"""
        for record in self:
            # Neu la vang mat / nghi phep thi luon = 0
            if record.trang_thai in ['vang_mat', 'nghi_phep', 'nghi_le', 'nghi_bu']:
                record.so_gio_lam = 0
                continue

            if record.gio_vao and record.gio_ra:
                # Tinh tong gio
                tong_gio = record.gio_ra - record.gio_vao
                
                # Lay thong tin nghi trua tu ca lam viec hoac mac dinh
                if record.ca_lam_viec_id and record.ca_lam_viec_id.nghi_trua:
                    gio_nghi_bat_dau = record.ca_lam_viec_id.gio_nghi_trua_bat_dau
                    gio_nghi_ket_thuc = record.ca_lam_viec_id.gio_nghi_trua_ket_thuc
                else:
                    gio_nghi_bat_dau = 12.0
                    gio_nghi_ket_thuc = 13.0
                
                gio_nghi_trua = gio_nghi_ket_thuc - gio_nghi_bat_dau
                
                # Kiem tra xem co lam qua gio nghi trua khong
                if record.gio_vao < gio_nghi_bat_dau and record.gio_ra > gio_nghi_ket_thuc:
                    record.so_gio_lam = tong_gio - gio_nghi_trua
                else:
                    record.so_gio_lam = tong_gio
                
                # Dam bao so gio khong am
                if record.so_gio_lam < 0:
                    record.so_gio_lam = 0
                    
                # Xac dinh trang thai tu dong
                if record.trang_thai in [False, 'co_mat', 'di_tre', 've_som']:
                    # Lay gio chuan tu ca hoac mac dinh
                    if record.ca_lam_viec_id:
                        gio_vao_chuan = record.ca_lam_viec_id.gio_bat_dau
                        gio_ra_chuan = record.ca_lam_viec_id.gio_ket_thuc
                        cho_phep_tre = record.ca_lam_viec_id.cho_phep_tre_phut / 60.0
                    else:
                        gio_vao_chuan = 8.0
                        gio_ra_chuan = 17.0
                        cho_phep_tre = 0.25  # 15 phut
                    
                    if record.gio_vao > gio_vao_chuan + cho_phep_tre:
                        record.trang_thai = 'di_tre'
                    elif record.gio_ra < gio_ra_chuan:
                        record.trang_thai = 've_som'
                    else:
                        record.trang_thai = 'co_mat'
            else:
                record.so_gio_lam = 0

    @api.depends('gio_vao', 'gio_ra', 'ca_lam_viec_id', 'so_gio_lam')
    def _compute_tang_ca(self):
        """Tinh so gio tang ca"""
        for record in self:
            if record.ca_lam_viec_id and record.so_gio_lam > 0:
                so_gio_chuan = record.ca_lam_viec_id.so_gio_lam_chuan
                if record.so_gio_lam > so_gio_chuan:
                    record.so_gio_tang_ca = record.so_gio_lam - so_gio_chuan
                    # Kiem tra tang ca dem (sau 22h)
                    if record.gio_ra >= 22:
                        record.he_so_tang_ca = record.ca_lam_viec_id.he_so_tang_ca_dem
                    else:
                        record.he_so_tang_ca = record.ca_lam_viec_id.he_so_tang_ca
                else:
                    record.so_gio_tang_ca = 0
                    record.he_so_tang_ca = 1.0
            else:
                record.so_gio_tang_ca = 0
                record.he_so_tang_ca = 1.0

    @api.onchange('trang_thai')
    def _onchange_trang_thai(self):
        """Neu vang mat hoac nghi phep thi so gio lam = 0"""
        if self.trang_thai in ['vang_mat', 'nghi_phep', 'nghi_le', 'nghi_bu']:
            self.gio_vao = 0
            self.gio_ra = 0
            self.so_gio_lam = 0
    
    @api.onchange('ca_lam_viec_id')
    def _onchange_ca_lam_viec(self):
        """Tu dong dien gio vao/ra theo ca"""
        if self.ca_lam_viec_id:
            self.gio_vao = self.ca_lam_viec_id.gio_bat_dau
            self.gio_ra = self.ca_lam_viec_id.gio_ket_thuc
