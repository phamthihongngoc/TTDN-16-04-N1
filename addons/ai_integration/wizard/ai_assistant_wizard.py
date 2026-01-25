# -*- coding: utf-8 -*-
"""
AI Assistant Wizard - Chat với AI theo ngữ cảnh
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import json


class AIAssistantWizard(models.TransientModel):
    """
    Wizard cho phép người dùng chat với AI trực tiếp trong Odoo.
    Có thể mở từ bất kỳ record nào để hỏi đáp theo ngữ cảnh.
    """
    _name = 'ai.assistant.wizard'
    _description = 'AI Assistant'

    # Source context
    model_name = fields.Char('Model', default=lambda self: self._context.get('active_model'))
    record_id = fields.Integer('Record ID', default=lambda self: self._context.get('active_id'))
    record_name = fields.Char('Tên bản ghi', compute='_compute_record_name')
    
    # Input
    user_prompt = fields.Text('Câu hỏi / Yêu cầu', required=True,
                              help='Nhập câu hỏi hoặc yêu cầu cho AI')
    
    action_type = fields.Selection([
        ('chat', 'Chat tự do'),
        ('summarize', 'Tóm tắt'),
        ('extract', 'Trích xuất thông tin'),
        ('generate', 'Sinh nội dung'),
        ('translate_en', 'Dịch sang tiếng Anh'),
        ('translate_vi', 'Dịch sang tiếng Việt'),
        ('analyze_risk', 'Phân tích rủi ro'),
    ], string='Loại hành động', default='chat')
    
    # Context options
    include_record_context = fields.Boolean('Bao gồm ngữ cảnh bản ghi', default=True,
                                            help='Gửi thông tin bản ghi hiện tại cho AI')
    
    # Output
    ai_response = fields.Text('Phản hồi từ AI', readonly=True)
    response_ready = fields.Boolean('Đã có phản hồi', default=False)
    
    # Advanced options
    show_advanced = fields.Boolean('Tùy chọn nâng cao', default=False)
    temperature = fields.Float('Temperature', default=0.3)
    max_tokens = fields.Integer('Max tokens', default=2000)
    
    @api.depends('model_name', 'record_id')
    def _compute_record_name(self):
        for wizard in self:
            if wizard.model_name and wizard.record_id:
                try:
                    record = self.env[wizard.model_name].browse(wizard.record_id)
                    if record.exists():
                        wizard.record_name = record.display_name
                    else:
                        wizard.record_name = False
                except:
                    wizard.record_name = False
            else:
                wizard.record_name = False
    
    def _get_record_context(self):
        """Lấy ngữ cảnh từ record hiện tại."""
        if not self.model_name or not self.record_id:
            return ""
        
        try:
            record = self.env[self.model_name].browse(self.record_id)
            if not record.exists():
                return ""
            
            context_parts = [f"Bản ghi: {record.display_name}"]
            context_parts.append(f"Model: {self.model_name}")
            
            # Get important fields based on model
            important_fields = self._get_important_fields()
            
            for field_name in important_fields:
                if hasattr(record, field_name):
                    value = getattr(record, field_name)
                    if value:
                        field_info = record._fields.get(field_name)
                        if field_info:
                            label = field_info.string or field_name
                            if isinstance(value, models.BaseModel):
                                value = value.display_name
                            context_parts.append(f"{label}: {value}")
            
            return "\n".join(context_parts)
            
        except Exception as e:
            return f"Không thể lấy ngữ cảnh: {e}"
    
    def _get_important_fields(self):
        """Danh sách các field quan trọng theo model."""
        field_map = {
            'van_ban': ['ma_van_ban', 'ten_van_ban', 'trang_thai', 'nguoi_tao_id', 
                       'ngay_tao', 'noi_dung', 'loai_van_ban_id'],
            'van_ban_di': ['name', 'trich_yeu', 'trang_thai', 'nguoi_soan_thao_id',
                          'nguoi_ky_id', 'ngay_ban_hanh', 'noi_nhan'],
            'van_ban_den': ['name', 'trich_yeu', 'trang_thai', 'nguoi_gui',
                           'nguoi_nhan_id', 'ngay_den', 'ngay_het_han'],
            'nhan_vien': ['ma_dinh_danh', 'ten_nv', 'chuc_vu', 'phong_ban',
                         'email', 'so_dien_thoai', 'trang_thai_lam_viec'],
            'khach_hang': ['ten_khach_hang', 'so_dien_thoai', 'email', 'cong_ty',
                          'trang_thai', 'phan_loai', 'nhan_vien_phu_trach_id'],
            'don_hang': ['ma_don_hang', 'khach_hang_id', 'trang_thai', 'tong_tien',
                        'ngay_dat_hang'],
            'ho_so.nhan_vien': ['name', 'loai_ho_so', 'nhan_vien_id', 'trang_thai',
                               'ngay_het_han', 'bat_buoc'],
        }
        
        return field_map.get(self.model_name, ['name', 'display_name'])
    
    def action_send(self):
        """Gửi prompt và nhận phản hồi từ AI."""
        self.ensure_one()
        
        if not self.user_prompt:
            raise UserError(_("Vui lòng nhập câu hỏi hoặc yêu cầu."))
        
        ai_service = self.env['ai.service']
        
        # Build context
        context_text = ""
        if self.include_record_context:
            context_text = self._get_record_context()
        
        # Build prompt based on action type
        if self.action_type == 'chat':
            if context_text:
                prompt = f"""Ngữ cảnh:
{context_text}

