# -*- coding: utf-8 -*-
"""
AI Features for Khach Hang Module
=================================
Tích hợp các tính năng AI vào quản lý khách hàng:
- Tóm tắt khách hàng 360°
- Phân nhóm nâng cao
- Gợi ý Next Best Action
- Soạn email chăm sóc
- Dự đoán churn
- Trợ lý CSKH
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import json
import logging

_logger = logging.getLogger(__name__)


class KhachHangAI(models.Model):
    """Extend KhachHang with AI capabilities."""
    _inherit = 'khach_hang'

    # AI Fields
    ai_customer_summary = fields.Text('Tóm tắt 360°', readonly=True, copy=False,
                                      help='Tóm tắt toàn diện về khách hàng')
    ai_next_best_action = fields.Text('Hành động tiếp theo', readonly=True, copy=False,
                                      help='Gợi ý hành động tiếp theo với khách hàng')
    ai_churn_analysis = fields.Text('Phân tích Churn', readonly=True, copy=False,
                                    help='Phân tích rủi ro mất khách hàng')
    ai_persona = fields.Char('AI Persona', readonly=True, copy=False,
                             help='Phân loại khách hàng bởi AI')
    ai_email_draft = fields.Text('Email mẫu', readonly=True, copy=False)
    ai_last_analyzed = fields.Datetime('Lần phân tích cuối', readonly=True, copy=False)
    
    def _get_customer_context(self):
        """Get comprehensive customer data for AI."""
        self.ensure_one()
        
        context = {
            'ten_khach_hang': self.ten_khach_hang,
            'email': self.email or '',
            'so_dien_thoai': self.so_dien_thoai or '',
            'cong_ty': self.cong_ty or '',
            'phan_loai': dict(self._fields['phan_loai'].selection).get(self.phan_loai, ''),
            'trang_thai': dict(self._fields['trang_thai'].selection).get(self.trang_thai, ''),
            'ngay_tao': str(self.ngay_tao) if self.ngay_tao else '',
        }
        
        # RFM data
        context['rfm'] = {
            'recency_days': self.rfm_recency,
            'frequency': self.rfm_frequency,
            'monetary': self.rfm_monetary,
            'segment': self.rfm_segment,
        }
        
        # Order statistics
        context['thong_ke'] = {
            'so_don_hang': self.don_hang_count,
            'tong_chi_tieu': self.tong_chi_tieu,
            'so_lan_mua': self.so_lan_mua_hang,
        }
        
        # Recent orders
        recent_orders = []
        for order in self.don_hang_ids[:5]:
            recent_orders.append({
                'ma': order.ma_don_hang,
                'ngay': str(order.ngay_dat_hang),
                'trang_thai': dict(order._fields['trang_thai'].selection).get(order.trang_thai, ''),
                'gia_tri': order.tong_tien,
            })
        context['don_hang_gan_day'] = recent_orders
        
        # Support tickets
        context['so_ticket'] = self.ho_tro_count
        
        # AI insights
        if self.churn_probability:
            context['churn_probability'] = f"{self.churn_probability:.1f}%"
        if self.purchase_probability:
            context['purchase_probability'] = f"{self.purchase_probability:.1f}%"
        if self.sentiment_score:
            context['sentiment_score'] = self.sentiment_score
        
        # Staff in charge
        if self.nhan_vien_phu_trach_id:
            context['nhan_vien_phu_trach'] = self.nhan_vien_phu_trach_id.ten_nv
        
        return context
    
    def action_ai_customer_360(self):
        """Tạo tóm tắt 360° về khách hàng."""
        self.ensure_one()
        
        ai_service = self.env['ai.service']
        if not ai_service.is_available():
            raise UserError(_("AI Service chưa được cấu hình."))
        
        context = self._get_customer_context()
        
        prompt = f"""Tạo tóm tắt 360° về khách hàng sau:

{json.dumps(context, ensure_ascii=False, indent=2)}

Yêu cầu tóm tắt:
1. Thông tin tổng quan (1-2 câu)
2. Hành vi mua hàng (dựa trên RFM và đơn hàng)
3. Giá trị khách hàng (tiềm năng/đóng góp)
4. Tình trạng hiện tại (active/at risk/cần chú ý)
5. Điểm cần lưu ý khi chăm sóc

Viết ngắn gọn (100-150 từ), tiếng Việt, thực tế:"""
        
        summary = ai_service.chat_completion(
            prompt=prompt,
            model_name=self._name,
            record_id=self.id,
            action_type='summarize'
        )
        
        self.write({
            'ai_customer_summary': summary,
            'ai_last_analyzed': fields.Datetime.now(),
        })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Hoàn thành'),
                'message': _('AI đã tạo tóm tắt khách hàng 360°.'),
                'type': 'success',
            }
        }
    
    def action_ai_next_best_action(self):
        """Gợi ý hành động tiếp theo."""
        self.ensure_one()
        
        ai_service = self.env['ai.service']
        if not ai_service.is_available():
            raise UserError(_("AI Service chưa được cấu hình."))
        
        context = self._get_customer_context()
        
        prompt = f"""Dựa trên dữ liệu khách hàng, đề xuất hành động tiếp theo tốt nhất:

