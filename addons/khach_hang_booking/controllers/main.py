# -*- coding: utf-8 -*-

import logging
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class GoogleCalendarCallbackController(http.Controller):
    """
    Controller xử lý Google OAuth callback.
    
    Khi user authorize Google Calendar, Google sẽ redirect về URL này
    với authorization code để đổi lấy access_token + refresh_token.
    """

    @http.route('/khach_hang_booking/google_callback', type='http', auth='user', website=False)
    def google_callback(self, code=None, state=None, error=None, **kwargs):
        """
        Xử lý callback từ Google OAuth.
        
        :param code: Authorization code từ Google
        :param state: Integration record ID
        :param error: Error message nếu có lỗi
        """
        if error:
            _logger.error("Google OAuth error: %s", error)
            return request.render('khach_hang_booking.oauth_callback_error', {
                'error_message': error
            })
        
        if not code:
            _logger.error("Google OAuth callback missing code")
            return request.render('khach_hang_booking.oauth_callback_error', {
                'error_message': 'Missing authorization code'
            })
        
        if not state:
            _logger.error("Google OAuth callback missing state")
            return request.render('khach_hang_booking.oauth_callback_error', {
                'error_message': 'Missing state parameter'
            })
        
        try:
            # Get integration record from state
            integration_id = int(state)
            integration = request.env['google.calendar.integration'].browse(integration_id)
            
            if not integration.exists():
                return request.render('khach_hang_booking.oauth_callback_error', {
                    'error_message': 'Integration configuration not found'
                })
            
            # Exchange code for tokens
            success = integration._exchange_code_for_tokens(code)
            
            if success:
                return request.render('khach_hang_booking.oauth_callback_success', {
                    'email': integration.authorized_email
                })
            else:
                return request.render('khach_hang_booking.oauth_callback_error', {
                    'error_message': integration.error_message or 'Unknown error'
                })
                
        except Exception as e:
            _logger.exception("Error processing Google OAuth callback")
            return request.render('khach_hang_booking.oauth_callback_error', {
                'error_message': str(e)
            })

    @http.route('/khach_hang_booking/google_callback_close', type='http', auth='user')
    def google_callback_close(self, **kwargs):
        """Trang đóng popup sau khi authorize thành công"""
        return """
        <html>
        <head>
            <script>
                if (window.opener) {
                    window.opener.location.reload();
                }
                window.close();
            </script>
        </head>
        <body>
            <p>Đang đóng cửa sổ...</p>
            <p>Nếu cửa sổ không tự đóng, vui lòng đóng thủ công và refresh trang chính.</p>
        </body>
        </html>
        """
