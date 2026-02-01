# -*- coding: utf-8 -*-

import logging
from datetime import datetime, timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class BookingQuickCreateWizard(models.TransientModel):
    """
    Wizard để tạo lịch hẹn nhanh với calendar picker.
    Cho phép chọn ngày giờ trực quan và tự động đồng bộ với Google Calendar + Zoom.
    """
    _name = 'booking.quick.create.wizard'
    _description = 'Wizard Đặt lịch hẹn nhanh'

    # Customer info
    khach_hang_id = fields.Many2one('khach_hang', string='Khách hàng', required=True,
                                     readonly=True)
    customer_name = fields.Char('Tên khách hàng', related='khach_hang_id.ten_khach_hang')
    customer_email = fields.Char('Email', related='khach_hang_id.email')
    customer_phone = fields.Char('Số điện thoại', related='khach_hang_id.so_dien_thoai')
    
    # Meeting details
    title = fields.Char('Tiêu đề cuộc hẹn', required=True)
    description = fields.Text('Mô tả / Ghi chú')
    
    # Date time selection - using datetime widget for calendar picker
    start_datetime = fields.Datetime('Ngày và giờ bắt đầu', required=True,
                                      default=lambda self: fields.Datetime.now() + timedelta(hours=1))
    end_datetime = fields.Datetime('Ngày và giờ kết thúc', required=True,
                                    default=lambda self: fields.Datetime.now() + timedelta(hours=2))
    duration = fields.Float('Thời lượng (giờ)', compute='_compute_duration', store=True)
    
    # Meeting type
    meeting_type = fields.Selection([
        ('offline', 'Trực tiếp (Offline)'),
        ('online', 'Trực tuyến (Zoom)')
    ], string='Hình thức họp', required=True, default='offline')
    
    location = fields.Char('Địa điểm', 
                           help='Địa điểm họp nếu là cuộc hẹn trực tiếp')
    
    # Integration options
    sync_google_calendar = fields.Boolean('Đồng bộ Google Calendar', default=True,
                                           help='Tự động tạo sự kiện trên Google Calendar')
    create_zoom_meeting = fields.Boolean('Tạo cuộc họp Zoom', default=False,
                                          help='Tự động tạo phòng Zoom (chỉ áp dụng cho meeting online)')
    
    # Responsible user
    user_id = fields.Many2one('res.users', string='Người phụ trách',
                              default=lambda self: self.env.user, required=True)
    
    # Additional attendees
    attendee_ids = fields.Many2many('res.partner', string='Người tham dự khác')
    
    # Integration status display
    google_integration_available = fields.Boolean('Google Calendar khả dụng',
                                                   compute='_compute_integration_status')
    zoom_integration_available = fields.Boolean('Zoom khả dụng',
                                                 compute='_compute_integration_status')

    @api.depends('start_datetime', 'end_datetime')
    def _compute_duration(self):
        for wizard in self:
            if wizard.start_datetime and wizard.end_datetime:
                delta = wizard.end_datetime - wizard.start_datetime
                wizard.duration = delta.total_seconds() / 3600.0
            else:
                wizard.duration = 1.0

    @api.onchange('start_datetime')
    def _onchange_start_datetime(self):
        """Auto-update end time when start time changes"""
        if self.start_datetime:
            self.end_datetime = self.start_datetime + timedelta(hours=1)

    @api.onchange('meeting_type')
    def _onchange_meeting_type(self):
        """Auto-toggle Zoom option based on meeting type"""
        if self.meeting_type == 'online':
            self.create_zoom_meeting = True
            self.location = False
        else:
            self.create_zoom_meeting = False

    def _compute_integration_status(self):
        """Check if Google Calendar and Zoom integrations are configured"""
        for wizard in self:
            # Check Google Calendar - tìm cấu hình đã xác thực và đang hoạt động
            google_config = self.env['google.calendar.integration'].sudo().search([
                ('is_active', '=', True),
                ('sync_status', 'in', ['authorized', 'connected'])
            ], limit=1)
            wizard.google_integration_available = bool(google_config)
            
            # Check Zoom - tìm cấu hình đã kết nối và đang hoạt động
            zoom_config = self.env['zoom.integration'].sudo().search([
                ('is_active', '=', True),
                ('sync_status', 'in', ['configured', 'connected'])
            ], limit=1)
            wizard.zoom_integration_available = bool(zoom_config)

    @api.constrains('start_datetime', 'end_datetime')
    def _check_dates(self):
        for wizard in self:
            if wizard.start_datetime and wizard.end_datetime:
                if wizard.end_datetime <= wizard.start_datetime:
                    raise ValidationError(_('Thời gian kết thúc phải sau thời gian bắt đầu!'))
                if wizard.start_datetime < fields.Datetime.now():
                    raise ValidationError(_('Không thể đặt lịch hẹn trong quá khứ!'))

    def action_create_booking(self):
        """Tạo lịch hẹn và tự động đồng bộ"""
        self.ensure_one()
        
        # Calculate booking_date and booking_time from start_datetime
        start_dt = fields.Datetime.context_timestamp(self, self.start_datetime)
        booking_date = start_dt.date()
        booking_time = start_dt.hour + start_dt.minute / 60.0
        
        # Prepare booking values
        booking_vals = {
            'khach_hang_id': self.khach_hang_id.id,
            'title': self.title,
            'description': self.description,
            'booking_date': booking_date,
            'booking_time': booking_time,
            'duration': self.duration,
            'meeting_type': self.meeting_type,
            'location': self.location if self.meeting_type == 'offline' else False,
            'user_id': self.user_id.id,
            'attendee_ids': [(6, 0, self.attendee_ids.ids)] if self.attendee_ids else False,
            'state': 'draft',
        }
        
        # Create booking
        booking = self.env['customer.booking'].create(booking_vals)
        
        # Auto-confirm to trigger integrations
        booking.action_confirm()
        
        # Sync with Google Calendar if requested
        if self.sync_google_calendar and self.google_integration_available:
            try:
                booking._sync_to_google_calendar()
            except Exception as e:
                _logger.warning("Failed to sync to Google Calendar: %s", str(e))
        
        # Create Zoom meeting if requested
        if self.create_zoom_meeting and self.meeting_type == 'online' and self.zoom_integration_available:
            try:
                booking._create_zoom_meeting()
            except Exception as e:
                _logger.warning("Failed to create Zoom meeting: %s", str(e))
        
        # Return action to view the created booking
        return {
            'type': 'ir.actions.act_window',
            'name': _('Lịch hẹn đã tạo'),
            'res_model': 'customer.booking',
            'res_id': booking.id,
            'view_mode': 'form',
            'target': 'current',
            'context': {'form_view_initial_mode': 'edit'}
        }

    def action_open_calendar_view(self):
        """Mở view Calendar để chọn ngày giờ trực quan hơn"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Chọn ngày hẹn'),
            'res_model': 'calendar.event',
            'view_mode': 'calendar,tree,form',
            'target': 'new',
            'context': {
                'default_name': self.title or _('Hẹn gặp %s') % self.customer_name,
                'default_start': self.start_datetime,
                'default_stop': self.end_datetime,
            }
        }