{json.dumps(context, ensure_ascii=False, indent=2)}

Yêu cầu:
1. Đề xuất 1 hành động chính (ưu tiên cao nhất)
2. Lý do đề xuất (dựa trên dữ liệu)
3. Thời điểm thực hiện phù hợp
4. Kịch bản/script gợi ý (nếu là gọi điện/email)
5. 2-3 hành động phụ (backup options)

Các loại hành động có thể:
- Gọi điện chăm sóc
- Gửi email follow-up
- Gửi báo giá/ưu đãi
- Upsell/Cross-sell
- Nhắc thanh toán
- Khảo sát hài lòng
- Chúc mừng/tri ân

Trả lời tiếng Việt, cụ thể và thực tế:"""
        
        suggestion = ai_service.chat_completion(
            prompt=prompt,
            model_name=self._name,
            record_id=self.id,
            action_type='generate'
        )
        
        self.write({
            'ai_next_best_action': suggestion,
            'ai_last_analyzed': fields.Datetime.now(),
        })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Gợi ý hành động'),
                'message': _('AI đã đề xuất hành động tiếp theo.'),
                'type': 'success',
            }
        }
    
    def action_ai_analyze_churn(self):
        """Phân tích rủi ro mất khách hàng."""
        self.ensure_one()
        
        ai_service = self.env['ai.service']
        if not ai_service.is_available():
            raise UserError(_("AI Service chưa được cấu hình."))
        
        context = self._get_customer_context()
        
        prompt = f"""Phân tích rủi ro mất khách hàng (churn) dựa trên dữ liệu:

{json.dumps(context, ensure_ascii=False, indent=2)}

Yêu cầu phân tích:
1. Đánh giá mức độ rủi ro (Thấp/Trung bình/Cao/Rất cao)
2. Các dấu hiệu cảnh báo (nếu có)
3. Nguyên nhân có thể (dựa trên dữ liệu)
4. Đề xuất hành động giữ chân khách hàng
5. Mức độ ưu tiên can thiệp

QUAN TRỌNG: Chỉ phân tích dựa trên dữ liệu có sẵn, không suy đoán.

Phân tích:"""
        
        analysis = ai_service.chat_completion(
            prompt=prompt,
            model_name=self._name,
            record_id=self.id,
            action_type='analyze'
        )
        
        self.write({
            'ai_churn_analysis': analysis,
            'ai_last_analyzed': fields.Datetime.now(),
        })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Phân tích Churn'),
                'message': _('AI đã phân tích rủi ro mất khách hàng.'),
                'type': 'success',
            }
        }
    
    def action_ai_classify_persona(self):
        """Phân loại khách hàng thành persona."""
        self.ensure_one()
        
        ai_service = self.env['ai.service']
        if not ai_service.is_available():
            raise UserError(_("AI Service chưa được cấu hình."))
        
        context = self._get_customer_context()
        
        personas = [
            'VIP - Khách hàng giá trị cao, trung thành',
            'Promising - Tiềm năng cao, cần nuôi dưỡng',
            'At Risk - Có nguy cơ rời đi, cần can thiệp',
            'New - Khách hàng mới, cần onboarding',
            'Dormant - Không hoạt động, cần kích hoạt',
            'Price Sensitive - Nhạy cảm giá',
            'Loyal Regular - Trung thành, mua đều đặn',
        ]
        
        result = ai_service.classify_text(
            text=json.dumps(context, ensure_ascii=False),
            categories=personas,
            model_name=self._name,
            record_id=self.id
        )
        
        self.write({
            'ai_persona': result.get('category', ''),
            'ai_last_analyzed': fields.Datetime.now(),
        })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Phân loại hoàn thành'),
                'message': _('Persona: %s') % result.get('category', 'Không xác định'),
                'type': 'success',
            }
        }
    
    def action_ai_draft_email(self):
        """Soạn email chăm sóc khách hàng."""
        self.ensure_one()
        
        ai_service = self.env['ai.service']
        if not ai_service.is_available():
            raise UserError(_("AI Service chưa được cấu hình."))
        
        context = self._get_customer_context()
        
        # Determine email type based on customer status
        if context['thong_ke']['so_don_hang'] == 0:
            email_type = "email chào mừng khách hàng mới"
        elif context['rfm']['recency_days'] and context['rfm']['recency_days'] > 60:
            email_type = "email kích hoạt khách hàng lâu không mua"
        elif context['rfm']['segment'] == 'vip':
            email_type = "email tri ân khách VIP"
        else:
            email_type = "email follow-up chăm sóc định kỳ"
        
        prompt = f"""Soạn {email_type} cho khách hàng:

{json.dumps(context, ensure_ascii=False, indent=2)}

Yêu cầu:
1. Tiêu đề email hấp dẫn
2. Lời chào cá nhân hóa
3. Nội dung phù hợp với tình trạng khách hàng
4. Call-to-action rõ ràng
5. Kết thúc chuyên nghiệp

