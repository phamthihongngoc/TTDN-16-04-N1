# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta
import base64
import logging

_logger = logging.getLogger(__name__)


class HoSoNhanVien(models.Model):
    _name = 'ho_so.nhan_vien'
    _description = 'Hồ sơ Nhân viên'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'ngay_nop desc'
    _rec_name = 'name'
    
    # ============ THÔNG TIN CƠ BẢN ============
    name = fields.Char(
        string='Tên tài liệu', 
        required=True, 
        tracking=True,
        help='Tên mô tả tài liệu, VD: CMND mặt trước'
    )
    
    nhan_vien_id = fields.Many2one(
        'nhan_vien', 
        string='Nhân viên', 
        required=True, 
        ondelete='cascade',
        tracking=True,
        index=True
    )
    
    # ============ LOẠI HỒ SƠ ============
    loai_ho_so = fields.Selection([
        # Giấy tờ cá nhân
        ('cmnd', '🪪 CMND/CCCD'),
        ('ho_chieu', '🛂 Hộ chiếu'),
        ('so_ho_khau', '🏠 Sổ hộ khẩu'),
        ('giay_khai_sinh', '👶 Giấy khai sinh'),
        
        # Bằng cấp & Chứng chỉ
        ('bang_cap', '🎓 Bằng cấp'),
        ('chung_chi', '📜 Chứng chỉ'),
        ('bang_lai_xe', '🚗 Bằng lái xe'),
        
        # Hợp đồng & Quyết định
        ('hop_dong', '📄 Hợp đồng lao động'),
        ('phu_luc_hd', '📑 Phụ lục hợp đồng'),
        ('quyet_dinh', '📋 Quyết định'),
        
        # Bảo hiểm
        ('so_bhxh', '💳 Sổ BHXH'),
        ('the_bhyt', '🏥 Thẻ BHYT'),
        
        # Y tế
        ('kham_suc_khoe', '🩺 Giấy khám sức khỏe'),
        ('xet_nghiem', '🔬 Kết quả xét nghiệm'),
        
        # Tài chính
        ('so_tai_khoan', '🏦 Sổ tài khoản ngân hàng'),
        ('ma_so_thue', '💼 Mã số thuế cá nhân'),
        
        # Khác
        ('cv_resume', '📝 CV/Resume'),
        ('anh_chan_dung', '📸 Ảnh chân dung'),
        ('giay_gioi_thieu', '📨 Giấy giới thiệu'),
        ('bang_tot_nghiep', '🎓 Bằng tốt nghiệp'),
        ('khac', '📂 Khác'),
    ], string='Loại hồ sơ', required=True, tracking=True, index=True)
    
    # ============ FILE ĐÍNH KÈM ============
    file_dinh_kem = fields.Binary(
        string='File', 
        required=True, 
        attachment=True,
        help='Upload file hồ sơ (PDF, hình ảnh, Word, Excel)'
    )
    file_name = fields.Char(string='Tên file')
    file_size = fields.Float(
        string='Kích thước (KB)', 
        compute='_compute_file_size',
        store=True
    )
    file_type = fields.Selection([
        ('pdf', '📄 PDF'),
        ('image', '🖼️ Hình ảnh'),
        ('word', '📝 Word'),
        ('excel', '📊 Excel'),
        ('other', '📁 Khác')
    ], compute='_compute_file_type', store=True, string='Loại file')
    
    # ============ THÔNG TIN BỔ SUNG ============
    mo_ta = fields.Text(
        string='Mô tả',
        help='Mô tả ngắn gọn về tài liệu'
    )
    ghi_chu = fields.Text(string='Ghi chú')
    
    # ============ NGÀY THÁNG ============
    ngay_nop = fields.Date(
        string='Ngày nộp', 
        default=fields.Date.today, 
        tracking=True,
        required=True
    )
    ngay_cap = fields.Date(
        string='Ngày cấp',
        help='Ngày cấp giấy tờ (nếu có)'
    )
    ngay_het_han = fields.Date(
        string='Ngày hết hạn', 
        tracking=True,
        help='Ngày hết hiệu lực của tài liệu (nếu có)'
    )
    con_hieu_luc = fields.Boolean(
        string='Còn hiệu lực', 
        compute='_compute_con_hieu_luc', 
        store=True,
        help='Tự động kiểm tra dựa trên ngày hết hạn'
    )
    so_ngay_con_lai = fields.Integer(
        string='Số ngày còn lại',
        compute='_compute_so_ngay_con_lai',
        help='Số ngày còn lại đến hết hạn'
    )
    
    # ============ TRẠNG THÁI ============
    trang_thai = fields.Selection([
        ('nhap', '📝 Nháp'),
        ('cho_duyet', '⏳ Chờ duyệt'),
        ('da_duyet', '✅ Đã duyệt'),
        ('tu_choi', '❌ Từ chối'),
        ('het_han', '⚠️ Hết hạn'),
    ], string='Trạng thái', default='nhap', required=True, tracking=True, index=True)
    
    bat_buoc = fields.Boolean(
        string='Bắt buộc', 
        default=False, 
        help='Hồ sơ bắt buộc phải có khi onboarding'
    )
    
    # ============ NGƯỜI XỬ LÝ ============
    nguoi_nop_id = fields.Many2one(
        'res.users', 
        string='Người nộp', 
        default=lambda self: self.env.user,
        readonly=True
    )
    nguoi_duyet_id = fields.Many2one(
        'res.users', 
        string='Người duyệt',
        readonly=True
    )
    ngay_duyet = fields.Datetime(
        string='Ngày duyệt',
        readonly=True
    )
    ly_do_tu_choi = fields.Text(
        string='Lý do từ chối',
        tracking=True
    )
    
    # ============ VERSION CONTROL ============
    phien_ban = fields.Integer(
        string='Phiên bản', 
        default=1,
        readonly=True
    )
    ho_so_goc_id = fields.Many2one(
        'ho_so.nhan_vien', 
        string='Hồ sơ gốc',
        readonly=True,
        help='Tài liệu gốc trước khi cập nhật'
    )
    ho_so_moi_nhat = fields.Boolean(
        string='Là bản mới nhất', 
        default=True,
        help='Đánh dấu đây là phiên bản mới nhất'
    )
    ho_so_cu_ids = fields.One2many(
        'ho_so.nhan_vien',
        'ho_so_goc_id',
        string='Các phiên bản cũ'
    )
    
    # ============ COMPUTED FIELDS ============
    
    @api.depends('file_dinh_kem')
    def _compute_file_size(self):
        """Tính kích thước file"""
        for rec in self:
            if rec.file_dinh_kem:
                try:
                    rec.file_size = len(base64.b64decode(rec.file_dinh_kem)) / 1024
                except:
                    rec.file_size = 0
            else:
                rec.file_size = 0
    
    @api.depends('file_name')
    def _compute_file_type(self):
        """Xác định loại file dựa trên extension"""
        for rec in self:
            if rec.file_name:
                ext = rec.file_name.split('.')[-1].lower()
                if ext == 'pdf':
                    rec.file_type = 'pdf'
                elif ext in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'svg']:
                    rec.file_type = 'image'
                elif ext in ['doc', 'docx']:
                    rec.file_type = 'word'
                elif ext in ['xls', 'xlsx']:
                    rec.file_type = 'excel'
                else:
                    rec.file_type = 'other'
            else:
                rec.file_type = 'other'
    
    @api.depends('ngay_het_han')
    def _compute_con_hieu_luc(self):
        """Kiểm tra hồ sơ còn hiệu lực không"""
        today = fields.Date.today()
        for rec in self:
            if rec.ngay_het_han:
                rec.con_hieu_luc = rec.ngay_het_han >= today
                # Auto update status nếu hết hạn
                if not rec.con_hieu_luc and rec.trang_thai == 'da_duyet':
                    rec.trang_thai = 'het_han'
            else:
                rec.con_hieu_luc = True
    
    @api.depends('ngay_het_han')
    def _compute_so_ngay_con_lai(self):
        """Tính số ngày còn lại đến hết hạn"""
        today = fields.Date.today()
        for rec in self:
            if rec.ngay_het_han:
                delta = rec.ngay_het_han - today
                rec.so_ngay_con_lai = delta.days
            else:
                rec.so_ngay_con_lai = 9999
    
    # ============ CONSTRAINTS ============
    
    @api.constrains('file_size')
    def _check_file_size(self):
        """Kiểm tra kích thước file không quá 10MB"""
        for rec in self:
            if rec.file_size > 10240:  # 10MB = 10240KB
                raise ValidationError(
                    _('Kích thước file không được vượt quá 10MB!\n'
                      'File hiện tại: %.2f MB') % (rec.file_size / 1024)
                )
    
    @api.constrains('ngay_cap', 'ngay_het_han')
    def _check_dates(self):
        """Kiểm tra ngày cấp phải trước ngày hết hạn"""
        for rec in self:
            if rec.ngay_cap and rec.ngay_het_han:
                if rec.ngay_cap > rec.ngay_het_han:
                    raise ValidationError(
                        _('Ngày cấp không thể sau ngày hết hạn!')
                    )
    
    # ============ ACTIONS ============
    
    def action_gui_duyet(self):
        """Gửi hồ sơ đi duyệt"""
        self.ensure_one()
        if not self.file_dinh_kem:
            raise ValidationError(_('Vui lòng upload file trước khi gửi duyệt!'))
        
        self.write({
            'trang_thai': 'cho_duyet',
            'ngay_nop': fields.Date.today()
        })
        
        # Gửi email thông báo
        self._send_approval_notification()
        
        # Tạo activity cho người duyệt
        self._create_approval_activity()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Thành công'),
                'message': _('Đã gửi hồ sơ đi duyệt!'),
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_duyet(self):
        """Duyệt hồ sơ"""
        self.ensure_one()
        self.write({
            'trang_thai': 'da_duyet',
            'nguoi_duyet_id': self.env.user.id,
            'ngay_duyet': fields.Datetime.now()
        })
        
        # Gửi email xác nhận
        self._send_approved_notification()
        
        # Đánh dấu activity hoàn thành
        self._complete_approval_activity()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Đã duyệt'),
                'message': _('Hồ sơ đã được duyệt thành công!'),
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_tu_choi(self):
        """Mở wizard từ chối hồ sơ"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Từ chối hồ sơ'),
            'res_model': 'wizard.tu_choi_ho_so',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_ho_so_id': self.id}
        }
    
    def action_cap_nhat_phien_ban(self):
        """Tạo phiên bản mới của hồ sơ"""
        self.ensure_one()
        
        # Đánh dấu bản cũ không còn mới nhất
        self.ho_so_moi_nhat = False
        
        # Copy sang phiên bản mới
        new_version = self.copy({
            'phien_ban': self.phien_ban + 1,
            'ho_so_goc_id': self.ho_so_goc_id.id or self.id,
            'trang_thai': 'nhap',
            'nguoi_duyet_id': False,
            'ngay_duyet': False,
            'ly_do_tu_choi': False,
        })
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Cập nhật hồ sơ'),
            'res_model': 'ho_so.nhan_vien',
            'res_id': new_version.id,
            'view_mode': 'form',
            'target': 'current'
        }
    
    def action_view_history(self):
        """Xem lịch sử các phiên bản"""
        self.ensure_one()
        
        # Lấy hồ sơ gốc
        ho_so_goc = self.ho_so_goc_id or self
        
        # Lấy tất cả phiên bản
        all_versions = self.search([
            '|',
            ('id', '=', ho_so_goc.id),
            ('ho_so_goc_id', '=', ho_so_goc.id)
        ])
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Lịch sử phiên bản'),
            'res_model': 'ho_so.nhan_vien',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', all_versions.ids)],
            'context': {'create': False}
        }
    
    def action_download(self):
        """Download file"""
        self.ensure_one()
        if not self.file_dinh_kem:
            raise ValidationError(_('Không có file để tải!'))
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/ho_so.nhan_vien/{self.id}/file_dinh_kem/{self.file_name}?download=true',
            'target': 'new',
        }
    
    # ============ PRIVATE METHODS ============
    
    def _send_approval_notification(self):
        """Gửi email thông báo cần duyệt"""
        template = self.env.ref('nhan_su.email_template_ho_so_approval', raise_if_not_found=False)
        if template:
            for rec in self:
                # Gửi cho HR manager
                hr_managers = self.env.ref('nhan_su.group_quan_tri_nhan_su').users
                for manager in hr_managers:
                    template.with_context(recipient_user=manager).send_mail(rec.id, force_send=True)
    
    def _send_approved_notification(self):
        """Gửi email xác nhận đã duyệt"""
        template = self.env.ref('nhan_su.email_template_ho_so_approved', raise_if_not_found=False)
        if template:
            for rec in self:
                # Gửi cho người nộp
                if rec.nguoi_nop_id:
                    template.with_context(recipient_user=rec.nguoi_nop_id).send_mail(rec.id, force_send=True)
    
    def _send_rejected_notification(self):
        """Gửi email thông báo bị từ chối"""
        template = self.env.ref('nhan_su.email_template_ho_so_rejected', raise_if_not_found=False)
        if template:
            for rec in self:
                # Gửi cho người nộp
                if rec.nguoi_nop_id:
                    template.with_context(recipient_user=rec.nguoi_nop_id).send_mail(rec.id, force_send=True)
    
    def _send_expiry_reminder(self):
        """Gửi email nhắc nhở sắp hết hạn"""
        template = self.env.ref('nhan_su.email_template_ho_so_expiry', raise_if_not_found=False)
        if template:
            for rec in self:
                template.send_mail(rec.id, force_send=True)
    
    def _create_approval_activity(self):
        """Tạo activity cho người duyệt"""
        for rec in self:
            hr_managers = self.env.ref('nhan_su.group_quan_tri_nhan_su').users
            for manager in hr_managers:
                self.env['mail.activity'].create({
                    'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
                    'summary': f'Duyệt hồ sơ: {rec.name}',
                    'note': f'Nhân viên {rec.nhan_vien_id.name} đã gửi hồ sơ {rec.loai_ho_so} cần duyệt.',
                    'res_id': rec.id,
                    'res_model_id': self.env.ref('nhan_su.model_ho_so_nhan_vien').id,
                    'user_id': manager.id,
                })
    
    def _complete_approval_activity(self):
        """Đánh dấu activity hoàn thành"""
        for rec in self:
            activities = self.env['mail.activity'].search([
                ('res_id', '=', rec.id),
                ('res_model_id', '=', self.env.ref('nhan_su.model_ho_so_nhan_vien').id),
                ('user_id', '=', self.env.user.id),
            ])
            activities.action_done()
    
    # ============ CRON JOBS ============
    
    @api.model
    def _cron_check_het_han(self):
        """Kiểm tra hồ sơ hết hạn mỗi ngày"""
        today = fields.Date.today()
        
        # Tìm hồ sơ sắp hết hạn trong 30 ngày
        sap_het_han = self.search([
            ('ngay_het_han', '<=', today + timedelta(days=30)),
            ('ngay_het_han', '>=', today),
            ('trang_thai', '=', 'da_duyet'),
            ('bat_buoc', '=', True)
        ])
        
        for ho_so in sap_het_han:
            ho_so._send_expiry_reminder()
            _logger.info(f'Sent expiry reminder for document: {ho_so.name} (Employee: {ho_so.nhan_vien_id.name})')
        
        # Tự động chuyển trạng thái hết hạn
        het_han = self.search([
            ('ngay_het_han', '<', today),
            ('trang_thai', '=', 'da_duyet')
        ])
        het_han.write({'trang_thai': 'het_han'})
        
        _logger.info(f'Auto-updated {len(het_han)} expired documents')
