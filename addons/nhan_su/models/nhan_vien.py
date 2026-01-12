from odoo import models, fields, api
from datetime import datetime


class NhanVien(models.Model):
    _name = 'nhan_vien'
    _description = 'Nhân viên'
    _rec_name = 'ten_nv'
    _order = 'ma_dinh_danh'

    ma_dinh_danh = fields.Char("Mã nhân viên", required=True, copy=False)
    ten_nv = fields.Char("Họ và tên", required=True)
    ngay_sinh = fields.Date("Ngày sinh")
    que_quan = fields.Char("Quê quán")
    dia_chi = fields.Text("Địa chỉ")
    email = fields.Char("Email", help="Email nội bộ của nhân viên")
    so_dien_thoai = fields.Char("Số điện thoại")
    chuc_vu = fields.Char("Chức vụ")
    phong_ban = fields.Char("Phòng ban")
    
    # Trạng thái làm việc
    trang_thai_lam_viec = fields.Selection([
        ('dang_lam', 'Đang làm việc'),
        ('nghi_viec', 'Nghỉ việc'),
        ('tam_nghi', 'Tạm nghỉ')
    ], string='Trạng thái', default='dang_lam', required=True, tracking=True)
    ngay_vao_lam = fields.Date("Ngày vào làm", help="Ngày bắt đầu làm việc tại công ty")
    ngay_nghi_viec = fields.Date("Ngày nghỉ việc", help="Ngày kết thúc làm việc")
    
    # Vai trò và quyền hạn
    vai_tro_ids = fields.Many2many('vai_tro', string='Vai trò', 
                                    help='Vai trò của nhân viên trong quy trình xử lý văn bản')
    user_id = fields.Many2one('res.users', string='Người dùng hệ thống', 
                              help='Liên kết với tài khoản đăng nhập')
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
    
    # === SYSTEM INTEGRATION - THỐNG KÊ LIÊN KẾT ===
    # Computed fields để thống kê công việc liên kết với các module khác
    so_van_ban_tao = fields.Integer("Số văn bản đã tạo", compute='_compute_thong_ke_lien_ket', store=True)
    so_van_ban_duyet = fields.Integer("Số văn bản đã duyệt", compute='_compute_thong_ke_lien_ket', store=True)
    so_van_ban_ky = fields.Integer("Số văn bản đã ký", compute='_compute_thong_ke_lien_ket', store=True)
    so_khach_hang_phu_trach = fields.Integer("Số khách hàng phụ trách", compute='_compute_thong_ke_lien_ket', store=True)
    
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
    
    # === SYSTEM INTEGRATION COMPUTE METHODS ===
    @api.depends('trang_thai_lam_viec')
    def _compute_thong_ke_lien_ket(self):
        """Thống kê công việc liên kết với các module khác (van_ban, khach_hang)"""
        for record in self:
            if record.trang_thai_lam_viec == 'dang_lam':
                # Thống kê văn bản - chỉ tính nếu model van_ban có sẵn
                try:
                    van_ban_model = self.env.get('van_ban')
                    if van_ban_model:
                        record.so_van_ban_tao = van_ban_model.search_count([('nguoi_tao_id', '=', record.id)])
                        record.so_van_ban_duyet = van_ban_model.search_count([('nguoi_duyet_id', '=', record.id)])
                        record.so_van_ban_ky = van_ban_model.search_count([('nguoi_ky_id', '=', record.id)])
                    else:
                        record.so_van_ban_tao = 0
                        record.so_van_ban_duyet = 0
                        record.so_van_ban_ky = 0
                except:
                    record.so_van_ban_tao = 0
                    record.so_van_ban_duyet = 0
                    record.so_van_ban_ky = 0
                
                # Thống kê khách hàng - chỉ tính nếu model khach_hang có sẵn
                try:
                    khach_hang_model = self.env.get('khach_hang')
                    if khach_hang_model:
                        record.so_khach_hang_phu_trach = khach_hang_model.search_count([('nhan_vien_phu_trach_id', '=', record.id)])
                    else:
                        record.so_khach_hang_phu_trach = 0
                except:
                    record.so_khach_hang_phu_trach = 0
            else:
                # Nếu không còn làm việc, reset về 0
                record.so_van_ban_tao = 0
                record.so_van_ban_duyet = 0
                record.so_van_ban_ky = 0
                record.so_khach_hang_phu_trach = 0
                record.so_van_ban_ky = 0
                record.so_khach_hang_phu_trach = 0
    
    # === SYSTEM INTEGRATION CONSTRAINTS ===
    @api.constrains('email')
    def _check_email_format(self):
        """Đảm bảo email có định dạng hợp lệ"""
        for record in self:
            if record.email and '@' not in record.email:
                raise ValidationError('Email phải có định dạng hợp lệ!')
    
    @api.constrains('trang_thai_lam_viec', 'ngay_nghi_viec')
    def _check_ngay_nghi_viec(self):
        """Đảm bảo logic ngày nghỉ việc"""
        for record in self:
            if record.trang_thai_lam_viec == 'nghi_viec' and not record.ngay_nghi_viec:
                raise ValidationError('Phải nhập ngày nghỉ việc khi trạng thái là "Nghỉ việc"!')
            if record.ngay_nghi_viec and record.ngay_nghi_viec < record.ngay_vao_lam:
                raise ValidationError('Ngày nghỉ việc không thể trước ngày vào làm!')