Viết bằng tiếng Việt, tone thân thiện nhưng chuyên nghiệp:"""
        
        email = ai_service.chat_completion(
            prompt=prompt,
            model_name=self._name,
            record_id=self.id,
            action_type='generate'
        )
        
        self.write({
            'ai_email_draft': email,
            'ai_last_analyzed': fields.Datetime.now(),
        })
        
        # Open compose email with draft
        return {
            'type': 'ir.actions.act_window',
            'name': 'Soạn Email',
            'res_model': 'ai.assistant.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_user_prompt': f'Soạn {email_type}',
                'default_ai_response': email,
                'default_response_ready': True,
                'active_model': self._name,
                'active_id': self.id,
            }
        }
    
    def action_ai_assistant(self):
        """Open Trợ lý AI."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Trợ lý AI - Khách hàng',
            'res_model': 'ai.assistant.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'active_model': self._name,
                'active_id': self.id,
            }
        }
    
    @api.model
    def action_ai_batch_analyze(self):
        """Phân tích hàng loạt khách hàng (chạy nền)."""
        customers = self.search([('trang_thai', '=', 'dang_giao_dich')], limit=50)
        
        job_model = self.env['ai.job']
        jobs_created = 0
        
        for customer in customers:
            # Skip if recently analyzed
            if customer.ai_last_analyzed:
                from datetime import datetime, timedelta
                if customer.ai_last_analyzed > datetime.now() - timedelta(days=7):
                    continue
            
            context = customer._get_customer_context()
            
            job_model.create_job(
                name=f"Phân tích KH: {customer.ten_khach_hang}",
                job_type='analyze',
                input_data=json.dumps(context, ensure_ascii=False),
                params={'analysis_type': 'customer_360'},
                model_name=self._name,
                record_id=customer.id,
                priority='1'
            )
            jobs_created += 1
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Tạo Jobs'),
                'message': _('Đã tạo %s AI jobs để phân tích khách hàng.') % jobs_created,
                'type': 'success',
            }
        }


class HoTroKhachHangAI(models.Model):
    """Extend HoTroKhachHang with AI capabilities."""
    _inherit = 'ho_tro_khach_hang'

    ai_suggested_response = fields.Text('Gợi ý trả lời', readonly=True, copy=False)
    ai_ticket_summary = fields.Text('Tóm tắt ticket', readonly=True, copy=False)
    ai_priority_suggestion = fields.Char('Độ ưu tiên đề xuất', readonly=True, copy=False)
    
    def action_ai_suggest_response(self):
        """Gợi ý câu trả lời cho ticket."""
        self.ensure_one()
        
        ai_service = self.env['ai.service']
        if not ai_service.is_available():
            raise UserError(_("AI Service chưa được cấu hình."))
        
        context = {
            'khach_hang': self.khach_hang_id.ten_khach_hang if self.khach_hang_id else '',
            'tieu_de': self.name if hasattr(self, 'name') else '',
            'noi_dung': self.mo_ta if hasattr(self, 'mo_ta') else '',
            'loai_yeu_cau': self.loai_yeu_cau if hasattr(self, 'loai_yeu_cau') else '',
        }
        
        prompt = f"""Gợi ý câu trả lời cho ticket hỗ trợ khách hàng:

{json.dumps(context, ensure_ascii=False, indent=2)}

Yêu cầu:
1. Câu trả lời lịch sự, chuyên nghiệp
2. Giải quyết vấn đề hoặc hướng dẫn bước tiếp theo
3. Thể hiện sự thấu hiểu và quan tâm
4. Cung cấp thông tin hữu ích
5. Kết thúc với lời mời liên hệ nếu cần hỗ trợ thêm

Viết bằng tiếng Việt:"""
        
        response = ai_service.chat_completion(
            prompt=prompt,
            model_name=self._name,
            record_id=self.id,
            action_type='generate'
        )
        
        self.write({
            'ai_suggested_response': response,
        })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Gợi ý trả lời'),
                'message': _('AI đã đề xuất câu trả lời.'),
                'type': 'success',
            }
        }
    
    def action_ai_summarize_ticket(self):
        """Tóm tắt ticket trước khi escalate."""
        self.ensure_one()
        
        ai_service = self.env['ai.service']
        if not ai_service.is_available():
            raise UserError(_("AI Service chưa được cấu hình."))
        
        context = {
            'khach_hang': self.khach_hang_id.ten_khach_hang if self.khach_hang_id else '',
            'tieu_de': self.name if hasattr(self, 'name') else '',
            'noi_dung': self.mo_ta if hasattr(self, 'mo_ta') else '',
            'trang_thai': self.trang_thai if hasattr(self, 'trang_thai') else '',
            'ngay_tao': str(self.create_date) if hasattr(self, 'create_date') else '',
        }
        
        summary = ai_service.summarize_text(
            text=json.dumps(context, ensure_ascii=False),
            max_words=80,
            focus="vấn đề chính và yêu cầu của khách hàng",
            model_name=self._name,
            record_id=self.id
        )
        
        self.write({
            'ai_ticket_summary': summary,
        })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Tóm tắt'),
                'message': _('AI đã tóm tắt ticket.'),
                'type': 'success',
            }
        }
