# -*- coding: utf-8 -*-
"""
AI Features for Nhan Su Module
==============================
Tích hợp các tính năng AI vào quản lý nhân sự:
- Tóm tắt hồ sơ nhân viên
- Kiểm tra hồ sơ thiếu
- Gợi ý đào tạo
- Tạo JD và câu hỏi phỏng vấn
- Viết nhận xét đánh giá
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import json
import logging

_logger = logging.getLogger(__name__)


class NhanVienAI(models.Model):
    """Extend NhanVien with AI capabilities."""
    _inherit = 'nhan_vien'

    # AI Fields
    ai_profile_summary = fields.Text('Tóm tắt hồ sơ', readonly=True, copy=False,
                                     help='Tóm tắt hồ sơ nhân viên bởi AI')
    ai_missing_documents = fields.Text('Hồ sơ còn thiếu', readonly=True, copy=False,
                                       help='Danh sách hồ sơ cần bổ sung')
    ai_training_suggestions = fields.Text('Gợi ý đào tạo', readonly=True, copy=False,
                                          help='Đề xuất khóa đào tạo phù hợp')
    ai_performance_review = fields.Text('Nhận xét AI', readonly=True, copy=False,
                                        help='Nhận xét đánh giá hiệu suất')
    ai_last_analyzed = fields.Datetime('Lần phân tích cuối', readonly=True, copy=False)
    
    def _get_employee_context(self):
        """Get employee data for AI processing."""
        self.ensure_one()
        
        context = {
            'ma_nhan_vien': self.ma_dinh_danh,
            'ho_ten': self.ten_nv,
            'chuc_vu': self.chuc_vu_id.name if self.chuc_vu_id else self.chuc_vu,
            'phong_ban': self.phong_ban_id.name if self.phong_ban_id else self.phong_ban,
            'trang_thai': dict(self._fields['trang_thai_lam_viec'].selection).get(self.trang_thai_lam_viec, ''),
            'ngay_vao_lam': str(self.ngay_vao_lam) if self.ngay_vao_lam else '',
            'email': self.email or '',
        }
        
        # Add statistics
        context['so_ngay_lam_thang'] = self.so_ngay_lam_thang
        context['so_ngay_di_tre'] = self.so_ngay_di_tre
        context['ty_le_cham_cong'] = f"{self.ty_le_cham_cong:.1f}%"
        context['kpi'] = f"{self.kpi:.1f}"
        
        # Add document status
        if hasattr(self, 'ho_so_ids'):
            context['so_ho_so'] = len(self.ho_so_ids)
            context['ho_so_da_duyet'] = len(self.ho_so_ids.filtered(lambda h: h.trang_thai == 'da_duyet'))
            context['ho_so_het_han'] = len(self.ho_so_ids.filtered(lambda h: h.trang_thai == 'het_han'))
        
        return context
    
    def action_ai_summarize_profile(self):
        """Tóm tắt hồ sơ nhân viên."""
        self.ensure_one()
        
        ai_service = self.env['ai.service']
        if not ai_service.is_available():
            raise UserError(_("AI Service chưa được cấu hình."))
        
        context = self._get_employee_context()
        
        prompt = f"""Tóm tắt hồ sơ nhân viên sau thành profile card ngắn gọn:

{json.dumps(context, ensure_ascii=False, indent=2)}

Yêu cầu:
- Tóm tắt trong 100-150 từ
- Nêu điểm mạnh và tiềm năng
- Đánh giá tình trạng làm việc hiện tại
- Gợi ý ngắn gọn nếu cần cải thiện
- Viết bằng tiếng Việt, chuyên nghiệp

Profile:"""
        
        summary = ai_service.chat_completion(
            prompt=prompt,
            model_name=self._name,
            record_id=self.id,
            action_type='summarize'
        )
        
        self.write({
            'ai_profile_summary': summary,
            'ai_last_analyzed': fields.Datetime.now(),
        })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Hoàn thành'),
                'message': _('AI đã tạo tóm tắt hồ sơ.'),
                'type': 'success',
            }
        }
    
    def action_ai_check_documents(self):
        """Kiểm tra hồ sơ còn thiếu."""
        self.ensure_one()
        
        ai_service = self.env['ai.service']
        if not ai_service.is_available():
            raise UserError(_("AI Service chưa được cấu hình."))
        
        # Get current documents
        existing_docs = []
        if hasattr(self, 'ho_so_ids'):
            for ho_so in self.ho_so_ids:
                existing_docs.append({
                    'loai': dict(ho_so._fields['loai_ho_so'].selection).get(ho_so.loai_ho_so, ho_so.loai_ho_so),
                    'trang_thai': dict(ho_so._fields['trang_thai'].selection).get(ho_so.trang_thai, ''),
                    'het_han': str(ho_so.ngay_het_han) if ho_so.ngay_het_han else 'Không có',
                })
        
        context = {
            'chuc_vu': self.chuc_vu_id.name if self.chuc_vu_id else self.chuc_vu or 'Nhân viên',
            'phong_ban': self.phong_ban_id.name if self.phong_ban_id else self.phong_ban or 'Chưa xác định',
            'ho_so_hien_co': existing_docs,
        }
        
        prompt = f"""Kiểm tra hồ sơ nhân viên và liệt kê những giấy tờ còn thiếu:

