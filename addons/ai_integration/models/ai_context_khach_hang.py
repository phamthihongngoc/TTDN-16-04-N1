# -*- coding: utf-8 -*-

from odoo import models, api
import logging

_logger = logging.getLogger(__name__)


class AIContextKhachHang(models.AbstractModel):
    """Context Provider cho module Quản lý Khách hàng"""
    _name = 'ai.context.khach_hang'
    _description = 'AI Context Provider - Khách hàng'

    @api.model
    def get_context(self, model, res_id):
        """Lấy context nghiệp vụ cho chatbot"""
        if model == 'khach_hang':
            return self._get_customer_context(res_id)
        elif model == 'don_hang':
            return self._get_order_context(res_id)
        elif model == 'ho_tro_khach_hang':
            return self._get_support_context(res_id)
        return None

    def _get_customer_context(self, customer_id):
        """Lấy context chi tiết khách hàng"""
        try:
            customer = self.env['khach_hang'].sudo().browse(customer_id)
            if not customer.exists():
                return None
            
            # Get phone - check both field names
            phone = customer.so_dien_thoai if hasattr(customer, 'so_dien_thoai') and customer.so_dien_thoai else (customer.dien_thoai if hasattr(customer, 'dien_thoai') else 'N/A')
            
            # Get classification - check both field names
            classification = 'N/A'
            if hasattr(customer, 'phan_loai') and customer.phan_loai:
                classification = dict(customer._fields['phan_loai'].selection).get(customer.phan_loai, 'N/A')
            elif hasattr(customer, 'loai_khach_hang') and customer.loai_khach_hang:
                classification = dict(customer._fields['loai_khach_hang'].selection).get(customer.loai_khach_hang, 'N/A')
            
            # Basic info
            context = f"""KHÁCH HÀNG: {customer.display_name}
- Mã: {customer.id}
- Email: {customer.email or 'N/A'}
- Điện thoại: {phone}
- Địa chỉ: {customer.dia_chi or 'N/A'}
- Phân loại: {classification}
- Trạng thái: {dict(customer._fields['trang_thai'].selection).get(customer.trang_thai, 'N/A') if hasattr(customer, 'trang_thai') else 'N/A'}
"""
            
            # Orders summary
            if hasattr(customer, 'don_hang_ids'):
                orders = customer.don_hang_ids
                total_orders = len(orders)
                if total_orders > 0:
                    total_revenue = sum(orders.mapped('tong_tien')) if hasattr(orders[0], 'tong_tien') else 0
                    context += f"""
ĐƠN HÀNG:
- Tổng số: {total_orders} đơn
- Doanh thu: {total_revenue:,.0f} VND
"""
                    # Recent orders
                    recent = orders.sorted('create_date', reverse=True)[:3]
                    if recent:
                        context += "- Đơn gần đây:\n"
                        for order in recent:
                            status = dict(order._fields['trang_thai'].selection).get(order.trang_thai, '') if hasattr(order, 'trang_thai') else ''
                            context += f"  • {order.display_name}: {status}\n"
            
            # Support tickets
            if hasattr(customer, 'ho_tro_ids'):
                tickets = customer.ho_tro_ids
                open_tickets = tickets.filtered(lambda t: t.trang_thai not in ['done', 'cancel'] if hasattr(t, 'trang_thai') else True)
                context += f"""
HỖ TRỢ:
- Tổng phiếu: {len(tickets)}
- Đang mở: {len(open_tickets)}
"""
                if open_tickets:
                    context += "- Phiếu đang xử lý:\n"
                    for ticket in open_tickets[:3]:
                        context += f"  • {ticket.display_name}\n"
            
            # RFM if available
            if hasattr(customer, 'rfm_segment'):
                context += f"""
PHÂN LOẠI RFM: {customer.rfm_segment or 'N/A'}
"""
            
            # Notes
            if hasattr(customer, 'ghi_chu') and customer.ghi_chu:
                context += f"""
GHI CHÚ: {customer.ghi_chu[:200]}...
""" if len(customer.ghi_chu) > 200 else f"""
GHI CHÚ: {customer.ghi_chu}
"""
            
            return context
            
        except Exception as e:
            _logger.warning(f"Error getting customer context: {e}")
            return None

    def _get_order_context(self, order_id):
        """Lấy context đơn hàng"""
        try:
            order = self.env['don_hang'].sudo().browse(order_id)
            if not order.exists():
                return None
            
            # Get order date - check both field names
            order_date = 'N/A'
            if hasattr(order, 'ngay_dat_hang') and order.ngay_dat_hang:
                order_date = order.ngay_dat_hang.strftime('%d/%m/%Y')
            elif hasattr(order, 'ngay_dat') and order.ngay_dat:
                order_date = order.ngay_dat.strftime('%d/%m/%Y')
            
            # Get total amount
            total = order.tong_tien if hasattr(order, 'tong_tien') else 0
            
            context = f"""ĐƠN HÀNG: {order.display_name}
- Mã: {order.ma_don_hang if hasattr(order, 'ma_don_hang') else order.id}
- Khách hàng: {order.khach_hang_id.display_name if hasattr(order, 'khach_hang_id') and order.khach_hang_id else 'N/A'}
- Ngày đặt: {order_date}
- Tổng tiền: {total:,.0f} VND
- Trạng thái: {dict(order._fields['trang_thai'].selection).get(order.trang_thai, 'N/A') if hasattr(order, 'trang_thai') else 'N/A'}
"""
            
            # Order lines - check both field names
            order_lines = None
            if hasattr(order, 'line_ids') and order.line_ids:
                order_lines = order.line_ids
            elif hasattr(order, 'chi_tiet_ids') and order.chi_tiet_ids:
                order_lines = order.chi_tiet_ids
            
            if order_lines:
                context += "\nCHI TIẾT ĐƠN:\n"
                for line in order_lines[:10]:
                    product = line.san_pham_id.display_name if hasattr(line, 'san_pham_id') and line.san_pham_id else 'N/A'
                    qty = line.so_luong if hasattr(line, 'so_luong') else 0
                    if hasattr(line, 'don_gia') and hasattr(line, 'thanh_tien'):
                        context += f"  • {product}: {qty} x {line.don_gia:,.0f} = {line.thanh_tien:,.0f}\n"
                    else:
                        context += f"  • {product}: {qty}\n"
            
            return context
            
        except Exception as e:
            _logger.warning(f"Error getting order context: {e}")
            return None

    def _get_support_context(self, ticket_id):
        """Lấy context phiếu hỗ trợ"""
        try:
            ticket = self.env['ho_tro_khach_hang'].browse(ticket_id)
            if not ticket.exists():
                return None
            
            context = f"""PHIẾU HỖ TRỢ: {ticket.display_name}
- Mã: {ticket.ma_ho_tro if hasattr(ticket, 'ma_ho_tro') else ticket.id}
- Khách hàng: {ticket.khach_hang_id.display_name if hasattr(ticket, 'khach_hang_id') and ticket.khach_hang_id else 'N/A'}
- Loại: {dict(ticket._fields['loai_yeu_cau'].selection).get(ticket.loai_yeu_cau, 'N/A') if hasattr(ticket, 'loai_yeu_cau') else 'N/A'}
- Mức độ: {dict(ticket._fields['muc_do_uu_tien'].selection).get(ticket.muc_do_uu_tien, 'N/A') if hasattr(ticket, 'muc_do_uu_tien') else 'N/A'}
- Trạng thái: {dict(ticket._fields['trang_thai'].selection).get(ticket.trang_thai, 'N/A') if hasattr(ticket, 'trang_thai') else 'N/A'}
- Người xử lý: {ticket.nguoi_xu_ly_id.display_name if hasattr(ticket, 'nguoi_xu_ly_id') and ticket.nguoi_xu_ly_id else 'Chưa phân công'}
"""
            
            # Description
            if hasattr(ticket, 'mo_ta') and ticket.mo_ta:
                desc = ticket.mo_ta[:500] + '...' if len(ticket.mo_ta) > 500 else ticket.mo_ta
                context += f"""
MÔ TẢ VẤN ĐỀ:
{desc}
"""
            
            # Solution if exists
            if hasattr(ticket, 'giai_phap') and ticket.giai_phap:
                context += f"""
GIẢI PHÁP:
{ticket.giai_phap[:300]}
"""
            
            return context
            
        except Exception as e:
            _logger.warning(f"Error getting support context: {e}")
            return None

    # ==================== DATA RETRIEVAL METHODS ====================

    @api.model
    def search_customers(self, query, filters=None, limit=10):
        """Tìm kiếm khách hàng"""
        try:
            KhachHang = self.env['khach_hang'].sudo()
            fields_map = KhachHang._fields
            
            domain = []
            if query:
                or_parts = []
                # Check available fields for search
                if 'ten_khach_hang' in fields_map:
                    or_parts.append(('ten_khach_hang', 'ilike', query))
                if 'name' in fields_map:
                    or_parts.append(('name', 'ilike', query))
                if 'email' in fields_map:
                    or_parts.append(('email', 'ilike', query))
                if 'so_dien_thoai' in fields_map:
                    or_parts.append(('so_dien_thoai', 'ilike', query))
                if 'dien_thoai' in fields_map:
                    or_parts.append(('dien_thoai', 'ilike', query))
                if 'cong_ty' in fields_map:
                    or_parts.append(('cong_ty', 'ilike', query))
                
                if or_parts:
                    domain = ['|'] * (len(or_parts) - 1) + or_parts
            
            if filters:
                if filters.get('phan_loai') and 'phan_loai' in fields_map:
                    domain.append(('phan_loai', '=', filters['phan_loai']))
                if filters.get('loai_khach_hang') and 'loai_khach_hang' in fields_map:
                    domain.append(('loai_khach_hang', '=', filters['loai_khach_hang']))
                if filters.get('trang_thai'):
                    domain.append(('trang_thai', '=', filters['trang_thai']))
            
            customers = KhachHang.search(domain, limit=limit)
            
            result = []
            for c in customers:
                phone = c.so_dien_thoai if hasattr(c, 'so_dien_thoai') and c.so_dien_thoai else (c.dien_thoai if hasattr(c, 'dien_thoai') else None)
                result.append({
                    'id': c.id,
                    'name': c.display_name,
                    'email': c.email if hasattr(c, 'email') else None,
                    'dien_thoai': phone,
                })
            return result
            
        except Exception as e:
            _logger.warning(f"Error searching customers: {e}")
            return []

    @api.model
    def get_customer_brief(self, customer_id):
        """Lấy tóm tắt 360° khách hàng"""
        context = self._get_customer_context(customer_id)
        if not context:
            return {'error': 'Không tìm thấy khách hàng'}
        
        return {
            'success': True,
            'brief': context,
        }

    @api.model
    def get_customer_interactions(self, customer_id, days=30):
        """Lấy lịch sử tương tác gần đây"""
        try:
            from datetime import datetime, timedelta
            
            customer = self.env['khach_hang'].browse(customer_id)
            if not customer.exists():
                return {'error': 'Không tìm thấy khách hàng'}
            
            since = datetime.now() - timedelta(days=days)
            interactions = []
            
            # Orders
            if hasattr(customer, 'don_hang_ids'):
                for order in customer.don_hang_ids.filtered(lambda o: o.create_date >= since):
                    interactions.append({
                        'type': 'order',
                        'date': order.create_date.strftime('%d/%m/%Y'),
                        'summary': f"Đơn hàng {order.display_name}",
                    })
            
            # Support tickets
            if hasattr(customer, 'ho_tro_ids'):
                for ticket in customer.ho_tro_ids.filtered(lambda t: t.create_date >= since):
                    interactions.append({
                        'type': 'support',
                        'date': ticket.create_date.strftime('%d/%m/%Y'),
                        'summary': f"Hỗ trợ: {ticket.display_name}",
                    })
            
            # Sort by date
            interactions.sort(key=lambda x: x['date'], reverse=True)
            
            return {
                'success': True,
                'customer': customer.display_name,
                'period_days': days,
                'interactions': interactions[:20],
            }
            
        except Exception as e:
            return {'error': str(e)}

    @api.model
    def get_customer_risk_analysis(self, customer_id):
        """Phân tích rủi ro khách hàng"""
        try:
            customer = self.env['khach_hang'].browse(customer_id)
            if not customer.exists():
                return {'error': 'Không tìm thấy khách hàng'}
            
            risks = []
            recommendations = []
            
            # Check open support tickets
            if hasattr(customer, 'ho_tro_ids'):
                open_tickets = customer.ho_tro_ids.filtered(
                    lambda t: t.trang_thai not in ['done', 'cancel'] if hasattr(t, 'trang_thai') else True
                )
                if len(open_tickets) > 2:
                    risks.append(f"Có {len(open_tickets)} phiếu hỗ trợ chưa xử lý")
                    recommendations.append("Ưu tiên giải quyết các vấn đề tồn đọng")
            
            # Check recent orders
            if hasattr(customer, 'don_hang_ids'):
                from datetime import datetime, timedelta
                recent_orders = customer.don_hang_ids.filtered(
                    lambda o: o.create_date >= datetime.now() - timedelta(days=90)
                )
                if not recent_orders:
                    risks.append("Không có đơn hàng trong 90 ngày qua")
                    recommendations.append("Gửi email khuyến mãi hoặc khảo sát")
            
            return {
                'success': True,
                'customer': customer.display_name,
                'risks': risks,
                'recommendations': recommendations,
                'risk_level': 'high' if len(risks) > 1 else ('medium' if risks else 'low'),
            }
            
        except Exception as e:
            return {'error': str(e)}
