# -*- coding: utf-8 -*-
"""
AI Features for Van Ban Module
===============================
Tích hợp các tính năng AI vào quản lý văn bản:
- Tóm tắt văn bản
- Trích xuất metadata (ngày, bên ký, giá trị, điều khoản)
- Phân tích rủi ro hợp đồng
- Gợi ý quy trình duyệt
- Chat hỏi đáp theo văn bản
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import json
import logging
import base64

_logger = logging.getLogger(__name__)


class VanBanAI(models.Model):
    """Extend VanBan with AI capabilities."""
    _inherit = 'van_ban'

    # AI Fields
    ai_summary = fields.Text('Tóm tắt AI', readonly=True, copy=False,
                             help='Tóm tắt tự động bởi AI')
    ai_risk_score = fields.Integer('Điểm rủi ro', readonly=True, copy=False,
                                   help='Điểm rủi ro từ 0-100')
    ai_risk_details = fields.Text('Chi tiết rủi ro', readonly=True, copy=False)
    ai_extracted_data = fields.Text('Dữ liệu trích xuất', readonly=True, copy=False,
                                    help='JSON chứa metadata trích xuất từ AI')
    ai_suggested_workflow = fields.Text('Quy trình đề xuất', readonly=True, copy=False)
    ai_last_analyzed = fields.Datetime('Lần phân tích cuối', readonly=True, copy=False)
    
    # Computed display fields
    ai_risk_level = fields.Selection([
        ('low', 'Thấp'),
        ('medium', 'Trung bình'),
        ('high', 'Cao'),
        ('critical', 'Nghiêm trọng'),
    ], string='Mức rủi ro', compute='_compute_ai_risk_level', store=True)
    
    @api.depends('ai_risk_score')
    def _compute_ai_risk_level(self):
        for record in self:
            score = record.ai_risk_score or 0
            if score < 25:
                record.ai_risk_level = 'low'
            elif score < 50:
                record.ai_risk_level = 'medium'
            elif score < 75:
                record.ai_risk_level = 'high'
            else:
                record.ai_risk_level = 'critical'
    
    def _get_document_text(self):
        """Get all text content from document for AI processing."""
        self.ensure_one()
        
        text_parts = []
        
        # Basic info
        text_parts.append(f"Mã văn bản: {self.ma_van_ban}")
        text_parts.append(f"Tên văn bản: {self.ten_van_ban}")
        
        if self.loai_van_ban_id:
            text_parts.append(f"Loại: {self.loai_van_ban_id.ten_loai}")
        
        if self.mo_ta:
            text_parts.append(f"Mô tả: {self.mo_ta}")
        
        if self.khach_hang_id:
            text_parts.append(f"Khách hàng: {self.khach_hang_id.ten_khach_hang}")
        
        if self.nguoi_tao_id:
            text_parts.append(f"Người tạo: {self.nguoi_tao_id.ten_nv}")
        
        if self.ngay_hieu_luc:
            text_parts.append(f"Ngày hiệu lực: {self.ngay_hieu_luc}")
        
        if self.ngay_het_han:
            text_parts.append(f"Ngày hết hạn: {self.ngay_het_han}")
        
        return "\n".join(text_parts)
    
    def action_ai_summarize(self):
        """Tóm tắt văn bản bằng AI."""
        self.ensure_one()
        
        ai_service = self.env['ai.service']
        if not ai_service.is_available():
            raise UserError(_("AI Service chưa được cấu hình. Vui lòng vào Settings > AI Integration."))
        
        text = self._get_document_text()
        
        if len(text) < 50:
            raise UserError(_("Văn bản quá ngắn để tóm tắt."))
        
        summary = ai_service.summarize_text(
            text=text,
            max_words=200,
            focus="các điều khoản chính, nghĩa vụ, quyền lợi và thời hạn",
            model_name=self._name,
            record_id=self.id
        )
        
        self.write({
            'ai_summary': summary,
            'ai_last_analyzed': fields.Datetime.now(),
        })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Tóm tắt hoàn thành'),
                'message': _('AI đã tóm tắt văn bản thành công.'),
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_ai_extract_metadata(self):
        """Trích xuất metadata từ văn bản."""
        self.ensure_one()
        
        ai_service = self.env['ai.service']
        if not ai_service.is_available():
            raise UserError(_("AI Service chưa được cấu hình."))
        
        text = self._get_document_text()
        
        schema = {
            "ben_a": "Tên bên A (bên cung cấp/bán)",
            "ben_b": "Tên bên B (bên mua/khách hàng)",
            "gia_tri_hop_dong": "Giá trị hợp đồng (số tiền)",
            "don_vi_tien_te": "Đơn vị tiền tệ (VND, USD, etc.)",
            "ngay_ky": "Ngày ký hợp đồng",
            "ngay_hieu_luc": "Ngày có hiệu lực",
            "ngay_het_han": "Ngày hết hạn",
            "thoi_han": "Thời hạn hợp đồng",
            "dieu_khoan_thanh_toan": "Điều khoản thanh toán",
            "san_pham_dich_vu": "Sản phẩm/dịch vụ chính",
            "phat_cham_thanh_toan": "Phạt chậm thanh toán (%)",
            "bao_hanh": "Thời gian bảo hành",
            "dieu_khoan_cham_dut": "Điều kiện chấm dứt hợp đồng"
        }
        
        extracted = ai_service.extract_structured_data(
            text=text,
            schema=schema,
            instructions="Trích xuất thông tin từ hợp đồng/văn bản pháp lý. Nếu không tìm thấy thì để null.",
            model_name=self._name,
            record_id=self.id
        )
        
        self.write({
            'ai_extracted_data': json.dumps(extracted, ensure_ascii=False, indent=2),
            'ai_last_analyzed': fields.Datetime.now(),
        })
        
        # Auto-fill some fields if empty
        vals = {}
        if not self.ngay_hieu_luc and extracted.get('ngay_hieu_luc'):
            try:
                from datetime import datetime
                ngay = datetime.strptime(extracted['ngay_hieu_luc'], '%Y-%m-%d').date()
                vals['ngay_hieu_luc'] = ngay
            except:
                pass
        
        if not self.ngay_het_han and extracted.get('ngay_het_han'):
            try:
                from datetime import datetime
                ngay = datetime.strptime(extracted['ngay_het_han'], '%Y-%m-%d').date()
                vals['ngay_het_han'] = ngay
            except:
                pass
        
        if vals:
            self.write(vals)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Trích xuất hoàn thành'),
                'message': _('AI đã trích xuất metadata từ văn bản.'),
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_ai_analyze_risk(self):
        """Phân tích rủi ro văn bản/hợp đồng."""
        self.ensure_one()
        
        ai_service = self.env['ai.service']
        if not ai_service.is_available():
            raise UserError(_("AI Service chưa được cấu hình."))
        
        text = self._get_document_text()
        
        risk_types = [
            'điều khoản phạt quá nặng',
            'miễn trừ trách nhiệm một chiều',
            'thanh toán mơ hồ hoặc không rõ ràng',
            'không có điều khoản bảo mật',
            'điều kiện chấm dứt bất lợi',
            'không có giải quyết tranh chấp',
            'thiếu điều khoản bất khả kháng',
            'thời hạn quá ngắn hoặc không rõ',
            'thiếu cam kết chất lượng/SLA',
        ]
        
        result = ai_service.analyze_risk(
            text=text,
            risk_types=risk_types,
            model_name=self._name,
            record_id=self.id
        )
        
        self.write({
            'ai_risk_score': result.get('risk_score', 0),
            'ai_risk_details': json.dumps(result, ensure_ascii=False, indent=2),
            'ai_last_analyzed': fields.Datetime.now(),
        })
        
        # Create activity if high risk
        if result.get('risk_score', 0) >= 70:
            self.activity_schedule(
                'mail.mail_activity_data_warning',
                summary=_('Văn bản có rủi ro cao'),
                note=_('AI phát hiện văn bản này có điểm rủi ro %s/100. Vui lòng xem xét kỹ.') % result.get('risk_score'),
            )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Phân tích rủi ro hoàn thành'),
                'message': _('Điểm rủi ro: %s/100') % result.get('risk_score', 0),
                'type': 'warning' if result.get('risk_score', 0) >= 50 else 'success',
                'sticky': False,
            }
        }
    
    def action_ai_suggest_workflow(self):
        """Gợi ý quy trình duyệt dựa trên loại văn bản."""
        self.ensure_one()
        
        ai_service = self.env['ai.service']
        if not ai_service.is_available():
            raise UserError(_("AI Service chưa được cấu hình."))
        
        context = {
            'loai_van_ban': self.loai_van_ban_id.ten_loai if self.loai_van_ban_id else 'Không xác định',
            'nguoi_tao': self.nguoi_tao_id.ten_nv if self.nguoi_tao_id else '',
            'phong_ban': self.nguoi_tao_id.phong_ban if self.nguoi_tao_id else '',
            'khach_hang': self.khach_hang_id.ten_khach_hang if self.khach_hang_id else '',
        }
        
        if self.ai_risk_score:
            context['diem_rui_ro'] = self.ai_risk_score
        
        prompt = f"""Dựa trên thông tin văn bản sau, đề xuất quy trình phê duyệt phù hợp:

{json.dumps(context, ensure_ascii=False, indent=2)}

Yêu cầu:
1. Liệt kê các bước phê duyệt theo thứ tự
2. Nêu người/bộ phận nên duyệt mỗi bước
3. Thời gian dự kiến mỗi bước
4. Lưu ý đặc biệt nếu có

Trả lời bằng tiếng Việt, ngắn gọn và thực tế."""
        
        suggestion = ai_service.chat_completion(
            prompt=prompt,
            model_name=self._name,
            record_id=self.id,
            action_type='generate'
        )
        
        self.write({
            'ai_suggested_workflow': suggestion,
            'ai_last_analyzed': fields.Datetime.now(),
        })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Gợi ý quy trình'),
                'message': _('AI đã đề xuất quy trình phê duyệt.'),
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_ai_assistant(self):
        """Mở AI Assistant để chat hỏi đáp về văn bản."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'AI Assistant - Văn bản',
            'res_model': 'ai.assistant.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'active_model': self._name,
                'active_id': self.id,
            }
        }
    
    def action_ai_generate_email(self):
        """Sinh email gửi văn bản cho khách hàng."""
        self.ensure_one()
        
        ai_service = self.env['ai.service']
        if not ai_service.is_available():
            raise UserError(_("AI Service chưa được cấu hình."))
        
        context = {
            'loai_van_ban': self.loai_van_ban_id.ten_loai if self.loai_van_ban_id else 'văn bản',
            'ten_van_ban': self.ten_van_ban,
            'khach_hang': self.khach_hang_id.ten_khach_hang if self.khach_hang_id else 'Quý khách',
            'nguoi_gui': self.nguoi_tao_id.ten_nv if self.nguoi_tao_id else '',
            'cong_ty': self.env.company.name,
        }
        
        email_content = ai_service.generate_content(
            template='email gửi văn bản cho khách hàng',
            context=context,
            tone='professional',
            model_name=self._name,
            record_id=self.id
        )
        
        # Return action to compose email with generated content
        return {
            'type': 'ir.actions.act_window',
            'name': 'Soạn Email',
            'res_model': 'mail.compose.message',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_model': self._name,
                'default_res_id': self.id,
                'default_body': email_content,
                'default_partner_ids': [(4, self.khach_hang_id.id)] if self.khach_hang_id else [],
            }
        }


