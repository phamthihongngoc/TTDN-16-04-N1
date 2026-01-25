# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request
import json
import logging

_logger = logging.getLogger(__name__)


class AIChatController(http.Controller):
    """
    HTTP Controllers cho AI Chatbot
    Cung cấp API endpoints cho frontend widget
    """

    @http.route('/ai/chat/send', type='json', auth='user', methods=['POST'])
    def send_message(self, session_id=None, message='', context=None):
        """
        Gửi tin nhắn và nhận phản hồi từ AI
        
        Args:
            session_id: ID session (optional, sẽ tạo mới nếu không có)
            message: Nội dung tin nhắn
            context: Dict chứa active_model, active_res_id
            
        Returns:
            Dict với response từ AI
        """
        try:
            _logger.info(f"AI Chat: Received message from user {request.env.uid}: {message[:50]}")
            context = context or {}
            
            # Get or create session
            if not session_id:
                _logger.info("AI Chat: Creating new session")
                session = request.env['ai.chat.session'].get_or_create_session(
                    active_model=context.get('active_model'),
                    active_res_id=context.get('active_res_id'),
                )
                session_id = session.id
                _logger.info(f"AI Chat: Created session {session_id}")
            
            # Send message through orchestrator
            _logger.info(f"AI Chat: Sending to orchestrator, session_id={session_id}")
            orchestrator = request.env['ai.chat.orchestrator']
            result = orchestrator.send_message(session_id, message, context)
            
            # Add session_id to result
            result['session_id'] = session_id
            _logger.info(f"AI Chat: Response success={result.get('success')}")
            
            return result
            
        except Exception as e:
            _logger.exception("Error in send_message")
            return {
                'success': False,
                'error': str(e),
            }

    @http.route('/ai/chat/session', type='json', auth='user', methods=['POST'])
    def get_or_create_session(self, active_model=None, active_res_id=None):
        """
        Lấy hoặc tạo session mới
        
        Args:
            active_model: Model đang active
            active_res_id: Record ID đang active
            
        Returns:
            Session info
        """
        try:
            session = request.env['ai.chat.session'].get_or_create_session(
                active_model=active_model,
                active_res_id=active_res_id,
            )
            
            return {
                'success': True,
                'session': {
                    'id': session.id,
                    'name': session.name,
                    'active_model': session.active_model,
                    'active_res_id': session.active_res_id,
                    'message_count': session.message_count,
                }
            }
            
        except Exception as e:
            _logger.exception("Error getting/creating session")
            return {
                'success': False,
                'error': str(e),
            }

    @http.route('/ai/chat/history', type='json', auth='user', methods=['POST'])
    def get_history(self, session_id, limit=50):
        """
        Lấy lịch sử chat của session
        
        Args:
            session_id: ID session
            limit: Số tin nhắn tối đa
            
        Returns:
            List các tin nhắn
        """
        try:
            session = request.env['ai.chat.session'].browse(session_id)
            if not session.exists():
                return {
                    'success': False,
                    'error': 'Session không tồn tại',
                }
            
            # Check permission
            if session.user_id.id != request.env.uid:
                return {
                    'success': False,
                    'error': 'Không có quyền xem session này',
                }
            
            messages = session.message_ids.sorted('create_date')[-limit:]
            
            return {
                'success': True,
                'session': {
                    'id': session.id,
                    'name': session.name,
                },
                'messages': [{
                    'id': msg.id,
                    'role': msg.role,
                    'content': msg.content,
                    'content_html': msg.content_html,
                    'created_at': msg.create_date.isoformat() if msg.create_date else None,
                    'requires_confirmation': msg.requires_confirmation,
                    'action_confirmed': msg.action_confirmed,
                    'action_type': msg.action_type,
                    'is_error': msg.is_error,
                } for msg in messages]
            }
            
        except Exception as e:
            _logger.exception("Error getting history")
            return {
                'success': False,
                'error': str(e),
            }

    @http.route('/ai/chat/confirm', type='json', auth='user', methods=['POST'])
    def confirm_action(self, session_id, message_id):
        """
        Xác nhận thực hiện action
        
        Args:
            session_id: ID session
            message_id: ID message có action cần confirm
            
        Returns:
            Kết quả thực hiện action
        """
        try:
            orchestrator = request.env['ai.chat.orchestrator']
            result = orchestrator.confirm_action(session_id, message_id)
            return result
            
        except Exception as e:
            _logger.exception("Error confirming action")
            return {
                'success': False,
                'error': str(e),
            }

    @http.route('/ai/chat/reject', type='json', auth='user', methods=['POST'])
    def reject_action(self, session_id, message_id):
        """
        Từ chối action
        
        Args:
            session_id: ID session
            message_id: ID message có action cần reject
            
        Returns:
            Kết quả
        """
        try:
            orchestrator = request.env['ai.chat.orchestrator']
            result = orchestrator.reject_action(session_id, message_id)
            return result
            
        except Exception as e:
            _logger.exception("Error rejecting action")
            return {
                'success': False,
                'error': str(e),
            }

    @http.route('/ai/chat/quick_actions', type='json', auth='user', methods=['POST'])
    def get_quick_actions(self, active_model=None):
        """
        Lấy danh sách quick actions cho context
        
        Args:
            active_model: Model đang active
            
        Returns:
            List các quick actions
        """
        try:
            # Determine module from model
            module = None
            if active_model:
                if 'khach_hang' in active_model or 'don_hang' in active_model or 'ho_tro' in active_model:
                    module = 'khach_hang'
                elif 'van_ban' in active_model:
                    module = 'van_ban'
            
            actions = request.env['ai.chat.tool'].get_quick_actions_for_context(
                module=module,
                active_model=active_model,
            )
            
            return {
                'success': True,
                'quick_actions': actions,
            }
            
        except Exception as e:
            _logger.exception("Error getting quick actions")
            return {
                'success': False,
                'error': str(e),
            }

    @http.route('/ai/chat/sessions', type='json', auth='user', methods=['POST'])
    def get_user_sessions(self, limit=20, state='active'):
        """
        Lấy danh sách sessions của user
        
        Args:
            limit: Số session tối đa
            state: Filter theo state (active, archived, all)
            
        Returns:
            List các sessions
        """
        try:
            domain = [('user_id', '=', request.env.uid)]
            if state != 'all':
                domain.append(('state', '=', state))
            
            sessions = request.env['ai.chat.session'].search(
                domain,
                limit=limit,
                order='last_activity desc'
            )
            
            return {
                'success': True,
                'sessions': [{
                    'id': s.id,
                    'name': s.name,
                    'active_model': s.active_model,
                    'active_res_id': s.active_res_id,
                    'active_record_name': s.active_record_name,
                    'message_count': s.message_count,
                    'last_activity': s.last_activity.isoformat() if s.last_activity else None,
                    'state': s.state,
                } for s in sessions]
            }
            
        except Exception as e:
            _logger.exception("Error getting sessions")
            return {
                'success': False,
                'error': str(e),
            }

    @http.route('/ai/chat/clear', type='json', auth='user', methods=['POST'])
    def clear_session(self, session_id):
        """
        Xóa tin nhắn trong session
        
        Args:
            session_id: ID session
            
        Returns:
            Kết quả
        """
        try:
            session = request.env['ai.chat.session'].browse(session_id)
            if not session.exists():
                return {
                    'success': False,
                    'error': 'Session không tồn tại',
                }
            
            if session.user_id.id != request.env.uid:
                return {
                    'success': False,
                    'error': 'Không có quyền xóa session này',
                }
            
            session.action_clear_messages()
            
            return {
                'success': True,
                'message': 'Đã xóa lịch sử chat',
            }
            
        except Exception as e:
            _logger.exception("Error clearing session")
            return {
                'success': False,
                'error': str(e),
            }

    @http.route('/ai/chat/archive', type='json', auth='user', methods=['POST'])
    def archive_session(self, session_id):
        """
        Lưu trữ session
        
        Args:
            session_id: ID session
            
        Returns:
            Kết quả
        """
        try:
            session = request.env['ai.chat.session'].browse(session_id)
            if not session.exists():
                return {
                    'success': False,
                    'error': 'Session không tồn tại',
                }
            
            if session.user_id.id != request.env.uid:
                return {
                    'success': False,
                    'error': 'Không có quyền lưu trữ session này',
                }
            
            session.action_archive()
            
            return {
                'success': True,
                'message': 'Đã lưu trữ session',
            }
            
        except Exception as e:
            _logger.exception("Error archiving session")
            return {
                'success': False,
                'error': str(e),
            }

    @http.route('/ai/chat/test', type='json', auth='user', methods=['POST'])
    def test_chat(self):
        """
        Test endpoint để kiểm tra luồng chat
        """
        try:
            # 1. Test tạo session
            session = request.env['ai.chat.session'].get_or_create_session()
            
            # 2. Test gửi message qua orchestrator
            orchestrator = request.env['ai.chat.orchestrator']
            result = orchestrator.send_message(
                session.id, 
                "Xin chào, bạn là ai?",
                {}
            )
            
            return {
                'success': True,
                'session_id': session.id,
                'result': result,
            }
            
        except Exception as e:
            _logger.exception("Error in test_chat")
            import traceback
            return {
                'success': False,
                'error': str(e),
                'traceback': traceback.format_exc(),
            }
