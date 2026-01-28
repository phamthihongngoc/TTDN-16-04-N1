# -*- coding: utf-8 -*-
"""
AI Mixin - Mixin class cung cấp các phương thức AI cho models khác
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import json
import logging

_logger = logging.getLogger(__name__)


class AIMixin(models.AbstractModel):
    """
    Mixin class để thêm các tính năng AI vào bất kỳ model nào.
    
    Sử dụng:
        class MyModel(models.Model):
            _inherit = ['ai.mixin']
            
            # Sau đó có thể gọi:
            # self.ai_summarize(field_name)
            # self.ai_extract_data(field_name, schema)
            # etc.
    """
    _name = 'ai.mixin'
    _description = 'AI Mixin'

    # AI Fields (optional - can be added to inheriting models)
    ai_summary = fields.Text('AI Summary', readonly=True, copy=False)
    ai_risk_score = fields.Integer('AI Risk Score', readonly=True, copy=False)
    ai_classification = fields.Char('AI Classification', readonly=True, copy=False)
    ai_last_analyzed = fields.Datetime('AI Last Analyzed', readonly=True, copy=False)
    
    def _get_ai_service(self):
        """Get AI service instance."""
        return self.env['ai.service']
    
    def _get_text_for_ai(self, field_names=None):
        """
        Get text content from record for AI processing.
        
        Args:
            field_names: List of field names to include (optional)
        """
        self.ensure_one()
        
        if field_names:
            fields_to_check = field_names
        else:
            # Default text fields to look for
            fields_to_check = ['noi_dung', 'mo_ta', 'ghi_chu', 'noi_dung_ocr', 
                              'trich_yeu', 'content', 'description', 'notes']
        
        text_parts = []
        
        # Add display name
        text_parts.append(f"Tên: {self.display_name}")
        
        # Add model description
        text_parts.append(f"Loại: {self._description}")
        
        for field_name in fields_to_check:
            if hasattr(self, field_name):
                value = getattr(self, field_name)
                if value and isinstance(value, str):
                    field_info = self._fields.get(field_name)
                    label = field_info.string if field_info else field_name
                    text_parts.append(f"{label}: {value}")
        
        return "\n\n".join(text_parts)
    
    def ai_summarize(self, field_names=None, max_words=150, focus=None):
        """
        Tóm tắt nội dung record.
        
        Args:
            field_names: List of field names to summarize
            max_words: Maximum words in summary
            focus: Optional focus area
            
        Returns:
            str: Summary text
        """
        self.ensure_one()
        
        text = self._get_text_for_ai(field_names)
        if not text or len(text) < 50:
            return text
        
        ai_service = self._get_ai_service()
        summary = ai_service.summarize_text(
            text=text,
            max_words=max_words,
            focus=focus,
            model_name=self._name,
            record_id=self.id
        )
        
        # Update record if has ai_summary field
        if 'ai_summary' in self._fields:
            self.write({
                'ai_summary': summary,
                'ai_last_analyzed': fields.Datetime.now(),
            })
        
        return summary
    
    def ai_extract_data(self, schema, field_names=None, instructions=None):
        """
        Trích xuất dữ liệu có cấu trúc từ record.
        
        Args:
            schema: Dict defining fields to extract
            field_names: Source field names
            instructions: Additional instructions
            
        Returns:
            dict: Extracted data
        """
        self.ensure_one()
        
        text = self._get_text_for_ai(field_names)
        if not text:
            return {}
        
        ai_service = self._get_ai_service()
        return ai_service.extract_structured_data(
            text=text,
            schema=schema,
            instructions=instructions,
            model_name=self._name,
            record_id=self.id
        )
    
    def ai_classify(self, categories, field_names=None):
        """
        Phân loại record vào các danh mục.
        
        Args:
            categories: List of category names
            field_names: Source field names
            
        Returns:
            dict: {'category': str, 'confidence': float, 'reason': str}
        """
        self.ensure_one()
        
        text = self._get_text_for_ai(field_names)
        if not text or not categories:
            return {'category': None, 'confidence': 0, 'reason': 'No input'}
        
        ai_service = self._get_ai_service()
        result = ai_service.classify_text(
            text=text,
            categories=categories,
            model_name=self._name,
            record_id=self.id
        )
        
        # Update record if has ai_classification field
        if 'ai_classification' in self._fields:
            self.write({
                'ai_classification': result.get('category'),
                'ai_last_analyzed': fields.Datetime.now(),
            })
        
        return result
    
    def ai_analyze_risk(self, risk_types=None, field_names=None):
        """
        Phân tích rủi ro trong record.
        
        Args:
            risk_types: List of risk types to check
            field_names: Source field names
            
        Returns:
            dict: {'risk_score': int, 'risks': [...], 'recommendations': [...]}
        """
        self.ensure_one()
        
        text = self._get_text_for_ai(field_names)
        if not text:
            return {'risk_score': 0, 'risks': [], 'recommendations': []}
        
        ai_service = self._get_ai_service()
        result = ai_service.analyze_risk(
            text=text,
            risk_types=risk_types,
            model_name=self._name,
            record_id=self.id
        )
        
        # Update record if has ai_risk_score field
        if 'ai_risk_score' in self._fields:
            self.write({
                'ai_risk_score': result.get('risk_score', 0),
                'ai_last_analyzed': fields.Datetime.now(),
            })
        
        return result
    
    def ai_generate_content(self, template, context=None, tone='professional'):
        """
        Sinh nội dung dựa trên record.
        
        Args:
            template: Content type (email, report, etc.)
            context: Additional context dict
            tone: Writing tone
            
        Returns:
            str: Generated content
        """
        self.ensure_one()
        
        # Build context from record
        record_context = {
            'tên': self.display_name,
            'loại': self._description,
        }
        
        # Add common fields
        for field_name in ['ten_nv', 'ten_khach_hang', 'trich_yeu', 'ma_van_ban']:
            if hasattr(self, field_name):
                value = getattr(self, field_name)
                if value:
                    record_context[field_name] = value
        
        # Merge with provided context
        if context:
            record_context.update(context)
        
        ai_service = self._get_ai_service()
        return ai_service.generate_content(
            template=template,
            context=record_context,
            tone=tone,
            model_name=self._name,
            record_id=self.id
        )
    
    def ai_answer_question(self, question, field_names=None):
        """
        Trả lời câu hỏi về record.
        
        Args:
            question: User's question
            field_names: Source field names for context
            
        Returns:
            dict: {'answer': str, 'sources': [...], 'confidence': float}
        """
        self.ensure_one()
        
        context = self._get_text_for_ai(field_names)
        
        ai_service = self._get_ai_service()
        return ai_service.answer_question(
            question=question,
            context=context,
            model_name=self._name,
            record_id=self.id
        )
    
    def ai_translate(self, field_name, target_language='en'):
        """
        Dịch nội dung field sang ngôn ngữ khác.
        
        Args:
            field_name: Field to translate
            target_language: Target language code
            
        Returns:
            str: Translated text
        """
        self.ensure_one()
        
        if not hasattr(self, field_name):
            raise UserError(_("Field '%s' không tồn tại.") % field_name)
        
        text = getattr(self, field_name)
        if not text:
            return ""
        
        ai_service = self._get_ai_service()
        return ai_service.translate_text(
            text=text,
            target_language=target_language,
            model_name=self._name,
            record_id=self.id
        )
    
    def action_ai_assistant(self):
        """Open Trợ lý AI wizard for this record."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Trợ lý AI',
            'res_model': 'ai.assistant.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'active_model': self._name,
                'active_id': self.id,
            }
        }