Thông tin nhân viên:
{json.dumps(context, ensure_ascii=False, indent=2)}

Danh sách hồ sơ bắt buộc theo quy định:
- CMND/CCCD (bắt buộc)
- Sổ hộ khẩu (bắt buộc)
- Bằng cấp cao nhất (bắt buộc)
- Giấy khám sức khỏe (bắt buộc, phải còn hạn)
- Hợp đồng lao động (bắt buộc)
- Đơn xin việc
- CV/Sơ yếu lý lịch
- Ảnh 3x4

Yêu cầu:
1. So sánh hồ sơ hiện có với danh sách bắt buộc
2. Liệt kê hồ sơ còn thiếu
3. Cảnh báo hồ sơ sắp hết hạn
4. Ưu tiên theo mức độ quan trọng

Trả lời bằng tiếng Việt, dạng danh sách:"""
        
        result = ai_service.chat_completion(
            prompt=prompt,
            model_name=self._name,
            record_id=self.id,
            action_type='analyze'
        )
        
        self.write({
            'ai_missing_documents': result,
            'ai_last_analyzed': fields.Datetime.now(),
        })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Kiểm tra hoàn thành'),
                'message': _('AI đã kiểm tra danh sách hồ sơ.'),
                'type': 'success',
            }
        }
    
    def action_ai_suggest_training(self):
        """Gợi ý đào tạo dựa trên KPI và chức vụ."""
        self.ensure_one()
        
        ai_service = self.env['ai.service']
        if not ai_service.is_available():
            raise UserError(_("AI Service chưa được cấu hình."))
        
        context = self._get_employee_context()
        
        prompt = f"""Đề xuất chương trình đào tạo phù hợp cho nhân viên:

{json.dumps(context, ensure_ascii=False, indent=2)}

Yêu cầu:
1. Phân tích điểm cần cải thiện dựa trên KPI và chấm công
2. Đề xuất 3-5 khóa đào tạo phù hợp với chức vụ
3. Sắp xếp theo mức độ ưu tiên
4. Gợi ý lộ trình phát triển nghề nghiệp

Trả lời bằng tiếng Việt, thực tế và cụ thể:"""
        
        suggestions = ai_service.chat_completion(
            prompt=prompt,
            model_name=self._name,
            record_id=self.id,
            action_type='generate'
        )
        
        self.write({
            'ai_training_suggestions': suggestions,
            'ai_last_analyzed': fields.Datetime.now(),
        })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Gợi ý đào tạo'),
                'message': _('AI đã đề xuất chương trình đào tạo.'),
                'type': 'success',
            }
        }
    
    def action_ai_write_review(self):
        """Viết nhận xét đánh giá định kỳ."""
        self.ensure_one()
        
        ai_service = self.env['ai.service']
        if not ai_service.is_available():
            raise UserError(_("AI Service chưa được cấu hình."))
        
        context = self._get_employee_context()
        
        prompt = f"""Viết nhận xét đánh giá hiệu suất làm việc cho nhân viên:

{json.dumps(context, ensure_ascii=False, indent=2)}

Yêu cầu:
1. Dựa hoàn toàn vào dữ liệu có sẵn (KPI, chấm công, tỷ lệ đi trễ)
2. Nhận xét khách quan, công bằng
3. Nêu điểm mạnh và điểm cần cải thiện
4. Đề xuất mục tiêu cho giai đoạn tiếp theo
5. Độ dài: 150-200 từ
6. Giọng văn: chuyên nghiệp, động viên

QUAN TRỌNG: Chỉ nhận xét dựa trên dữ liệu, KHÔNG bịa đặt thông tin.

Nhận xét:"""
        
        review = ai_service.chat_completion(
            prompt=prompt,
            temperature=0.4,
            model_name=self._name,
            record_id=self.id,
            action_type='generate'
        )
        
        self.write({
            'ai_performance_review': review,
            'ai_last_analyzed': fields.Datetime.now(),
        })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Nhận xét hoàn thành'),
                'message': _('AI đã viết nhận xét đánh giá.'),
                'type': 'success',
            }
        }
    
    def action_ai_generate_jd(self):
        """Tạo mô tả công việc dựa trên chức vụ."""
        self.ensure_one()
        
        ai_service = self.env['ai.service']
        if not ai_service.is_available():
            raise UserError(_("AI Service chưa được cấu hình."))
        
        context = {
            'chuc_vu': self.chuc_vu_id.name if self.chuc_vu_id else self.chuc_vu or 'Nhân viên',
            'phong_ban': self.phong_ban_id.name if self.phong_ban_id else self.phong_ban or '',
            'cong_ty': self.env.company.name,
        }
        
        prompt = f"""Tạo mô tả công việc (Job Description) cho vị trí:

{json.dumps(context, ensure_ascii=False, indent=2)}

