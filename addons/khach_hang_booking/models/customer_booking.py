# -*- coding: utf-8 -*-

import logging
from datetime import datetime, timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class CustomerBooking(models.Model):
    """
    Đặt lịch hẹn khách hàng - tích hợp calendar.event, Zoom và Google Calendar.
    
    Lifecycle:
    1. Tạo booking (draft)
    2. Xác nhận booking (confirmed) -> tạo calendar.event + Zoom meeting (nếu online) + sync Google
    3. Hoàn thành (done) hoặc Hủy (cancelled) -> xóa Zoom meeting + Google event nếu hủy
    """
    _name = 'customer.booking'
    _description = 'Lịch hẹn khách hàng'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'booking_date desc, booking_time desc'
    _rec_name = 'name'

    # Basic info
    name = fields.Char('Mã lịch hẹn', readonly=True, copy=False, default='New')
    title = fields.Char('Tiêu đề', required=True, tracking=True)
    description = fields.Html('Mô tả')
    
    # Customer link
    khach_hang_id = fields.Many2one('khach_hang', string='Khách hàng', required=True,
                                     tracking=True, ondelete='cascade')
    customer_name = fields.Char('Tên khách hàng', related='khach_hang_id.ten_khach_hang', store=True)
    customer_email = fields.Char('Email khách hàng', related='khach_hang_id.email', store=True)
    customer_phone = fields.Char('SĐT khách hàng', related='khach_hang_id.so_dien_thoai', store=True)
    
    # Responsible user
    user_id = fields.Many2one('res.users', string='Người phụ trách', required=True,
                              default=lambda self: self.env.user, tracking=True)
    
    # Additional attendees
    attendee_ids = fields.Many2many('res.partner', string='Người tham dự khác',
                                     help='Thêm người tham dự ngoài khách hàng')
    
    # Scheduling
    booking_date = fields.Date('Ngày hẹn', required=True, tracking=True,
                                default=fields.Date.context_today)
    booking_time = fields.Float('Giờ bắt đầu', required=True, default=9.0,
                                 help='Giờ bắt đầu (format 24h, ví dụ: 9.5 = 9:30)')
    duration = fields.Float('Thời lượng (giờ)', required=True, default=1.0)
    
    # Computed datetime fields
    start_datetime = fields.Datetime('Thời gian bắt đầu', compute='_compute_datetimes', store=True)
    end_datetime = fields.Datetime('Thời gian kết thúc', compute='_compute_datetimes', store=True)
    
    # Meeting type
    meeting_type = fields.Selection([
        ('offline', 'Trực tiếp (Offline)'),
        ('online', 'Trực tuyến (Zoom)')
    ], string='Hình thức', required=True, default='offline', tracking=True)
    
    location = fields.Char('Địa điểm', 
                           help='Địa điểm họp (cho meeting offline)')
    
    # Calendar event link
    calendar_event_id = fields.Many2one('calendar.event', string='Calendar Event',
                                         readonly=True, copy=False, ondelete='set null')
    
    # Zoom integration
    zoom_meeting_id = fields.Char('Zoom Meeting ID', readonly=True, copy=False)
    zoom_join_url = fields.Char('Zoom Join URL', readonly=True, copy=False)
    zoom_start_url = fields.Char('Zoom Start URL (Host)', readonly=True, copy=False)
    zoom_password = fields.Char('Zoom Password', readonly=True, copy=False)
    zoom_sync_status = fields.Selection([
        ('not_applicable', 'Không áp dụng'),
        ('pending', 'Chờ đồng bộ'),
        ('synced', 'Đã đồng bộ'),
        ('error', 'Lỗi')
    ], string='Trạng thái Zoom', default='not_applicable', readonly=True)
    
    # Google Calendar integration
    google_calendar_event_id = fields.Char('Google Event ID', readonly=True, copy=False)
    google_calendar_link = fields.Char('Google Calendar Link', readonly=True, copy=False)
    google_sync_status = fields.Selection([
        ('not_synced', 'Chưa đồng bộ'),
        ('pending', 'Chờ đồng bộ'),
        ('synced', 'Đã đồng bộ'),
        ('error', 'Lỗi')
    ], string='Trạng thái Google', default='not_synced', readonly=True)
    
    # State
    state = fields.Selection([
        ('draft', 'Nháp'),
        ('confirmed', 'Đã xác nhận'),
        ('done', 'Hoàn thành'),
        ('cancelled', 'Đã hủy')
    ], string='Trạng thái', default='draft', required=True, tracking=True)
    
    # Reminder
    reminder_sent = fields.Boolean('Đã gửi nhắc nhở', default=False)
    reminder_datetime = fields.Datetime('Thời gian nhắc nhở', 
                                         compute='_compute_reminder_datetime', store=True)
    
    # Notes
    notes = fields.Text('Ghi chú nội bộ')
    meeting_notes = fields.Html('Ghi chú cuộc họp')
    
    # Display fields
    meeting_url = fields.Char('Link họp', compute='_compute_meeting_url')
    
    @api.depends('booking_date', 'booking_time', 'duration')
    def _compute_datetimes(self):
        """Tính start_datetime và end_datetime từ date + time"""
        import pytz
        for record in self:
            if record.booking_date and record.booking_time is not False:
                # Convert booking_time (float) to hours and minutes
                hours = int(record.booking_time)
                minutes = int((record.booking_time - hours) * 60)
                
                # Create datetime in local timezone
                tz = pytz.timezone(self.env.user.tz or 'Asia/Ho_Chi_Minh')
                local_dt = tz.localize(datetime.combine(
                    record.booking_date,
                    datetime.min.time().replace(hour=hours, minute=minutes)
                ))
                
                # Convert to UTC for storage
                utc_dt = local_dt.astimezone(pytz.UTC).replace(tzinfo=None)
                record.start_datetime = utc_dt
                
                # Calculate end time
                duration_hours = int(record.duration)
                duration_minutes = int((record.duration - duration_hours) * 60)
                record.end_datetime = utc_dt + timedelta(hours=duration_hours, minutes=duration_minutes)
            else:
                record.start_datetime = False
                record.end_datetime = False

    @api.depends('start_datetime')
    def _compute_reminder_datetime(self):
        """Tính thời gian nhắc nhở (30 phút trước)"""
        for record in self:
            if record.start_datetime:
                record.reminder_datetime = record.start_datetime - timedelta(minutes=30)
            else:
                record.reminder_datetime = False

    @api.depends('meeting_type', 'zoom_join_url', 'location')
    def _compute_meeting_url(self):
        """Compute meeting URL hiển thị"""
        for record in self:
            if record.meeting_type == 'online' and record.zoom_join_url:
                record.meeting_url = record.zoom_join_url
            else:
                record.meeting_url = record.location or ''

    @api.model_create_multi
    def create(self, vals_list):
        """Override create để tạo sequence"""
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('customer.booking') or 'New'
        return super().create(vals_list)

    def action_confirm(self):
        """Xác nhận booking - tạo calendar.event + Zoom meeting nếu online + sync Google"""
        for record in self:
            if record.state != 'draft':
                continue
            
            # Validate
            if record.start_datetime <= fields.Datetime.now():
                raise ValidationError(_('Không thể xác nhận lịch hẹn trong quá khứ.'))
            
            # 1. Create Zoom meeting if online
            if record.meeting_type == 'online':
                record._create_zoom_meeting()
            
            # 2. Create calendar.event
            record._create_calendar_event()
            
            # 3. Sync to Google Calendar
            record._sync_to_google_calendar()
            
            record.state = 'confirmed'
            
            # Log to chatter
            record.message_post(
                body=_('Lịch hẹn đã được xác nhận.'),
                subtype_xmlid='mail.mt_note'
            )

    def action_done(self):
        """Đánh dấu hoàn thành"""
        for record in self:
            if record.state != 'confirmed':
                raise UserError(_('Chỉ có thể hoàn thành lịch hẹn đã xác nhận.'))
            record.state = 'done'
            record.message_post(
                body=_('Lịch hẹn đã hoàn thành.'),
                subtype_xmlid='mail.mt_note'
            )

    def action_cancel(self):
        """Hủy booking - xóa Zoom meeting + Google event"""
        for record in self:
            if record.state == 'cancelled':
                continue
            
            # Delete Zoom meeting
            if record.zoom_meeting_id:
                record._delete_zoom_meeting()
            
            # Delete Google Calendar event
            if record.google_calendar_event_id:
                record._delete_google_calendar_event()
            
            # Archive calendar event
            if record.calendar_event_id:
                record.calendar_event_id.sudo().active = False
            
            record.state = 'cancelled'
            record.message_post(
                body=_('Lịch hẹn đã bị hủy.'),
                subtype_xmlid='mail.mt_note'
            )

    def action_reset_draft(self):
        """Reset về draft"""
        for record in self:
            if record.state == 'cancelled':
                record.state = 'draft'

    def _get_attendee_emails(self):
        """Lấy danh sách email attendees"""
        self.ensure_one()
        emails = []
        
        # Customer email
        if self.customer_email:
            emails.append(self.customer_email)
        
        # User email
        if self.user_id.email:
            emails.append(self.user_id.email)
        
        # Additional attendees
        for partner in self.attendee_ids:
            if partner.email:
                emails.append(partner.email)
        
        return list(set(emails))  # Remove duplicates

    def _create_zoom_meeting(self):
        """Tạo Zoom meeting"""
        self.ensure_one()
        
        zoom_integration = self.env['zoom.integration'].get_active_integration()
        if not zoom_integration:
            self.zoom_sync_status = 'error'
            self.message_post(
                body=_('⚠️ Không thể tạo Zoom meeting: Chưa cấu hình tích hợp Zoom.'),
                subtype_xmlid='mail.mt_note'
            )
            return
        
        try:
            # Calculate duration in minutes
            duration_minutes = int(self.duration * 60)
            
            # Get attendee emails
            attendees = self._get_attendee_emails()
            
            # Create meeting
            result = zoom_integration.create_meeting(
                topic=self.title,
                start_time=self.start_datetime,
                duration=duration_minutes,
                description=self.description and self.env['mail.render.mixin']._render_template(
                    self.description, 'customer.booking', self.ids
                )[self.id] or '',
                attendees=attendees
            )
            
            self.write({
                'zoom_meeting_id': result.get('zoom_meeting_id'),
                'zoom_join_url': result.get('zoom_join_url'),
                'zoom_start_url': result.get('zoom_start_url'),
                'zoom_password': result.get('zoom_password'),
                'zoom_sync_status': 'synced'
            })
            
            self.message_post(
                body=_('✅ Đã tạo Zoom meeting: <a href="%s" target="_blank">%s</a>') % (
                    result.get('zoom_join_url'), result.get('zoom_meeting_id')
                ),
                subtype_xmlid='mail.mt_note'
            )
            
        except Exception as e:
            self.zoom_sync_status = 'error'
            self.message_post(
                body=_('❌ Lỗi tạo Zoom meeting: %s') % str(e),
                subtype_xmlid='mail.mt_note'
            )
            _logger.error("Error creating Zoom meeting for booking %s: %s", self.name, str(e))

    def _delete_zoom_meeting(self):
        """Xóa Zoom meeting"""
        self.ensure_one()
        
        if not self.zoom_meeting_id:
            return
        
        zoom_integration = self.env['zoom.integration'].get_active_integration()
        if not zoom_integration:
            return
        
        try:
            zoom_integration.delete_meeting(self.zoom_meeting_id)
            self.write({
                'zoom_meeting_id': False,
                'zoom_join_url': False,
                'zoom_start_url': False,
                'zoom_password': False,
                'zoom_sync_status': 'not_applicable'
            })
            self.message_post(
                body=_('🗑️ Đã xóa Zoom meeting.'),
                subtype_xmlid='mail.mt_note'
            )
        except Exception as e:
            _logger.warning("Error deleting Zoom meeting %s: %s", self.zoom_meeting_id, str(e))

    def _create_calendar_event(self):
        """Tạo calendar.event trong Odoo"""
        self.ensure_one()
        
        # Build partner_ids
        partner_ids = []
        if self.user_id.partner_id:
            partner_ids.append(self.user_id.partner_id.id)
        for partner in self.attendee_ids:
            if partner.id not in partner_ids:
                partner_ids.append(partner.id)
        
        # Determine location
        if self.meeting_type == 'online' and self.zoom_join_url:
            location = self.zoom_join_url
            videocall_location = self.zoom_join_url
        else:
            location = self.location or ''
            videocall_location = ''
        
        # Create calendar event
        event_vals = {
            'name': f"[{self.name}] {self.title}",
            'description': self.description,
            'start': self.start_datetime,
            'stop': self.end_datetime,
            'user_id': self.user_id.id,
            'location': location,
            'videocall_location': videocall_location,
            'partner_ids': [(6, 0, partner_ids)],
            'privacy': 'private',
        }
        
        calendar_event = self.env['calendar.event'].sudo().create(event_vals)
        self.sudo().write({'calendar_event_id': calendar_event.id})

    def _sync_to_google_calendar(self):
        """Đồng bộ lên Google Calendar"""
        self.ensure_one()
        
        google_integration = self.env['google.calendar.integration'].get_active_integration()
        if not google_integration or not google_integration.authorized:
            self.google_sync_status = 'not_synced'
            return
        
        try:
            # Get attendee emails
            attendees = self._get_attendee_emails()
            
            # Determine location
            if self.meeting_type == 'online' and self.zoom_join_url:
                location = self.zoom_join_url
            else:
                location = self.location
            
            # Build description with Zoom info if applicable
            description = self.description or ''
            if self.meeting_type == 'online' and self.zoom_join_url:
                zoom_info = f"""
<p><strong>🎥 Zoom Meeting</strong></p>
<p>Link tham gia: <a href="{self.zoom_join_url}">{self.zoom_join_url}</a></p>
"""
                if self.zoom_password:
                    zoom_info += f"<p>Mật khẩu: {self.zoom_password}</p>"
                description = zoom_info + (f"<hr/>{description}" if description else "")
            
            # Log datetime values for debugging
            _logger.info(
                f"Syncing to Google Calendar: booking={self.name}, "
                f"start_datetime={self.start_datetime} (UTC), "
                f"end_datetime={self.end_datetime} (UTC), "
                f"booking_date={self.booking_date}, booking_time={self.booking_time}"
            )
            
            result = google_integration.create_event(
                summary=f"[{self.name}] {self.title}",
                start_time=self.start_datetime,
                end_time=self.end_datetime,
                description=description,
                location=location,
                attendees=attendees
            )
            
            self.write({
                'google_calendar_event_id': result.get('google_calendar_event_id'),
                'google_calendar_link': result.get('google_calendar_link'),
                'google_sync_status': 'synced'
            })
            
            self.message_post(
                body=_('✅ Đã đồng bộ Google Calendar: <a href="%s" target="_blank">Xem trên Google</a>') % (
                    result.get('google_calendar_link')
                ),
                subtype_xmlid='mail.mt_note'
            )
            
        except Exception as e:
            self.google_sync_status = 'error'
            self.message_post(
                body=_('❌ Lỗi đồng bộ Google Calendar: %s') % str(e),
                subtype_xmlid='mail.mt_note'
            )
            _logger.error("Error syncing to Google Calendar for booking %s: %s", self.name, str(e))

    def _delete_google_calendar_event(self):
        """Xóa event trên Google Calendar"""
        self.ensure_one()
        
        if not self.google_calendar_event_id:
            return
        
        google_integration = self.env['google.calendar.integration'].get_active_integration()
        if not google_integration or not google_integration.authorized:
            return
        
        try:
            google_integration.delete_event(self.google_calendar_event_id)
            self.write({
                'google_calendar_event_id': False,
                'google_calendar_link': False,
                'google_sync_status': 'not_synced'
            })
            self.message_post(
                body=_('🗑️ Đã xóa event trên Google Calendar.'),
                subtype_xmlid='mail.mt_note'
            )
        except Exception as e:
            _logger.warning("Error deleting Google Calendar event %s: %s", 
                          self.google_calendar_event_id, str(e))

    def action_sync_google_calendar(self):
        """Đồng bộ thủ công lên Google Calendar"""
        for record in self:
            if record.state != 'confirmed':
                raise UserError(_('Chỉ có thể đồng bộ lịch hẹn đã xác nhận.'))
            
            if record.google_calendar_event_id:
                # Update existing
                record._update_google_calendar_event()
            else:
                # Create new
                record._sync_to_google_calendar()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Đồng bộ Google Calendar'),
                'message': _('Đã đồng bộ thành công!'),
                'type': 'success',
                'sticky': False,
            }
        }

    def _update_google_calendar_event(self):
        """Cập nhật event trên Google Calendar"""
        self.ensure_one()
        
        if not self.google_calendar_event_id:
            return self._sync_to_google_calendar()
        
        google_integration = self.env['google.calendar.integration'].get_active_integration()
        if not google_integration or not google_integration.authorized:
            return
        
        try:
            attendees = self._get_attendee_emails()
            
            if self.meeting_type == 'online' and self.zoom_join_url:
                location = self.zoom_join_url
            else:
                location = self.location
            
            google_integration.update_event(
                event_id=self.google_calendar_event_id,
                summary=f"[{self.name}] {self.title}",
                start_time=self.start_datetime,
                end_time=self.end_datetime,
                description=self.description,
                location=location,
                attendees=attendees
            )
            
            self.google_sync_status = 'synced'
            self.message_post(
                body=_('✅ Đã cập nhật Google Calendar.'),
                subtype_xmlid='mail.mt_note'
            )
            
        except Exception as e:
            self.google_sync_status = 'error'
            _logger.error("Error updating Google Calendar event: %s", str(e))

    def action_open_zoom_meeting(self):
        """Mở link Zoom meeting"""
        self.ensure_one()
        if not self.zoom_join_url:
            raise UserError(_('Không có link Zoom meeting.'))
        return {
            'type': 'ir.actions.act_url',
            'url': self.zoom_join_url,
            'target': 'new',
        }

    def action_open_zoom_host(self):
        """Mở link Zoom host (start meeting)"""
        self.ensure_one()
        if not self.zoom_start_url:
            raise UserError(_('Không có link Zoom host.'))
        return {
            'type': 'ir.actions.act_url',
            'url': self.zoom_start_url,
            'target': 'new',
        }

    def action_open_google_calendar(self):
        """Mở Google Calendar event"""
        self.ensure_one()
        if not self.google_calendar_link:
            raise UserError(_('Chưa đồng bộ Google Calendar.'))
        return {
            'type': 'ir.actions.act_url',
            'url': self.google_calendar_link,
            'target': 'new',
        }

    def action_open_calendar_event(self):
        """Mở calendar event trong Odoo"""
        self.ensure_one()
        if not self.calendar_event_id:
            raise UserError(_('Chưa có calendar event.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Calendar Event'),
            'res_model': 'calendar.event',
            'res_id': self.calendar_event_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
