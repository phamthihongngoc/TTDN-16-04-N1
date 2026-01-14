# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ChamCong(models.Model):
    _name = 'cham_cong'
    _description = 'Chấm công nhân viên'
    _order = 'ngay_cham_cong desc'

    nhan_vien_id = fields.Many2one('nhan_vien', string='Nhân viên', required=True, ondelete='cascade')
    ngay_cham_cong = fields.Date('Ngày chấm công', required=True, default=fields.Date.context_today)
    gio_vao = fields.Float('Giờ vào', help='Ví dụ: 7.5 = 7h30')
    gio_ra = fields.Float('Giờ ra', help='Ví dụ: 17.5 = 17h30')
    so_gio_lam = fields.Float('Số giờ làm', compute='_compute_so_gio_lam', store=True)
    trang_thai = fields.Selection([
        ('co_mat', 'Có mặt'),
        ('vang_mat', 'Vắng mặt'),
        ('nghi_phep', 'Nghỉ phép'),
        ('di_tre', 'Đi trễ'),
        ('ve_som', 'Về sớm')
    ], string='Trạng thái', default='co_mat')
    ghi_chu = fields.Text('Ghi chú')

    _sql_constraints = [
        ('unique_nhan_vien_ngay', 'unique(nhan_vien_id, ngay_cham_cong)', 
         'Một nhân viên chỉ có một bản ghi chấm công mỗi ngày!')
    ]

    @api.depends('gio_vao', 'gio_ra')
    def _compute_so_gio_lam(self):
        """Tính số giờ làm việc, trừ giờ nghỉ trưa (12h-13h30 = 1.5 giờ)"""
        for record in self:
            # Nếu là vắng mặt / nghỉ phép thì luôn = 0, không auto-đè trạng thái
            if record.trang_thai in ['vang_mat', 'nghi_phep']:
                record.so_gio_lam = 0
                continue

            if record.gio_vao and record.gio_ra:
                # Tính tổng giờ
                tong_gio = record.gio_ra - record.gio_vao
                
                # Trừ giờ nghỉ trưa 1.5 giờ (12h-13h30)
                gio_nghi_trua = 1.5
                
                # Kiểm tra xem có làm qua giờ nghỉ trưa không
                if record.gio_vao < 12 and record.gio_ra > 13.5:
                    record.so_gio_lam = tong_gio - gio_nghi_trua
                else:
                    record.so_gio_lam = tong_gio
                
                # Đảm bảo số giờ không âm
                if record.so_gio_lam < 0:
                    record.so_gio_lam = 0
                    
                # Xác định trạng thái (chỉ auto khi trạng thái hiện tại không phải do người dùng chọn)
                if record.trang_thai in [False, 'co_mat', 'di_tre', 've_som']:
                    if record.gio_vao > 7.5:  # Vào sau 7h30
                        record.trang_thai = 'di_tre'
                    elif record.gio_ra < 17.5:  # Ra trước 17h30
                        record.trang_thai = 've_som'
                    else:
                        record.trang_thai = 'co_mat'
            else:
                record.so_gio_lam = 0

    @api.onchange('trang_thai')
    def _onchange_trang_thai(self):
        """Nếu vắng mặt hoặc nghỉ phép thì số giờ làm = 0"""
        if self.trang_thai in ['vang_mat', 'nghi_phep']:
            self.gio_vao = 0
            self.gio_ra = 0
            self.so_gio_lam = 0
