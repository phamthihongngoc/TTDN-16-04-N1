from odoo import models, fields, api
from datetime import datetime


class NhanVien(models.Model):
    _name = 'nhan_vien'
    _description = 'Nhân viên'
    _order = 'ma_dinh_danh'

    ma_dinh_danh = fields.Char("Mã nhân viên", required=True, copy=False)
    ten_nv = fields.Char("Họ và tên", required=True)
    ngay_sinh = fields.Date("Ngày sinh")
    que_quan = fields.Char("Quê quán")
    dia_chi = fields.Text("Địa chỉ")
    email = fields.Char("Email")
    so_dien_thoai = fields.Char("Số điện thoại")
    chuc_vu = fields.Char("Chức vụ")
    phong_ban = fields.Char("Phòng ban")
    luong_co_ban = fields.Monetary("Lương cơ bản", default=0.0, currency_field='currency_id')
    so_cong_chuan = fields.Integer("Số công chuẩn/tháng", default=26)
    muc_phat_di_tre = fields.Monetary("Mức phạt đi trễ/lần", default=50000.0, currency_field='currency_id', help="Số tiền phạt mỗi lần đi trễ")
    muc_phat_ve_som = fields.Monetary("Mức phạt về sớm/lần", default=50000.0, currency_field='currency_id', help="Số tiền phạt mỗi lần về sớm")
    currency_id = fields.Many2one('res.currency', string='Đơn vị tiền tệ', default=lambda self: self.env.company.currency_id)
    
    # Quan hệ
    cham_cong_ids = fields.One2many('cham_cong', 'nhan_vien_id', string='Chấm công')
    bang_luong_ids = fields.One2many('bang_luong', 'nhan_vien_id', string='Bảng lương')
    
    # Thống kê
    so_ngay_lam_thang = fields.Integer("Số ngày làm tháng này", compute='_compute_thong_ke_thang', store=False)
    so_ngay_di_tre = fields.Integer("Số ngày đi trễ", compute='_compute_thong_ke_thang', store=False)
    so_ngay_vang = fields.Integer("Số ngày vắng", compute='_compute_thong_ke_thang', store=False)
    luong_thang_nay = fields.Monetary("Lương tháng này", compute='_compute_luong_thang_nay', currency_field='currency_id', store=False)
    ty_le_cham_cong = fields.Float("Tỷ lệ chấm công (%)", compute='_compute_thong_ke_thang', store=False)
    
    _sql_constraints = [
        ('ma_nv_unique', 'unique(ma_dinh_danh)', 'Mã nhân viên đã tồn tại!')
    ]
    
    @api.depends('cham_cong_ids', 'cham_cong_ids.ngay_cham_cong', 'cham_cong_ids.trang_thai')
    def _compute_thong_ke_thang(self):
        """Tính thống kê chấm công tháng hiện tại"""
        for record in self:
            today = fields.Date.today()
            thang = today.month
            nam = today.year
            
            # Tìm tất cả chấm công trong tháng
            cham_cong = self.env['cham_cong'].search([
                ('nhan_vien_id', '=', record.id),
                ('ngay_cham_cong', '>=', f'{nam}-{thang:02d}-01'),
                ('ngay_cham_cong', '<=', f'{nam}-{thang:02d}-31')
            ])
            
            record.so_ngay_lam_thang = len(cham_cong.filtered(lambda c: c.trang_thai in ['co_mat', 'di_tre', 've_som']))
            record.so_ngay_di_tre = len(cham_cong.filtered(lambda c: c.trang_thai == 'di_tre'))
            record.so_ngay_vang = len(cham_cong.filtered(lambda c: c.trang_thai == 'vang_mat'))
            
            # Tính tỷ lệ chấm công (dựa trên số công chuẩn)
            if record.so_cong_chuan > 0:
                record.ty_le_cham_cong = (record.so_ngay_lam_thang / record.so_cong_chuan) * 100
            else:
                record.ty_le_cham_cong = 0
    
    @api.depends('bang_luong_ids', 'bang_luong_ids.luong_nhan')
    def _compute_luong_thang_nay(self):
        """Lấy lương tháng hiện tại"""
        for record in self:
            today = fields.Date.today()
            thang = str(today.month)
            nam = today.year
            
            bang_luong = self.env['bang_luong'].search([
                ('nhan_vien_id', '=', record.id),
                ('thang', '=', thang),
                ('nam', '=', nam)
            ], limit=1)
            
            record.luong_thang_nay = bang_luong.luong_nhan if bang_luong else 0
