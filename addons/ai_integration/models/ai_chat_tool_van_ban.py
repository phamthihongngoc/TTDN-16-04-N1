# -*- coding: utf-8 -*-

from odoo import models, api
import json
import logging
import re

_logger = logging.getLogger(__name__)


class AIChatToolVanBan(models.AbstractModel):
    """
    Tập hợp các tools cho module Quản lý Văn bản
    Được gọi bởi AI Chat Orchestrator khi LLM yêu cầu
    """
    _name = 'ai.chat.tool.van_ban'
    _description = 'AI Chat Tools - Văn bản'

    # ==================== SEARCH & READ TOOLS ====================

    @api.model
    def tool_search_document(self, arguments, session=None):
        """
        Tìm kiếm văn bản theo từ khóa
        
        Arguments:
            query: Từ khóa tìm kiếm
            doc_type: Loại văn bản (incoming, outgoing, all)
            filters: Dict các filter
            limit: Số kết quả tối đa
        """
        query = arguments.get('query', '')
        doc_type = arguments.get('doc_type')
        filters = arguments.get('filters', {})
        limit = arguments.get('limit', 10)
        
        provider = self.env['ai.context.van_ban']
        results = provider.search_documents(query, doc_type, filters, limit)
        
        if not results:
            return {
                'message': f'Không tìm thấy văn bản nào với từ khóa "{query}"',
                'documents': [],
            }
        
        return {
            'message': f'Tìm thấy {len(results)} văn bản',
            'documents': results,
        }

    @api.model
    def tool_summarize_document(self, arguments, session=None):
        """
        Tóm tắt nội dung văn bản
        
        Arguments:
            model: Model văn bản (van_ban_den, van_ban_di)
            res_id: ID văn bản
        """
        model = arguments.get('model')
        res_id = arguments.get('res_id')
        
        # Get from session context if not provided
        if not model and session:
            model = session.active_model
            res_id = session.active_res_id
        
        if not model or not res_id:
            return {'error': 'Thiếu thông tin văn bản'}
        
        try:
            doc = self.env[model].browse(res_id)
            if not doc.exists():
                return {'error': 'Không tìm thấy văn bản'}
            
            # Get document content
            content = ''
            if hasattr(doc, 'noi_dung') and doc.noi_dung:
                content = re.sub('<[^<]+?>', '', doc.noi_dung)
            elif hasattr(doc, 'trich_yeu') and doc.trich_yeu:
                content = doc.trich_yeu
            
            if not content:
                return {'error': 'Văn bản không có nội dung để tóm tắt'}
            
            # Use AI to summarize
            ai_service = self.env['ai.service']
            
            prompt = f"""Tóm tắt văn bản sau một cách ngắn gọn, rõ ràng:

{content[:3000]}

Yêu cầu:
1. Tóm tắt ý chính (2-3 câu)
2. Các điểm quan trọng (bullet points)
3. Deadline/hạn xử lý (nếu có)
4. Yêu cầu hành động (nếu có)
"""
            
            response = ai_service.chat([
                {"role": "system", "content": "Bạn là chuyên gia phân tích văn bản hành chính."},
                {"role": "user", "content": prompt}
            ])
            
            if response.get('success'):
                summary = response.get('content', '')
                return {
                    'document': doc.display_name,
                    'summary': summary,
                }
            else:
                # Fallback to basic summary
                return {
                    'document': doc.display_name,
                    'summary': content[:500] + '...' if len(content) > 500 else content,
                }
                
        except Exception as e:
            return {'error': str(e)}

    @api.model
    def tool_extract_entities(self, arguments, session=None):
        """
        Trích xuất thực thể từ văn bản (người, cơ quan, ngày, số văn bản...)
        
        Arguments:
            model: Model văn bản
            res_id: ID văn bản
        """
        model = arguments.get('model')
        res_id = arguments.get('res_id')
        
        if not model and session:
            model = session.active_model
            res_id = session.active_res_id
        
        if not model or not res_id:
            return {'error': 'Thiếu thông tin văn bản'}
        
        try:
            doc = self.env[model].browse(res_id)
            if not doc.exists():
                return {'error': 'Không tìm thấy văn bản'}
            
            # Get content
            content = ''
            if hasattr(doc, 'noi_dung') and doc.noi_dung:
                content = re.sub('<[^<]+?>', '', doc.noi_dung)
            if hasattr(doc, 'trich_yeu') and doc.trich_yeu:
                content = doc.trich_yeu + '\n' + content
            
            if not content:
                return {'error': 'Văn bản không có nội dung'}
            
            # Use AI to extract entities
            ai_service = self.env['ai.service']
            
            prompt = f"""Trích xuất các thực thể quan trọng từ văn bản sau:

{content[:3000]}

Trả về JSON với format:
{{
    "people": ["Danh sách người được đề cập"],
    "organizations": ["Danh sách cơ quan/tổ chức"],
    "dates": ["Các ngày tháng quan trọng"],
    "document_numbers": ["Số văn bản liên quan"],
    "deadlines": ["Các thời hạn cần chú ý"],
    "amounts": ["Số tiền/số lượng nếu có"],
    "locations": ["Địa điểm"],
    "actions": ["Các yêu cầu hành động"]
}}

Chỉ trả về JSON, không có text khác.
"""
            
            response = ai_service.chat([
                {"role": "system", "content": "Bạn là chuyên gia trích xuất thông tin từ văn bản. Luôn trả về JSON hợp lệ."},
                {"role": "user", "content": prompt}
            ])
            
            if response.get('success'):
                try:
                    content = response.get('content', '{}')
                    # Extract JSON from response
                    json_match = re.search(r'\{[\s\S]*\}', content)
                    if json_match:
                        entities = json.loads(json_match.group())
                        return {
                            'document': doc.display_name,
                            'entities': entities,
                        }
                except json.JSONDecodeError:
                    pass
            
            return {
                'document': doc.display_name,
                'entities': {
                    'error': 'Không thể trích xuất thực thể',
                    'raw_content': content[:200],
                }
            }
            
        except Exception as e:
            return {'error': str(e)}

    @api.model
    def tool_classify_document(self, arguments, session=None):
        """
        Phân loại văn bản (loại, độ khẩn, độ mật)
        
        Arguments:
            model: Model văn bản
            res_id: ID văn bản
        """
        model = arguments.get('model')
        res_id = arguments.get('res_id')
        
        if not model and session:
            model = session.active_model
            res_id = session.active_res_id
        
        if not model or not res_id:
            return {'error': 'Thiếu thông tin văn bản'}
        
        try:
            doc = self.env[model].browse(res_id)
            if not doc.exists():
                return {'error': 'Không tìm thấy văn bản'}
            
            # Get content
            content = ''
            if hasattr(doc, 'trich_yeu') and doc.trich_yeu:
                content = doc.trich_yeu
            if hasattr(doc, 'noi_dung') and doc.noi_dung:
                content += '\n' + re.sub('<[^<]+?>', '', doc.noi_dung)
            
            ai_service = self.env['ai.service']
            
            prompt = f"""Phân loại văn bản sau:

{content[:2000]}

Trả về JSON với format:
{{
    "category": "Loại văn bản (công văn/quyết định/thông báo/báo cáo/tờ trình/khác)",
    "urgency": "Độ khẩn (binh_thuong/khan/thuong_khan/hoa_toc)",
    "confidentiality": "Độ mật (thuong/mat/toi_mat)",
    "topic": "Chủ đề chính",
    "department": "Phòng ban liên quan",
    "action_required": true/false,
    "response_needed": true/false,
    "reasoning": "Giải thích ngắn gọn cách phân loại"
}}

Chỉ trả về JSON.
"""
            
            response = ai_service.chat([
                {"role": "system", "content": "Bạn là chuyên gia phân loại văn bản hành chính."},
                {"role": "user", "content": prompt}
            ])
            
            if response.get('success'):
                try:
                    content = response.get('content', '{}')
                    json_match = re.search(r'\{[\s\S]*\}', content)
                    if json_match:
                        classification = json.loads(json_match.group())
                        return {
                            'document': doc.display_name,
                            'classification': classification,
                        }
                except json.JSONDecodeError:
                    pass
            
            return {
                'document': doc.display_name,
                'classification': {'error': 'Không thể phân loại'},
            }
            
        except Exception as e:
            return {'error': str(e)}

    @api.model
    def tool_get_pending_documents(self, arguments, session=None):
        """
        Lấy danh sách văn bản đang chờ xử lý
        
        Arguments:
            days: Số ngày lấy (default 7)
        """
        days = arguments.get('days', 7)
        
        provider = self.env['ai.context.van_ban']
        result = provider.get_pending_documents(days=days)
        
        return result

    @api.model
    def tool_suggest_workflow(self, arguments, session=None):
        """
        Đề xuất bước xử lý tiếp theo cho văn bản
        
        Arguments:
            model: Model văn bản
            res_id: ID văn bản
        """
        model = arguments.get('model')
        res_id = arguments.get('res_id')
        
        if not model and session:
            model = session.active_model
            res_id = session.active_res_id
        
        if not model or not res_id:
            return {'error': 'Thiếu thông tin văn bản'}
        
        provider = self.env['ai.context.van_ban']
        result = provider.get_document_workflow_status(model, res_id)
        
        if result.get('error'):
            return result
        
        # Use AI to suggest next steps
        try:
            doc = self.env[model].browse(res_id)
            context = provider.get_context(model, res_id)
            
            ai_service = self.env['ai.service']
            
            prompt = f"""Dựa trên thông tin văn bản sau, đề xuất các bước xử lý tiếp theo:

{context}

Trạng thái hiện tại: {result.get('current_state')}

Yêu cầu:
1. Liệt kê 2-3 bước xử lý tiếp theo theo thứ tự ưu tiên
2. Mỗi bước cần có: tên hành động, người thực hiện (nếu biết), deadline đề xuất
3. Nêu rõ lý do đề xuất
"""
            
            response = ai_service.chat([
                {"role": "system", "content": "Bạn là chuyên gia quy trình xử lý văn bản hành chính."},
                {"role": "user", "content": prompt}
            ])
            
            if response.get('success'):
                result['ai_suggestions'] = response.get('content', '')
            
            return result
            
        except Exception as e:
            return {'error': str(e)}

    @api.model
    def tool_generate_action_items(self, arguments, session=None):
        """
        Tạo checklist việc cần làm từ văn bản
        
        Arguments:
            model: Model văn bản
            res_id: ID văn bản
        """
        model = arguments.get('model')
        res_id = arguments.get('res_id')
        
        if not model and session:
            model = session.active_model
            res_id = session.active_res_id
        
        if not model or not res_id:
            return {'error': 'Thiếu thông tin văn bản'}
        
        try:
            doc = self.env[model].browse(res_id)
            if not doc.exists():
                return {'error': 'Không tìm thấy văn bản'}
            
            # Get content
            content = ''
            if hasattr(doc, 'trich_yeu') and doc.trich_yeu:
                content = doc.trich_yeu
            if hasattr(doc, 'noi_dung') and doc.noi_dung:
                content += '\n' + re.sub('<[^<]+?>', '', doc.noi_dung)
            
            ai_service = self.env['ai.service']
            
            prompt = f"""Từ văn bản sau, tạo danh sách các việc cần làm (action items):

{content[:3000]}

Trả về JSON array với format:
[
    {{
        "task": "Mô tả công việc",
        "deadline": "Hạn chót (nếu có trong văn bản)",
        "priority": "high/medium/low",
        "assignee": "Người/đơn vị thực hiện (nếu biết)"
    }}
]

Chỉ trả về JSON array.
"""
            
            response = ai_service.chat([
                {"role": "system", "content": "Bạn là chuyên gia phân tích văn bản và quản lý công việc."},
                {"role": "user", "content": prompt}
            ])
            
            if response.get('success'):
                try:
                    content = response.get('content', '[]')
                    json_match = re.search(r'\[[\s\S]*\]', content)
                    if json_match:
                        action_items = json.loads(json_match.group())
                        return {
                            'document': doc.display_name,
                            'action_items': action_items,
                        }
                except json.JSONDecodeError:
                    pass
            
            return {
                'document': doc.display_name,
                'action_items': [],
                'error': 'Không thể tạo checklist',
            }
            
        except Exception as e:
            return {'error': str(e)}

    # ==================== ACTION TOOLS (REQUIRE CONFIRMATION) ====================

    @api.model
    def tool_draft_outgoing_from_incoming(self, arguments, session=None):
        """
        Soạn văn bản đi dựa trên văn bản đến (cần xác nhận)
        
        Arguments:
            incoming_id: ID văn bản đến
            template: Loại văn bản đi (reply, forward, report)
            recipients: Danh sách người nhận
        """
        incoming_id = arguments.get('incoming_id')
        template = arguments.get('template', 'reply')
        recipients = arguments.get('recipients', '')
        
        if not incoming_id and session:
            if session.active_model == 'van_ban_den':
                incoming_id = session.active_res_id
        
        if not incoming_id:
            return {'error': 'Thiếu ID văn bản đến'}
        
        try:
            incoming = self.env['van_ban_den'].browse(incoming_id)
            if not incoming.exists():
                return {'error': 'Không tìm thấy văn bản đến'}
            
            # Get incoming content
            content = ''
            if hasattr(incoming, 'noi_dung') and incoming.noi_dung:
                content = re.sub('<[^<]+?>', '', incoming.noi_dung)
            
            ai_service = self.env['ai.service']
            
            template_prompts = {
                'reply': 'Soạn văn bản phúc đáp, trả lời các yêu cầu trong văn bản đến',
                'forward': 'Soạn công văn chuyển tiếp văn bản đến cho đơn vị liên quan xử lý',
                'report': 'Soạn báo cáo kết quả thực hiện các yêu cầu trong văn bản đến',
            }
            
            prompt = f"""Dựa trên văn bản đến sau:

Số ký hiệu: {incoming.so_ky_hieu if hasattr(incoming, 'so_ky_hieu') else 'N/A'}
Trích yếu: {incoming.trich_yeu if hasattr(incoming, 'trich_yeu') else 'N/A'}
Nơi gửi: {incoming.don_vi_gui if hasattr(incoming, 'don_vi_gui') else 'N/A'}
Nội dung: {content[:2000]}

{template_prompts.get(template, template_prompts['reply'])}

Người nhận: {recipients or 'Đơn vị gửi văn bản đến'}

Trả về format:
TRICH_YEU: [Trích yếu văn bản đi]
NOI_DUNG:
[Nội dung văn bản đi, đầy đủ các phần: kính gửi, nội dung chính, đề nghị, ký tên]
"""
            
            response = ai_service.chat([
                {"role": "system", "content": "Bạn là chuyên gia soạn thảo văn bản hành chính Việt Nam."},
                {"role": "user", "content": prompt}
            ])
            
            if response.get('success'):
                draft_content = response.get('content', '')
                
                # Parse output
                lines = draft_content.split('\n')
                trich_yeu = ''
                noi_dung = ''
                in_noi_dung = False
                
                for line in lines:
                    if line.startswith('TRICH_YEU:'):
                        trich_yeu = line.replace('TRICH_YEU:', '').strip()
                    elif line.startswith('NOI_DUNG:'):
                        in_noi_dung = True
                    elif in_noi_dung:
                        noi_dung += line + '\n'
                
                preview = f"""**Văn bản đi mới (từ VB đến {incoming.display_name})**

**Trích yếu:** {trich_yeu}

**Nội dung:**
{noi_dung[:1000]}{'...' if len(noi_dung) > 1000 else ''}
"""
                
                return {
                    'requires_confirmation': True,
                    'preview': preview,
                    'subject': trich_yeu,
                    'content': noi_dung.strip(),
                    'incoming_id': incoming_id,
                    'incoming_ref': incoming.so_ky_hieu if hasattr(incoming, 'so_ky_hieu') else incoming.display_name,
                }
            else:
                return {'error': 'Không thể tạo văn bản đi'}
                
        except Exception as e:
            return {'error': str(e)}

    @api.model
    def tool_compare_documents(self, arguments, session=None):
        """
        So sánh 2 văn bản
        
        Arguments:
            doc1_model: Model văn bản 1
            doc1_id: ID văn bản 1
            doc2_model: Model văn bản 2
            doc2_id: ID văn bản 2
        """
        doc1_model = arguments.get('doc1_model')
        doc1_id = arguments.get('doc1_id')
        doc2_model = arguments.get('doc2_model')
        doc2_id = arguments.get('doc2_id')
        
        if not all([doc1_model, doc1_id, doc2_model, doc2_id]):
            return {'error': 'Thiếu thông tin văn bản để so sánh'}
        
        try:
            doc1 = self.env[doc1_model].browse(doc1_id)
            doc2 = self.env[doc2_model].browse(doc2_id)
            
            if not doc1.exists() or not doc2.exists():
                return {'error': 'Không tìm thấy một trong hai văn bản'}
            
            # Get contents
            content1 = doc1.noi_dung if hasattr(doc1, 'noi_dung') else doc1.trich_yeu if hasattr(doc1, 'trich_yeu') else ''
            content2 = doc2.noi_dung if hasattr(doc2, 'noi_dung') else doc2.trich_yeu if hasattr(doc2, 'trich_yeu') else ''
            
            content1 = re.sub('<[^<]+?>', '', content1)[:2000]
            content2 = re.sub('<[^<]+?>', '', content2)[:2000]
            
            ai_service = self.env['ai.service']
            
            prompt = f"""So sánh 2 văn bản sau:

VĂN BẢN 1: {doc1.display_name}
{content1}

VĂN BẢN 2: {doc2.display_name}
{content2}

Phân tích:
1. Điểm giống nhau
2. Điểm khác nhau chính
3. Mối liên hệ (nếu có)
4. Nhận xét tổng quan
"""
            
            response = ai_service.chat([
                {"role": "system", "content": "Bạn là chuyên gia phân tích văn bản."},
                {"role": "user", "content": prompt}
            ])
            
            if response.get('success'):
                return {
                    'doc1': doc1.display_name,
                    'doc2': doc2.display_name,
                    'comparison': response.get('content', ''),
                }
            
            return {'error': 'Không thể so sánh văn bản'}
            
        except Exception as e:
            return {'error': str(e)}
