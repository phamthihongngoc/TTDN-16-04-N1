# -*- coding: utf-8 -*-

from odoo import models, fields, api
from datetime import datetime
import calendar


class BangLuong(models.Model):
    _name = 'bang_luong'
    _description = 'Bảng lương nhân viên'
    _order = 'thang desc, nam desc'

    nhan_vien_id = fields.Many2one('nhan_vien', string='Nhân viên', required=True, ondelete='cascade')
    thang = fields.Selection([
        ('1', 'Tháng 1'),
        ('2', 'Tháng 2'),
        ('3', 'Tháng 3'),
        ('4', 'Tháng 4'),
        ('5', 'Tháng 5'),
        ('6', 'Tháng 6'),
        ('7', 'Tháng 7'),
        ('8', 'Tháng 8'),
        ('9', 'Tháng 9'),
        ('10', 'Tháng 10'),
        ('11', 'Tháng 11'),
        ('12', 'Tháng 12'),
    ], string='Tháng', required=True)
    nam = fields.Integer('Năm', required=True, default=lambda self: fields.Date.today().year)
    
    # Thông tin công
    so_cong_chuan = fields.Integer('Số công chuẩn', related='nhan_vien_id.so_cong_chuan', store=True)
    so_cong_thuc_te = fields.Float('Số công thực tế', compute='_compute_so_cong', store=True)
    
    # Thống kê đi trễ/về sớm
    so_lan_di_tre = fields.Integer('Số lần đi trễ', compute='_compute_so_cong', store=True)
    so_lan_ve_som = fields.Integer('Số lần về sớm', compute='_compute_so_cong', store=True)
    phat_di_tre_ve_som = fields.Monetary('Phạt đi trễ/về sớm', compute='_compute_phat_tu_dong', store=True, currency_field='currency_id')
    
    # Thông tin lương
    luong_co_ban = fields.Monetary('Lương cơ bản', related='nhan_vien_id.luong_co_ban', store=True, currency_field='currency_id')
    luong_theo_cong = fields.Monetary('Lương theo công', compute='_compute_luong', store=True, currency_field='currency_id')
    thuong = fields.Monetary('Thưởng', default=0.0, currency_field='currency_id')
    phat = fields.Monetary('Phạt khác', default=0.0, currency_field='currency_id', help="Các khoản phạt khác (không bao gồm đi trễ/về sớm)")
    luong_nhan = fields.Monetary('Lương nhận', compute='_compute_luong', store=True, currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', string='Đơn vị tiền tệ', default=lambda self: self.env.company.currency_id)
    
    trang_thai = fields.Selection([
        ('chua_duyet', 'Chưa duyệt'),
        ('da_duyet', 'Đã duyệt'),
        ('da_thanh_toan', 'Đã thanh toán')
    ], string='Trạng thái', default='chua_duyet')
    
    ghi_chu = fields.Text('Ghi chú')

    _sql_constraints = [
        ('unique_nhan_vien_thang_nam', 'unique(nhan_vien_id, thang, nam)', 
         'Một nhân viên chỉ có một bảng lương mỗi tháng!')
    ]

    @api.depends('nhan_vien_id', 'thang', 'nam')
    def _compute_so_cong(self):
        """Tính tổng số công trong tháng từ bảng chấm công"""
        for record in self:
            if record.nhan_vien_id and record.thang and record.nam:
                # Tính ngày cuối tháng chính xác
                thang_int = int(record.thang)
                ngay_cuoi = calendar.monthrange(record.nam, thang_int)[1]
                
                # Format ngày bắt đầu và kết thúc
                ngay_bat_dau = f'{record.nam}-{str(thang_int).zfill(2)}-01'
                ngay_ket_thuc = f'{record.nam}-{str(thang_int).zfill(2)}-{str(ngay_cuoi).zfill(2)}'
                
                # Lấy tất cả bản ghi chấm công trong tháng
                domain = [
                    ('nhan_vien_id', '=', record.nhan_vien_id.id),
                    ('ngay_cham_cong', '>=', ngay_bat_dau),
                    ('ngay_cham_cong', '<=', ngay_ket_thuc),
                    ('trang_thai', 'in', ['co_mat', 'di_tre', 've_som'])  # Không tính vắng mặt và nghỉ phép
                ]
                cham_cong_records = self.env['cham_cong'].search(domain)
                
                # Tính công: 1 ngày làm đủ 8 giờ = 1 công
                tong_gio = sum(cham_cong_records.mapped('so_gio_lam'))
                record.so_cong_thuc_te = tong_gio / 8.0
                
                # Đếm số lần đi trễ và về sớm
                record.so_lan_di_tre = len(cham_cong_records.filtered(lambda c: c.trang_thai == 'di_tre'))
                record.so_lan_ve_som = len(cham_cong_records.filtered(lambda c: c.trang_thai == 've_som'))
            else:
                record.so_cong_thuc_te = 0
                record.so_lan_di_tre = 0
                record.so_lan_ve_som = 0

    @api.depends('nhan_vien_id', 'so_lan_di_tre', 'so_lan_ve_som')
    def _compute_phat_tu_dong(self):
        """Tính tự động tiền phạt đi trễ và về sớm"""
        for record in self:
            if record.nhan_vien_id:
                phat_di_tre = record.so_lan_di_tre * record.nhan_vien_id.muc_phat_di_tre
                phat_ve_som = record.so_lan_ve_som * record.nhan_vien_id.muc_phat_ve_som
                record.phat_di_tre_ve_som = phat_di_tre + phat_ve_som
            else:
                record.phat_di_tre_ve_som = 0

    @api.depends('luong_co_ban', 'so_cong_thuc_te', 'so_cong_chuan', 'thuong', 'phat', 'phat_di_tre_ve_som')
    def _compute_luong(self):
        """
        Công thức: Lương nhận = (Số công × Lương cơ bản) / Số công chuẩn + Thưởng - Phạt khác - Phạt đi trễ/về sớm
        """
        for record in self:
            # Tính lương theo công
            if record.so_cong_chuan > 0:
                record.luong_theo_cong = (record.so_cong_thuc_te * record.luong_co_ban) / record.so_cong_chuan
            else:
                record.luong_theo_cong = 0
            
            # Tính lương nhận = lương theo công + thưởng - phạt khác - phạt đi trễ/về sớm
            record.luong_nhan = record.luong_theo_cong + record.thuong - record.phat - record.phat_di_tre_ve_som

    def action_duyet(self):
        """Duyệt bảng lương"""
        self.write({'trang_thai': 'da_duyet'})

    def action_thanh_toan(self):
        """Thanh toán lương"""
        self.write({'trang_thai': 'da_thanh_toan'})

    def action_tinh_lai_luong(self):
        """Tính lại lương (force recompute)"""
        for record in self:
            record._compute_so_cong()
            record._compute_luong()
        return True
    
    @api.model
    def action_tao_bang_luong_thang_nay(self):
        """Tạo bảng lương cho tất cả nhân viên chưa có trong tháng hiện tại"""
        today = fields.Date.today()
        thang = str(today.month)
        nam = today.year
        
        # Lấy tất cả nhân viên
        nhan_vien_ids = self.env['nhan_vien'].search([])
        
        created_count = 0
        for nv in nhan_vien_ids:
            # Kiểm tra xem nhân viên đã có bảng lương tháng này chưa
            existing = self.search([
                ('nhan_vien_id', '=', nv.id),
                ('thang', '=', thang),
                ('nam', '=', nam)
            ])
            
            # Nếu chưa có thì tạo mới
            if not existing:
                self.create({
                    'nhan_vien_id': nv.id,
                    'thang': thang,
                    'nam': nam,
                })
                created_count += 1
        
        # Thông báo kết quả
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Thành công!',
                'message': f'Đã tạo {created_count} bảng lương mới cho tháng {thang}/{nam}',
                'type': 'success',
                'sticky': False,
            }
        }
