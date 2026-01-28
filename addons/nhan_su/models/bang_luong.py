# -*- coding: utf-8 -*-

from odoo import models, fields, api
from datetime import datetime
import calendar


class BangLuong(models.Model):
    _name = 'bang_luong'
    _description = 'Bang luong nhan vien'
    _order = 'thang desc, nam desc'

    nhan_vien_id = fields.Many2one('nhan_vien', string='Nhan vien', required=True, ondelete='cascade')
    thang = fields.Selection([
        ('1', 'Thang 1'),
        ('2', 'Thang 2'),
        ('3', 'Thang 3'),
        ('4', 'Thang 4'),
        ('5', 'Thang 5'),
        ('6', 'Thang 6'),
        ('7', 'Thang 7'),
        ('8', 'Thang 8'),
        ('9', 'Thang 9'),
        ('10', 'Thang 10'),
        ('11', 'Thang 11'),
        ('12', 'Thang 12'),
    ], string='Thang', required=True)
    nam = fields.Integer('Nam', required=True, default=lambda self: fields.Date.today().year)
    
    # Thong tin cong
    so_cong_chuan = fields.Integer('So cong chuan', related='nhan_vien_id.so_cong_chuan', store=True)
    so_cong_thuc_te = fields.Float('So cong thuc te', compute='_compute_so_cong', store=True)
    
    # Thong ke di tre/ve som
    so_lan_di_tre = fields.Integer('So lan di tre', compute='_compute_so_cong', store=True)
    so_lan_ve_som = fields.Integer('So lan ve som', compute='_compute_so_cong', store=True)
    phat_di_tre_ve_som = fields.Monetary('Phat di tre/ve som', compute='_compute_phat_tu_dong', store=True, currency_field='currency_id')
    
    # Tang ca
    so_gio_tang_ca = fields.Float('So gio tang ca', compute='_compute_so_cong', store=True)
    luong_tang_ca = fields.Monetary('Luong tang ca', compute='_compute_luong', store=True, currency_field='currency_id')
    
    # Nghi phep
    so_ngay_nghi_phep = fields.Float('So ngay nghi phep', compute='_compute_so_cong', store=True)
    so_ngay_nghi_khong_luong = fields.Float('Nghi khong luong', compute='_compute_so_cong', store=True)
    
    # Thong tin luong
    luong_co_ban = fields.Monetary('Luong co ban', related='nhan_vien_id.luong_co_ban', store=True, currency_field='currency_id')
    luong_theo_cong = fields.Monetary('Luong theo cong', compute='_compute_luong', store=True, currency_field='currency_id')
    
    # Phu cap
    tong_phu_cap = fields.Monetary('Tong phu cap', compute='_compute_phu_cap', store=True, currency_field='currency_id')
    chi_tiet_phu_cap = fields.Text('Chi tiet phu cap', compute='_compute_phu_cap', store=True)
    
    # Khau tru BHXH
    luong_dong_bhxh = fields.Monetary('Luong dong BHXH', compute='_compute_bhxh', store=True, currency_field='currency_id')
    khau_tru_bhxh = fields.Monetary('Khau tru BHXH (NLD)', compute='_compute_bhxh', store=True, currency_field='currency_id')
    bhxh_doanh_nghiep = fields.Monetary('BHXH (DN dong)', compute='_compute_bhxh', store=True, currency_field='currency_id')
    
    # Thue TNCN
    thu_nhap_chiu_thue = fields.Monetary('Thu nhap chiu thue', compute='_compute_thue_tncn', store=True, currency_field='currency_id')
    so_nguoi_phu_thuoc = fields.Integer('So nguoi phu thuoc', default=0)
    thue_tncn = fields.Monetary('Thue TNCN', compute='_compute_thue_tncn', store=True, currency_field='currency_id')
    
    thuong = fields.Monetary('Thuong', default=0.0, currency_field='currency_id')
    phat = fields.Monetary('Phat khac', default=0.0, currency_field='currency_id', help="Cac khoan phat khac")
    luong_nhan = fields.Monetary('Luong nhan', compute='_compute_luong', store=True, currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', string='Don vi tien te', default=lambda self: self.env.company.currency_id)
    
    trang_thai = fields.Selection([
        ('chua_duyet', 'Chua duyet'),
        ('da_duyet', 'Da duyet'),
        ('da_thanh_toan', 'Da thanh toan')
    ], string='Trang thai', default='chua_duyet')
    
    ghi_chu = fields.Text('Ghi chu')

    _sql_constraints = [
        ('unique_nhan_vien_thang_nam', 'unique(nhan_vien_id, thang, nam)', 
         'Mot nhan vien chi co mot bang luong moi thang!')
    ]

    @api.depends('nhan_vien_id', 'thang', 'nam')
    def _compute_so_cong(self):
        """Tinh tong so cong trong thang tu bang cham cong"""
        for record in self:
            if record.nhan_vien_id and record.thang and record.nam:
                # Tinh ngay cuoi thang chinh xac
                thang_int = int(record.thang)
                ngay_cuoi = calendar.monthrange(record.nam, thang_int)[1]
                
                # Format ngay bat dau va ket thuc
                ngay_bat_dau = f'{record.nam}-{str(thang_int).zfill(2)}-01'
                ngay_ket_thuc = f'{record.nam}-{str(thang_int).zfill(2)}-{str(ngay_cuoi).zfill(2)}'
                
                # Lay tat ca ban ghi cham cong trong thang
                domain = [
                    ('nhan_vien_id', '=', record.nhan_vien_id.id),
                    ('ngay_cham_cong', '>=', ngay_bat_dau),
                    ('ngay_cham_cong', '<=', ngay_ket_thuc),
                ]
                cham_cong_records = self.env['cham_cong'].search(domain)
                
                # Tinh cong lam viec (khong tinh vang mat va nghi khong luong)
                lam_viec_records = cham_cong_records.filtered(
                    lambda c: c.trang_thai in ['co_mat', 'di_tre', 've_som', 'nghi_phep', 'nghi_le', 'nghi_bu']
                )
                tong_gio = sum(lam_viec_records.mapped('so_gio_lam'))
                record.so_cong_thuc_te = tong_gio / 8.0
                
                # Tinh tang ca
                record.so_gio_tang_ca = sum(cham_cong_records.mapped('so_gio_tang_ca'))
                
                # Dem so lan di tre va ve som
                record.so_lan_di_tre = len(cham_cong_records.filtered(lambda c: c.trang_thai == 'di_tre'))
                record.so_lan_ve_som = len(cham_cong_records.filtered(lambda c: c.trang_thai == 've_som'))
                
                # Tinh ngay nghi phep
                nghi_phep_records = cham_cong_records.filtered(lambda c: c.trang_thai == 'nghi_phep')
                record.so_ngay_nghi_phep = len(nghi_phep_records)
                
                # Tinh nghi khong luong
                nghi_kl_records = cham_cong_records.filtered(lambda c: c.trang_thai == 'vang_mat')
                record.so_ngay_nghi_khong_luong = len(nghi_kl_records)
            else:
                record.so_cong_thuc_te = 0
                record.so_lan_di_tre = 0
                record.so_lan_ve_som = 0
                record.so_gio_tang_ca = 0
                record.so_ngay_nghi_phep = 0
                record.so_ngay_nghi_khong_luong = 0

    @api.depends('nhan_vien_id', 'so_lan_di_tre', 'so_lan_ve_som')
    def _compute_phat_tu_dong(self):
        """Tinh tu dong tien phat di tre va ve som"""
        for record in self:
            if record.nhan_vien_id:
                phat_di_tre = record.so_lan_di_tre * record.nhan_vien_id.muc_phat_di_tre
                phat_ve_som = record.so_lan_ve_som * record.nhan_vien_id.muc_phat_ve_som
                record.phat_di_tre_ve_som = phat_di_tre + phat_ve_som
            else:
                record.phat_di_tre_ve_som = 0

    @api.depends('nhan_vien_id', 'thang', 'nam')
    def _compute_phu_cap(self):
        """Tinh tong phu cap"""
        for record in self:
            if record.nhan_vien_id:
                # Lay phu cap con hieu luc
                phu_cap_records = self.env['phu_cap_nhan_vien'].search([
                    ('nhan_vien_id', '=', record.nhan_vien_id.id),
                    ('con_hieu_luc', '=', True)
                ])
                
                tong = 0
                chi_tiet = []
                for pc in phu_cap_records:
                    if pc.loai_phu_cap_id.loai_tinh == 'co_dinh':
                        so_tien = pc.so_tien
                    elif pc.loai_phu_cap_id.loai_tinh == 'theo_cong':
                        so_tien = pc.so_tien * record.so_cong_thuc_te
                    else:  # theo_gio
                        so_tien = pc.so_tien * (record.so_cong_thuc_te * 8)
                    
                    tong += so_tien
                    chi_tiet.append(f"{pc.loai_phu_cap_id.name}: {so_tien:,.0f}")
                
                record.tong_phu_cap = tong
                record.chi_tiet_phu_cap = '\n'.join(chi_tiet) if chi_tiet else ''
            else:
                record.tong_phu_cap = 0
                record.chi_tiet_phu_cap = ''

    @api.depends('luong_co_ban', 'tong_phu_cap')
    def _compute_bhxh(self):
        """Tinh khau tru BHXH"""
        for record in self:
            # Lay cau hinh BHXH hien tai
            config = self.env['cau_hinh_bhxh'].get_current_config()
            
            if config and record.luong_co_ban:
                # Tinh luong dong BHXH (luong co ban + phu cap tinh vao BHXH)
                phu_cap_bhxh = 0
                if record.nhan_vien_id:
                    phu_cap_records = self.env['phu_cap_nhan_vien'].search([
                        ('nhan_vien_id', '=', record.nhan_vien_id.id),
                        ('con_hieu_luc', '=', True),
                        ('loai_phu_cap_id.tinh_vao_bhxh', '=', True)
                    ])
                    phu_cap_bhxh = sum(phu_cap_records.mapped('so_tien'))
                
                luong_dong = record.luong_co_ban + phu_cap_bhxh
                # Gioi han muc toi da
                if luong_dong > config.luong_toi_da_bhxh:
                    luong_dong = config.luong_toi_da_bhxh
                
                record.luong_dong_bhxh = luong_dong
                record.khau_tru_bhxh = luong_dong * config.tong_ty_le_nld / 100
                record.bhxh_doanh_nghiep = luong_dong * config.tong_ty_le_dn / 100
            else:
                record.luong_dong_bhxh = 0
                record.khau_tru_bhxh = 0
                record.bhxh_doanh_nghiep = 0

    @api.depends('luong_theo_cong', 'tong_phu_cap', 'thuong', 'khau_tru_bhxh', 'so_nguoi_phu_thuoc')
    def _compute_thue_tncn(self):
        """Tinh thue thu nhap ca nhan"""
        for record in self:
            config = self.env['cau_hinh_bhxh'].get_current_config()
            
            if config:
                # Thu nhap truoc thue
                thu_nhap = record.luong_theo_cong + record.tong_phu_cap + record.thuong + record.luong_tang_ca
                
                # Tru BHXH
                thu_nhap -= record.khau_tru_bhxh
                
                # Tru giam tru gia canh
                giam_tru = config.giam_tru_ban_than + (record.so_nguoi_phu_thuoc * config.giam_tru_nguoi_phu_thuoc)
                
                thu_nhap_chiu_thue = thu_nhap - giam_tru
                record.thu_nhap_chiu_thue = max(0, thu_nhap_chiu_thue)
                
                # Tinh thue theo bieu luy tien
                record.thue_tncn = self.env['bang_thue_tncn'].tinh_thue_tncn(record.thu_nhap_chiu_thue)
            else:
                record.thu_nhap_chiu_thue = 0
                record.thue_tncn = 0

    @api.depends('luong_co_ban', 'so_cong_thuc_te', 'so_cong_chuan', 'thuong', 'phat', 
                 'phat_di_tre_ve_som', 'tong_phu_cap', 'khau_tru_bhxh', 'thue_tncn',
                 'so_gio_tang_ca')
    def _compute_luong(self):
        """
        Cong thuc: Luong nhan = Luong theo cong + Phu cap + Tang ca + Thuong - Phat - BHXH - Thue TNCN
        """
        for record in self:
            # Tinh luong theo cong
            if record.so_cong_chuan > 0:
                record.luong_theo_cong = (record.so_cong_thuc_te * record.luong_co_ban) / record.so_cong_chuan
            else:
                record.luong_theo_cong = 0
            
            # Tinh luong tang ca
            if record.so_gio_tang_ca > 0 and record.so_cong_chuan > 0:
                luong_gio = record.luong_co_ban / record.so_cong_chuan / 8
                record.luong_tang_ca = record.so_gio_tang_ca * luong_gio * 1.5  # He so tang ca mac dinh
            else:
                record.luong_tang_ca = 0
            
            # Tinh luong nhan
            record.luong_nhan = (
                record.luong_theo_cong 
                + record.tong_phu_cap 
                + record.luong_tang_ca
                + record.thuong 
                - record.phat 
                - record.phat_di_tre_ve_som
                - record.khau_tru_bhxh
                - record.thue_tncn
            )

    def action_duyet(self):
        """Duyet bang luong"""
        self.write({'trang_thai': 'da_duyet'})

    def action_thanh_toan(self):
        """Thanh toan luong"""
        self.write({'trang_thai': 'da_thanh_toan'})

    def action_tinh_lai_luong(self):
        """Tinh lai luong (force recompute)"""
        for record in self:
            record._compute_so_cong()
            record._compute_phu_cap()
            record._compute_bhxh()
            record._compute_thue_tncn()
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
