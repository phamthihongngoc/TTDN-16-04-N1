# -*- coding: utf-8 -*-

from odoo import models, fields, api
import json
import logging

_logger = logging.getLogger(__name__)


class AIChatMessage(models.Model):
    """Tin nhắn trong phiên chat AI"""
    _name = 'ai.chat.message'
    _description = 'AI Chat Message'
    _order = 'create_date asc, id asc'

    session_id = fields.Many2one(
        'ai.chat.session',
        string='Phiên chat',
        required=True,
        ondelete='cascade',
        index=True
    )
    
    # Message content
    role = fields.Selection([
        ('user', 'Người dùng'),
        ('assistant', 'Trợ lý AI'),
        ('system', 'Hệ thống'),
        ('tool', 'Tool Result'),
    ], string='Vai trò', required=True)
    
    content = fields.Text(
        string='Nội dung',
        required=True
    )
    content_html = fields.Html(
        string='Nội dung HTML',
        compute='_compute_content_html',
        sanitize=False
    )
    
    # Tool calling
    tool_calls = fields.Text(
        string='Tool Calls',
        help='JSON array các tool calls từ AI'
    )
    tool_name = fields.Char(
        string='Tool Name',
        help='Tên tool được gọi'
    )
    tool_call_id = fields.Char(
        string='Tool Call ID'
    )
    tool_arguments = fields.Text(
        string='Tool Arguments',
        help='JSON arguments cho tool'
    )
    tool_result = fields.Text(
        string='Tool Result',
        help='Kết quả trả về từ tool'
    )
    
    # Action pending (for confirm)
    requires_confirmation = fields.Boolean(
        string='Cần xác nhận',
        default=False
    )
    action_type = fields.Char(
        string='Loại action'
    )
    action_payload = fields.Text(
        string='Action Payload',
        help='JSON data cho action cần xác nhận'
    )
    action_confirmed = fields.Boolean(
        string='Đã xác nhận',
        default=False
    )
    action_result = fields.Text(
        string='Kết quả action'
    )
    
    # Metrics
    tokens_used = fields.Integer(
        string='Tokens',
        default=0
    )
    prompt_tokens = fields.Integer(
        string='Prompt Tokens',
        default=0
    )
    completion_tokens = fields.Integer(
        string='Completion Tokens',
        default=0
    )
    cost = fields.Float(
        string='Chi phí (USD)',
        digits=(16, 6),
        default=0
    )
    latency = fields.Float(
        string='Latency (ms)',
        digits=(16, 2),
        default=0
    )
    
    # Metadata
    model_used = fields.Char(
        string='Model AI'
    )
    context_model = fields.Char(
        string='Context Model',
        help='Model Odoo làm context'
    )
    context_res_id = fields.Integer(
        string='Context Record ID'
    )
    
    # Error handling
    is_error = fields.Boolean(
        string='Có lỗi',
        default=False
    )
    error_message = fields.Text(
        string='Thông báo lỗi'
    )

    @api.depends('content', 'role')
    def _compute_content_html(self):
        """Convert markdown-like content to HTML"""
        import re
        for msg in self:
            content = msg.content or ''
            # Basic markdown conversion
            # Code blocks
            content = re.sub(
                r'```(\w+)?\n(.*?)```',
                r'<pre><code class="language-\1">\2</code></pre>',
                content,
                flags=re.DOTALL
            )
            # Inline code
            content = re.sub(r'`([^`]+)`', r'<code>\1</code>', content)
            # Bold
            content = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', content)
            # Italic
            content = re.sub(r'\*([^*]+)\*', r'<em>\1</em>', content)
            # Line breaks
            content = content.replace('\n', '<br/>')
            # Lists
            content = re.sub(r'<br/>- ', '<br/>• ', content)
            
            msg.content_html = content

    @api.model
    def create_user_message(self, session_id, content, context_model=None, context_res_id=None):
        """Tạo tin nhắn từ user"""
        return self.create({
            'session_id': session_id,
            'role': 'user',
            'content': content,
            'context_model': context_model,
            'context_res_id': context_res_id,
        })

    @api.model
    def create_assistant_message(self, session_id, content, tokens_info=None, 
                                  tool_calls=None, model_used=None, latency=0):
        """Tạo tin nhắn từ Trợ lý AI"""
        values = {
            'session_id': session_id,
            'role': 'assistant',
            'content': content,
            'model_used': model_used,
            'latency': latency,
        }
        
        if tokens_info:
            values.update({
                'tokens_used': tokens_info.get('total_tokens', 0),
                'prompt_tokens': tokens_info.get('prompt_tokens', 0),
                'completion_tokens': tokens_info.get('completion_tokens', 0),
                'cost': tokens_info.get('cost', 0),
            })
        
        if tool_calls:
            values['tool_calls'] = json.dumps(tool_calls, ensure_ascii=False)
        
        return self.create(values)

    @api.model
    def create_tool_result_message(self, session_id, tool_name, tool_call_id, 
                                    arguments, result):
        """Tạo tin nhắn kết quả tool"""
        return self.create({
            'session_id': session_id,
            'role': 'tool',
            'content': f"[Tool: {tool_name}]",
            'tool_name': tool_name,
            'tool_call_id': tool_call_id,
            'tool_arguments': json.dumps(arguments, ensure_ascii=False) if arguments else None,
            'tool_result': json.dumps(result, ensure_ascii=False) if isinstance(result, dict) else str(result),
        })

    @api.model
    def create_action_message(self, session_id, content, action_type, action_payload):
        """Tạo tin nhắn có action cần xác nhận"""
        return self.create({
            'session_id': session_id,
            'role': 'assistant',
            'content': content,
            'requires_confirmation': True,
            'action_type': action_type,
            'action_payload': json.dumps(action_payload, ensure_ascii=False),
        })

    def confirm_action(self):
        """Xác nhận thực hiện action"""
        self.ensure_one()
        if not self.requires_confirmation:
            return {'success': False, 'error': 'Không có action cần xác nhận'}
        
        if self.action_confirmed:
            return {'success': False, 'error': 'Action đã được xác nhận trước đó'}
        
        try:
            payload = json.loads(self.action_payload) if self.action_payload else {}
            # Execute action through orchestrator
            orchestrator = self.env['ai.chat.orchestrator']
            result = orchestrator.execute_confirmed_action(
                self.action_type,
                payload,
                self.session_id
            )
            
            self.write({
                'action_confirmed': True,
                'action_result': json.dumps(result, ensure_ascii=False),
            })
            
            return {'success': True, 'result': result}
            
        except Exception as e:
            self.write({
                'is_error': True,
                'error_message': str(e),
            })
            return {'success': False, 'error': str(e)}

    def reject_action(self):
        """Từ chối action"""
        self.ensure_one()
        self.write({
            'requires_confirmation': False,
            'action_result': 'Đã từ chối bởi người dùng',
        })
        self.session_id.clear_pending_action()
        return {'success': True}

    def get_tool_calls_parsed(self):
        """Parse tool calls JSON"""
        if self.tool_calls:
            try:
                return json.loads(self.tool_calls)
            except Exception:
                return []
        return []

    def get_action_payload_parsed(self):
        """Parse action payload JSON"""
        if self.action_payload:
            try:
                return json.loads(self.action_payload)
            except Exception:
                return {}
        return {}
