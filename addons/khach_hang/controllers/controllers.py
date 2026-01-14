# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)


class KhachHangController(http.Controller):
    
    @http.route('/khach_hang/dashboard', type='json', auth='user')
    def get_dashboard_data(self):
        """API lấy dữ liệu dashboard"""
        KhachHang = request.env['khach_hang']
        HoTro = request.env['ho_tro_khach_hang']
        DonHang = request.env['don_hang']
        
        return {
            'tong_khach_hang': KhachHang.search_count([]),
            'khach_hang_moi': KhachHang.search_count([('trang_thai', '=', 'moi')]),
            'tong_ho_tro': HoTro.search_count([]),
            'ho_tro_chua_giai_quyet': HoTro.search_count([('trang_thai', '!=', 'da_giai_quyet')]),
            'tong_don_hang': DonHang.search_count([]),
            'don_hang_hoan_thanh': DonHang.search_count([('trang_thai', '=', 'hoan_thanh')]),
        }
    
    @http.route('/khach_hang/chatbot/webhook', type='json', auth='public', methods=['POST'], csrf=False)
    def chatbot_webhook(self, **kwargs):
        """Webhook cho Dialogflow chatbot"""
        try:
            # Optional shared-secret protection (recommended for production)
            expected_token = request.env['ir.config_parameter'].sudo().get_param('khach_hang.chatbot_token')
            if expected_token:
                provided = request.httprequest.headers.get('X-Chatbot-Token') or request.httprequest.args.get('token')
                if provided != expected_token:
                    return {'fulfillmentText': 'Unauthorized webhook.'}

            data = request.jsonrequest or {}
            intent = data.get('queryResult', {}).get('intent', {}).get('displayName')
            parameters = data.get('queryResult', {}).get('parameters', {})
            session = data.get('session') or ''
            session_id = session.split('/')[-1] if session else 'anonymous'
            
            response_text = self._process_chatbot_intent(intent, parameters, session_id)
            
            return {
                'fulfillmentText': response_text
            }
        except Exception as e:
            _logger.error("Chatbot webhook error: %s", e)
            return {
                'fulfillmentText': 'Xin lỗi, có lỗi xảy ra. Vui lòng thử lại sau.'
            }
    
    def _process_chatbot_intent(self, intent, parameters, session_id):
        """Xử lý intent từ Dialogflow"""
        if intent == 'customer_support':
            customer_email = parameters.get('email')
            issue = parameters.get('issue')
            
            if customer_email and issue:
                # Tạo yêu cầu hỗ trợ
                customer = request.env['khach_hang'].sudo().search([('email', '=', customer_email)], limit=1)
                if customer:
                    request.env['ho_tro_khach_hang'].sudo().create({
                        'khach_hang_id': customer.id,
                        'tieu_de': f'Hỗ trợ từ chatbot: {issue}',
                        'mo_ta': f'Yêu cầu từ chatbot: {issue}',
                        'nguon': 'chatbot'
                    })
                    return f'Cảm ơn {customer.ten_khach_hang}! Chúng tôi đã nhận được yêu cầu hỗ trợ của bạn về "{issue}". Nhân viên sẽ liên hệ sớm.'
                else:
                    return 'Không tìm thấy thông tin khách hàng với email này. Vui lòng kiểm tra lại.'
            else:
                return 'Vui lòng cung cấp email và mô tả vấn đề cần hỗ trợ.'
        
        elif intent == 'order_status':
            order_code = parameters.get('order_code')
            if order_code:
                order = request.env['don_hang'].sudo().search([('ma_don_hang', '=', order_code)], limit=1)
                if order:
                    return f'Đơn hàng {order_code} hiện tại ở trạng thái: {dict(order._fields["trang_thai"].selection).get(order.trang_thai)}'
                else:
                    return f'Không tìm thấy đơn hàng với mã {order_code}'
            else:
                return 'Vui lòng cung cấp mã đơn hàng.'
        
        elif intent == 'product_recommendation':
            customer_email = parameters.get('email')
            if customer_email:
                customer = request.env['khach_hang'].sudo().search([('email', '=', customer_email)], limit=1)
                if customer and customer.san_pham_du_doan_ids:
                    products = customer.san_pham_du_doan_ids.mapped('ten_san_pham')
                    return f'Dựa trên lịch sử mua hàng, chúng tôi đề xuất các sản phẩm: {", ".join(products)}'
                else:
                    return 'Chúng tôi cần thêm thông tin để đưa ra đề xuất phù hợp.'
            else:
                return 'Vui lòng cung cấp email để nhận đề xuất sản phẩm.'
        
        return 'Xin chào! Tôi có thể giúp bạn với thông tin đơn hàng, hỗ trợ kỹ thuật, hoặc đề xuất sản phẩm. Bạn cần gì?'
