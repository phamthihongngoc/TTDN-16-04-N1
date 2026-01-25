# -*- coding: utf-8 -*-
"""
Res Config Settings - Cấu hình AI Integration
"""

from odoo import models, fields, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # OpenAI API Configuration
    ai_openai_api_key = fields.Char(
        string='OpenAI API Key',
        config_parameter='ai_integration.openai_api_key',
        help='API Key từ OpenAI Platform (https://platform.openai.com/api-keys)'
    )
    
    ai_openai_model = fields.Selection([
        ('gpt-4o', 'GPT-4o (Mới nhất, thông minh)'),
        ('gpt-4o-mini', 'GPT-4o Mini (Nhanh, rẻ)'),
        ('gpt-4-turbo', 'GPT-4 Turbo'),
        ('gpt-4', 'GPT-4'),
        ('gpt-3.5-turbo', 'GPT-3.5 Turbo (Rẻ nhất)'),
    ], string='Model AI',
       default='gpt-4o-mini',
       config_parameter='ai_integration.openai_model',
       help='Model AI sử dụng. GPT-4o-mini là lựa chọn cân bằng giữa chi phí và hiệu suất.'
    )
    
    ai_max_tokens = fields.Integer(
        string='Max Tokens',
        default=2000,
        config_parameter='ai_integration.max_tokens',
        help='Số token tối đa cho response. Tăng nếu cần output dài hơn.'
    )
    
    ai_temperature = fields.Float(
        string='Temperature',
        default=0.3,
        config_parameter='ai_integration.temperature',
        help='0.0 = Chính xác, 1.0 = Sáng tạo. Khuyến nghị 0.2-0.5 cho business.'
    )
    
    ai_timeout = fields.Integer(
        string='Timeout (giây)',
        default=60,
        config_parameter='ai_integration.timeout',
        help='Thời gian chờ tối đa cho mỗi request API'
    )
    
    ai_max_retries = fields.Integer(
        string='Max Retries',
        default=3,
        config_parameter='ai_integration.max_retries',
        help='Số lần thử lại khi gặp lỗi network/rate limit'
    )
    
    # Logging & Cache
    ai_log_enabled = fields.Boolean(
        string='Ghi Log',
        default=True,
        config_parameter='ai_integration.log_enabled',
        help='Ghi log tất cả request/response cho audit và debug'
    )
    
    ai_cache_enabled = fields.Boolean(
        string='Bật Cache',
        default=True,
        config_parameter='ai_integration.cache_enabled',
        help='Cache response để giảm chi phí với các prompt giống nhau'
    )
    
    ai_cache_ttl = fields.Integer(
        string='Cache TTL (giây)',
        default=3600,
        config_parameter='ai_integration.cache_ttl',
        help='Thời gian cache response (giây)'
    )
    
    ai_log_retention_days = fields.Integer(
        string='Lưu log (ngày)',
        default=90,
        config_parameter='ai_integration.log_retention_days',
        help='Số ngày giữ log trước khi tự động xóa'
    )
    
    # Privacy & Security
    ai_mask_pii = fields.Boolean(
        string='Che thông tin nhạy cảm',
        default=True,
        config_parameter='ai_integration.mask_pii',
        help='Tự động che SĐT, email, CMND trước khi gửi lên AI'
    )
    
    # Statistics (read-only)
    ai_total_requests = fields.Integer(
        string='Tổng requests (30 ngày)',
        compute='_compute_ai_stats'
    )
    ai_total_cost = fields.Float(
        string='Tổng chi phí (30 ngày)',
        compute='_compute_ai_stats'
    )
    ai_success_rate = fields.Float(
        string='Tỉ lệ thành công (%)',
        compute='_compute_ai_stats'
    )
    
    def _compute_ai_stats(self):
        for record in self:
            try:
                # Use sudo() to bypass access rights for statistics
                stats = self.env['ai.log'].sudo().get_usage_stats(days=30)
                record.ai_total_requests = stats.get('total_requests', 0)
                record.ai_total_cost = stats.get('total_cost_usd', 0)
                record.ai_success_rate = stats.get('success_rate', 0)
            except Exception as e:
                # Silently fail if ai.log is not accessible
                record.ai_total_requests = 0
                record.ai_total_cost = 0
                record.ai_success_rate = 0
    
    def action_test_connection(self):
        """Test OpenAI API connection."""
        self.ensure_one()
        
        # IMPORTANT: Save settings first before testing
        self.execute()
        
        try:
            ai_service = self.env['ai.service']
            response = ai_service.chat_completion(
                prompt="Trả lời ngắn gọn: 2 + 2 = ?",
                max_tokens=50,
                use_cache=False
            )
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Kết nối thành công!',
                    'message': f'OpenAI API hoạt động bình thường. Response: {response}',
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Lỗi kết nối',
                    'message': str(e),
                    'type': 'danger',
                    'sticky': True,
                }
            }
    
    def action_view_logs(self):
        """Open AI logs."""
        return {
            'type': 'ir.actions.act_window',
            'name': 'AI Logs',
            'res_model': 'ai.log',
            'view_mode': 'tree,form',
            'target': 'current',
        }
    
    def action_view_jobs(self):
        """Open AI jobs."""
        return {
            'type': 'ir.actions.act_window',
            'name': 'AI Jobs',
            'res_model': 'ai.job',
            'view_mode': 'tree,form',
            'target': 'current',
        }
