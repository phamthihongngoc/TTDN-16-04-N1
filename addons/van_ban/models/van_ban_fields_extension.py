# -*- coding: utf-8 -*-
"""
Extension fields cho van_ban model
Thêm các trường: Độ mật, Độ khẩn, Hạn xử lý, Ủy quyền, Phiên bản
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import timedelta
import logging

_logger = logging.getLogger(__name__)


class VanBanFieldsExtension(models.Model):
    _inherit = 'van_ban'

    # === Trường phân loại theo quy định ===
    so_hieu_van_ban = fields.Char(
        string='Số hiệu văn bản',
        help="Số hiệu văn bản theo quy định (VD: 123/QĐ-UBND)",
        tracking=True,
        copy=False,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('so_hieu_van_ban'):
                seq = self.env['ir.sequence'].next_by_code('van_ban.so_hieu')
                if seq:
                    year = fields.Date.today().strftime('%Y')
                    suffix = ''
                    loai_id = vals.get('loai_van_ban_id')
                    if loai_id:
                        loai = self.env['loai_van_ban'].browse(loai_id)
                        if loai.exists() and loai.ma_loai:
                            suffix = f"/{loai.ma_loai}"
                    vals['so_hieu_van_ban'] = f"{seq}/{year}{suffix}"
        return super().create(vals_list)
    
    co_quan_ban_hanh = fields.Char(
        string='Cơ quan ban hành',
        help="Tên cơ quan/đơn vị ban hành văn bản",
    )
    
    # === Độ mật, độ khẩn ===
    do_mat = fields.Selection([
        ('thuong', '🟢 Thường'),
        ('mat', '🟡 Mật'),
        ('toi_mat', '🟠 Tối mật'),
        ('tuyet_mat', '🔴 Tuyệt mật'),
    ], string='Độ mật', default='thuong', tracking=True,
       help="Phân loại mức độ bảo mật của văn bản")
    
    do_khan = fields.Selection([
        ('thuong', 'Thường'),
        ('khan', '⚡ Khẩn'),
        ('thuong_khan', '⚡⚡ Thượng khẩn'),
        ('hoa_toc', '🔥 Hỏa tốc'),
    ], string='Độ khẩn', default='thuong', tracking=True,
       help="Mức độ ưu tiên xử lý văn bản")
    
    # === Hạn xử lý ===
    han_xu_ly = fields.Datetime(
        string='Hạn xử lý',
        tracking=True,
        help="Thời hạn phải hoàn thành xử lý văn bản",
    )
    
    qua_han = fields.Boolean(
        string='Quá hạn',
        compute='_compute_qua_han',
        store=True,
    )
    
    so_gio_con_lai = fields.Float(
        string='Số giờ còn lại',
        compute='_compute_qua_han',
        store=True,
    )
    
    # === Ủy quyền ===
    nguoi_uy_quyen_id = fields.Many2one(
        'nhan_vien',
        string='Người được ủy quyền ký',
        help="Người được ủy quyền ký thay khi người ký chính vắng",
        tracking=True,
    )
    
    ly_do_uy_quyen = fields.Text(string='Lý do ủy quyền')
    
    ngay_uy_quyen_tu = fields.Date(string='Ủy quyền từ ngày')
    ngay_uy_quyen_den = fields.Date(string='Ủy quyền đến ngày')
    
    ky_thay = fields.Boolean(
        string='Ký thay',
        default=False,
        readonly=True,
        help="Đánh dấu văn bản được ký bởi người ủy quyền",
    )
    
    # === Phiên bản ===
    version = fields.Integer(string='Phiên bản', default=1, readonly=True)
    version_note = fields.Text(string='Ghi chú phiên bản')
    parent_version_id = fields.Many2one('van_ban', string='Phiên bản gốc', readonly=True)
    child_version_ids = fields.One2many('van_ban', 'parent_version_id', string='Các phiên bản sau')
    is_latest_version = fields.Boolean(string='Phiên bản mới nhất', default=True)
    
    # === Nhắc nhở ===
    da_gui_nhac_han = fields.Boolean(string='Đã gửi nhắc hạn', default=False)
    so_lan_nhac = fields.Integer(string='Số lần nhắc', default=0)
    
    @api.depends('han_xu_ly')
    def _compute_qua_han(self):
        now = fields.Datetime.now()
        for rec in self:
            if rec.han_xu_ly:
                delta = rec.han_xu_ly - now
                rec.so_gio_con_lai = delta.total_seconds() / 3600
                rec.qua_han = delta.total_seconds() < 0
            else:
                rec.qua_han = False
                rec.so_gio_con_lai = 0
    
    def action_create_new_version(self):
        """Tạo phiên bản mới từ văn bản hiện tại"""
        self.ensure_one()
        
        if self.trang_thai == 'nhap':
            raise UserError(_("Không thể tạo phiên bản mới từ văn bản đang ở trạng thái Nháp!"))
        
        # Đánh dấu bản hiện tại không còn là mới nhất
        self.is_latest_version = False
        
        # Copy và tạo phiên bản mới
        new_version = self.copy({
            'version': self.version + 1,
            'parent_version_id': self.id,
            'is_latest_version': True,
            'trang_thai': 'nhap',
            'da_ky_noi_bo': False,
            'da_khach_ky': False,
            'file_da_ky': False,
            'version_note': False,
            'chu_ky_noi_bo': False,
            'chu_ky_khach': False,
            'ngay_ky_noi_bo': False,
            'ngay_khach_ky': False,
            'bi_khoa': False,
        })
        
        # Ghi lịch sử
        if hasattr(self, '_ghi_lich_su'):
            self._ghi_lich_su('tao_phien_ban', f'Tạo phiên bản {new_version.version} từ phiên bản {self.version}')
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'van_ban',
            'res_id': new_version.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def _get_nguoi_ky_hieu_luc(self):
        """Lấy người ký hiệu lực (có thể là người ủy quyền)"""
        self.ensure_one()
        today = fields.Date.today()
        
        # Kiểm tra ủy quyền có hiệu lực
        if (self.nguoi_uy_quyen_id and 
            self.ngay_uy_quyen_tu and self.ngay_uy_quyen_den and
            self.ngay_uy_quyen_tu <= today <= self.ngay_uy_quyen_den):
            return self.nguoi_uy_quyen_id, True  # Trả về người ủy quyền và flag ký thay
        
        return self.nguoi_ky_id, False  # Trả về người ký chính
    
    def _check_security_access(self):
        """Kiểm tra quyền truy cập theo độ mật"""
        self.ensure_one()
        user = self.env.user
        
        if self.do_mat == 'tuyet_mat':
            if not user.has_group('van_ban.group_quan_tri_van_ban'):
                raise UserError(_("Bạn không có quyền xem văn bản Tuyệt mật!"))
        elif self.do_mat == 'toi_mat':
            if not user.has_group('van_ban.group_giam_doc_ky'):
                raise UserError(_("Bạn không có quyền xem văn bản Tối mật!"))
    
    # === CRON JOBS ===
    
    @api.model
    def _cron_check_deadline_reminder(self):
        """Cron job kiểm tra và gửi nhắc nhở văn bản sắp hết hạn"""
        # Tìm văn bản sắp hết hạn (trong 24h)
        deadline_threshold = fields.Datetime.now() + timedelta(hours=24)
        
        van_bans = self.search([
            ('han_xu_ly', '<=', deadline_threshold),
            ('han_xu_ly', '>=', fields.Datetime.now()),
            ('trang_thai', 'not in', ['da_ky', 'da_gui', 'huy']),
            ('da_gui_nhac_han', '=', False),
        ])
        
        count = 0
        for vb in van_bans:
            try:
                vb._send_deadline_reminder()
                vb.da_gui_nhac_han = True
                vb.so_lan_nhac += 1
                count += 1
            except Exception as e:
                _logger.warning("Không thể gửi nhắc hạn cho %s: %s", vb.ma_van_ban, e)
        
        _logger.info("Đã gửi nhắc hạn cho %d văn bản", count)
        return True
    
    @api.model
    def _cron_mark_overdue(self):
        """Cron job đánh dấu văn bản quá hạn"""
        # Tìm văn bản đã quá hạn nhưng chưa xử lý xong
        van_bans = self.search([
            ('han_xu_ly', '<', fields.Datetime.now()),
            ('trang_thai', 'not in', ['da_ky', 'da_gui', 'huy']),
            ('qua_han', '=', False),
        ])
        
        for vb in van_bans:
            vb.qua_han = True
            if hasattr(vb, '_ghi_lich_su'):
                vb._ghi_lich_su('qua_han', 'Văn bản đã quá hạn xử lý!')
        
        _logger.info("Đánh dấu %d văn bản quá hạn", len(van_bans))
        return True
    
    def _send_deadline_reminder(self):
        """Gửi thông báo nhắc hạn"""
        self.ensure_one()
        
        # Gửi activity cho người xử lý
        users_to_notify = []
        if self.nguoi_tao_id and self.nguoi_tao_id.user_id:
            users_to_notify.append(self.nguoi_tao_id.user_id)
        if self.nguoi_ky_id and self.nguoi_ky_id.user_id:
            users_to_notify.append(self.nguoi_ky_id.user_id)
        if self.nguoi_duyet_id and self.nguoi_duyet_id.user_id:
            users_to_notify.append(self.nguoi_duyet_id.user_id)
        
        # Loại bỏ trùng lặp
        users_to_notify = list(set(users_to_notify))
        
        for user in users_to_notify:
            try:
                self.activity_schedule(
                    'mail.mail_activity_data_warning',
                    user_id=user.id,
                    summary=f'⏰ Văn bản {self.ma_van_ban} sắp hết hạn!',
                    note=f'Văn bản "{self.ten_van_ban}" có hạn xử lý vào {self.han_xu_ly}. Vui lòng xử lý sớm.',
                )
            except Exception as e:
                _logger.warning("Không thể tạo activity cho user %s: %s", user.login, e)
        
        _logger.info("Đã gửi nhắc hạn cho văn bản %s", self.ma_van_ban)
    
    # === BULK OPERATIONS ===
    
    def action_bulk_approve(self):
        """Duyệt hàng loạt các văn bản đã chọn"""
        count_success = 0
        count_fail = 0
        
        for rec in self:
            if rec.trang_thai == 'cho_duyet':
                try:
                    rec.action_duyet()
                    count_success += 1
                except UserError as e:
                    _logger.warning(f"Không thể duyệt văn bản {rec.ma_van_ban}: {e}")
                    count_fail += 1
        
        message = f'Đã duyệt thành công {count_success} văn bản.'
        if count_fail > 0:
            message += f' Không thể duyệt {count_fail} văn bản.'
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Duyệt hàng loạt'),
                'message': message,
                'type': 'success' if count_fail == 0 else 'warning',
                'sticky': False,
            }
        }
    
    def action_bulk_send_sign(self):
        """Gửi ký hàng loạt các văn bản đã duyệt"""
        count_success = 0
        count_fail = 0
        
        for rec in self:
            if rec.trang_thai == 'da_duyet':
                # Kiểm tra có người ký chưa
                rec_sudo = rec.sudo()
                if not rec_sudo.nguoi_ky_id:
                    _logger.warning(f"Văn bản {rec.ma_van_ban} chưa có người ký")
                    count_fail += 1
                    continue
                    
                try:
                    rec.action_gui_ky()
                    count_success += 1
                except UserError as e:
                    _logger.warning(f"Không thể gửi ký văn bản {rec.ma_van_ban}: {e}")
                    count_fail += 1
        
        message = f'Đã gửi ký thành công {count_success} văn bản.'
        if count_fail > 0:
            message += f' Không thể gửi {count_fail} văn bản.'
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Gửi ký hàng loạt'),
                'message': message,
                'type': 'success' if count_fail == 0 else 'warning',
                'sticky': False,
            }
        }