Câu hỏi/Yêu cầu: {self.user_prompt}"""
            else:
                prompt = self.user_prompt
            
            response = ai_service.chat_completion(
                prompt=prompt,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                model_name=self.model_name,
                record_id=self.record_id,
                action_type='chat'
            )
            
        elif self.action_type == 'summarize':
            input_text = context_text if context_text else self.user_prompt
            response = ai_service.summarize_text(
                text=input_text,
                focus=self.user_prompt if context_text else None,
                model_name=self.model_name,
                record_id=self.record_id
            )
            
        elif self.action_type == 'extract':
            input_text = context_text if context_text else self.user_prompt
            # Parse schema from user prompt or use default
            schema = {"thông tin": "mô tả"}
            try:
                if self.user_prompt.strip().startswith('{'):
                    schema = json.loads(self.user_prompt)
            except:
                pass
            
            result = ai_service.extract_structured_data(
                text=input_text,
                schema=schema,
                model_name=self.model_name,
                record_id=self.record_id
            )
            response = json.dumps(result, ensure_ascii=False, indent=2)
            
        elif self.action_type == 'generate':
            context = {'yêu_cầu': self.user_prompt}
            if context_text:
                context['ngữ_cảnh'] = context_text
            
            response = ai_service.generate_content(
                template='general',
                context=context,
                model_name=self.model_name,
                record_id=self.record_id
            )
            
        elif self.action_type == 'translate_en':
            input_text = context_text if context_text else self.user_prompt
            response = ai_service.translate_text(
                text=input_text,
                target_language='en',
                model_name=self.model_name,
                record_id=self.record_id
            )
            
        elif self.action_type == 'translate_vi':
            response = ai_service.translate_text(
                text=self.user_prompt,
                target_language='vi',
                model_name=self.model_name,
                record_id=self.record_id
            )
            
        elif self.action_type == 'analyze_risk':
            input_text = context_text if context_text else self.user_prompt
            result = ai_service.analyze_risk(
                text=input_text,
                model_name=self.model_name,
                record_id=self.record_id
            )
            response = json.dumps(result, ensure_ascii=False, indent=2)
        else:
            response = "Loại hành động không được hỗ trợ."
        
        self.write({
            'ai_response': response,
            'response_ready': True,
        })
        
        # Keep wizard open to show response
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'ai.assistant.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
    
    def action_copy_response(self):
        """Copy response to clipboard (via JS notification)."""
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Đã copy',
                'message': 'Nội dung đã được copy vào clipboard',
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_new_chat(self):
        """Reset wizard for new chat."""
        self.write({
            'user_prompt': False,
            'ai_response': False,
            'response_ready': False,
        })
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'ai.assistant.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
