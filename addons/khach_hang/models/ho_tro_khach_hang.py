# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import timedelta
import logging

_logger = logging.getLogger(__name__)


class HoTroKhachHang(models.Model):
    _name = 'ho_tro_khach_hang'
    _description = 'Hỗ trợ khách hàng'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'ngay_tao desc'

    # Thông tin cơ bản
    ten_yeu_cau = fields.Char('Tiêu đề yêu cầu', required=True, tracking=True)
    khach_hang_id = fields.Many2one('khach_hang', string='Khách hàng', required=True, 
                                     ondelete='cascade', tracking=True)
    mo_ta = fields.Text('Mô tả chi tiết')
    
    # Priority và Category
    priority = fields.Selection([
        ('0', 'Thấp'),
        ('1', 'Trung bình'),
        ('2', 'Cao'),
        ('3', 'Khẩn cấp')
    ], string='Độ ưu tiên', default='1', tracking=True)
    
    category_id = fields.Many2one('ho_tro_khach_hang.category', string='Danh mục',
                                   help='Phân loại ticket theo loại vấn đề')
    
    # Phương thức liên lạc
    phuong_thuc = fields.Selection([
        ('email', 'Email'),
        ('dien_thoai', 'Điện thoại'),
        ('truc_tiep', 'Trực tiếp'),
        ('chat', 'Chat/Zalo'),
        ('facebook', 'Facebook')
    ], string='Phương thức', default='email', tracking=True)
    
    # Thời gian
    ngay_tao = fields.Datetime('Ngày tạo', default=fields.Datetime.now, required=True)
    ngay_phan_hoi = fields.Datetime('Ngày phản hồi đầu tiên', tracking=True)
    ngay_hoan_thanh = fields.Datetime('Ngày hoàn thành', tracking=True)
    
    # Trạng thái
    trang_thai = fields.Selection([
        ('moi', 'Mới'),
        ('dang_xu_ly', 'Đang xử lý'),
        ('cho_phan_hoi', 'Chờ phản hồi khách'),
        ('hoan_thanh', 'Hoàn thành'),
        ('huy', 'Hủy')
    ], string='Trạng thái', default='moi', required=True, tracking=True)
    
    # Nhân viên
    nhan_vien_id = fields.Many2one('nhan_vien', string='Nhân viên xử lý', tracking=True)
    team_id = fields.Many2one('ho_tro_khach_hang.team', string='Team hỗ trợ')
    
    # SLA Tracking
    sla_deadline = fields.Datetime('SLA Deadline', compute='_compute_sla_deadline', store=True)
    sla_exceeded = fields.Boolean('SLA Vượt quá', compute='_compute_sla_status')
    sla_hours_remaining = fields.Float('SLA Hours Remaining', compute='_compute_sla_status')
    
    # CSAT & NPS
    csat_score = fields.Selection([
        ('1', '😡 Rất không hài lòng'),
        ('2', '😟 Không hài lòng'),
        ('3', '😐 Bình thường'),
        ('4', '😊 Hài lòng'),
        ('5', '😍 Rất hài lòng')
    ], string='CSAT Score', tracking=True, help='Customer Satisfaction Score')
    
    nps_score = fields.Selection([
        ('0', '0 - Detractor'),
        ('1', '1'),
        ('2', '2'),
        ('3', '3'),
        ('4', '4'),
        ('5', '5'),
        ('6', '6'),
        ('7', '7 - Passive'),
        ('8', '8'),
        ('9', '9 - Promoter'),
        ('10', '10 - Promoter')
    ], string='NPS Score', tracking=True, help='Net Promoter Score: Bạn có giới thiệu chúng tôi?')
    
    # Đánh giá (kept for backward compatibility)
    danh_gia = fields.Selection([
        ('1', '⭐'),
        ('2', '⭐⭐'),
        ('3', '⭐⭐⭐'),
        ('4', '⭐⭐⭐⭐'),
        ('5', '⭐⭐⭐⭐⭐')
    ], string='Đánh giá', tracking=True)
    
    nhan_xet = fields.Text('Nhận xét khách hàng')
    giai_phap = fields.Text('Giải pháp đã áp dụng')
    
    # Tính toán
    thoi_gian_xu_ly = fields.Float('Thời gian xử lý (giờ)', compute='_compute_thoi_gian_xu_ly', store=True)
    thoi_gian_phan_hoi = fields.Float('Thời gian phản hồi (giờ)', compute='_compute_thoi_gian_phan_hoi', store=True)
    
    # Tags và Color
    tag_ids = fields.Many2many('ho_tro_khach_hang.tag', string='Tags')
    color = fields.Integer('Color Index', compute='_compute_color')
    
    # Tiện ích
    active = fields.Boolean('Active', default=True)
    
    @api.depends('priority', 'ngay_tao', 'category_id')
    def _compute_sla_deadline(self):
        """Tính SLA deadline dựa trên priority và category"""
        for record in self:
            if not record.ngay_tao:
                record.sla_deadline = False
                continue
            
            # SLA hours based on priority
            sla_hours = {
                '3': 2,   # Khẩn cấp: 2 giờ
                '2': 8,   # Cao: 8 giờ
                '1': 24,  # Trung bình: 24 giờ
                '0': 48   # Thấp: 48 giờ
            }
            
            hours = sla_hours.get(record.priority, 24)
            record.sla_deadline = record.ngay_tao + timedelta(hours=hours)
    
    @api.depends('sla_deadline', 'trang_thai')
    def _compute_sla_status(self):
        """Kiểm tra SLA status"""
        now = fields.Datetime.now()
        for record in self:
            if record.trang_thai in ['hoan_thanh', 'huy']:
                record.sla_exceeded = False
                record.sla_hours_remaining = 0
            elif record.sla_deadline:
                delta = record.sla_deadline - now
                record.sla_hours_remaining = delta.total_seconds() / 3600
                record.sla_exceeded = record.sla_hours_remaining < 0
            else:
                record.sla_exceeded = False
                record.sla_hours_remaining = 0
    
    @api.depends('priority', 'sla_exceeded')
    def _compute_color(self):
        """Tính màu cho Kanban"""
        for record in self:
            if record.sla_exceeded:
                record.color = 1  # Red - SLA exceeded
            elif record.priority == '3':
                record.color = 2  # Orange - Urgent
            elif record.priority == '2':
                record.color = 3  # Yellow - High
            else:
                record.color = 0  # Default
    
    # Tiện ích
    active = fields.Boolean('Active', default=True)
    
    @api.depends('ngay_tao', 'ngay_hoan_thanh')
    def _compute_thoi_gian_xu_ly(self):
        """Tính thời gian xử lý tính bằng giờ"""
        for record in self:
            if record.ngay_tao and record.ngay_hoan_thanh:
                delta = record.ngay_hoan_thanh - record.ngay_tao
                record.thoi_gian_xu_ly = delta.total_seconds() / 3600
            else:
                record.thoi_gian_xu_ly = 0.0
    
    @api.depends('ngay_tao', 'ngay_phan_hoi')
    def _compute_thoi_gian_phan_hoi(self):
        """Tính thời gian phản hồi đầu tiên"""
        for record in self:
            if record.ngay_tao and record.ngay_phan_hoi:
                delta = record.ngay_phan_hoi - record.ngay_tao
                record.thoi_gian_phan_hoi = delta.total_seconds() / 3600
            else:
                record.thoi_gian_phan_hoi = 0.0
    
    def name_get(self):
        """Hiển thị tên yêu cầu"""
        result = []
        for record in self:
            name = f"#{record.id} - {record.ten_yeu_cau}"
            result.append((record.id, name))
        return result
    
    def action_xu_ly(self):
        """Bắt đầu xử lý"""
        for record in self:
            record.write({
                'trang_thai': 'dang_xu_ly',
                'ngay_phan_hoi': fields.Datetime.now() if not record.ngay_phan_hoi else record.ngay_phan_hoi
            })
    
    def action_cho_phan_hoi(self):
        """Chờ phản hồi từ khách hàng"""
        self.write({'trang_thai': 'cho_phan_hoi'})
    
    def action_hoan_thanh(self):
        """Hoàn thành"""
        for record in self:
            record.write({
                'trang_thai': 'hoan_thanh',
                'ngay_hoan_thanh': fields.Datetime.now()
            })
            # Gửi survey CSAT/NPS
            record._send_satisfaction_survey()
    
    def action_huy(self):
        """Hủy yêu cầu"""
        self.write({'trang_thai': 'huy'})
    
    def action_escalate(self):
        """Escalate ticket lên quản lý"""
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Escalated'),
                'message': _('Ticket đã được chuyển lên cấp cao hơn'),
                'type': 'success',
                'sticky': False,
            }
        }
    
    def _send_satisfaction_survey(self):
        """Gửi survey đánh giá sau khi hoàn thành"""
        self.ensure_one()
        _logger.info(f"Sending satisfaction survey for ticket #{self.id}")
    
    @api.model
    def cron_check_sla_violations(self):
        """Cron job kiểm tra SLA violations và gửi cảnh báo"""
        violated_tickets = self.search([
            ('trang_thai', 'not in', ['hoan_thanh', 'huy']),
            ('sla_exceeded', '=', True)
        ])
        
        for ticket in violated_tickets:
            ticket.activity_schedule(
                'mail.mail_activity_data_warning',
                summary=f'SLA Violation: {ticket.ten_yeu_cau}',
                note=f'Ticket #{ticket.id} đã vượt quá SLA deadline',
                user_id=ticket.nhan_vien_id.id if ticket.nhan_vien_id else self.env.uid
            )
        
        _logger.info(f"Checked SLA for {len(violated_tickets)} violated tickets")
    
    @api.model
    def cron_auto_assign_tickets(self):
        """Tự động assign tickets mới cho nhân viên"""
        unassigned_tickets = self.search([
            ('trang_thai', '=', 'moi'),
            ('nhan_vien_id', '=', False)
        ])
        
        nhan_vien_list = self.env['nhan_vien'].search([
            ('trang_thai_lam_viec', '=', 'dang_lam')
        ])
        
        if not nhan_vien_list:
            return
        
        for idx, ticket in enumerate(unassigned_tickets):
            assigned_nv = nhan_vien_list[idx % len(nhan_vien_list)]
            ticket.write({'nhan_vien_id': assigned_nv.id})
        
        _logger.info(f"Auto-assigned {len(unassigned_tickets)} tickets")


class HoTroKhachHangCategory(models.Model):
    _name = 'ho_tro_khach_hang.category'
    _description = 'Danh mục hỗ trợ'

    name = fields.Char('Tên danh mục', required=True)
    description = fields.Text('Mô tả')
    active = fields.Boolean('Active', default=True)


class HoTroKhachHangTeam(models.Model):
    _name = 'ho_tro_khach_hang.team'
    _description = 'Team hỗ trợ khách hàng'

    name = fields.Char('Tên team', required=True)
    team_lead_id = fields.Many2one('nhan_vien', string='Team Lead')
    member_ids = fields.Many2many('nhan_vien', string='Thành viên')
    active = fields.Boolean('Active', default=True)


class HoTroKhachHangTag(models.Model):
    _name = 'ho_tro_khach_hang.tag'
    _description = 'Tags cho hỗ trợ'

    name = fields.Char('Tag Name', required=True)
    color = fields.Integer('Color Index')
    active = fields.Boolean('Active', default=True)
