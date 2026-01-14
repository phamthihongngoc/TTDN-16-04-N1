from odoo import models, fields, api
from odoo.exceptions import ValidationError
import calendar


class NhanVien(models.Model):
    _name = 'nhan_vien'
    _description = 'Nhân viên'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'ten_nv'
    _order = 'ma_dinh_danh'

    company_id = fields.Many2one(
        'res.company',
        string='Công ty',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    image_1920 = fields.Image('Ảnh đại diện')

    ma_dinh_danh = fields.Char(
        "Mã nhân viên",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: 'New',
        tracking=True,
    )
    ten_nv = fields.Char("Họ và tên", required=True)
    ngay_sinh = fields.Date("Ngày sinh")
    que_quan = fields.Char("Quê quán")
    dia_chi = fields.Text("Địa chỉ")
    email = fields.Char("Email", help="Email nội bộ của nhân viên")
    so_dien_thoai = fields.Char("Số điện thoại")

    # Chuẩn hoá chức vụ / phòng ban (giữ field text để tương thích dữ liệu cũ)
    chuc_vu_id = fields.Many2one('nhan_su.chuc_vu', string="Chức vụ", ondelete='restrict', index=True)
    phong_ban_id = fields.Many2one('nhan_su.phong_ban', string="Phòng ban", ondelete='restrict', index=True)
    chuc_vu = fields.Char("Chức vụ (cũ)")
    phong_ban = fields.Char("Phòng ban (cũ)")

    manager_id = fields.Many2one('nhan_vien', string='Quản lý trực tiếp', ondelete='set null')
    
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
    so_cong_chuan = fields.Integer(
        "Số công chuẩn/tháng",
        default=lambda self: self.env.company.nhan_su_so_cong_chuan,
    )
    muc_phat_di_tre = fields.Monetary(
        "Mức phạt đi trễ/lần",
        default=lambda self: self.env.company.nhan_su_muc_phat_di_tre,
        currency_field='currency_id',
        help="Số tiền phạt mỗi lần đi trễ",
    )
    muc_phat_ve_som = fields.Monetary(
        "Mức phạt về sớm/lần",
        default=lambda self: self.env.company.nhan_su_muc_phat_ve_som,
        currency_field='currency_id',
        help="Số tiền phạt mỗi lần về sớm",
    )
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
    
    # KPI tổng hợp từ các module
    kpi = fields.Float("KPI Tổng hợp", compute='_compute_kpi', store=True, help="KPI dựa trên chấm công")
    
    # === SYSTEM INTEGRATION - THỐNG KÊ LIÊN KẾT ===
    # Computed fields để thống kê công việc liên kết với các module khác
    so_van_ban_tao = fields.Integer("Số văn bản đã tạo", compute='_compute_thong_ke_lien_ket', store=True)
    so_van_ban_duyet = fields.Integer("Số văn bản đã duyệt", compute='_compute_thong_ke_lien_ket', store=True)
    so_van_ban_ky = fields.Integer("Số văn bản đã ký", compute='_compute_thong_ke_lien_ket', store=True)
    so_khach_hang_phu_trach = fields.Integer("Số khách hàng phụ trách", compute='_compute_thong_ke_lien_ket', store=True)
    
    _sql_constraints = [
        ('ma_nv_unique', 'unique(ma_dinh_danh)', 'Mã nhân viên đã tồn tại!')
    ]

    def _is_placeholder_ma_dinh_danh(self, value):
        return not value or value in {'New', 'NEW', 'Mới'}

    def _generate_unique_ma_dinh_danh(self):
        for _i in range(100):
            candidate = self.env['ir.sequence'].next_by_code('nhan_vien')
            if self._is_placeholder_ma_dinh_danh(candidate):
                continue
            if not self.sudo().search_count([('ma_dinh_danh', '=', candidate)]):
                return candidate
        return self.env['ir.sequence'].next_by_code('nhan_vien') or 'New'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if self._is_placeholder_ma_dinh_danh(vals.get('ma_dinh_danh')):
                vals['ma_dinh_danh'] = self._generate_unique_ma_dinh_danh()
        records = super().create(vals_list)
        records.with_context(skip_nhan_su_sync=True)._sync_phong_ban_chuc_vu_from_text(create_missing=True)
        return records

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get('skip_nhan_su_sync'):
            self.with_context(skip_nhan_su_sync=True)._sync_phong_ban_chuc_vu_from_text(create_missing=True)
        return res

    def _sync_phong_ban_chuc_vu_from_text(self, create_missing=False):
        """Keep backward compatibility with legacy text fields.

        - If *_id is set, keep text fields updated for reporting/legacy views.
        - If text fields are filled but *_id is empty, optionally create/find matching records.
        """
        for record in self:
            vals_to_write = {}
            # From IDs -> text
            if record.phong_ban_id and not record.phong_ban:
                vals_to_write['phong_ban'] = record.phong_ban_id.name
            if record.chuc_vu_id and not record.chuc_vu:
                vals_to_write['chuc_vu'] = record.chuc_vu_id.name

            # From text -> IDs
            if create_missing:
                if record.phong_ban and not record.phong_ban_id:
                    pb = self.env['nhan_su.phong_ban'].search([
                        ('name', '=', record.phong_ban.strip()),
                        ('company_id', '=', record.company_id.id),
                    ], limit=1)
                    if not pb:
                        pb = self.env['nhan_su.phong_ban'].create({
                            'name': record.phong_ban.strip(),
                            'company_id': record.company_id.id,
                        })
                    vals_to_write['phong_ban_id'] = pb.id

                if record.chuc_vu and not record.chuc_vu_id:
                    cv = self.env['nhan_su.chuc_vu'].search([
                        ('name', '=', record.chuc_vu.strip()),
                        ('company_id', '=', record.company_id.id),
                    ], limit=1)
                    if not cv:
                        cv = self.env['nhan_su.chuc_vu'].create({
                            'name': record.chuc_vu.strip(),
                            'company_id': record.company_id.id,
                        })
                    vals_to_write['chuc_vu_id'] = cv.id

            if vals_to_write:
                record.with_context(skip_nhan_su_sync=True).write(vals_to_write)
    
    @api.model
    def _valid_field_parameter(self, field, name):
        return name == 'tracking' or super()._valid_field_parameter(field, name)
    
    @api.depends('cham_cong_ids', 'cham_cong_ids.ngay_cham_cong', 'cham_cong_ids.trang_thai')
    def _compute_thong_ke_thang(self):
        """Tính thống kê chấm công tháng hiện tại"""
        for record in self:
            today = fields.Date.today()
            thang = today.month
            nam = today.year

            ngay_cuoi = calendar.monthrange(nam, thang)[1]
            
            # Tìm tất cả chấm công trong tháng
            cham_cong = self.env['cham_cong'].search([
                ('nhan_vien_id', '=', record.id),
                ('ngay_cham_cong', '>=', f'{nam}-{thang:02d}-01'),
                ('ngay_cham_cong', '<=', f'{nam}-{thang:02d}-{ngay_cuoi:02d}')
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
            record.so_van_ban_tao = 0
            record.so_van_ban_duyet = 0
            record.so_van_ban_ky = 0
            record.so_khach_hang_phu_trach = 0

            if record.trang_thai_lam_viec != 'dang_lam':
                continue

            # Thống kê văn bản
            if 'van_ban' in self.env:
                van_ban_model = self.env['van_ban']
                if 'nguoi_tao_id' in van_ban_model._fields:
                    record.so_van_ban_tao = van_ban_model.search_count([('nguoi_tao_id', '=', record.id)])
                if 'nguoi_duyet_id' in van_ban_model._fields:
                    record.so_van_ban_duyet = van_ban_model.search_count([('nguoi_duyet_id', '=', record.id)])
                if 'nguoi_ky_id' in van_ban_model._fields:
                    record.so_van_ban_ky = van_ban_model.search_count([('nguoi_ky_id', '=', record.id)])

            # Thống kê khách hàng
            if 'khach_hang' in self.env:
                khach_hang_model = self.env['khach_hang']
                if 'nhan_vien_phu_trach_id' in khach_hang_model._fields:
                    record.so_khach_hang_phu_trach = khach_hang_model.search_count([
                        ('nhan_vien_phu_trach_id', '=', record.id)
                    ])
                
    
    @api.depends('ty_le_cham_cong')
    def _compute_kpi(self):
        """Tính KPI tổng hợp từ chấm công"""
        for record in self:            
            # Tỷ lệ chấm công (100% trọng số)
            ty_le_cham_cong = record.ty_le_cham_cong or 0
            
            # Công thức KPI
            record.kpi = ty_le_cham_cong


    
    @api.model
    def _cron_gui_bao_cao_kpi(self):
        """Cron job gửi báo cáo KPI hàng tháng cho nhân viên"""
        for nhan_vien in self.search([('trang_thai_lam_viec', '=', 'dang_lam')]):
            if nhan_vien.user_id and nhan_vien.user_id.email:
                template = self.env.ref('nhan_su.email_template_bao_cao_kpi', raise_if_not_found=False)
                if template:
                    template.send_mail(nhan_vien.id, force_send=True)
                else:
                    # Gửi email đơn giản
                    mail_values = {
                        'subject': 'Báo cáo KPI tháng này',
                        'body_html': f'<p>Kính chào {nhan_vien.ten_nv},</p><p>KPI của bạn tháng này: {nhan_vien.kpi}</p>',
                        'email_to': nhan_vien.user_id.email,
                    }
                    self.env['mail.mail'].create(mail_values).send()

    # === Onboarding / Offboarding ===
    def _get_user_groups_from_roles(self):
        self.ensure_one()
        groups = self.env['res.groups']
        # Link role -> res.groups (if configured)
        for role in self.vai_tro_ids:
            if role.group_id:
                groups |= role.group_id
        # Fallback default group
        default_group = self.env.ref('nhan_su.group_nhan_vien_kinh_doanh', raise_if_not_found=False)
        if default_group:
            groups |= default_group
        return groups

    def action_create_user_account(self):
        for record in self:
            if record.user_id:
                continue
            if not record.email:
                raise ValidationError('Cần Email để tạo tài khoản người dùng!')

            existing = self.env['res.users'].sudo().search([('login', '=', record.email)], limit=1)
            if existing:
                record.user_id = existing.id
                continue

            groups = record._get_user_groups_from_roles()
            user_vals = {
                'name': record.ten_nv,
                'login': record.email,
                'email': record.email,
                'company_id': record.company_id.id,
                'company_ids': [(4, record.company_id.id)],
                'groups_id': [(6, 0, groups.ids)],
            }
            user = self.env['res.users'].sudo().create(user_vals)
            record.user_id = user.id

    def action_offboard(self):
        today = fields.Date.today()
        for record in self:
            vals = {
                'trang_thai_lam_viec': 'nghi_viec',
                'ngay_nghi_viec': record.ngay_nghi_viec or today,
            }
            record.write(vals)
            if record.user_id:
                record.user_id.sudo().write({'active': False})

    def action_reactivate(self):
        for record in self:
            record.write({'trang_thai_lam_viec': 'dang_lam', 'ngay_nghi_viec': False})
            if record.user_id:
                record.user_id.sudo().write({'active': True})

    def action_apply_company_defaults(self):
        for record in self:
            vals = {}
            if not record.so_cong_chuan:
                vals['so_cong_chuan'] = record.company_id.nhan_su_so_cong_chuan
            if not record.muc_phat_di_tre:
                vals['muc_phat_di_tre'] = record.company_id.nhan_su_muc_phat_di_tre
            if not record.muc_phat_ve_som:
                vals['muc_phat_ve_som'] = record.company_id.nhan_su_muc_phat_ve_som
            if vals:
                record.write(vals)

    # === Smart button actions ===
    def action_view_cham_cong(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Chấm công',
            'res_model': 'cham_cong',
            'view_mode': 'tree,form,calendar,pivot,graph',
            'domain': [('nhan_vien_id', '=', self.id)],
            'context': {'default_nhan_vien_id': self.id},
        }

    def action_view_bang_luong(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Bảng lương',
            'res_model': 'bang_luong',
            'view_mode': 'tree,form,pivot,graph',
            'domain': [('nhan_vien_id', '=', self.id)],
            'context': {'default_nhan_vien_id': self.id},
        }

    def action_view_khach_hang(self):
        self.ensure_one()
        if 'khach_hang' not in self.env:
            return False
        return {
            'type': 'ir.actions.act_window',
            'name': 'Khách hàng phụ trách',
            'res_model': 'khach_hang',
            'view_mode': 'tree,form',
            'domain': [('nhan_vien_phu_trach_id', '=', self.id)],
            'context': {'default_nhan_vien_phu_trach_id': self.id},
        }

    def action_view_van_ban(self):
        self.ensure_one()
        if 'van_ban' not in self.env:
            return False
        # Prefer creator field if exists
        domain = []
        if 'nguoi_tao_id' in self.env['van_ban']._fields:
            domain = [('nguoi_tao_id', '=', self.id)]
        return {
            'type': 'ir.actions.act_window',
            'name': 'Văn bản',
            'res_model': 'van_ban',
            'view_mode': 'tree,form',
            'domain': domain,
        }
    
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
            if record.ngay_nghi_viec and record.ngay_vao_lam and record.ngay_nghi_viec < record.ngay_vao_lam:
                raise ValidationError('Ngày nghỉ việc không thể trước ngày vào làm!')
