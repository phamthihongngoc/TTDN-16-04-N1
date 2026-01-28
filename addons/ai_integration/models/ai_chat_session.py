# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError
import json
import logging

_logger = logging.getLogger(__name__)


class AIChatSession(models.Model):
    """Phiên chat với Trợ lý AI"""
    _name = 'ai.chat.session'
    _description = 'AI Chat Session'
    _order = 'last_activity desc, id desc'

    name = fields.Char(
        string='Tiêu đề',
        compute='_compute_name',
        store=True
    )
    user_id = fields.Many2one(
        'res.users',
        string='Người dùng',
        default=lambda self: self.env.user,
        required=True,
        index=True
    )
    
    # Module context
    module = fields.Selection([
        ('khach_hang', 'Khách hàng'),
        ('van_ban', 'Văn bản'),
        ('nhan_su', 'Nhân sự'),
    ], string='Module', help='Module hiện tại')
    
    # Context - màn hình đang mở
    active_model = fields.Char(
        string='Model',
        help='Model Odoo đang active (vd: khach_hang, van_ban_di)'
    )
    active_res_id = fields.Integer(
        string='Record ID',
        help='ID của record đang mở'
    )
    active_record_name = fields.Char(
        string='Tên Record',
        compute='_compute_active_record_name'
    )
    
    # State
    state = fields.Selection([
        ('active', 'Đang hoạt động'),
        ('archived', 'Đã lưu trữ'),
    ], string='Trạng thái', default='active', required=True)
    
    # Messages
    message_ids = fields.One2many(
        'ai.chat.message',
        'session_id',
        string='Tin nhắn'
    )
    message_count = fields.Integer(
        string='Số tin nhắn',
        compute='_compute_message_count'
    )
    
    # Timestamps
    last_activity = fields.Datetime(
        string='Hoạt động cuối',
        default=fields.Datetime.now
    )
    
    # Statistics
    total_tokens = fields.Integer(
        string='Tổng tokens',
        compute='_compute_stats',
        store=True
    )
    total_cost = fields.Float(
        string='Tổng chi phí (USD)',
        compute='_compute_stats',
        store=True,
        digits=(16, 6)
    )
    
    # Pending action (for confirm flow)
    pending_action = fields.Text(
        string='Pending Action',
        help='JSON chứa action đang chờ xác nhận'
    )
    pending_action_type = fields.Char(
        string='Loại Action'
    )

    @api.depends('active_model', 'active_res_id', 'create_date')
    def _compute_name(self):
        for session in self:
            if session.active_model and session.active_res_id:
                try:
                    record = self.env[session.active_model].sudo().browse(session.active_res_id)
                    if record.exists():
                        record_name = record.display_name or f"#{session.active_res_id}"
                        session.name = f"Chat: {record_name}"
                    else:
                        session.name = f"Chat: {session.active_model}"
                except Exception:
                    session.name = f"Chat: {session.active_model}"
            else:
                date_str = session.create_date.strftime('%d/%m/%Y %H:%M') if session.create_date else ''
                session.name = f"Chat phiên {date_str}"

    def _compute_active_record_name(self):
        for session in self:
            if session.active_model and session.active_res_id:
                try:
                    record = self.env[session.active_model].browse(session.active_res_id)
                    if record.exists():
                        session.active_record_name = record.display_name
                    else:
                        session.active_record_name = f"[Deleted #{session.active_res_id}]"
                except Exception:
                    session.active_record_name = f"[Error]"
            else:
                session.active_record_name = False

    @api.depends('message_ids')
    def _compute_message_count(self):
        for session in self:
            session.message_count = len(session.message_ids)

    def _infer_module_from_model(self, model_name):
        if not model_name:
            return None
        if 'khach_hang' in model_name or 'don_hang' in model_name or 'ho_tro' in model_name:
            return 'khach_hang'
        if 'van_ban' in model_name or 'yeu_cau_ky' in model_name:
            return 'van_ban'
        if 'nhan_vien' in model_name or 'phong_ban' in model_name or 'cham_cong' in model_name or 'bang_luong' in model_name or 'ho_so' in model_name:
            return 'nhan_su'
        return None

    @api.depends('message_ids.tokens_used', 'message_ids.cost')
    def _compute_stats(self):
        for session in self:
            session.total_tokens = sum(session.message_ids.mapped('tokens_used'))
            session.total_cost = sum(session.message_ids.mapped('cost'))

    def action_archive(self):
        """Lưu trữ session"""
        self.write({'state': 'archived'})

    def action_activate(self):
        """Kích hoạt lại session"""
        self.write({'state': 'active'})

    def action_clear_messages(self):
        """Xóa tất cả tin nhắn"""
        self.message_ids.unlink()
        self.pending_action = False
        self.pending_action_type = False

    @api.model
    def get_or_create_session(self, active_model=None, active_res_id=None):
        """Lấy session hiện tại hoặc tạo mới"""
        domain = [
            ('user_id', '=', self.env.uid),
            ('state', '=', 'active'),
        ]
        
        if active_model and active_res_id:
            domain += [
                ('active_model', '=', active_model),
                ('active_res_id', '=', active_res_id),
            ]
        
        session = self.search(domain, limit=1, order='last_activity desc')
        
        if not session:
            module = self._infer_module_from_model(active_model)
            session = self.create({
                'user_id': self.env.uid,
                'active_model': active_model,
                'active_res_id': active_res_id,
                'module': module,
            })
        else:
            module = self._infer_module_from_model(active_model)
            if module and session.module != module:
                session.write({'module': module})
        
        return session

    def update_activity(self):
        """Cập nhật thời gian hoạt động"""
        self.write({'last_activity': fields.Datetime.now()})

    @api.model
    def create_or_get_session(self, context_data):
        """
        Tạo hoặc lấy session hiện tại cho user
        
        Args:
            context_data: dict chứa active_model và active_res_id
            
        Returns:
            dict: Session data với messages
        """
        active_model = context_data.get('active_model')
        active_res_id = context_data.get('active_res_id')
        module = context_data.get('module') or self._infer_module_from_model(active_model)
        
        # Tìm session đang active của user với context tương tự
        domain = [
            ('user_id', '=', self.env.user.id),
            ('state', '=', 'active'),
        ]
        
        if active_model:
            domain.append(('active_model', '=', active_model))
        if active_res_id:
            domain.append(('active_res_id', '=', active_res_id))
        
        session = self.search(domain, limit=1, order='last_activity desc')
        
        # Nếu không tìm thấy, tạo mới
        if not session:
            session = self.create({
                'user_id': self.env.user.id,
                'active_model': active_model,
                'active_res_id': active_res_id,
                'module': module,
                'state': 'active',
            })
        else:
            if module and session.module != module:
                session.write({'module': module})
            session.update_activity()
        
        # Lấy messages
        messages = []
        for msg in session.message_ids.sorted('create_date'):
            messages.append({
                'role': msg.role,
                'content': msg.content,
                'timestamp': msg.create_date.isoformat() if msg.create_date else None,
            })
        
        return {
            'id': session.id,
            'name': session.name,
            'messages': messages,
            'active_model': session.active_model,
            'active_res_id': session.active_res_id,
        }

    def set_pending_action(self, action_type, action_data):
        """Lưu action đang chờ xác nhận"""
        self.write({
            'pending_action': json.dumps(action_data, ensure_ascii=False),
            'pending_action_type': action_type,
        })

    def get_pending_action(self):
        """Lấy action đang chờ"""
        if self.pending_action:
            return {
                'type': self.pending_action_type,
                'data': json.loads(self.pending_action),
            }
        return None

    def clear_pending_action(self):
        """Xóa pending action"""
        self.write({
            'pending_action': False,
            'pending_action_type': False,
        })

    def clear_session(self):
        """Xóa toàn bộ tin nhắn trong session"""
        self.ensure_one()
        self.message_ids.unlink()
        return True

    def get_conversation_history(self, limit=20):
        """Lấy lịch sử hội thoại cho context
        
        Chỉ trả về các message user và assistant để tránh lỗi format với OpenAI.
        Tool results được bỏ qua vì chúng yêu cầu format đặc biệt.
        """
        messages = self.message_ids.filtered(
            lambda m: m.role in ('user', 'assistant')
        ).sorted('create_date')[-limit:]
        
        history = []
        for msg in messages:
            # Chỉ thêm message có content
            if msg.content:
                history.append({
                    'role': msg.role,
                    'content': msg.content,
                })
        return history
