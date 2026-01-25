# -*- coding: utf-8 -*-
"""
AI Job Model - Quản lý các tác vụ AI chạy nền
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime
import json
import logging

_logger = logging.getLogger(__name__)


class AIJob(models.Model):
    """
    AI Job - Tác vụ AI chạy nền (async processing)
    Dùng cho các tác vụ nặng: tóm tắt file lớn, xử lý hàng loạt, etc.
    """
    _name = 'ai.job'
    _description = 'AI Job - Tác vụ AI'
    _order = 'create_date desc'
    _inherit = ['mail.thread']

    name = fields.Char('Tên tác vụ', required=True, tracking=True)
    
    state = fields.Selection([
        ('pending', 'Chờ xử lý'),
        ('running', 'Đang chạy'),
        ('done', 'Hoàn thành'),
        ('failed', 'Lỗi'),
        ('cancelled', 'Đã hủy'),
    ], string='Trạng thái', default='pending', required=True, tracking=True)
    
    job_type = fields.Selection([
        ('summarize', 'Tóm tắt'),
        ('extract', 'Trích xuất dữ liệu'),
        ('classify', 'Phân loại'),
        ('generate', 'Sinh nội dung'),
        ('analyze', 'Phân tích'),
        ('translate', 'Dịch thuật'),
        ('batch', 'Xử lý hàng loạt'),
        ('custom', 'Tùy chỉnh'),
    ], string='Loại tác vụ', required=True, default='custom')
    
    priority = fields.Selection([
        ('0', 'Thấp'),
        ('1', 'Bình thường'),
        ('2', 'Cao'),
        ('3', 'Khẩn cấp'),
    ], string='Độ ưu tiên', default='1')
    
    # Source reference
    model_name = fields.Char('Model nguồn', help='Odoo model name')
    record_id = fields.Integer('Record ID')
    record_ref = fields.Char('Tham chiếu', compute='_compute_record_ref')
    
    # Input/Output
    input_data = fields.Text('Dữ liệu đầu vào')
    input_params = fields.Text('Tham số', help='JSON params')
    output_data = fields.Text('Kết quả')
    output_summary = fields.Text('Tóm tắt kết quả')
    
    # Progress
    progress = fields.Integer('Tiến độ (%)', default=0)
    total_items = fields.Integer('Tổng số items')
    processed_items = fields.Integer('Đã xử lý')
    
    # Timing
    scheduled_date = fields.Datetime('Thời gian lên lịch')
    started_date = fields.Datetime('Bắt đầu')
    finished_date = fields.Datetime('Kết thúc')
    duration = fields.Float('Thời gian (giây)', compute='_compute_duration', store=True)
    
    # Cost tracking
    input_tokens = fields.Integer('Input tokens')
    output_tokens = fields.Integer('Output tokens')
    cost_usd = fields.Float('Chi phí (USD)', digits=(10, 6))
    
    # Error handling
    error_message = fields.Text('Thông báo lỗi')
    retry_count = fields.Integer('Số lần thử lại', default=0)
    max_retries = fields.Integer('Tối đa lần thử', default=3)
    
    # User
    user_id = fields.Many2one('res.users', string='Người tạo', default=lambda self: self.env.uid)
    
    @api.depends('model_name', 'record_id')
    def _compute_record_ref(self):
        for job in self:
            if job.model_name and job.record_id:
                job.record_ref = f"{job.model_name},{job.record_id}"
            else:
                job.record_ref = False
    
    @api.depends('started_date', 'finished_date')
    def _compute_duration(self):
        for job in self:
            if job.started_date and job.finished_date:
                delta = job.finished_date - job.started_date
                job.duration = delta.total_seconds()
            else:
                job.duration = 0
    
    def action_run(self):
        """Chạy tác vụ ngay lập tức."""
        for job in self:
            if job.state != 'pending':
                raise UserError(_("Chỉ có thể chạy tác vụ đang chờ xử lý."))
            job._execute()
    
    def action_cancel(self):
        """Hủy tác vụ."""
        for job in self:
            if job.state in ('pending', 'running'):
                job.write({
                    'state': 'cancelled',
                    'finished_date': datetime.now(),
                })
    
    def action_retry(self):
        """Thử lại tác vụ lỗi."""
        for job in self:
            if job.state == 'failed':
                job.write({
                    'state': 'pending',
                    'retry_count': job.retry_count + 1,
                    'error_message': False,
                })
    
    def action_view_record(self):
        """Mở record nguồn."""
        self.ensure_one()
        if self.model_name and self.record_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': self.model_name,
                'res_id': self.record_id,
                'view_mode': 'form',
                'target': 'current',
            }
    
    def _execute(self):
        """Thực thi tác vụ AI."""
        self.ensure_one()
        
        self.write({
            'state': 'running',
            'started_date': datetime.now(),
        })
        
        try:
            ai_service = self.env['ai.service']
            params = json.loads(self.input_params) if self.input_params else {}
            
            result = None
            
            if self.job_type == 'summarize':
                result = ai_service.summarize_text(
                    self.input_data,
                    max_words=params.get('max_words', 150),
                    model_name=self.model_name,
                    record_id=self.record_id
                )
            elif self.job_type == 'extract':
                result = ai_service.extract_structured_data(
                    self.input_data,
                    schema=params.get('schema', {}),
                    model_name=self.model_name,
                    record_id=self.record_id
                )
                result = json.dumps(result, ensure_ascii=False, indent=2)
            elif self.job_type == 'classify':
                result = ai_service.classify_text(
                    self.input_data,
                    categories=params.get('categories', []),
                    model_name=self.model_name,
                    record_id=self.record_id
                )
                result = json.dumps(result, ensure_ascii=False, indent=2)
            elif self.job_type == 'generate':
                result = ai_service.generate_content(
                    template=params.get('template', 'email'),
                    context=params.get('context', {}),
                    tone=params.get('tone', 'professional'),
                    model_name=self.model_name,
                    record_id=self.record_id
                )
            elif self.job_type == 'analyze':
                result = ai_service.analyze_risk(
                    self.input_data,
                    risk_types=params.get('risk_types'),
                    model_name=self.model_name,
                    record_id=self.record_id
                )
                result = json.dumps(result, ensure_ascii=False, indent=2)
            elif self.job_type == 'translate':
                result = ai_service.translate_text(
                    self.input_data,
                    target_language=params.get('target_language', 'en'),
                    model_name=self.model_name,
                    record_id=self.record_id
                )
            else:
                # Custom job - use direct chat
                result = ai_service.chat_completion(
                    prompt=self.input_data,
                    system_prompt=params.get('system_prompt'),
                    model_name=self.model_name,
                    record_id=self.record_id
                )
            
            self.write({
                'state': 'done',
                'finished_date': datetime.now(),
                'output_data': result,
                'output_summary': result[:500] if result else '',
                'progress': 100,
            })
            
        except Exception as e:
            _logger.error(f"AI Job {self.id} failed: {e}")
            self.write({
                'state': 'failed',
                'finished_date': datetime.now(),
                'error_message': str(e),
            })
    
    @api.model
    def _cron_process_pending_jobs(self):
        """Cron job to process pending AI jobs."""
        pending_jobs = self.search([
            ('state', '=', 'pending'),
            '|',
            ('scheduled_date', '=', False),
            ('scheduled_date', '<=', datetime.now()),
        ], order='priority desc, create_date asc', limit=10)
        
        for job in pending_jobs:
            try:
                job._execute()
            except Exception as e:
                _logger.error(f"Cron AI Job {job.id} failed: {e}")
    
    @api.model
    def create_job(self, name, job_type, input_data, params=None, 
                   model_name=None, record_id=None, priority='1'):
        """
        Helper method to create AI job.
        
        Args:
            name: Job name
            job_type: Type of job (summarize, extract, etc.)
            input_data: Input text/data
            params: Dict of parameters
            model_name: Source model name
            record_id: Source record ID
            priority: Job priority
            
        Returns:
            ai.job record
        """
        return self.create({
            'name': name,
            'job_type': job_type,
            'input_data': input_data,
            'input_params': json.dumps(params or {}, ensure_ascii=False),
            'model_name': model_name,
            'record_id': record_id,
            'priority': priority,
        })


class AICache(models.Model):
    """Cache for AI responses to reduce API calls and costs."""
    _name = 'ai.cache'
    _description = 'AI Response Cache'
    _order = 'create_date desc'

    cache_key = fields.Char('Cache Key', required=True, index=True)
    prompt_hash = fields.Char('Prompt Hash')
    response = fields.Text('Response')
    expires_at = fields.Datetime('Expires At', required=True, index=True)
    hit_count = fields.Integer('Hit Count', default=0)
    
    _sql_constraints = [
        ('cache_key_unique', 'unique(cache_key)', 'Cache key must be unique!')
    ]
    
    @api.model
    def _cron_cleanup_expired(self):
        """Remove expired cache entries."""
        self.search([('expires_at', '<', datetime.now())]).unlink()
