# -*- coding: utf-8 -*-
"""
AI Log Model - Ghi log tất cả các tương tác với AI
"""

from odoo import models, fields, api
from datetime import datetime, timedelta


class AILog(models.Model):
    """
    AI Log - Ghi log mọi request/response với OpenAI API.
    Dùng cho audit, monitoring, debug và phân tích chi phí.
    """
    _name = 'ai.log'
    _description = 'AI Request Log'
    _order = 'create_date desc'
    _rec_name = 'action_type'

    # User & Context
    user_id = fields.Many2one('res.users', string='Người dùng', required=True, index=True)
    company_id = fields.Many2one('res.company', string='Công ty', 
                                  default=lambda self: self.env.company)
    
    # Source reference
    model_name = fields.Char('Model', index=True, help='Odoo model name')
    record_id = fields.Integer('Record ID')
    record_ref = fields.Reference(
        selection='_get_reference_models',
        string='Bản ghi tham chiếu',
        compute='_compute_record_ref',
        store=False
    )
    
    # Action
    action_type = fields.Selection([
        ('chat', 'Chat'),
        ('summarize', 'Tóm tắt'),
        ('extract', 'Trích xuất'),
        ('classify', 'Phân loại'),
        ('generate', 'Sinh nội dung'),
        ('analyze_risk', 'Phân tích rủi ro'),
        ('qa', 'Hỏi đáp'),
        ('translate', 'Dịch thuật'),
        ('other', 'Khác'),
    ], string='Loại hành động', required=True, index=True)
    
    # AI Model
    ai_model = fields.Char('AI Model', help='e.g., gpt-4o-mini')
    
    # Content (truncated for storage)
    prompt_preview = fields.Text('Prompt (preview)', help='First 500 chars')
    response_preview = fields.Text('Response (preview)', help='First 500 chars')
    
    # Metrics
    input_tokens = fields.Integer('Input Tokens')
    output_tokens = fields.Integer('Output Tokens')
    total_tokens = fields.Integer('Total Tokens')
    cost_usd = fields.Float('Chi phí (USD)', digits=(10, 6))
    latency_ms = fields.Integer('Latency (ms)')
    
    # Status
    status = fields.Selection([
        ('success', 'Thành công'),
        ('error', 'Lỗi'),
        ('timeout', 'Timeout'),
        ('rate_limit', 'Rate Limit'),
    ], string='Trạng thái', default='success', required=True, index=True)
    error_message = fields.Text('Thông báo lỗi')
    
    # Timestamps
    request_time = fields.Datetime('Thời gian request', default=fields.Datetime.now)
    
    @api.model
    def _get_reference_models(self):
        """Get list of models for reference field."""
        models_list = self.env['ir.model'].search([])
        return [(model.model, model.name) for model in models_list]
    
    @api.depends('model_name', 'record_id')
    def _compute_record_ref(self):
        for log in self:
            if log.model_name and log.record_id:
                try:
                    record = self.env[log.model_name].browse(log.record_id)
                    if record.exists():
                        log.record_ref = f"{log.model_name},{log.record_id}"
                    else:
                        log.record_ref = False
                except:
                    log.record_ref = False
            else:
                log.record_ref = False
    
    def action_view_record(self):
        """Open the source record."""
        self.ensure_one()
        if self.model_name and self.record_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': self.model_name,
                'res_id': self.record_id,
                'view_mode': 'form',
                'target': 'current',
            }
    
    @api.model
    def get_usage_stats(self, days=30, user_id=None):
        """
        Get usage statistics for monitoring.
        
        Args:
            days: Number of days to look back
            user_id: Filter by user (optional)
            
        Returns:
            dict with statistics
        """
        date_from = datetime.now() - timedelta(days=days)
        domain = [('create_date', '>=', date_from)]
        if user_id:
            domain.append(('user_id', '=', user_id))
        
        logs = self.search(domain)
        
        total_requests = len(logs)
        success_requests = len(logs.filtered(lambda l: l.status == 'success'))
        error_requests = len(logs.filtered(lambda l: l.status == 'error'))
        
        total_tokens = sum(logs.mapped('total_tokens'))
        total_cost = sum(logs.mapped('cost_usd'))
        avg_latency = sum(logs.mapped('latency_ms')) / total_requests if total_requests else 0
        
        # Group by action type
        action_counts = {}
        for log in logs:
            action_counts[log.action_type] = action_counts.get(log.action_type, 0) + 1
        
        # Group by model
        model_counts = {}
        for log in logs:
            if log.model_name:
                model_counts[log.model_name] = model_counts.get(log.model_name, 0) + 1
        
        return {
            'total_requests': total_requests,
            'success_requests': success_requests,
            'error_requests': error_requests,
            'success_rate': (success_requests / total_requests * 100) if total_requests else 0,
            'total_tokens': total_tokens,
            'total_cost_usd': round(total_cost, 4),
            'avg_latency_ms': round(avg_latency, 2),
            'by_action': action_counts,
            'by_model': model_counts,
        }
    
    @api.model
    def _cron_cleanup_old_logs(self):
        """Remove logs older than retention period."""
        retention_days = int(self.env['ir.config_parameter'].sudo().get_param(
            'ai_integration.log_retention_days', '90'))
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        self.search([('create_date', '<', cutoff_date)]).unlink()
