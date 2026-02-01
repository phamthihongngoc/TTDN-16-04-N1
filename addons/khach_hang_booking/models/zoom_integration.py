# -*- coding: utf-8 -*-

import base64
import logging
import requests
from datetime import datetime, timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

ZOOM_OAUTH_TOKEN_URL = "https://zoom.us/oauth/token"
ZOOM_API_BASE_URL = "https://api.zoom.us/v2"


class ZoomIntegration(models.Model):
    """
    Zoom Integration - Server-to-Server OAuth
    
    Chỉ cho phép 1 bản ghi is_active=True tại một thời điểm.
    Admin cấu hình account_id, client_id, client_secret từ Zoom Marketplace.
    """
    _name = 'zoom.integration'
    _description = 'Cấu hình tích hợp Zoom'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'

    name = fields.Char('Tên cấu hình', required=True, default='Zoom Integration')
    is_active = fields.Boolean('Đang hoạt động', default=False, tracking=True)
    
    # Zoom Server-to-Server OAuth credentials
    account_id = fields.Char('Account ID', required=True, 
                             help='Zoom Account ID từ Server-to-Server OAuth App')
    client_id = fields.Char('Client ID', required=True,
                            help='Client ID từ Zoom Server-to-Server OAuth App')
    client_secret = fields.Char('Client Secret', required=True,
                                help='Client Secret từ Zoom Server-to-Server OAuth App')
    
    # Token management
    access_token = fields.Char('Access Token', readonly=True, copy=False)
    token_expiry = fields.Datetime('Token Expiry', readonly=True, copy=False)
    
    # Meeting defaults
    default_duration = fields.Integer('Thời lượng mặc định (phút)', default=60)
    timezone = fields.Char('Timezone', default='Asia/Ho_Chi_Minh')
    host_video = fields.Boolean('Bật video Host', default=True)
    participant_video = fields.Boolean('Bật video Participant', default=True)
    join_before_host = fields.Boolean('Cho phép vào trước Host', default=False)
    waiting_room = fields.Boolean('Phòng chờ', default=True)
    mute_upon_entry = fields.Boolean('Tắt mic khi vào', default=True)
    
    # Status
    last_sync = fields.Datetime('Lần đồng bộ cuối', readonly=True)
    sync_status = fields.Selection([
        ('not_configured', 'Chưa cấu hình'),
        ('configured', 'Đã cấu hình'),
        ('connected', 'Đã kết nối'),
        ('error', 'Lỗi')
    ], string='Trạng thái', default='not_configured', readonly=True)
    error_message = fields.Text('Thông báo lỗi', readonly=True)

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
                        'Chỉ được phép có một cấu hình Zoom đang hoạt động. '
                        'Vui lòng tắt cấu hình "%s" trước.'
                    ) % existing[0].name)

    @api.model
    def get_active_integration(self):
        """Lấy cấu hình Zoom đang active"""
        return self.search([('is_active', '=', True)], limit=1)

    def _get_auth_header(self):
        """Tạo Basic Auth header cho OAuth token request"""
        self.ensure_one()
        credentials = f"{self.client_id}:{self.client_secret}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded}"

    def _is_token_valid(self):
        """Kiểm tra access_token còn hạn không (trừ 60s buffer)"""
        self.ensure_one()
        if not self.access_token or not self.token_expiry:
            return False
        # Buffer 60 seconds để tránh "sát hạn"
        return fields.Datetime.now() < self.token_expiry - timedelta(seconds=60)

    def _refresh_access_token(self):
        """
        Lấy access_token mới từ Zoom OAuth endpoint.
        Server-to-Server OAuth sử dụng grant_type=account_credentials.
        """
        self.ensure_one()
        
        try:
            response = requests.post(
                ZOOM_OAUTH_TOKEN_URL,
                headers={
                    'Authorization': self._get_auth_header(),
                    'Content-Type': 'application/x-www-form-urlencoded'
                },
                data={
                    'grant_type': 'account_credentials',
                    'account_id': self.account_id
                },
                timeout=30
            )
            
            if response.status_code != 200:
                error_msg = f"Zoom OAuth Error: {response.status_code} - {response.text}"
                _logger.error(error_msg)
                self.write({
                    'sync_status': 'error',
                    'error_message': error_msg
                })
                raise UserError(_('Không thể lấy Zoom access token: %s') % error_msg)
            
            data = response.json()
            access_token = data.get('access_token')
            expires_in = data.get('expires_in', 3600)  # Default 1 hour
            
            # Tính thời gian hết hạn (trừ 60s buffer)
            token_expiry = fields.Datetime.now() + timedelta(seconds=expires_in - 60)
            
            self.write({
                'access_token': access_token,
                'token_expiry': token_expiry,
                'sync_status': 'connected',
                'error_message': False,
                'last_sync': fields.Datetime.now()
            })
            
            _logger.info("Zoom access token refreshed successfully")
            return access_token
            
        except requests.RequestException as e:
            error_msg = f"Zoom Connection Error: {str(e)}"
            _logger.error(error_msg)
            self.write({
                'sync_status': 'error',
                'error_message': error_msg
            })
            raise UserError(_('Lỗi kết nối Zoom: %s') % str(e))

    def get_access_token(self):
        """Lấy access_token, tự động refresh nếu hết hạn"""
        self.ensure_one()
        if self._is_token_valid():
            return self.access_token
        return self._refresh_access_token()

    def action_test_connection(self):
        """Test kết nối Zoom"""
        self.ensure_one()
        try:
            token = self.get_access_token()
            
            # Test bằng cách gọi API lấy thông tin user
            response = requests.get(
                f"{ZOOM_API_BASE_URL}/users/me",
                headers={'Authorization': f'Bearer {token}'},
                timeout=30
            )
            
            if response.status_code == 200:
                user_info = response.json()
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
                        'message': _('Đã kết nối với Zoom account: %s') % user_info.get('email', 'N/A'),
                        'type': 'success',
                        'sticky': False,
                    }
                }
            else:
                raise UserError(_('Zoom API Error: %s') % response.text)
                
        except Exception as e:
            self.write({
                'sync_status': 'error',
                'error_message': str(e)
            })
            raise UserError(_('Lỗi kiểm tra kết nối: %s') % str(e))

    def create_meeting(self, topic, start_time, duration=None, description=None, attendees=None):
        """
        Tạo Zoom scheduled meeting.
        
        :param topic: Chủ đề cuộc họp
        :param start_time: Thời gian bắt đầu (datetime UTC)
        :param duration: Thời lượng (phút), mặc định lấy từ cấu hình
        :param description: Mô tả cuộc họp
        :param attendees: Danh sách email người tham gia
        :return: dict với zoom_meeting_id, join_url, start_url, password
        """
        self.ensure_one()
        token = self.get_access_token()
        
        if duration is None:
            duration = self.default_duration
        
        # Convert UTC to target timezone string format
        start_time_str = start_time.strftime('%Y-%m-%dT%H:%M:%S')
        
        payload = {
            'topic': topic,
            'type': 2,  # Scheduled meeting
            'start_time': start_time_str,
            'duration': duration,
            'timezone': self.timezone,
            'agenda': description or '',
            'settings': {
                'host_video': self.host_video,
                'participant_video': self.participant_video,
                'join_before_host': self.join_before_host,
                'waiting_room': self.waiting_room,
                'mute_upon_entry': self.mute_upon_entry,
                'approval_type': 2,  # No registration required
                'audio': 'both',
                'auto_recording': 'none',
            }
        }
        
        # Add registrants if provided
        if attendees:
            payload['settings']['meeting_invitees'] = [
                {'email': email} for email in attendees if email
            ]
        
        try:
            response = requests.post(
                f"{ZOOM_API_BASE_URL}/users/me/meetings",
                headers={
                    'Authorization': f'Bearer {token}',
                    'Content-Type': 'application/json'
                },
                json=payload,
                timeout=30
            )
            
            if response.status_code not in [200, 201]:
                error_msg = f"Zoom Create Meeting Error: {response.status_code} - {response.text}"
                _logger.error(error_msg)
                raise UserError(_('Không thể tạo Zoom meeting: %s') % response.text)
            
            data = response.json()
            
            result = {
                'zoom_meeting_id': str(data.get('id', '')),
                'zoom_join_url': data.get('join_url', ''),
                'zoom_start_url': data.get('start_url', ''),
                'zoom_password': data.get('password', ''),
            }
            
            _logger.info("Zoom meeting created: %s", result['zoom_meeting_id'])
            return result
            
        except requests.RequestException as e:
            error_msg = f"Zoom API Connection Error: {str(e)}"
            _logger.error(error_msg)
            raise UserError(_('Lỗi kết nối Zoom API: %s') % str(e))

    def update_meeting(self, meeting_id, topic=None, start_time=None, duration=None, description=None):
        """
        Cập nhật Zoom meeting.
        
        :param meeting_id: ID cuộc họp Zoom
        :param topic: Chủ đề mới (optional)
        :param start_time: Thời gian bắt đầu mới (optional)
        :param duration: Thời lượng mới (optional)
        :param description: Mô tả mới (optional)
        :return: True nếu thành công
        """
        self.ensure_one()
        token = self.get_access_token()
        
        payload = {}
        if topic:
            payload['topic'] = topic
        if start_time:
            payload['start_time'] = start_time.strftime('%Y-%m-%dT%H:%M:%S')
            payload['timezone'] = self.timezone
        if duration:
            payload['duration'] = duration
        if description is not None:
            payload['agenda'] = description
            
        if not payload:
            return True  # Nothing to update
        
        try:
            response = requests.patch(
                f"{ZOOM_API_BASE_URL}/meetings/{meeting_id}",
                headers={
                    'Authorization': f'Bearer {token}',
                    'Content-Type': 'application/json'
                },
                json=payload,
                timeout=30
            )
            
            if response.status_code == 204:
                _logger.info("Zoom meeting updated: %s", meeting_id)
                return True
            else:
                error_msg = f"Zoom Update Meeting Error: {response.status_code} - {response.text}"
                _logger.error(error_msg)
                raise UserError(_('Không thể cập nhật Zoom meeting: %s') % response.text)
                
        except requests.RequestException as e:
            error_msg = f"Zoom API Connection Error: {str(e)}"
            _logger.error(error_msg)
            raise UserError(_('Lỗi kết nối Zoom API: %s') % str(e))

    def delete_meeting(self, meeting_id):
        """
        Xóa Zoom meeting.
        
        :param meeting_id: ID cuộc họp Zoom
        :return: True nếu thành công
        """
        self.ensure_one()
        token = self.get_access_token()
        
        try:
            response = requests.delete(
                f"{ZOOM_API_BASE_URL}/meetings/{meeting_id}",
                headers={'Authorization': f'Bearer {token}'},
                timeout=30
            )
            
            if response.status_code in [204, 404]:  # 404 = already deleted
                _logger.info("Zoom meeting deleted: %s", meeting_id)
                return True
            else:
                error_msg = f"Zoom Delete Meeting Error: {response.status_code} - {response.text}"
                _logger.error(error_msg)
                raise UserError(_('Không thể xóa Zoom meeting: %s') % response.text)
                
        except requests.RequestException as e:
            error_msg = f"Zoom API Connection Error: {str(e)}"
            _logger.error(error_msg)
            raise UserError(_('Lỗi kết nối Zoom API: %s') % str(e))

    @api.model
    def get_meeting_info(self, meeting_id):
        """Lấy thông tin chi tiết của meeting"""
        integration = self.get_active_integration()
        if not integration:
            return None
            
        token = integration.get_access_token()
        
        try:
            response = requests.get(
                f"{ZOOM_API_BASE_URL}/meetings/{meeting_id}",
                headers={'Authorization': f'Bearer {token}'},
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()
            return None
            
        except requests.RequestException:
            return None
