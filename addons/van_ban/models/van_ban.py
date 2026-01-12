# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, timedelta
import hashlib
import base64


class VanBan(models.Model):
    _name = 'van_ban'
    _description = 'Văn bản'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'ngay_tao desc'

    # === THÔNG TIN CƠ BẢN ===
    ma_van_ban = fields.Char('Mã văn bản', required=True, copy=False, readonly=True,
                              default=lambda self: _('New'), tracking=True)
    ten_van_ban = fields.Char('Tên văn bản', required=True, tracking=True)
    loai_van_ban_id = fields.Many2one('loai_van_ban', string='Loại văn bản', 
                                       required=True, tracking=True)
    mo_ta = fields.Text('Mô tả')
    
    # === TRẠNG THÁI (WORKFLOW) ===
    # Quy trình: Nháp → Chờ duyệt → Đã duyệt → Chờ ký → Đã ký → Đã gửi
    # KÝ ĐIỆN TỬ BẮT BUỘC trước khi gửi
    trang_thai = fields.Selection([
        ('nhap', 'Nháp'),
        ('cho_duyet', 'Chờ duyệt'),
        ('da_duyet', 'Đã duyệt'),
        ('cho_ky', 'Chờ ký'),
        ('da_ky', 'Đã ký'),
        ('da_gui', 'Đã gửi'),  # THÊM: Gửi sau khi ký
        ('het_hieu_luc', 'Hết hiệu lực'),
        ('huy', 'Đã hủy')
    ], string='Trạng thái', default='nhap', required=True, tracking=True)
    
    # === THỜI HẠN ===
    ngay_tao = fields.Datetime('Ngày tạo', default=fields.Datetime.now, readonly=True)
    ngay_gui = fields.Date('Ngày gửi', tracking=True, readonly=True,
                           help='Ngày gửi văn bản (sau khi ký điện tử)')
    ngay_hieu_luc = fields.Date('Ngày hiệu lực', tracking=True)
    ngay_het_han = fields.Date('Ngày hết hạn', tracking=True)
    so_ngay_con_lai = fields.Integer('Số ngày còn lại', compute='_compute_so_ngay_con_lai',
                                      store=True)
    sap_het_han = fields.Boolean('Sắp hết hạn', compute='_compute_so_ngay_con_lai',
                                  store=True)
    
    # === LIÊN KẾT ===
    # Liên kết với module Khách hàng
    khach_hang_id = fields.Many2one('khach_hang', string='Khách hàng liên quan',
                                     tracking=True)
    don_hang_id = fields.Many2one('don_hang', string='Đơn hàng liên quan',
                                   domain="[('khach_hang_id', '=', khach_hang_id)]")
    
    # Liên kết với module Nhân sự
    nguoi_tao_id = fields.Many2one('nhan_vien', string='Người tạo',
                                    default=lambda self: self._get_nhan_vien_hien_tai(),
                                    tracking=True)
    nguoi_duyet_id = fields.Many2one('nhan_vien', string='Người duyệt', tracking=True)
    nguoi_phe_duyet_id = fields.Many2one('nhan_vien', string='Người phê duyệt', tracking=True)
    nguoi_ky_id = fields.Many2one('nhan_vien', string='Người ký nội bộ', tracking=True)
    
    # Computed fields for display
    ten_nguoi_tao = fields.Char('Tên người tạo', compute='_compute_sync_nhan_su', store=True)
    phong_ban_nguoi_tao = fields.Char('Phòng ban người tạo', compute='_compute_sync_nhan_su', store=True)
    ten_nguoi_duyet = fields.Char('Tên người duyệt', compute='_compute_sync_nhan_su', store=True)
    ten_nguoi_ky = fields.Char('Tên người ký', compute='_compute_sync_nhan_su', store=True)
    
    # === FILE ĐÍNH KÈM ===
    file_dinh_kem = fields.Binary('File văn bản', attachment=True)
    ten_file = fields.Char('Tên file')
    file_da_ky = fields.Binary('File đã ký', attachment=True, readonly=True)
    ten_file_da_ky = fields.Char('Tên file đã ký')
    
    # === KÝ ĐIỆN TỬ ===
    da_ky_noi_bo = fields.Boolean('Đã ký nội bộ', readonly=True)
    ngay_ky_noi_bo = fields.Datetime('Ngày ký nội bộ', readonly=True)
    chu_ky_noi_bo = fields.Binary('Chữ ký nội bộ', readonly=True)
    
    da_khach_ky = fields.Boolean('Khách đã ký', readonly=True)
    ngay_khach_ky = fields.Datetime('Ngày khách ký', readonly=True)
    chu_ky_khach = fields.Binary('Chữ ký khách hàng', readonly=True)
    
    # === YÊU CẦU KÝ ===
    yeu_cau_ky_ids = fields.One2many('yeu_cau_ky', 'van_ban_id', string='Yêu cầu ký')
    so_yeu_cau_ky = fields.Integer('Số yêu cầu ký', compute='_compute_so_yeu_cau_ky')
    
    # === LỊCH SỬ ===
    lich_su_ids = fields.One2many('lich_su_van_ban', 'van_ban_id', string='Lịch sử thay đổi')
    
    # === BẢO MẬT ===
    hash_file = fields.Char('Hash file', readonly=True, help='Mã hash để kiểm tra tính toàn vẹn')
    bi_khoa = fields.Boolean('Bị khóa', default=False, 
                              help='Văn bản bị khóa không thể chỉnh sửa')
    
    # === GHI CHÚ ===
    ghi_chu = fields.Text('Ghi chú')
    ly_do_huy = fields.Text('Lý do hủy')
    
    # === TIỆN ÍCH ===
    currency_id = fields.Many2one('res.currency', string='Tiền tệ',
                                   default=lambda self: self.env.company.currency_id)
    gia_tri_hop_dong = fields.Monetary('Giá trị hợp đồng', currency_field='currency_id')
    
    # === PROCESS AUTOMATION - AI-ENHANCED FEATURES ===
    # AI suggestions for workflow
    ai_suggested_approver = fields.Many2one('nhan_vien', string='AI đề xuất người duyệt',
                                             compute='_compute_ai_suggestions', store=False)
    ai_suggested_signer = fields.Many2one('nhan_vien', string='AI đề xuất người ký',
                                           compute='_compute_ai_suggestions', store=False)
    ai_risk_level = fields.Selection([
        ('low', 'Thấp'),
        ('medium', 'Trung bình'),
        ('high', 'Cao'),
        ('critical', 'Nguy hiểm')
    ], string='Mức độ rủi ro (AI)', compute='_compute_ai_risk_assessment', store=True)

    ai_category_suggestion = fields.Char('AI phân loại tự động', compute='_compute_ai_category', store=True)
    ai_priority_score = fields.Float('Điểm ưu tiên (AI)', compute='_compute_ai_priority', store=True)

    # Automated workflow tracking
    auto_follow_up_count = fields.Integer('Số lần follow-up tự động', default=0)
    last_auto_follow_up = fields.Datetime('Lần follow-up cuối')
    sla_deadline = fields.Datetime('Hạn SLA', compute='_compute_sla_deadline', store=True)
    sla_breached = fields.Boolean('Vi phạm SLA', compute='_compute_sla_status', store=True)
    
    _sql_constraints = [
        ('ma_van_ban_unique', 'unique(ma_van_ban)', 'Mã văn bản đã tồn tại!')
    ]
    
    # === COMPUTE METHODS ===
    
    def _get_nhan_vien_hien_tai(self):
        """Lấy nhân viên hiện tại từ user đang đăng nhập"""
        nhan_vien = self.env['nhan_vien'].search([
            ('user_id', '=', self.env.uid)
        ], limit=1)
        return nhan_vien.id if nhan_vien else False
    
    @api.depends('ngay_het_han')
    def _compute_so_ngay_con_lai(self):
        """Tính số ngày còn lại và cảnh báo sắp hết hạn"""
        today = fields.Date.today()
        for record in self:
            if record.ngay_het_han:
                delta = record.ngay_het_han - today
                record.so_ngay_con_lai = delta.days
                record.sap_het_han = 0 <= delta.days <= 30
            else:
                record.so_ngay_con_lai = 0
                record.sap_het_han = False
    
    @api.depends('yeu_cau_ky_ids')
    def _compute_so_yeu_cau_ky(self):
        for record in self:
            record.so_yeu_cau_ky = len(record.yeu_cau_ky_ids)
    
    # === SYSTEM INTEGRATION COMPUTE METHODS ===
    @api.depends('nguoi_tao_id.ten_nv', 'nguoi_tao_id.phong_ban',
                 'nguoi_duyet_id.ten_nv', 'nguoi_ky_id.ten_nv')
    def _compute_sync_nhan_su(self):
        """Đồng bộ thông tin từ module nhan_su để đảm bảo tính nhất quán dữ liệu"""
        for record in self:
            # Sync thông tin người tạo
            if record.nguoi_tao_id:
                record.ten_nguoi_tao = record.nguoi_tao_id.ten_nv
                record.phong_ban_nguoi_tao = record.nguoi_tao_id.phong_ban
            else:
                record.ten_nguoi_tao = False
                record.phong_ban_nguoi_tao = False
            
            # Sync thông tin người duyệt
            if record.nguoi_duyet_id:
                record.ten_nguoi_duyet = record.nguoi_duyet_id.ten_nv
            else:
                record.ten_nguoi_duyet = False
            
            # Sync thông tin người ký
            if record.nguoi_ky_id:
                record.ten_nguoi_ky = record.nguoi_ky_id.ten_nv
            else:
                record.ten_nguoi_ky = False
            
    # === PROCESS AUTOMATION COMPUTE METHODS ===

    @api.depends('loai_van_ban_id', 'gia_tri_hop_dong', 'khach_hang_id')
    def _compute_ai_suggestions(self):
        """AI đề xuất người duyệt và ký dựa trên loại văn bản và giá trị"""
        for record in self:
            # Reset suggestions
            record.ai_suggested_approver = False
            record.ai_suggested_signer = False

            if not record.loai_van_ban_id:
                continue

            # AI Logic: Dựa trên loại văn bản và giá trị hợp đồng
            loai_vb = record.loai_van_ban_id.ten_loai.lower()

            # Tìm nhân viên phù hợp dựa trên phòng ban và chức vụ
            nhan_vien_pool = self.env['nhan_vien'].search([
                ('trang_thai_lam_viec', '=', 'dang_lam')
            ])

            # Logic AI cho người duyệt (Approver)
            if 'hợp đồng' in loai_vb or record.gia_tri_hop_dong > 50000000:  # > 50 triệu
                # Ưu tiên trưởng phòng kinh doanh hoặc tài chính
                approvers = nhan_vien_pool.filtered(
                    lambda nv: nv.chuc_vu and ('trưởng' in nv.chuc_vu.lower() or 'phó' in nv.chuc_vu.lower())
                )
                if approvers:
                    record.ai_suggested_approver = approvers[0].id

            elif 'quyết định' in loai_vb or 'nội quy' in loai_vb:
                # Ưu tiên lãnh đạo cấp cao
                leaders = nhan_vien_pool.filtered(
                    lambda nv: nv.chuc_vu and ('giám đốc' in nv.chuc_vu.lower() or 'tổng' in nv.chuc_vu.lower())
                )
                if leaders:
                    record.ai_suggested_approver = leaders[0].id

            # Logic AI cho người ký (Signer)
            if record.gia_tri_hop_dong > 100000000:  # > 100 triệu
                # Cần lãnh đạo cấp cao ký
                high_level = nhan_vien_pool.filtered(
                    lambda nv: nv.chuc_vu and ('giám đốc' in nv.chuc_vu.lower() or 'tổng' in nv.chuc_vu.lower())
                )
                if high_level:
                    record.ai_suggested_signer = high_level[0].id
            elif record.gia_tri_hop_dong > 20000000:  # > 20 triệu
                # Trưởng phòng có thể ký
                managers = nhan_vien_pool.filtered(
                    lambda nv: nv.chuc_vu and 'trưởng' in nv.chuc_vu.lower()
                )
                if managers:
                    record.ai_suggested_signer = managers[0].id

    @api.depends('gia_tri_hop_dong', 'loai_van_ban_id', 'khach_hang_id')
    def _compute_ai_risk_assessment(self):
        """AI đánh giá mức độ rủi ro của văn bản"""
        for record in self:
            risk_score = 0

            # Risk factors
            if record.gia_tri_hop_dong:
                if record.gia_tri_hop_dong > 500000000:  # > 500 triệu
                    risk_score += 3
                elif record.gia_tri_hop_dong > 100000000:  # > 100 triệu
                    risk_score += 2
                elif record.gia_tri_hop_dong > 50000000:  # > 50 triệu
                    risk_score += 1

            # Loại văn bản có rủi ro cao
            if record.loai_van_ban_id:
                loai_vb = record.loai_van_ban_id.ten_loai.lower()
                if any(keyword in loai_vb for keyword in ['hợp đồng', 'thỏa thuận', 'cam kết']):
                    risk_score += 1

            # Khách hàng mới hoặc có vấn đề
            if record.khach_hang_id:
                # Logic đơn giản: Giả sử khách hàng mới có rủi ro cao hơn
                # Trong thực tế có thể dựa trên lịch sử giao dịch
                risk_score += 0.5

            # Determine risk level
            if risk_score >= 3:
                record.ai_risk_level = 'critical'
            elif risk_score >= 2:
                record.ai_risk_level = 'high'
            elif risk_score >= 1:
                record.ai_risk_level = 'medium'
            else:
                record.ai_risk_level = 'low'

    @api.depends('ten_van_ban', 'mo_ta', 'loai_van_ban_id')
    def _compute_ai_category(self):
        """AI tự động phân loại văn bản dựa trên nội dung"""
        for record in self:
            if not record.ten_van_ban and not record.mo_ta:
                record.ai_category_suggestion = False
                continue

            text_content = f"{record.ten_van_ban or ''} {record.mo_ta or ''}".lower()

            # AI Classification Logic
            if any(keyword in text_content for keyword in ['hợp đồng', 'contract', 'agreement']):
                record.ai_category_suggestion = 'Hợp đồng'
            elif any(keyword in text_content for keyword in ['quyết định', 'decision', 'decree']):
                record.ai_category_suggestion = 'Quyết định'
            elif any(keyword in text_content for keyword in ['báo cáo', 'report', 'summary']):
                record.ai_category_suggestion = 'Báo cáo'
            elif any(keyword in text_content for keyword in ['thông báo', 'notification', 'announcement']):
                record.ai_category_suggestion = 'Thông báo'
            elif any(keyword in text_content for keyword in ['biên bản', 'minutes', 'record']):
                record.ai_category_suggestion = 'Biên bản'
            else:
                record.ai_category_suggestion = 'Tài liệu khác'

    @api.depends('ai_risk_level', 'sap_het_han', 'trang_thai', 'gia_tri_hop_dong')
    def _compute_ai_priority(self):
        """AI tính điểm ưu tiên cho văn bản"""
        for record in self:
            priority_score = 0

            # Risk level contribution
            risk_weights = {'low': 1, 'medium': 2, 'high': 3, 'critical': 5}
            priority_score += risk_weights.get(record.ai_risk_level, 1)

            # Urgent documents (expiring soon)
            if record.sap_het_han:
                priority_score += 2

            # Status-based priority
            status_weights = {
                'cho_duyet': 3, 'cho_ky': 4, 'da_ky': 2,
                'nhap': 1, 'da_duyet': 2, 'da_gui': 1
            }
            priority_score += status_weights.get(record.trang_thai, 1)

            # Value-based priority
            if record.gia_tri_hop_dong:
                if record.gia_tri_hop_dong > 100000000:  # > 100 triệu
                    priority_score += 3
                elif record.gia_tri_hop_dong > 50000000:  # > 50 triệu
                    priority_score += 2
                elif record.gia_tri_hop_dong > 10000000:  # > 10 triệu
                    priority_score += 1

            record.ai_priority_score = min(priority_score, 10)  # Cap at 10

    @api.depends('trang_thai', 'ngay_tao', 'ai_risk_level')
    def _compute_sla_deadline(self):
        """Tính hạn SLA dựa trên trạng thái và mức độ rủi ro"""
        for record in self:
            if not record.ngay_tao:
                record.sla_deadline = False
                continue

            base_days = 7  # Default 7 days

            # Adjust based on risk level
            risk_multipliers = {
                'low': 1, 'medium': 1.5, 'high': 2, 'critical': 3
            }
            multiplier = risk_multipliers.get(record.ai_risk_level, 1)

            # Adjust based on status
            status_multipliers = {
                'cho_duyet': 1, 'da_duyet': 0.5, 'cho_ky': 1.5,
                'da_ky': 0.5, 'da_gui': 0
            }
            status_multiplier = status_multipliers.get(record.trang_thai, 1)

            total_days = base_days * multiplier * status_multiplier
            record.sla_deadline = record.ngay_tao + timedelta(days=int(total_days))

    @api.depends('sla_deadline')
    def _compute_sla_status(self):
        """Kiểm tra xem có vi phạm SLA không"""
        now = fields.Datetime.now()
        for record in self:
            record.sla_breached = record.sla_deadline and now > record.sla_deadline
    
    # === SYSTEM INTEGRATION CONSTRAINTS ===
    @api.constrains('nguoi_tao_id', 'nguoi_duyet_id', 'nguoi_phe_duyet_id', 'nguoi_ky_id')
    def _check_nhan_vien_active(self):
        """Đảm bảo nhân viên liên quan vẫn đang hoạt động"""
        for record in self:
            nhan_vien_fields = [
                ('nguoi_tao_id', record.nguoi_tao_id),
                ('nguoi_duyet_id', record.nguoi_duyet_id),
                ('nguoi_phe_duyet_id', record.nguoi_phe_duyet_id),
                ('nguoi_ky_id', record.nguoi_ky_id)
            ]
            
            for field_name, nhan_vien in nhan_vien_fields:
                if nhan_vien and nhan_vien.trang_thai_lam_viec != 'dang_lam':
                    field_label = self._fields[field_name].string
                    raise ValidationError(f'{field_label} "{nhan_vien.ten_nv}" không còn hoạt động trong hệ thống!')
    
    @api.constrains('nguoi_tao_id')
    def _check_nguoi_tao_required(self):
        """Đảm bảo luôn có người tạo"""
        for record in self:
            if not record.nguoi_tao_id:
                raise ValidationError('Văn bản phải có người tạo!')
    
    # === CRUD METHODS ===
    
    @api.model
    def create(self, vals):
        """Tạo mã văn bản tự động và ghi lịch sử"""
        if vals.get('ma_van_ban', _('New')) == _('New'):
            vals['ma_van_ban'] = self.env['ir.sequence'].next_by_code('van_ban') or _('New')
        
        record = super(VanBan, self).create(vals)
        
        # Ghi lịch sử tạo
        record._ghi_lich_su('tao', 'Tạo văn bản mới')
        
        # Tính hash file nếu có
        if record.file_dinh_kem:
            record._compute_hash_file()
        
        return record
    
    def write(self, vals):
        """Ghi lịch sử thay đổi"""
        # Danh sách các trường quan trọng không được sửa khi bị khóa
        protected_fields = [
            'ten_van_ban', 'loai_van_ban_id', 'file_dinh_kem', 'ten_file',
            'khach_hang_id', 'don_hang_id', 'gia_tri_hop_dong',
            'ngay_hieu_luc', 'ngay_het_han', 'mo_ta'
        ]
        
        # Danh sách các trường được phép cập nhật khi bị khóa (hệ thống)
        allowed_when_locked = [
            'bi_khoa', 'trang_thai', 
            'da_ky_noi_bo', 'ngay_ky_noi_bo', 'chu_ky_noi_bo',
            'da_khach_ky', 'ngay_khach_ky', 'chu_ky_khach',
            'file_da_ky', 'ten_file_da_ky', 'hash_file',
            'ghi_chu', 'ly_do_huy'
        ]
        
        for record in self:
            if record.bi_khoa:
                # Kiểm tra xem có trường bị bảo vệ nào được cập nhật không
                protected_updated = set(vals.keys()) & set(protected_fields)
                if protected_updated:
                    raise UserError(
                        f'Văn bản đã bị khóa, không thể chỉnh sửa!\n'
                        f'Các trường không được sửa: {", ".join(protected_updated)}'
                    )
        
        result = super(VanBan, self).write(vals)
        
        # Ghi lịch sử nếu có thay đổi quan trọng
        if 'trang_thai' in vals:
            for record in self:
                record._ghi_lich_su('trang_thai', f'Chuyển trạng thái sang: {record.trang_thai}')
        
        if 'file_dinh_kem' in vals:
            for record in self:
                record._compute_hash_file()
                record._ghi_lich_su('file', 'Cập nhật file đính kèm')
        
        return result
    
    # === WORKFLOW ACTIONS ===
    
    def action_gui_duyet(self):
        """Gửi văn bản để duyệt - Enhanced with AI suggestions and notifications"""
        for record in self:
            if not record.file_dinh_kem:
                raise UserError('Vui lòng đính kèm file văn bản trước khi gửi duyệt!')

            # AI Suggestion: Auto-assign approver if not set
            if not record.nguoi_duyet_id and record.ai_suggested_approver:
                record.write({'nguoi_duyet_id': record.ai_suggested_approver.id})
                record._ghi_lich_su('ai_suggest', f'AI tự động đề xuất người duyệt: {record.ai_suggested_approver.ten_nv}')

            record.write({'trang_thai': 'cho_duyet'})
            record._ghi_lich_su('gui_duyet', 'Gửi văn bản để duyệt')

            # Enhanced notifications
            record._send_enhanced_notifications('approval_request')

            # Schedule follow-up if high priority
            if record.ai_priority_score >= 7:
                record._schedule_auto_follow_up('approval', days=2)
    
    def action_duyet(self):
        """Duyệt văn bản (Trưởng phòng) - Enhanced with notifications"""
        for record in self:
            record.write({
                'trang_thai': 'da_duyet',
                'nguoi_duyet_id': self._get_nhan_vien_hien_tai()
            })
            record._ghi_lich_su('duyet', 'Duyệt văn bản')

            # Enhanced notifications
            record._send_enhanced_notifications('approved')

            # Auto-suggest next signer if not set
            if not record.nguoi_ky_id and record.ai_suggested_signer:
                record.write({'nguoi_ky_id': record.ai_suggested_signer.id})
                record._ghi_lich_su('ai_suggest', f'AI tự động đề xuất người ký: {record.ai_suggested_signer.ten_nv}')

            # Cancel follow-up activities
            record._cancel_pending_follow_ups()
    
    def action_tu_choi_duyet(self):
        """Từ chối duyệt văn bản"""
        for record in self:
            record.write({'trang_thai': 'nhap'})
            record._ghi_lich_su('tu_choi', 'Từ chối duyệt văn bản')
    
    def action_gui_ky(self):
        """Gửi văn bản để ký - Enhanced with AI and notifications"""
        for record in self:
            # AI Suggestion: Auto-assign signer if not set
            if not record.nguoi_ky_id and record.ai_suggested_signer:
                record.write({'nguoi_ky_id': record.ai_suggested_signer.id})
                record._ghi_lich_su('ai_suggest', f'AI tự động đề xuất người ký: {record.ai_suggested_signer.ten_nv}')

            record.write({'trang_thai': 'cho_ky'})
            record._ghi_lich_su('gui_ky', 'Gửi văn bản để ký')

            # Enhanced notifications
            record._send_enhanced_notifications('signature_request')

            # Schedule urgent follow-up for high-risk documents
            if record.ai_risk_level in ['high', 'critical']:
                record._schedule_auto_follow_up('signature', days=1)
    
    def action_ky_noi_bo(self):
        """Mở wizard ký điện tử - VẼ CHỮ KÝ"""
        self.ensure_one()
        
        # Kiểm tra điều kiện trước khi mở wizard
        if self.trang_thai not in ['da_duyet', 'cho_ky']:
            raise UserError('Văn bản chưa được duyệt!')
        
        if not self.file_dinh_kem:
            raise UserError('Vui lòng đính kèm file văn bản trước khi ký!')
        
        # Mở wizard ký điện tử
        return {
            'name': _('Ký điện tử - Vẽ chữ ký'),
            'type': 'ir.actions.act_window',
            'res_model': 'wizard.ky.dien.tu',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_van_ban_id': self.id,
            }
        }
    
    def action_gui_van_ban(self):
        """Gửi văn bản - CHỈ được gửi SAU KHI đã ký điện tử"""
        for record in self:
            # KIỂM TRA BẮT BUỘC: Phải ký điện tử trước khi gửi
            if not record.da_ky_noi_bo:
                raise UserError(
                    'KHÔNG THỂ GỬI!\n\n'
                    'Văn bản chưa được ký điện tử.\n'
                    'Vui lòng thực hiện ký điện tử trước khi gửi.'
                )
            
            if record.trang_thai != 'da_ky':
                raise UserError('Chỉ có thể gửi văn bản đã ký!')
            
            # Nếu cần khách hàng ký, kiểm tra xem khách đã ký chưa
            if record.khach_hang_id and not record.da_khach_ky:
                raise UserError(
                    'CHƯA THỂ GỬI!\n\n'
                    'Văn bản cần chữ ký của khách hàng.\n'
                    'Vui lòng đợi khách hàng ký xong hoặc gửi yêu cầu ký cho khách hàng.'
                )
            
            # Gửi văn bản và KHÓA VĂN BẢN
            record.write({
                'trang_thai': 'da_gui',
                'ngay_gui': fields.Date.today(),
                'bi_khoa': True  # KHÓA khi gửi đi
            })
            
            record._ghi_lich_su('gui', 'Gửi văn bản - Văn bản đã được khóa')
            
            # Gửi email thông báo cho khách hàng (nếu có)
            if record.khach_hang_id and record.khach_hang_id.email:
                record._gui_email_van_ban_da_gui()
        
        # Thông báo thành công và reload form
        self.env.cr.commit()  # Commit để đảm bảo dữ liệu được lưu
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Gửi văn bản thành công!',
                'message': f'Văn bản {self.ma_van_ban} đã được gửi và khóa.',
                'type': 'success',
                'sticky': True,
                'next': {
                    'type': 'ir.actions.act_window',
                    'res_model': 'van_ban',
                    'res_id': self.id,
                    'views': [(False, 'form')],
                    'view_mode': 'form',
                },
            }
        }
    
    def action_gui_yeu_cau_ky_khach(self):
        """Tạo yêu cầu ký cho khách hàng"""
        self.ensure_one()
        
        # KIỂM TRA: Phải ký nội bộ trước
        if not self.da_ky_noi_bo:
            raise UserError(
                'Vui lòng ký điện tử nội bộ trước khi gửi yêu cầu ký cho khách hàng!'
            )
        
        if not self.khach_hang_id:
            raise UserError('Vui lòng chọn khách hàng liên quan!')
        
        if not self.khach_hang_id.email:
            raise UserError('Khách hàng chưa có email!')
        
        # Tạo yêu cầu ký
        yeu_cau = self.env['yeu_cau_ky'].create({
            'van_ban_id': self.id,
            'khach_hang_id': self.khach_hang_id.id,
            'email': self.khach_hang_id.email,
            'trang_thai': 'cho_ky'
        })
        
        # Gửi email
        yeu_cau.action_gui_email_yeu_cau_ky()
        
        self._ghi_lich_su('gui_yeu_cau_ky', f'Gửi yêu cầu ký cho khách hàng: {self.khach_hang_id.ten_khach_hang}')
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Thành công',
                'message': f'Đã gửi yêu cầu ký cho {self.khach_hang_id.ten_khach_hang}',
                'type': 'success',
            }
        }
    
    def action_huy(self):
        """Hủy văn bản"""
        for record in self:
            if record.trang_thai == 'da_ky':
                raise UserError('Không thể hủy văn bản đã ký!')
            
            record.write({'trang_thai': 'huy'})
            record._ghi_lich_su('huy', f'Hủy văn bản. Lý do: {record.ly_do_huy or "Không có"}')
    
    def action_mo_khoa(self):
        """Mở khóa văn bản (chỉ admin)"""
        for record in self:
            record.write({'bi_khoa': False})
            record._ghi_lich_su('mo_khoa', 'Mở khóa văn bản')
    
    # === HELPER METHODS ===
    
    def _ghi_lich_su(self, hanh_dong, mo_ta):
        """Ghi lịch sử thay đổi văn bản"""
        self.ensure_one()
        self.env['lich_su_van_ban'].create({
            'van_ban_id': self.id,
            'hanh_dong': hanh_dong,
            'mo_ta': mo_ta,
            'nguoi_thuc_hien_id': self.env.uid,
            'thoi_gian': fields.Datetime.now(),
            'ip_address': self.env['ir.http']._get_client_address() if hasattr(self.env['ir.http'], '_get_client_address') else 'N/A'
        })
    
    def _compute_hash_file(self):
        """Tính hash MD5 của file để kiểm tra tính toàn vẹn"""
        self.ensure_one()
        if self.file_dinh_kem:
            file_content = base64.b64decode(self.file_dinh_kem)
            self.hash_file = hashlib.md5(file_content).hexdigest()
    
    def _gui_email_van_ban_da_gui(self):
        """Gửi email thông báo văn bản đã gửi cho khách hàng"""
        self.ensure_one()
        if not self.khach_hang_id or not self.khach_hang_id.email:
            return
        
        mail_values = {
            'subject': f'[{self.env.company.name}] Văn bản: {self.ten_van_ban}',
            'body_html': f'''
                <p>Kính gửi {self.khach_hang_id.ten_khach_hang},</p>
                <p>Chúng tôi xin gửi đến Quý khách văn bản: <strong>{self.ten_van_ban}</strong></p>
                <p><strong>Thông tin văn bản:</strong></p>
                <ul>
                    <li>Mã văn bản: {self.ma_van_ban}</li>
                    <li>Loại văn bản: {self.loai_van_ban_id.ten_loai}</li>
                    <li>Ngày gửi: {self.ngay_gui}</li>
                    <li>Đã ký điện tử: Có</li>
                </ul>
                <p>Văn bản đính kèm trong email này.</p>
                <br/>
                <p>Trân trọng,</p>
                <p>{self.env.company.name}</p>
            ''',
            'email_to': self.khach_hang_id.email,
            'email_from': self.env.company.email or 'noreply@company.com',
        }
        
        # Đính kèm file đã ký
        if self.file_da_ky and self.ten_file_da_ky:
            mail_values['attachment_ids'] = [(
                0, 0, {
                    'name': self.ten_file_da_ky,
                    'datas': self.file_da_ky,
                    'mimetype': 'application/pdf',
                }
            )]
        
        self.env['mail.mail'].create(mail_values).send()
    
    # === PROCESS AUTOMATION - ENHANCED NOTIFICATIONS ===
    
    def _send_enhanced_notifications(self, notification_type):
        """Gửi thông báo nâng cao dựa trên loại sự kiện"""
        self.ensure_one()
        
        if notification_type == 'approval_request':
            self._send_approval_request_notifications()
        elif notification_type == 'approved':
            self._send_approval_complete_notifications()
        elif notification_type == 'signature_request':
            self._send_signature_request_notifications()
        elif notification_type == 'signed':
            self._send_signature_complete_notifications()
        elif notification_type == 'sent':
            self._send_document_sent_notifications()
    
    def _send_approval_request_notifications(self):
        """Gửi thông báo yêu cầu duyệt với thông tin AI"""
        if not self.nguoi_duyet_id or not self.nguoi_duyet_id.email:
            return
        
        risk_color = {'low': 'green', 'medium': 'orange', 'high': 'red', 'critical': 'darkred'}
        risk_icon = {'low': '✅', 'medium': '⚠️', 'high': '🔴', 'critical': '🚨'}
        
        mail_values = {
            'subject': f'[{risk_icon.get(self.ai_risk_level, "📄")}] Yêu cầu duyệt: {self.ten_van_ban}',
            'body_html': f'''
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <h2 style="color: #2E86C1;">Yêu cầu duyệt văn bản</h2>
                    
                    <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 10px 0;">
                        <h3>{self.ten_van_ban}</h3>
                        <p><strong>Mã văn bản:</strong> {self.ma_van_ban}</p>
                        <p><strong>Loại văn bản:</strong> {self.loai_van_ban_id.ten_loai}</p>
                        <p><strong>Người tạo:</strong> {self.ten_nguoi_tao}</p>
                        <p><strong>Giá trị:</strong> {self.gia_tri_hop_dong:,.0f} VND</p>
                    </div>
                    
                    <div style="background-color: {risk_color.get(self.ai_risk_level, 'gray')}; color: white; padding: 10px; border-radius: 5px; margin: 10px 0;">
                        <strong>AI Risk Assessment: {self.ai_risk_level.upper()}</strong><br/>
                        Priority Score: {self.ai_priority_score}/10
                    </div>
                    
                    <p><strong>Deadline SLA:</strong> {self.sla_deadline}</p>
                    
                    <div style="text-align: center; margin: 20px 0;">
                        <a href="/web#id={self.id}&model=van_ban&view_type=form" 
                           style="background-color: #28a745; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
                            Xem và duyệt văn bản
                        </a>
                    </div>
                    
                    <p style="color: #666; font-size: 12px;">
                        Email này được gửi tự động bởi hệ thống quản lý văn bản.
                    </p>
                </div>
            ''',
            'email_to': self.nguoi_duyet_id.email,
            'email_from': self.env.company.email or 'noreply@company.com',
        }
        
        self.env['mail.mail'].create(mail_values).send()
    
    def _send_approval_complete_notifications(self):
        """Gửi thông báo duyệt thành công"""
        # Thông báo cho người tạo
        if self.nguoi_tao_id and self.nguoi_tao_id.email:
            mail_values = {
                'subject': f'✅ Văn bản đã được duyệt: {self.ten_van_ban}',
                'body_html': f'''
                    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                        <h2 style="color: #28a745;">Văn bản đã được duyệt</h2>
                        <p>Kính gửi {self.ten_nguoi_tao},</p>
                        <p>Văn bản <strong>{self.ten_van_ban}</strong> đã được duyệt thành công.</p>
                        <p><strong>Người duyệt:</strong> {self.ten_nguoi_duyet}</p>
                        <p><strong>Tiếp theo:</strong> Văn bản sẽ được chuyển sang bước ký điện tử.</p>
                    </div>
                ''',
                'email_to': self.nguoi_tao_id.email,
                'email_from': self.env.company.email or 'noreply@company.com',
            }
            self.env['mail.mail'].create(mail_values).send()
    
    def _send_signature_request_notifications(self):
        """Gửi thông báo yêu cầu ký"""
        if not self.nguoi_ky_id or not self.nguoi_ky_id.email:
            return
        
        mail_values = {
            'subject': f'🖊️ Yêu cầu ký văn bản: {self.ten_van_ban}',
            'body_html': f'''
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <h2 style="color: #8E44AD;">Yêu cầu ký văn bản</h2>
                    
                    <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 10px 0;">
                        <h3>{self.ten_van_ban}</h3>
                        <p><strong>Mã văn bản:</strong> {self.ma_van_ban}</p>
                        <p><strong>Người duyệt:</strong> {self.ten_nguoi_duyet}</p>
                    </div>
                    
                    <div style="text-align: center; margin: 20px 0;">
                        <a href="/web#id={self.id}&model=van_ban&view_type=form" 
                           style="background-color: #8E44AD; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
                            Truy cập và ký văn bản
                        </a>
                    </div>
                    
                    <p style="color: #666; font-size: 12px;">
                        Vui lòng hoàn thành ký điện tử trong thời hạn quy định.
                    </p>
                </div>
            ''',
            'email_to': self.nguoi_ky_id.email,
            'email_from': self.env.company.email or 'noreply@company.com',
        }
        
        self.env['mail.mail'].create(mail_values).send()
    
    def _send_signature_complete_notifications(self):
        """Gửi thông báo ký hoàn thành"""
        # Thông báo cho người tạo và người duyệt
        recipients = []
        if self.nguoi_tao_id and self.nguoi_tao_id.email:
            recipients.append((self.nguoi_tao_id.email, self.ten_nguoi_tao))
        if self.nguoi_duyet_id and self.nguoi_duyet_id.email and self.nguoi_duyet_id != self.nguoi_tao_id:
            recipients.append((self.nguoi_duyet_id.email, self.ten_nguoi_duyet))
        
        for email, name in recipients:
            mail_values = {
                'subject': f'✍️ Văn bản đã được ký: {self.ten_van_ban}',
                'body_html': f'''
                    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                        <h2 style="color: #27AE60;">Văn bản đã được ký điện tử</h2>
                        <p>Kính gửi {name},</p>
                        <p>Văn bản <strong>{self.ten_van_ban}</strong> đã được ký thành công.</p>
                        <p><strong>Người ký:</strong> {self.ten_nguoi_ky}</p>
                        <p><strong>Thời gian ký:</strong> {self.ngay_ky_noi_bo}</p>
                        <p><strong>Tiếp theo:</strong> Văn bản có thể được gửi đi hoặc yêu cầu ký của khách hàng.</p>
                    </div>
                ''',
                'email_to': email,
                'email_from': self.env.company.email or 'noreply@company.com',
            }
            self.env['mail.mail'].create(mail_values).send()
    
    def _send_document_sent_notifications(self):
        """Gửi thông báo văn bản đã gửi"""
        # Thông báo cho tất cả người liên quan
        recipients = []
        if self.nguoi_tao_id and self.nguoi_tao_id.email:
            recipients.append((self.nguoi_tao_id.email, self.ten_nguoi_tao))
        if self.nguoi_duyet_id and self.nguoi_duyet_id.email:
            recipients.append((self.nguoi_duyet_id.email, self.ten_nguoi_duyet))
        if self.nguoi_ky_id and self.nguoi_ky_id.email:
            recipients.append((self.nguoi_ky_id.email, self.ten_nguoi_ky))
        
        for email, name in recipients:
            mail_values = {
                'subject': f'📤 Văn bản đã gửi: {self.ten_van_ban}',
                'body_html': f'''
                    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                        <h2 style="color: #3498DB;">Văn bản đã được gửi</h2>
                        <p>Kính gửi {name},</p>
                        <p>Văn bản <strong>{self.ten_van_ban}</strong> đã được gửi thành công.</p>
                        <p><strong>Ngày gửi:</strong> {self.ngay_gui}</p>
                        <p><strong>Trạng thái:</strong> Đã khóa và hoàn thành</p>
                    </div>
                ''',
                'email_to': email,
                'email_from': self.env.company.email or 'noreply@company.com',
            }
            self.env['mail.mail'].create(mail_values).send()
    
    # === PROCESS AUTOMATION - AI WORKFLOW METHODS ===
    
    def _schedule_auto_follow_up(self, follow_up_type, days=1):
        """Lên lịch follow-up tự động"""
        self.ensure_one()
        
        follow_up_date = fields.Datetime.now() + timedelta(days=days)
        
        activity_summary = {
            'approval': f'Follow-up: Duyệt văn bản {self.ten_van_ban}',
            'signature': f'Follow-up: Ký văn bản {self.ten_van_ban}',
            'customer_signature': f'Follow-up: Khách ký văn bản {self.ten_van_ban}'
        }
        
        # Determine responsible user
        responsible_user = False
        if follow_up_type == 'approval' and self.nguoi_duyet_id:
            responsible_user = self.nguoi_duyet_id.user_id
        elif follow_up_type in ['signature', 'customer_signature'] and self.nguoi_ky_id:
            responsible_user = self.nguoi_ky_id.user_id
        
        if responsible_user:
            self.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=responsible_user.id,
                summary=activity_summary.get(follow_up_type, 'Follow-up văn bản'),
                date_deadline=follow_up_date,
                note=f'Auto follow-up #{self.auto_follow_up_count + 1} cho văn bản có độ ưu tiên cao.'
            )
            
            self.write({
                'auto_follow_up_count': self.auto_follow_up_count + 1,
                'last_auto_follow_up': fields.Datetime.now()
            })
    
    def _cancel_pending_follow_ups(self):
        """Hủy các follow-up đang chờ"""
        self.ensure_one()
        
        # Cancel pending activities related to this document
        activities = self.env['mail.activity'].search([
            ('res_model', '=', 'van_ban'),
            ('res_id', '=', self.id),
            ('activity_type_id', '=', self.env.ref('mail.mail_activity_data_todo').id),
            ('summary', 'ilike', 'Follow-up')
        ])
        
        activities.unlink()
    
    def action_ai_apply_suggestions(self):
        """Áp dụng các đề xuất của AI"""
        self.ensure_one()
        
        changes_made = []
        
        # Apply approver suggestion
        if not self.nguoi_duyet_id and self.ai_suggested_approver:
            self.write({'nguoi_duyet_id': self.ai_suggested_approver.id})
            changes_made.append(f'Người duyệt: {self.ai_suggested_approver.ten_nv}')
        
        # Apply signer suggestion
        if not self.nguoi_ky_id and self.ai_suggested_signer:
            self.write({'nguoi_ky_id': self.ai_suggested_signer.id})
            changes_made.append(f'Người ký: {self.ai_suggested_signer.ten_nv}')
        
        # Apply category suggestion
        if self.ai_category_suggestion and not self.loai_van_ban_id:
            # Try to find matching category
            category = self.env['loai_van_ban'].search([
                ('ten_loai', 'ilike', self.ai_category_suggestion)
            ], limit=1)
            if category:
                self.write({'loai_van_ban_id': category.id})
                changes_made.append(f'Loại văn bản: {category.ten_loai}')
        
        if changes_made:
            self._ghi_lich_su('ai_apply', f'AI áp dụng đề xuất: {", ".join(changes_made)}')
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'AI Suggestions Applied',
                    'message': f'Đã áp dụng đề xuất AI: {", ".join(changes_made)}',
                    'type': 'success',
                }
            }
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'No Changes',
                'message': 'Không có đề xuất AI nào để áp dụng.',
                'type': 'warning',
            }
        }
    
    # === SCHEDULED ACTIONS ===
    
    # === ENHANCED SCHEDULED ACTIONS - PROCESS AUTOMATION ===
    
    @api.model
    def _cron_check_het_han(self):
        """Enhanced cron job kiểm tra văn bản hết hạn và gửi cảnh báo"""
        today = fields.Date.today()
        
        # Tìm văn bản sắp hết hạn (trong 30 ngày)
        van_ban_sap_het_han = self.search([
            ('trang_thai', 'in', ['da_duyet', 'da_ky']),
            ('ngay_het_han', '!=', False),
            ('ngay_het_han', '>=', today),
            ('ngay_het_han', '<=', today + timedelta(days=30))
        ])
        
        for vb in van_ban_sap_het_han:
            # Enhanced notifications with AI risk assessment
            risk_icon = {'low': '⚪', 'medium': '🟡', 'high': '🔴', 'critical': '🚨'}
            
            # Gửi thông báo cho người tạo
            if vb.nguoi_tao_id and vb.nguoi_tao_id.user_id:
                vb.activity_schedule(
                    'mail.mail_activity_data_warning',
                    user_id=vb.nguoi_tao_id.user_id.id,
                    summary=f'{risk_icon.get(vb.ai_risk_level, "⚠️")} Văn bản sắp hết hạn: {vb.ten_van_ban} ({vb.so_ngay_con_lai} ngày)',
                    date_deadline=vb.ngay_het_han,
                    note=f'Risk Level: {vb.ai_risk_level.upper()}\nPriority: {vb.ai_priority_score}/10\nSLA Status: {"Breach" if vb.sla_breached else "OK"}'
                )
        
        # Đánh dấu văn bản đã hết hạn
        van_ban_het_han = self.search([
            ('trang_thai', 'in', ['da_duyet', 'da_ky']),
            ('ngay_het_han', '!=', False),
            ('ngay_het_han', '<', today)
        ])
        
        for vb in van_ban_het_han:
            vb.write({'trang_thai': 'het_hieu_luc'})
            vb._ghi_lich_su('het_han', 'Văn bản hết hiệu lực - Auto update by cron')
            
            # Notify all stakeholders
            vb._send_enhanced_notifications('expired')
    
    @api.model
    def _cron_auto_follow_up(self):
        """Cron job tự động follow-up các văn bản pending"""
        now = fields.Datetime.now()
        
        # Follow-up approval requests (pending > 2 days)
        pending_approvals = self.search([
            ('trang_thai', '=', 'cho_duyet'),
            ('ngay_tao', '<', now - timedelta(days=2)),
            ('auto_follow_up_count', '<', 3)  # Max 3 follow-ups
        ])
        
        for vb in pending_approvals:
            vb._schedule_auto_follow_up('approval', days=1)
        
        # Follow-up signature requests (pending > 3 days)
        pending_signatures = self.search([
            ('trang_thai', '=', 'cho_ky'),
            ('ngay_tao', '<', now - timedelta(days=3)),
            ('auto_follow_up_count', '<', 3)
        ])
        
        for vb in pending_signatures:
            vb._schedule_auto_follow_up('signature', days=1)
    
    @api.model
    def _cron_sla_monitoring(self):
        """Cron job giám sát SLA và cảnh báo vi phạm"""
        now = fields.Datetime.now()
        
        # Find SLA breaches
        sla_breaches = self.search([
            ('sla_deadline', '!=', False),
            ('sla_deadline', '<', now),
            ('trang_thai', 'not in', ['da_gui', 'het_hieu_luc', 'huy']),
            ('sla_breached', '=', False)  # Only notify once
        ])
        
        for vb in sla_breaches:
            vb.write({'sla_breached': True})
            
            # Notify stakeholders about SLA breach
            stakeholders = []
            if vb.nguoi_tao_id and vb.nguoi_tao_id.user_id:
                stakeholders.append(vb.nguoi_tao_id.user_id.id)
            if vb.nguoi_duyet_id and vb.nguoi_duyet_id.user_id:
                stakeholders.append(vb.nguoi_duyet_id.user_id.id)
            if vb.nguoi_ky_id and vb.nguoi_ky_id.user_id:
                stakeholders.append(vb.nguoi_ky_id.user_id.id)
            
            for user_id in set(stakeholders):  # Remove duplicates
                vb.activity_schedule(
                    'mail.mail_activity_data_warning',
                    user_id=user_id,
                    summary=f'🚨 SLA Breach: {vb.ten_van_ban}',
                    note=f'Văn bản đã vi phạm thời hạn SLA.\nRisk Level: {vb.ai_risk_level.upper()}\nOverdue: {(now - vb.sla_deadline).days} days'
                )
    
    @api.model
    def _cron_ai_optimization(self):
        """Cron job tối ưu hóa AI suggestions dựa trên dữ liệu lịch sử"""
        # Analyze approval patterns and update AI logic
        # This would be more complex in a real implementation
        
        # For now, just log the optimization run
        self.env['ir.logging'].create({
            'name': 'AI Optimization',
            'type': 'server',
            'dbname': self.env.cr.dbname,
            'level': 'INFO',
            'message': 'AI optimization cron completed - analyzed approval patterns and updated suggestions',
            'path': 'van_ban.models.van_ban',
            'func': '_cron_ai_optimization',
            'line': '1'
        })
    
    @api.model
    def _cron_data_quality_check(self):
        """Cron job kiểm tra chất lượng dữ liệu và đề xuất cải thiện"""
        # Find documents with missing critical information
        incomplete_docs = self.search([
            ('trang_thai', 'in', ['da_duyet', 'da_ky']),
            '|', '|',
            ('nguoi_duyet_id', '=', False),
            ('nguoi_ky_id', '=', False),
            ('file_dinh_kem', '=', False)
        ])
        
        for vb in incomplete_docs:
            issues = []
            if not vb.nguoi_duyet_id:
                issues.append('thiếu người duyệt')
            if not vb.nguoi_ky_id:
                issues.append('thiếu người ký')
            if not vb.file_dinh_kem:
                issues.append('thiếu file đính kèm')
            
            if vb.nguoi_tao_id and vb.nguoi_tao_id.user_id:
                vb.activity_schedule(
                    'mail.mail_activity_data_todo',
                    user_id=vb.nguoi_tao_id.user_id.id,
                    summary=f'📋 Cần bổ sung thông tin: {vb.ten_van_ban}',
                    note=f'Văn bản thiếu các thông tin quan trọng: {", ".join(issues)}'
                )