Format:
1. TÓM TẮT VỊ TRÍ (2-3 câu)
2. TRÁCH NHIỆM CHÍNH (5-7 bullet points)
3. YÊU CẦU
   - Học vấn
   - Kinh nghiệm
   - Kỹ năng cứng
   - Kỹ năng mềm
4. QUYỀN LỢI (3-5 bullet points)

Viết bằng tiếng Việt, chuyên nghiệp:"""
        
        jd = ai_service.chat_completion(
            prompt=prompt,
            max_tokens=1500,
            model_name=self._name,
            record_id=self.id,
            action_type='generate'
        )
        
        # Show in popup
        return {
            'type': 'ir.actions.act_window',
            'name': 'Job Description',
            'res_model': 'ai.assistant.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_user_prompt': f"Tạo JD cho vị trí: {context['chuc_vu']}",
                'default_ai_response': jd,
                'default_response_ready': True,
                'active_model': self._name,
                'active_id': self.id,
            }
        }
    
    def action_ai_generate_interview_questions(self):
        """Tạo câu hỏi phỏng vấn."""
        self.ensure_one()
        
        ai_service = self.env['ai.service']
        if not ai_service.is_available():
            raise UserError(_("AI Service chưa được cấu hình."))
        
        context = {
            'chuc_vu': self.chuc_vu_id.name if self.chuc_vu_id else self.chuc_vu or 'Nhân viên',
            'phong_ban': self.phong_ban_id.name if self.phong_ban_id else self.phong_ban or '',
        }
        
        prompt = f"""Tạo bộ câu hỏi phỏng vấn cho vị trí {context['chuc_vu']} - {context['phong_ban']}:

Yêu cầu:
1. 5 câu hỏi về kiến thức chuyên môn
2. 3 câu hỏi tình huống (behavioral)
3. 2 câu hỏi về kỹ năng mềm
4. 2 câu hỏi về động lực và mục tiêu

Mỗi câu hỏi kèm:
- Mục đích đánh giá
- Gợi ý câu trả lời tốt

Viết bằng tiếng Việt:"""
        
        questions = ai_service.chat_completion(
            prompt=prompt,
            max_tokens=2000,
            model_name=self._name,
            record_id=self.id,
            action_type='generate'
        )
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Câu hỏi phỏng vấn',
            'res_model': 'ai.assistant.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_user_prompt': f"Câu hỏi phỏng vấn: {context['chuc_vu']}",
                'default_ai_response': questions,
                'default_response_ready': True,
                'active_model': self._name,
                'active_id': self.id,
            }
        }
    
    def action_ai_assistant(self):
        """Open AI Assistant."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'AI Assistant - Nhân sự',
            'res_model': 'ai.assistant.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'active_model': self._name,
                'active_id': self.id,
            }
        }


class HoSoNhanVienAI(models.Model):
    """Extend HoSoNhanVien with AI capabilities."""
    _inherit = 'ho_so.nhan_vien'

    ai_extracted_info = fields.Text('Thông tin trích xuất', readonly=True, copy=False)
    
    def action_ai_extract_from_file(self):
        """Trích xuất thông tin từ file đính kèm."""
        self.ensure_one()
        
        if not self.file_dinh_kem:
            raise UserError(_("Chưa có file đính kèm."))
        
        ai_service = self.env['ai.service']
        if not ai_service.is_available():
            raise UserError(_("AI Service chưa được cấu hình."))
        
        # For now, use the document name and type
        # In production, would OCR the file first
        context = {
            'ten_ho_so': self.name,
            'loai_ho_so': dict(self._fields['loai_ho_so'].selection).get(self.loai_ho_so, ''),
            'nhan_vien': self.nhan_vien_id.ten_nv if self.nhan_vien_id else '',
        }
        
        schema = {
            "so_giay_to": "Số CMND/CCCD/Passport/Bằng cấp",
            "ngay_cap": "Ngày cấp",
            "noi_cap": "Nơi cấp",
            "ngay_het_han": "Ngày hết hạn (nếu có)",
            "ten_truong": "Tên trường/Tổ chức cấp",
            "chuyen_nganh": "Chuyên ngành (nếu là bằng cấp)",
            "xep_loai": "Xếp loại (nếu là bằng cấp)",
        }
        
        prompt = f"""Dựa trên thông tin hồ sơ sau, trích xuất các trường nếu có:

Thông tin hồ sơ: {json.dumps(context, ensure_ascii=False)}

Các trường cần trích xuất: {json.dumps(schema, ensure_ascii=False)}

Lưu ý: Nếu đây là loại hồ sơ không có trường nào phù hợp, trả về thông tin cơ bản.
Trả về JSON."""
        
        result = ai_service.chat_completion(
            prompt=prompt,
            json_mode=True,
            model_name=self._name,
            record_id=self.id,
            action_type='extract'
        )
        
        self.write({
            'ai_extracted_info': result,
        })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Trích xuất hoàn thành'),
                'message': _('AI đã trích xuất thông tin từ hồ sơ.'),
                'type': 'success',
            }
        }
