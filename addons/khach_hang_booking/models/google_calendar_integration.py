# -*- coding: utf-8 -*-

import logging
import requests
from datetime import datetime, timedelta
from urllib.parse import urlencode

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_CALENDAR_API = "https://www.googleapis.com/calendar/v3"


class GoogleCalendarIntegration(models.Model):
    """
    Google Calendar Integration - OAuth 2.0 với refresh token
    
    Chỉ cho phép 1 bản ghi is_active=True tại một thời điểm.
    Admin cần authorize 1 lần để lấy refresh_token.
    """
    _name = 'google.calendar.integration'
    _description = 'Cấu hình tích hợp Google Calendar'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'

    name = fields.Char('Tên cấu hình', required=True, default='Google Calendar Integration')
    is_active = fields.Boolean('Đang hoạt động', default=False, tracking=True)
    
    # Google OAuth credentials
    client_id = fields.Char('Client ID', required=True,
                           help='OAuth Client ID từ Google Cloud Console')
    client_secret = fields.Char('Client Secret', required=True,
                               help='OAuth Client Secret từ Google Cloud Console')
    redirect_uri = fields.Char('Redirect URI', required=True,
                               default='http://localhost:8069/khach_hang_booking/google_callback',
                               help='Phải khớp với Authorized redirect URI trong Google Cloud Console')
    
    # Token management
    access_token = fields.Char('Access Token', readonly=True, copy=False)
    refresh_token = fields.Char('Refresh Token', readonly=True, copy=False)
    token_expiry = fields.Datetime('Token Expiry', readonly=True, copy=False)
    
    # Calendar settings
    calendar_id = fields.Char('Calendar ID', default='primary',
                              help='ID của calendar để đồng bộ (primary = calendar chính)')
    timezone = fields.Char('Timezone', default='Asia/Ho_Chi_Minh')
    send_notifications = fields.Boolean('Gửi email mời', default=True,
                                        help='Gửi email thông báo đến attendees khi tạo/cập nhật event')
    
    # Default reminder settings
    reminder_minutes = fields.Integer('Nhắc nhở trước (phút)', default=30)
    popup_reminder = fields.Boolean('Popup reminder', default=True)
    email_reminder = fields.Boolean('Email reminder', default=True)
    
    # Status
    authorized = fields.Boolean('Đã Authorize', readonly=True, default=False)
    last_sync = fields.Datetime('Lần đồng bộ cuối', readonly=True)
    sync_status = fields.Selection([
        ('not_configured', 'Chưa cấu hình'),
        ('pending_auth', 'Chờ xác thực'),
        ('authorized', 'Đã xác thực'),
        ('connected', 'Đã kết nối'),
        ('error', 'Lỗi')
    ], string='Trạng thái', default='not_configured', readonly=True)
    error_message = fields.Text('Thông báo lỗi', readonly=True)
    authorized_email = fields.Char('Email đã xác thực', readonly=True)

    @api.constrains('is_active')
    def _check_unique_active(self):
        """Chỉ cho phép 1 bản ghi active tại một thời điểm"""
        for record in self:
            if record.is_active:
                existing = self.search([
                    ('is_active', '=', True),
                    ('id', '!=', record.id)
                ])
                if existing:
                    raise ValidationError(_(
                        'Chỉ được phép có một cấu hình Google Calendar đang hoạt động. '
                        'Vui lòng tắt cấu hình "%s" trước.'
                    ) % existing[0].name)

    @api.model
    def get_active_integration(self):
        """Lấy cấu hình Google Calendar đang active"""
        return self.search([('is_active', '=', True)], limit=1)

    def _get_oauth_scopes(self):
        """Các scope cần thiết cho Google Calendar API"""
        return [
            'https://www.googleapis.com/auth/calendar',
            'https://www.googleapis.com/auth/calendar.events',
            'https://www.googleapis.com/auth/userinfo.email'
        ]

    def action_authorize_google(self):
        """
        Mở URL authorize Google OAuth.
        User sẽ được redirect về callback URL với authorization code.
        """
        self.ensure_one()
        
        if not self.client_id or not self.client_secret:
            raise UserError(_('Vui lòng cấu hình Client ID và Client Secret trước.'))
        
        # Build authorization URL
        params = {
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri,
            'response_type': 'code',
            'scope': ' '.join(self._get_oauth_scopes()),
            'access_type': 'offline',  # Để nhận refresh_token
            'prompt': 'consent',  # Force consent để luôn nhận refresh_token
            'state': str(self.id),  # Để identify integration record
        }
        
        auth_url = f"{GOOGLE_AUTH_URL}?{urlencode(params)}"
        
        self.write({
            'sync_status': 'pending_auth',
            'error_message': False
        })
        
        return {
            'type': 'ir.actions.act_url',
            'url': auth_url,
            'target': 'new',
        }

    def _exchange_code_for_tokens(self, code):
        """
        Đổi authorization code lấy access_token và refresh_token.
        Được gọi từ callback controller.
        """
        self.ensure_one()
        
        try:
            response = requests.post(
                GOOGLE_TOKEN_URL,
                data={
                    'client_id': self.client_id,
                    'client_secret': self.client_secret,
                    'code': code,
                    'grant_type': 'authorization_code',
                    'redirect_uri': self.redirect_uri
                },
                timeout=30
            )
            
            if response.status_code != 200:
                error_msg = f"Google OAuth Error: {response.status_code} - {response.text}"
                _logger.error(error_msg)
                self.write({
                    'sync_status': 'error',
                    'error_message': error_msg
                })
                return False
            
            data = response.json()
            access_token = data.get('access_token')
            refresh_token = data.get('refresh_token')
            expires_in = data.get('expires_in', 3600)
            
            # Tính thời gian hết hạn
            token_expiry = fields.Datetime.now() + timedelta(seconds=expires_in - 60)
            
            # Lấy email của user đã authorize
            user_email = self._get_authorized_email(access_token)
            
            update_vals = {
                'access_token': access_token,
                'token_expiry': token_expiry,
                'authorized': True,
                'sync_status': 'authorized',
                'error_message': False,
                'last_sync': fields.Datetime.now(),
                'authorized_email': user_email
            }
            
            # Chỉ cập nhật refresh_token nếu Google trả về
            # (Google thường chỉ trả refresh_token lần đầu)
            if refresh_token:
                update_vals['refresh_token'] = refresh_token
            
            self.write(update_vals)
            
            _logger.info("Google Calendar authorized successfully for: %s", user_email)
            return True
            
        except requests.RequestException as e:
            error_msg = f"Google OAuth Connection Error: {str(e)}"
            _logger.error(error_msg)
            self.write({
                'sync_status': 'error',
                'error_message': error_msg
            })
            return False

    def _get_authorized_email(self, access_token):
        """Lấy email của user đã authorize"""
        try:
            response = requests.get(
                'https://www.googleapis.com/oauth2/v2/userinfo',
                headers={'Authorization': f'Bearer {access_token}'},
                timeout=10
            )
            if response.status_code == 200:
                return response.json().get('email', '')
        except:
            pass
        return ''

    def _is_token_valid(self):
        """Kiểm tra access_token còn hạn không"""
        self.ensure_one()
        if not self.access_token or not self.token_expiry:
            return False
        return fields.Datetime.now() < self.token_expiry - timedelta(seconds=60)

    def _refresh_access_token(self):
        """
        Refresh access_token sử dụng refresh_token.
        """
        self.ensure_one()
        
        if not self.refresh_token:
            self.write({
                'sync_status': 'error',
                'error_message': 'Không có refresh token. Vui lòng authorize lại.'
            })
            raise UserError(_('Không có refresh token. Vui lòng bấm "Authorize Google" để xác thực lại.'))
        
        try:
            response = requests.post(
                GOOGLE_TOKEN_URL,
                data={
                    'client_id': self.client_id,
                    'client_secret': self.client_secret,
                    'refresh_token': self.refresh_token,
                    'grant_type': 'refresh_token'
                },
                timeout=30
            )
            
            if response.status_code != 200:
                error_msg = f"Google Token Refresh Error: {response.status_code} - {response.text}"
                _logger.error(error_msg)
                self.write({
                    'sync_status': 'error',
                    'error_message': error_msg
                })
                raise UserError(_('Không thể refresh Google token: %s') % error_msg)
            
            data = response.json()
            access_token = data.get('access_token')
            expires_in = data.get('expires_in', 3600)
            
            token_expiry = fields.Datetime.now() + timedelta(seconds=expires_in - 60)
            
            self.write({
                'access_token': access_token,
                'token_expiry': token_expiry,
                'sync_status': 'connected',
                'error_message': False,
                'last_sync': fields.Datetime.now()
            })
            
            _logger.info("Google access token refreshed successfully")
            return access_token
            
        except requests.RequestException as e:
            error_msg = f"Google Token Refresh Connection Error: {str(e)}"
            _logger.error(error_msg)
            self.write({
                'sync_status': 'error',
                'error_message': error_msg
            })
            raise UserError(_('Lỗi kết nối Google: %s') % str(e))

    def get_access_token(self):
        """Lấy access_token, tự động refresh nếu hết hạn"""
        self.ensure_one()
        if self._is_token_valid():
            return self.access_token
        return self._refresh_access_token()

    def action_test_connection(self):
        """Test kết nối Google Calendar"""
        self.ensure_one()
        
        if not self.authorized:
            raise UserError(_('Vui lòng authorize Google Calendar trước.'))
        
        try:
            token = self.get_access_token()
            
            # Test bằng cách lấy thông tin calendar
            response = requests.get(
                f"{GOOGLE_CALENDAR_API}/calendars/{self.calendar_id}",
                headers={'Authorization': f'Bearer {token}'},
                timeout=30
            )
            
            if response.status_code == 200:
                cal_info = response.json()
                self.write({
                    'sync_status': 'connected',
                    'error_message': False,
                    'last_sync': fields.Datetime.now()
                })
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Kết nối thành công!'),
                        'message': _('Đã kết nối với Google Calendar: %s') % cal_info.get('summary', 'Primary'),
                        'type': 'success',
                        'sticky': False,
                    }
                }
            else:
                raise UserError(_('Google Calendar API Error: %s') % response.text)
                
        except Exception as e:
            self.write({
                'sync_status': 'error',
                'error_message': str(e)
            })
            raise UserError(_('Lỗi kiểm tra kết nối: %s') % str(e))

    def _convert_to_google_datetime(self, dt, allday=False):
        """Convert datetime thành format Google Calendar API"""
        import pytz
        
        if allday:
            return {'date': dt.strftime('%Y-%m-%d')}
        
        # Odoo stores datetime in UTC without timezone info
        # Need to localize as UTC first, then convert to target timezone
        tz = pytz.timezone(self.timezone)
        
        if dt.tzinfo is None:
            # Datetime from Odoo is UTC without tzinfo, localize it
            dt_utc = pytz.UTC.localize(dt)
        else:
            # Already has timezone, convert to UTC first
            dt_utc = dt.astimezone(pytz.UTC)
        
        # Convert UTC to target timezone
        local_dt = dt_utc.astimezone(tz)
        
        # Log for debugging
        _logger.debug(f"Converting datetime: UTC={dt_utc.isoformat()} -> {self.timezone}={local_dt.isoformat()}")
        
        return {
            'dateTime': local_dt.isoformat(),
            'timeZone': self.timezone
        }

    def _build_reminders(self):
        """Build reminders object cho Google Calendar API"""
        overrides = []
        if self.popup_reminder:
            overrides.append({'method': 'popup', 'minutes': self.reminder_minutes})
        if self.email_reminder:
            overrides.append({'method': 'email', 'minutes': self.reminder_minutes})
        
        if overrides:
            return {
                'useDefault': False,
                'overrides': overrides
            }
        return {'useDefault': True}

    def create_event(self, summary, start_time, end_time, description=None, 
                     location=None, attendees=None, allday=False):
        """
        Tạo event trên Google Calendar.
        
        :param summary: Tiêu đề event
        :param start_time: Thời gian bắt đầu (datetime UTC hoặc date)
        :param end_time: Thời gian kết thúc (datetime UTC hoặc date)
        :param description: Mô tả
        :param location: Địa điểm hoặc meeting URL
        :param attendees: List of email addresses
        :param allday: Boolean - có phải all-day event không
        :return: dict với google_calendar_event_id, google_calendar_link
        """
        self.ensure_one()
        token = self.get_access_token()
        
        event_body = {
            'summary': summary,
            'start': self._convert_to_google_datetime(start_time, allday),
            'end': self._convert_to_google_datetime(end_time, allday),
            'reminders': self._build_reminders()
        }
        
        if description:
            event_body['description'] = description
        if location:
            event_body['location'] = location
        if attendees:
            event_body['attendees'] = [{'email': email} for email in attendees if email]
        
        # Determine sendUpdates parameter
        send_updates = 'all' if self.send_notifications and attendees else 'none'
        
        try:
            response = requests.post(
                f"{GOOGLE_CALENDAR_API}/calendars/{self.calendar_id}/events",
                headers={
                    'Authorization': f'Bearer {token}',
                    'Content-Type': 'application/json'
                },
                params={'sendUpdates': send_updates},
                json=event_body,
                timeout=30
            )
            
            if response.status_code not in [200, 201]:
                error_msg = f"Google Calendar Create Event Error: {response.status_code} - {response.text}"
                _logger.error(error_msg)
                raise UserError(_('Không thể tạo Google Calendar event: %s') % response.text)
            
            data = response.json()
            
            result = {
                'google_calendar_event_id': data.get('id', ''),
                'google_calendar_link': data.get('htmlLink', ''),
            }
            
            _logger.info("Google Calendar event created: %s", result['google_calendar_event_id'])
            return result
            
        except requests.RequestException as e:
            error_msg = f"Google Calendar API Connection Error: {str(e)}"
            _logger.error(error_msg)
            raise UserError(_('Lỗi kết nối Google Calendar API: %s') % str(e))

    def update_event(self, event_id, summary=None, start_time=None, end_time=None,
                     description=None, location=None, attendees=None, allday=False):
        """
        Cập nhật event trên Google Calendar.
        """
        self.ensure_one()
        token = self.get_access_token()
        
        # Get existing event first
        try:
            get_response = requests.get(
                f"{GOOGLE_CALENDAR_API}/calendars/{self.calendar_id}/events/{event_id}",
                headers={'Authorization': f'Bearer {token}'},
                timeout=30
            )
            
            if get_response.status_code != 200:
                raise UserError(_('Không tìm thấy Google Calendar event: %s') % event_id)
            
            event_body = get_response.json()
            
        except requests.RequestException as e:
            raise UserError(_('Lỗi lấy thông tin event: %s') % str(e))
        
        # Update fields if provided
        if summary:
            event_body['summary'] = summary
        if start_time:
            event_body['start'] = self._convert_to_google_datetime(start_time, allday)
        if end_time:
            event_body['end'] = self._convert_to_google_datetime(end_time, allday)
        if description is not None:
            event_body['description'] = description
        if location is not None:
            event_body['location'] = location
        if attendees is not None:
            event_body['attendees'] = [{'email': email} for email in attendees if email]
        
        send_updates = 'all' if self.send_notifications else 'none'
        
        try:
            response = requests.put(
                f"{GOOGLE_CALENDAR_API}/calendars/{self.calendar_id}/events/{event_id}",
                headers={
                    'Authorization': f'Bearer {token}',
                    'Content-Type': 'application/json'
                },
                params={'sendUpdates': send_updates},
                json=event_body,
                timeout=30
            )
            
            if response.status_code != 200:
                error_msg = f"Google Calendar Update Event Error: {response.status_code} - {response.text}"
                _logger.error(error_msg)
                raise UserError(_('Không thể cập nhật Google Calendar event: %s') % response.text)
            
            _logger.info("Google Calendar event updated: %s", event_id)
            return True
            
        except requests.RequestException as e:
            error_msg = f"Google Calendar API Connection Error: {str(e)}"
            _logger.error(error_msg)
            raise UserError(_('Lỗi kết nối Google Calendar API: %s') % str(e))

    def delete_event(self, event_id):
        """
        Xóa event trên Google Calendar.
        """
        self.ensure_one()
        token = self.get_access_token()
        
        send_updates = 'all' if self.send_notifications else 'none'
        
        try:
            response = requests.delete(
                f"{GOOGLE_CALENDAR_API}/calendars/{self.calendar_id}/events/{event_id}",
                headers={'Authorization': f'Bearer {token}'},
                params={'sendUpdates': send_updates},
                timeout=30
            )
            
            if response.status_code in [204, 404, 410]:  # 404/410 = already deleted
                _logger.info("Google Calendar event deleted: %s", event_id)
                return True
            else:
                error_msg = f"Google Calendar Delete Event Error: {response.status_code} - {response.text}"
                _logger.error(error_msg)
                raise UserError(_('Không thể xóa Google Calendar event: %s') % response.text)
                
        except requests.RequestException as e:
            error_msg = f"Google Calendar API Connection Error: {str(e)}"
            _logger.error(error_msg)
            raise UserError(_('Lỗi kết nối Google Calendar API: %s') % str(e))

    def action_revoke_authorization(self):
        """Hủy authorization và xóa tokens"""
        self.ensure_one()
        self.write({
            'access_token': False,
            'refresh_token': False,
            'token_expiry': False,
            'authorized': False,
            'sync_status': 'not_configured',
            'authorized_email': False,
            'error_message': False
        })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Đã hủy xác thực'),
                'message': _('Authorization đã được hủy. Bạn có thể authorize lại nếu cần.'),
                'type': 'warning',
                'sticky': False,
            }
        }