class VanBanDiAI(models.Model):
    """Extend VanBanDi with AI capabilities."""
    _inherit = 'van_ban_di'

    ai_summary = fields.Text('Tóm tắt AI', readonly=True, copy=False)
    ai_risk_score = fields.Integer('Điểm rủi ro', readonly=True, copy=False)
    ai_last_analyzed = fields.Datetime('Lần phân tích cuối', readonly=True, copy=False)
    
    def _get_document_text(self):
        """Get text content for AI."""
        self.ensure_one()
        
        parts = [
            f"Số ký hiệu: {self.name}",
            f"Trích yếu: {self.trich_yeu}",
        ]
        
        if self.noi_dung:
            parts.append(f"Nội dung: {self.noi_dung}")
        
        if self.noi_dung_ocr:
            parts.append(f"Nội dung OCR: {self.noi_dung_ocr}")
        
        if self.loai_van_ban_id:
            parts.append(f"Loại: {self.loai_van_ban_id.ten_loai}")
        
        if self.noi_nhan:
            parts.append(f"Nơi nhận: {self.noi_nhan}")
        
        return "\n".join(parts)
    
    def action_ai_summarize(self):
        """Tóm tắt văn bản đi."""
        self.ensure_one()
        
        ai_service = self.env['ai.service']
        if not ai_service.is_available():
            raise UserError(_("AI Service chưa được cấu hình."))
        
        text = self._get_document_text()
        
        summary = ai_service.summarize_text(
            text=text,
            max_words=150,
            model_name=self._name,
            record_id=self.id
        )
        
        self.write({
            'ai_summary': summary,
            'ai_last_analyzed': fields.Datetime.now(),
        })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Hoàn thành'),
                'message': _('AI đã tóm tắt văn bản.'),
                'type': 'success',
            }
        }
    
    def action_ai_assistant(self):
        """Open AI Assistant."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'AI Assistant',
            'res_model': 'ai.assistant.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'active_model': self._name,
                'active_id': self.id,
            }
        }


class VanBanDenAI(models.Model):
    """Extend VanBanDen with AI capabilities."""
    _inherit = 'van_ban_den'

    ai_summary = fields.Text('Tóm tắt AI', readonly=True, copy=False)
    ai_classification = fields.Char('Phân loại AI', readonly=True, copy=False)
    ai_suggested_handler = fields.Char('Người xử lý đề xuất', readonly=True, copy=False)
    ai_last_analyzed = fields.Datetime('Lần phân tích cuối', readonly=True, copy=False)
    
    def action_ai_classify_and_route(self):
        """Phân loại và gợi ý người xử lý văn bản đến."""
        self.ensure_one()
        
        ai_service = self.env['ai.service']
        if not ai_service.is_available():
            raise UserError(_("AI Service chưa được cấu hình."))
        
        # Get document text
        text_parts = [
            f"Số đến: {self.name if hasattr(self, 'name') else ''}",
        ]
        
        if hasattr(self, 'trich_yeu') and self.trich_yeu:
            text_parts.append(f"Trích yếu: {self.trich_yeu}")
        
        if hasattr(self, 'noi_dung') and self.noi_dung:
            text_parts.append(f"Nội dung: {self.noi_dung}")
        
        if hasattr(self, 'nguoi_gui') and self.nguoi_gui:
            text_parts.append(f"Người gửi: {self.nguoi_gui}")
        
        text = "\n".join(text_parts)
        
        # Classify document
        categories = ['Hợp đồng', 'Công văn', 'Báo cáo', 'Đề xuất', 'Khiếu nại', 
                     'Yêu cầu thanh toán', 'Thông báo', 'Khác']
        
        classification = ai_service.classify_text(
            text=text,
            categories=categories,
            model_name=self._name,
            record_id=self.id
        )
        
        # Suggest handler based on classification
        handler_map = {
            'Hợp đồng': 'Phòng Pháp chế',
            'Công văn': 'Phòng Hành chính',
            'Báo cáo': 'Ban Giám đốc',
            'Đề xuất': 'Phòng Kế hoạch',
            'Khiếu nại': 'Phòng CSKH',
            'Yêu cầu thanh toán': 'Phòng Kế toán',
            'Thông báo': 'Phòng Hành chính',
        }
        
        suggested = handler_map.get(classification.get('category'), 'Cần xác định')
        
        self.write({
            'ai_classification': classification.get('category'),
            'ai_suggested_handler': suggested,
            'ai_last_analyzed': fields.Datetime.now(),
        })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Phân loại hoàn thành'),
                'message': _('Loại: %s\nĐề xuất: %s') % (classification.get('category'), suggested),
                'type': 'success',
            }
        }
    
    def action_ai_assistant(self):
        """Open AI Assistant."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'AI Assistant',
            'res_model': 'ai.assistant.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'active_model': self._name,
                'active_id': self.id,
            }
        }
