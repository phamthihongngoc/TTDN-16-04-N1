# -*- coding: utf-8 -*-

from odoo import models, api
import json
import logging

_logger = logging.getLogger(__name__)


class AIChatToolKhachHang(models.AbstractModel):
    """
    Tập hợp các tools cho module Quản lý Khách hàng
    Được gọi bởi AI Chat Orchestrator khi LLM yêu cầu
    """
    _name = 'ai.chat.tool.khach_hang'
    _description = 'AI Chat Tools - Khách hàng'

    # ==================== SEARCH & READ TOOLS ====================

    @api.model
    def tool_search_customer(self, arguments, session=None):
        """
        Tìm kiếm khách hàng theo query
        
        Arguments:
            query: Từ khóa tìm kiếm (tên, mã, email, SĐT)
            filters: Dict các filter (loai_khach_hang, trang_thai)
            limit: Số lượng kết quả tối đa
        """
        query = arguments.get('query', '')
        filters = arguments.get('filters', {})
        limit = arguments.get('limit', 10)
        
        provider = self.env['ai.context.khach_hang']
        results = provider.search_customers(query, filters, limit)
        
        if not results:
            return {
                'message': f'Không tìm thấy khách hàng nào với từ khóa "{query}"',
                'customers': [],
            }
        
        return {
            'message': f'Tìm thấy {len(results)} khách hàng',
            'customers': results,
        }

    @api.model
    def tool_get_customer_brief(self, arguments, session=None):
        """
        Lấy thông tin tóm tắt 360° của khách hàng
        
        Arguments:
            customer_id: ID khách hàng
        """
        customer_id = arguments.get('customer_id')
        
        # If no customer_id, try to get from session context
        if not customer_id and session:
            if session.active_model == 'khach_hang':
                customer_id = session.active_res_id
        
        if not customer_id:
            return {'error': 'Thiếu customer_id'}
        
        provider = self.env['ai.context.khach_hang']
        result = provider.get_customer_brief(customer_id)
        
        return result

    @api.model
    def tool_summarize_interactions(self, arguments, session=None):
        """
        Tổng hợp lịch sử tương tác với khách hàng
        
        Arguments:
            customer_id: ID khách hàng
            days: Số ngày lịch sử (default 30)
        """
        customer_id = arguments.get('customer_id')
        days = arguments.get('days', 30)
        
        if not customer_id and session:
            if session.active_model == 'khach_hang':
                customer_id = session.active_res_id
        
        if not customer_id:
            return {'error': 'Thiếu customer_id'}
        
        provider = self.env['ai.context.khach_hang']
        result = provider.get_customer_interactions(customer_id, days)
        
        return result

    @api.model
    def tool_analyze_customer_risk(self, arguments, session=None):
        """
        Phân tích rủi ro khách hàng
        
        Arguments:
            customer_id: ID khách hàng
        """
        customer_id = arguments.get('customer_id')
        
        if not customer_id and session:
            if session.active_model == 'khach_hang':
                customer_id = session.active_res_id
        
        if not customer_id:
            return {'error': 'Thiếu customer_id'}
        
        provider = self.env['ai.context.khach_hang']
        result = provider.get_customer_risk_analysis(customer_id)
        
        return result

    @api.model
    def tool_get_customer_orders(self, arguments, session=None):
        """
        Lấy danh sách đơn hàng của khách hàng
        
        Arguments:
            customer_id: ID khách hàng
            status: Filter theo trạng thái
            limit: Số lượng tối đa
        """
        customer_id = arguments.get('customer_id')
        status = arguments.get('status')
        limit = arguments.get('limit', 10)
        
        if not customer_id and session:
            if session.active_model == 'khach_hang':
                customer_id = session.active_res_id
            elif session.active_model == 'don_hang':
                # Get customer from order
                order = self.env['don_hang'].browse(session.active_res_id)
                if order.exists() and hasattr(order, 'khach_hang_id'):
                    customer_id = order.khach_hang_id.id
        
        if not customer_id:
            return {'error': 'Thiếu customer_id'}
        
        try:
            domain = [('khach_hang_id', '=', customer_id)]
            if status:
                domain.append(('trang_thai', '=', status))
            
            orders = self.env['don_hang'].search(domain, limit=limit, order='create_date desc')
            
            result = []
            for order in orders:
                result.append({
                    'id': order.id,
                    'name': order.display_name,
                    'date': order.ngay_dat.strftime('%d/%m/%Y') if hasattr(order, 'ngay_dat') and order.ngay_dat else None,
                    'total': order.tong_tien if hasattr(order, 'tong_tien') else 0,
                    'status': order.trang_thai if hasattr(order, 'trang_thai') else None,
                })
            
            return {
                'message': f'Tìm thấy {len(result)} đơn hàng',
                'orders': result,
            }
            
        except Exception as e:
            return {'error': str(e)}

    # ==================== ACTION TOOLS (REQUIRE CONFIRMATION) ====================

    @api.model
    def tool_draft_customer_email(self, arguments, session=None):
        """
        Soạn email cho khách hàng
        
        Arguments:
            customer_id: ID khách hàng
            intent: Mục đích email (care, reminder, survey, promotion)
            tone: Giọng văn (formal, friendly, urgent)
            additional_info: Thông tin bổ sung
        """
        customer_id = arguments.get('customer_id')
        intent = arguments.get('intent', 'care')
        tone = arguments.get('tone', 'friendly')
        additional_info = arguments.get('additional_info', '')
        
        if not customer_id and session:
            if session.active_model == 'khach_hang':
                customer_id = session.active_res_id
        
        if not customer_id:
            return {'error': 'Thiếu customer_id'}
        
        try:
            customer = self.env['khach_hang'].browse(customer_id)
            if not customer.exists():
                return {'error': 'Không tìm thấy khách hàng'}
            
            # Generate email using AI
            ai_service = self.env['ai.service']
            
            intent_prompts = {
                'care': 'Soạn email chăm sóc khách hàng, hỏi thăm và cảm ơn đã sử dụng dịch vụ',
                'reminder': 'Soạn email nhắc nhở thanh toán hoặc hẹn cuộc hẹn',
                'survey': 'Soạn email khảo sát ý kiến khách hàng về sản phẩm/dịch vụ',
                'promotion': 'Soạn email thông báo khuyến mãi, ưu đãi đặc biệt',
            }
            
            tone_instructions = {
                'formal': 'Giọng văn trang trọng, lịch sự, chuyên nghiệp',
                'friendly': 'Giọng văn thân thiện, gần gũi nhưng vẫn chuyên nghiệp',
                'urgent': 'Giọng văn nhấn mạnh tính cấp bách, cần hành động ngay',
            }
            
            prompt = f"""
Soạn email tiếng Việt cho khách hàng:
- Tên: {customer.display_name}
- Email: {customer.email if hasattr(customer, 'email') else 'N/A'}

Yêu cầu:
- {intent_prompts.get(intent, intent_prompts['care'])}
- {tone_instructions.get(tone, tone_instructions['friendly'])}
{f'- Thông tin thêm: {additional_info}' if additional_info else ''}

Trả về format:
SUBJECT: [Tiêu đề email]
BODY:
[Nội dung email]
"""
            
            response = ai_service.chat([
                {"role": "system", "content": "Bạn là chuyên gia viết email chuyên nghiệp."},
                {"role": "user", "content": prompt}
            ])
            
            if response.get('success'):
                email_content = response.get('content', '')
                
                # Parse subject and body
                lines = email_content.split('\n')
                subject = ''
                body = ''
                in_body = False
                
                for line in lines:
                    if line.startswith('SUBJECT:'):
                        subject = line.replace('SUBJECT:', '').strip()
                    elif line.startswith('BODY:'):
                        in_body = True
                    elif in_body:
                        body += line + '\n'
                
                return {
                    'preview': f"**Email cho {customer.display_name}**\n\n**Tiêu đề:** {subject}\n\n{body}",
                    'subject': subject,
                    'body': body.strip(),
                    'customer_id': customer_id,
                    'customer_email': customer.email if hasattr(customer, 'email') else None,
                }
            else:
                return {'error': 'Không thể tạo email'}
                
        except Exception as e:
            return {'error': str(e)}

    @api.model
    def tool_create_support_ticket(self, arguments, session=None):
        """
        Tạo phiếu hỗ trợ mới (cần xác nhận)
        
        Arguments:
            customer_id: ID khách hàng
            subject: Tiêu đề
            description: Mô tả vấn đề
            priority: Mức độ ưu tiên (low, normal, high, urgent)
        """
        customer_id = arguments.get('customer_id')
        subject = arguments.get('subject', 'Yêu cầu hỗ trợ mới')
        description = arguments.get('description', '')
        priority = arguments.get('priority', 'normal')
        
        if not customer_id and session:
            if session.active_model == 'khach_hang':
                customer_id = session.active_res_id
        
        if not customer_id:
            return {'error': 'Thiếu customer_id'}
        
        try:
            customer = self.env['khach_hang'].browse(customer_id)
            if not customer.exists():
                return {'error': 'Không tìm thấy khách hàng'}
            
            # Return preview for confirmation
            preview = f"""**Tạo phiếu hỗ trợ mới**

- **Khách hàng:** {customer.display_name}
- **Tiêu đề:** {subject}
- **Mức độ:** {priority}

**Mô tả:**
{description}
"""
            
            return {
                'requires_confirmation': True,
                'preview': preview,
                'customer_id': customer_id,
                'subject': subject,
                'description': description,
                'priority': priority,
            }
            
        except Exception as e:
            return {'error': str(e)}

    @api.model
    def tool_next_best_action(self, arguments, session=None):
        """
        Đề xuất bước tiếp theo với khách hàng
        
        Arguments:
            customer_id: ID khách hàng
        """
        customer_id = arguments.get('customer_id')
        
        if not customer_id and session:
            if session.active_model == 'khach_hang':
                customer_id = session.active_res_id
        
        if not customer_id:
            return {'error': 'Thiếu customer_id'}
        
        try:
            customer = self.env['khach_hang'].browse(customer_id)
            if not customer.exists():
                return {'error': 'Không tìm thấy khách hàng'}
            
            # Analyze customer data
            actions = []
            reasons = []
            
            # Check open support tickets
            if hasattr(customer, 'ho_tro_ids'):
                open_tickets = customer.ho_tro_ids.filtered(
                    lambda t: t.trang_thai not in ['done', 'cancel'] if hasattr(t, 'trang_thai') else True
                )
                if open_tickets:
                    actions.append({
                        'action': 'Giải quyết phiếu hỗ trợ',
                        'priority': 'high',
                        'reason': f'Có {len(open_tickets)} phiếu hỗ trợ đang chờ xử lý',
                    })
            
            # Check recent order activity
            if hasattr(customer, 'don_hang_ids'):
                from datetime import datetime, timedelta
                recent_orders = customer.don_hang_ids.filtered(
                    lambda o: o.create_date >= datetime.now() - timedelta(days=30)
                )
                
                if not recent_orders:
                    # No recent orders - consider re-engagement
                    last_order = customer.don_hang_ids.sorted('create_date', reverse=True)[:1]
                    if last_order:
                        days_since = (datetime.now() - last_order.create_date).days
                        actions.append({
                            'action': 'Gửi email tái kích hoạt',
                            'priority': 'medium',
                            'reason': f'Đã {days_since} ngày không có đơn hàng mới',
                        })
                    else:
                        actions.append({
                            'action': 'Liên hệ giới thiệu sản phẩm',
                            'priority': 'medium',
                            'reason': 'Khách hàng mới, chưa có đơn hàng',
                        })
                else:
                    actions.append({
                        'action': 'Gửi email cảm ơn',
                        'priority': 'low',
                        'reason': f'Có {len(recent_orders)} đơn hàng trong tháng',
                    })
            
            # Check RFM segment if available
            if hasattr(customer, 'rfm_segment') and customer.rfm_segment:
                segment = customer.rfm_segment
                if 'risk' in segment.lower() or 'lost' in segment.lower():
                    actions.append({
                        'action': 'Gọi điện tư vấn',
                        'priority': 'high',
                        'reason': f'Phân khúc {segment} - cần chú ý',
                    })
            
            if not actions:
                actions.append({
                    'action': 'Duy trì liên lạc định kỳ',
                    'priority': 'low',
                    'reason': 'Khách hàng ổn định',
                })
            
            # Sort by priority
            priority_order = {'high': 0, 'medium': 1, 'low': 2}
            actions.sort(key=lambda x: priority_order.get(x['priority'], 2))
            
            return {
                'customer': customer.display_name,
                'recommended_actions': actions,
                'top_action': actions[0] if actions else None,
            }
            
        except Exception as e:
            return {'error': str(e)}
