# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import logging

_logger = logging.getLogger(__name__)


class DashboardKhachHang(models.Model):
    _name = 'dashboard.khach_hang'
    _description = 'Dashboard Khách Hàng'

    name = fields.Char('Dashboard Name', default='Customer Dashboard', readonly=True)
    
    # ============ KPI CARDS ============
    
    # Tổng số khách hàng
    total_customers = fields.Integer('Tổng khách hàng', compute='_compute_customer_kpis')
    new_customers = fields.Integer('Khách hàng mới', compute='_compute_customer_kpis')
    active_customers = fields.Integer('Đang hoạt động', compute='_compute_customer_kpis')
    potential_customers = fields.Integer('Tiềm năng', compute='_compute_customer_kpis')
    inactive_customers = fields.Integer('Dừng hoạt động', compute='_compute_customer_kpis')
    
    # Doanh thu
    total_revenue = fields.Monetary('Tổng doanh thu', compute='_compute_revenue_kpis', currency_field='currency_id')
    monthly_revenue = fields.Monetary('Doanh thu tháng', compute='_compute_revenue_kpis', currency_field='currency_id')
    quarterly_revenue = fields.Monetary('Doanh thu quý', compute='_compute_revenue_kpis', currency_field='currency_id')
    yearly_revenue = fields.Monetary('Doanh thu năm', compute='_compute_revenue_kpis', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    
    # Đơn hàng
    total_orders = fields.Integer('Tổng đơn hàng', compute='_compute_order_kpis')
    new_orders = fields.Integer('Đơn mới', compute='_compute_order_kpis')
    processing_orders = fields.Integer('Đang xử lý', compute='_compute_order_kpis')
    completed_orders = fields.Integer('Hoàn thành', compute='_compute_order_kpis')
    cancelled_orders = fields.Integer('Đã hủy', compute='_compute_order_kpis')
    
    # Tỷ lệ & Metrics
    conversion_rate = fields.Float('Tỷ lệ chuyển đổi (%)', compute='_compute_conversion_metrics')
    average_order_value = fields.Monetary('Giá trị đơn TB', compute='_compute_conversion_metrics', currency_field='currency_id')
    customer_lifetime_value = fields.Monetary('CLV', compute='_compute_conversion_metrics', currency_field='currency_id')
    retention_rate = fields.Float('Tỷ lệ giữ chân (%)', compute='_compute_conversion_metrics')
    
    # Hỗ trợ
    total_tickets = fields.Integer('Tổng tickets', compute='_compute_support_kpis')
    open_tickets = fields.Integer('Tickets mở', compute='_compute_support_kpis')
    avg_response_time = fields.Float('TG phản hồi TB (giờ)', compute='_compute_support_kpis')
    satisfaction_score = fields.Float('CSAT Score', compute='_compute_support_kpis')
    
    # Data for charts
    revenue_trend_data = fields.Text('Revenue Trend Data', compute='_compute_chart_data')
    top_customers_data = fields.Text('Top Customers Data', compute='_compute_chart_data')
    customer_segment_data = fields.Text('Customer Segment Data', compute='_compute_chart_data')
    
    # Color-coded status fields
    revenue_status = fields.Selection([
        ('excellent', 'Xuất sắc'),
        ('good', 'Tốt'),
        ('warning', 'Cảnh báo'),
        ('danger', 'Nguy hiểm'),
        ('neutral', 'Trung bình')
    ], string='Trạng thái Doanh thu', compute='_compute_status_indicators')
    
    customer_growth_status = fields.Selection([
        ('excellent', 'Xuất sắc'),
        ('good', 'Tốt'),
        ('warning', 'Cảnh báo'),
        ('danger', 'Nguy hiểm'),
        ('neutral', 'Trung bình')
    ], string='Trạng thái Tăng trưởng KH', compute='_compute_status_indicators')
    
    order_status_indicator = fields.Selection([
        ('excellent', 'Xuất sắc'),
        ('good', 'Tốt'),
        ('warning', 'Cảnh báo'),
        ('danger', 'Nguy hiểm'),
        ('neutral', 'Trung bình')
    ], string='Trạng thái Đơn hàng', compute='_compute_status_indicators')
    
    support_status = fields.Selection([
        ('excellent', 'Xuất sắc'),
        ('good', 'Tốt'),
        ('warning', 'Cảnh báo'),
        ('danger', 'Nguy hiểm'),
        ('neutral', 'Trung bình')
    ], string='Trạng thái Hỗ trợ', compute='_compute_status_indicators')
    
    # Alert fields
    has_open_tickets_alert = fields.Boolean('Cảnh báo Tickets', compute='_compute_alerts')
    has_overdue_orders_alert = fields.Boolean('Cảnh báo Đơn quá hạn', compute='_compute_alerts')
    has_low_satisfaction_alert = fields.Boolean('Cảnh báo CSAT thấp', compute='_compute_alerts')
    overdue_orders_count = fields.Integer('Số đơn quá hạn', compute='_compute_alerts')
    
    # Revenue goal tracking
    revenue_goal = fields.Monetary('Mục tiêu doanh thu tháng', default=100000000, currency_field='currency_id')
    revenue_achievement = fields.Float('Đạt được (%)', compute='_compute_revenue_achievement')
    
    # Previous period comparison
    revenue_growth_rate = fields.Float('Tốc độ tăng trưởng DT (%)', compute='_compute_growth_rates')
    customer_growth_rate = fields.Float('Tốc độ tăng trưởng KH (%)', compute='_compute_growth_rates')
    order_growth_rate = fields.Float('Tốc độ tăng trưởng ĐH (%)', compute='_compute_growth_rates')
    
    @api.depends('total_customers')
    def _compute_customer_kpis(self):
        """Tính toán KPIs về khách hàng"""
        for record in self:
            KhachHang = self.env['khach_hang']
            
            # Tổng số khách hàng
            record.total_customers = KhachHang.search_count([])
            
            # Khách hàng mới (trong 30 ngày)
            thirty_days_ago = fields.Datetime.now() - timedelta(days=30)
            record.new_customers = KhachHang.search_count([
                ('ngay_tao', '>=', thirty_days_ago)
            ])
            
            # Đang hoạt động (có đơn hàng trong 60 ngày)
            sixty_days_ago = fields.Date.today() - timedelta(days=60)
            active_customer_ids = self.env['don_hang'].search([
                ('ngay_dat_hang', '>=', sixty_days_ago),
                ('trang_thai', '!=', 'huy')
            ]).mapped('khach_hang_id').ids
            record.active_customers = len(set(active_customer_ids))
            
            # Tiềm năng cao
            record.potential_customers = KhachHang.search_count([
                ('phan_loai', '=', 'tiem_nang_cao')
            ])
            
            # Không hoạt động (không có đơn >60 ngày)
            record.inactive_customers = record.total_customers - record.active_customers
    
    @api.depends('monthly_revenue')
    def _compute_revenue_kpis(self):
        """Tính toán KPIs về doanh thu"""
        for record in self:
            DonHang = self.env['don_hang']
            
            # Tổng doanh thu (tất cả đơn hoàn thành)
            completed_orders = DonHang.search([
                ('trang_thai', '=', 'hoan_thanh')
            ])
            record.total_revenue = sum(completed_orders.mapped('tong_tien'))
            
            # Doanh thu tháng này
            first_day_month = fields.Date.today().replace(day=1)
            monthly_orders = DonHang.search([
                ('ngay_dat_hang', '>=', first_day_month),
                ('trang_thai', '=', 'hoan_thanh')
            ])
            record.monthly_revenue = sum(monthly_orders.mapped('tong_tien'))
            
            # Doanh thu quý này
            current_quarter_start = self._get_quarter_start_date()
            quarterly_orders = DonHang.search([
                ('ngay_dat_hang', '>=', current_quarter_start),
                ('trang_thai', '=', 'hoan_thanh')
            ])
            record.quarterly_revenue = sum(quarterly_orders.mapped('tong_tien'))
            
            # Doanh thu năm nay
            first_day_year = fields.Date.today().replace(month=1, day=1)
            yearly_orders = DonHang.search([
                ('ngay_dat_hang', '>=', first_day_year),
                ('trang_thai', '=', 'hoan_thanh')
            ])
            record.yearly_revenue = sum(yearly_orders.mapped('tong_tien'))
    
    @api.depends('total_orders')
    def _compute_order_kpis(self):
        """Tính toán KPIs về đơn hàng"""
        for record in self:
            DonHang = self.env['don_hang']
            
            record.total_orders = DonHang.search_count([])
            record.new_orders = DonHang.search_count([('trang_thai', '=', 'moi')])
            record.processing_orders = DonHang.search_count([
                ('trang_thai', 'in', ['dang_xu_ly', 'dang_giao'])
            ])
            record.completed_orders = DonHang.search_count([('trang_thai', '=', 'hoan_thanh')])
            record.cancelled_orders = DonHang.search_count([('trang_thai', '=', 'huy')])
    
    @api.depends('conversion_rate')
    def _compute_conversion_metrics(self):
        """Tính toán các chỉ số chuyển đổi"""
        for record in self:
            KhachHang = self.env['khach_hang']
            DonHang = self.env['don_hang']
            
            # Tỷ lệ chuyển đổi (khách có đơn / tổng khách)
            total_customers = KhachHang.search_count([])
            customers_with_orders = len(DonHang.search([]).mapped('khach_hang_id'))
            
            if total_customers > 0:
                record.conversion_rate = (customers_with_orders / total_customers) * 100
            else:
                record.conversion_rate = 0.0
            
            # Giá trị đơn hàng trung bình (AOV)
            completed_orders = DonHang.search([('trang_thai', '=', 'hoan_thanh')])
            if len(completed_orders) > 0:
                record.average_order_value = sum(completed_orders.mapped('tong_tien')) / len(completed_orders)
            else:
                record.average_order_value = 0.0
            
            # Customer Lifetime Value (CLV) - trung bình doanh thu mỗi khách hàng
            if customers_with_orders > 0:
                record.customer_lifetime_value = sum(completed_orders.mapped('tong_tien')) / customers_with_orders
            else:
                record.customer_lifetime_value = 0.0
            
            # Retention Rate (% khách hàng mua lại trong 90 ngày)
            ninety_days_ago = fields.Date.today() - timedelta(days=90)
            repeat_customers = self.env['don_hang'].search([
                ('ngay_dat_hang', '>=', ninety_days_ago)
            ]).mapped('khach_hang_id').filtered(lambda c: c.so_lan_mua_hang > 1)
            
            if total_customers > 0:
                record.retention_rate = (len(repeat_customers) / total_customers) * 100
            else:
                record.retention_rate = 0.0
    
    @api.depends('total_tickets')
    def _compute_support_kpis(self):
        """Tính toán KPIs về hỗ trợ khách hàng"""
        for record in self:
            HoTro = self.env['ho_tro_khach_hang']
            
            record.total_tickets = HoTro.search_count([])
            record.open_tickets = HoTro.search_count([
                ('trang_thai', 'in', ['moi', 'dang_xu_ly'])
            ])
            
            # Thời gian phản hồi trung bình
            completed_tickets = HoTro.search([
                ('trang_thai', '=', 'hoan_thanh'),
                ('ngay_hoan_thanh', '!=', False)
            ])
            
            if completed_tickets:
                total_hours = 0
                for ticket in completed_tickets:
                    if ticket.ngay_tao and ticket.ngay_hoan_thanh:
                        delta = ticket.ngay_hoan_thanh - ticket.ngay_tao
                        total_hours += delta.total_seconds() / 3600
                record.avg_response_time = total_hours / len(completed_tickets)
            else:
                record.avg_response_time = 0.0
            
            # CSAT Score (từ đánh giá)
            rated_tickets = HoTro.search([('danh_gia', '!=', False)])
            if rated_tickets:
                total_rating = sum(int(t.danh_gia) for t in rated_tickets)
                record.satisfaction_score = (total_rating / len(rated_tickets) / 5) * 100
            else:
                record.satisfaction_score = 0.0
    
    @api.depends('revenue_trend_data')
    def _compute_chart_data(self):
        """Tính toán dữ liệu cho các biểu đồ"""
        for record in self:
            import json
            
            # Revenue Trend Data (12 tháng gần nhất)
            revenue_by_month = []
            for i in range(11, -1, -1):
                month_start = (fields.Date.today() - relativedelta(months=i)).replace(day=1)
                if i == 0:
                    month_end = fields.Date.today()
                else:
                    month_end = (month_start + relativedelta(months=1)) - timedelta(days=1)
                
                monthly_revenue = sum(self.env['don_hang'].search([
                    ('ngay_dat_hang', '>=', month_start),
                    ('ngay_dat_hang', '<=', month_end),
                    ('trang_thai', '=', 'hoan_thanh')
                ]).mapped('tong_tien'))
                
                revenue_by_month.append({
                    'month': month_start.strftime('%Y-%m'),
                    'revenue': float(monthly_revenue)
                })
            
            record.revenue_trend_data = json.dumps(revenue_by_month)
            
            # Top 10 Customers by Revenue
            customers = self.env['khach_hang'].search([])
            customer_revenues = []
            for customer in customers:
                total_revenue = sum(customer.don_hang_ids.filtered(
                    lambda o: o.trang_thai == 'hoan_thanh'
                ).mapped('tong_tien'))
                if total_revenue > 0:
                    customer_revenues.append({
                        'name': customer.ten_khach_hang,
                        'revenue': float(total_revenue)
                    })
            
            # Sort and get top 10
            customer_revenues.sort(key=lambda x: x['revenue'], reverse=True)
            record.top_customers_data = json.dumps(customer_revenues[:10])
            
            # Customer Segmentation Data
            segment_data = [
                {'segment': 'Mới', 'count': record.new_customers},
                {'segment': 'Đang hoạt động', 'count': record.active_customers},
                {'segment': 'Tiềm năng', 'count': record.potential_customers},
                {'segment': 'Không hoạt động', 'count': record.inactive_customers}
            ]
            record.customer_segment_data = json.dumps(segment_data)
    
    def _get_quarter_start_date(self):
        """Lấy ngày bắt đầu quý hiện tại"""
        today = fields.Date.today()
        quarter_month = ((today.month - 1) // 3) * 3 + 1
        return today.replace(month=quarter_month, day=1)
    
    @api.depends('revenue_achievement', 'new_customers', 'processing_orders', 'open_tickets')
    def _compute_status_indicators(self):
        """Tính toán các chỉ báo màu sắc theo performance"""
        for record in self:
            # Revenue Status
            if record.revenue_achievement >= 100:
                record.revenue_status = 'excellent'
            elif record.revenue_achievement >= 80:
                record.revenue_status = 'good'
            elif record.revenue_achievement >= 50:
                record.revenue_status = 'warning'
            elif record.revenue_achievement > 0:
                record.revenue_status = 'danger'
            else:
                record.revenue_status = 'neutral'
            
            # Customer Growth Status
            if record.customer_growth_rate >= 10:
                record.customer_growth_status = 'excellent'
            elif record.customer_growth_rate >= 5:
                record.customer_growth_status = 'good'
            elif record.customer_growth_rate >= 0:
                record.customer_growth_status = 'warning'
            else:
                record.customer_growth_status = 'danger'
            
            # Order Status
            completion_rate = (record.completed_orders / record.total_orders * 100) if record.total_orders > 0 else 0
            if completion_rate >= 80:
                record.order_status_indicator = 'excellent'
            elif completion_rate >= 60:
                record.order_status_indicator = 'good'
            elif completion_rate >= 40:
                record.order_status_indicator = 'warning'
            else:
                record.order_status_indicator = 'danger'
            
            # Support Status
            if record.satisfaction_score >= 80 and record.open_tickets < 10:
                record.support_status = 'excellent'
            elif record.satisfaction_score >= 60 and record.open_tickets < 20:
                record.support_status = 'good'
            elif record.satisfaction_score >= 40 or record.open_tickets < 50:
                record.support_status = 'warning'
            else:
                record.support_status = 'danger'
    
    @api.depends('open_tickets', 'satisfaction_score')
    def _compute_alerts(self):
        """Tính toán các cảnh báo"""
        for record in self:
            record.has_open_tickets_alert = record.open_tickets >= 10
            record.has_low_satisfaction_alert = record.satisfaction_score < 60
            
            # Đơn hàng quá hạn (đang xử lý quá 7 ngày)
            seven_days_ago = fields.Date.today() - timedelta(days=7)
            record.overdue_orders_count = self.env['don_hang'].search_count([
                ('trang_thai', 'in', ['moi', 'dang_xu_ly']),
                ('ngay_dat_hang', '<=', seven_days_ago)
            ])
            record.has_overdue_orders_alert = record.overdue_orders_count > 0
    
    @api.depends('monthly_revenue', 'revenue_goal')
    def _compute_revenue_achievement(self):
        """Tính % đạt mục tiêu doanh thu"""
        for record in self:
            if record.revenue_goal > 0:
                record.revenue_achievement = (record.monthly_revenue / record.revenue_goal) * 100
            else:
                record.revenue_achievement = 0.0
    
    @api.depends('monthly_revenue', 'new_customers', 'total_orders')
    def _compute_growth_rates(self):
        """Tính tốc độ tăng trưởng so với tháng trước"""
        for record in self:
            DonHang = self.env['don_hang']
            KhachHang = self.env['khach_hang']
            
            # Tháng trước
            last_month_start = (fields.Date.today() - relativedelta(months=1)).replace(day=1)
            last_month_end = fields.Date.today().replace(day=1) - timedelta(days=1)
            
            # Doanh thu tháng trước
            last_month_revenue = sum(DonHang.search([
                ('ngay_dat_hang', '>=', last_month_start),
                ('ngay_dat_hang', '<=', last_month_end),
                ('trang_thai', '=', 'hoan_thanh')
            ]).mapped('tong_tien'))
            
            if last_month_revenue > 0:
                record.revenue_growth_rate = ((record.monthly_revenue - last_month_revenue) / last_month_revenue) * 100
            else:
                record.revenue_growth_rate = 0.0
            
            # Khách hàng tháng trước
            last_month_customers = KhachHang.search_count([
                ('ngay_tao', '>=', last_month_start),
                ('ngay_tao', '<=', last_month_end)
            ])
            
            if last_month_customers > 0:
                record.customer_growth_rate = ((record.new_customers - last_month_customers) / last_month_customers) * 100
            else:
                record.customer_growth_rate = 0.0 if record.new_customers == 0 else 100.0
            
            # Đơn hàng tháng trước
            last_month_orders = DonHang.search_count([
                ('ngay_dat_hang', '>=', last_month_start),
                ('ngay_dat_hang', '<=', last_month_end)
            ])
            
            this_month_orders = DonHang.search_count([
                ('ngay_dat_hang', '>=', fields.Date.today().replace(day=1))
            ])
            
            if last_month_orders > 0:
                record.order_growth_rate = ((this_month_orders - last_month_orders) / last_month_orders) * 100
            else:
                record.order_growth_rate = 0.0 if this_month_orders == 0 else 100.0
    
    @api.model
    def get_dashboard_data(self):
        """API để lấy tất cả dữ liệu dashboard"""
        dashboard = self.search([], limit=1)
        if not dashboard:
            dashboard = self.create({'name': 'Customer Dashboard'})
        
        return {
            'kpis': {
                'customers': {
                    'total': dashboard.total_customers,
                    'new': dashboard.new_customers,
                    'active': dashboard.active_customers,
                    'potential': dashboard.potential_customers,
                    'inactive': dashboard.inactive_customers,
                },
                'revenue': {
                    'total': dashboard.total_revenue,
                    'monthly': dashboard.monthly_revenue,
                    'quarterly': dashboard.quarterly_revenue,
                    'yearly': dashboard.yearly_revenue,
                },
                'orders': {
                    'total': dashboard.total_orders,
                    'new': dashboard.new_orders,
                    'processing': dashboard.processing_orders,
                    'completed': dashboard.completed_orders,
                    'cancelled': dashboard.cancelled_orders,
                },
                'metrics': {
                    'conversion_rate': dashboard.conversion_rate,
                    'aov': dashboard.average_order_value,
                    'clv': dashboard.customer_lifetime_value,
                    'retention': dashboard.retention_rate,
                },
                'support': {
                    'total_tickets': dashboard.total_tickets,
                    'open_tickets': dashboard.open_tickets,
                    'avg_response_time': dashboard.avg_response_time,
                    'csat': dashboard.satisfaction_score,
                }
            },
            'charts': {
                'revenue_trend': dashboard.revenue_trend_data,
                'top_customers': dashboard.top_customers_data,
                'segments': dashboard.customer_segment_data,
            }
        }

    def action_view_revenue_chart(self):
        """Mở biểu đồ xu hướng doanh thu"""
        return {
            'name': '📈 Xu Hướng Doanh Thu',
            'type': 'ir.actions.act_window',
            'res_model': 'don_hang',
            'view_mode': 'graph,pivot,tree',
            'views': [(self.env.ref('khach_hang.view_don_hang_revenue_trend_graph').id, 'graph'),
                      (False, 'pivot'),
                      (False, 'tree')],
            'domain': [('trang_thai', '=', 'hoan_thanh')],
            'context': {'search_default_this_year': 1},
            'target': 'current',
        }
    
    def action_view_orders_chart(self):
        """Mở biểu đồ phân tích đơn hàng"""
        return {
            'name': '📊 Phân Tích Đơn Hàng',
            'type': 'ir.actions.act_window',
            'res_model': 'don_hang',
            'view_mode': 'graph,pivot,tree',
            'views': [(self.env.ref('khach_hang.view_don_hang_by_status_graph').id, 'graph'),
                      (False, 'pivot'),
                      (False, 'tree')],
            'target': 'current',
        }
    
    def action_view_customers_chart(self):
        """Mở biểu đồ phân khúc khách hàng"""
        return {
            'name': '🎯 Phân Khúc Khách Hàng',
            'type': 'ir.actions.act_window',
            'res_model': 'khach_hang',
            'view_mode': 'graph,kanban,tree,form',
            'views': [(self.env.ref('khach_hang.view_khach_hang_rfm_graph').id, 'graph'),
                      (False, 'kanban'),
                      (False, 'tree'),
                      (False, 'form')],
            'target': 'current',
        }
    
    def action_view_top_customers(self):
        """Mở bảng pivot top khách hàng"""
        return {
            'name': '💰 Top Khách Hàng',
            'type': 'ir.actions.act_window',
            'res_model': 'don_hang',
            'view_mode': 'pivot,graph,tree',
            'views': [(self.env.ref('khach_hang.view_don_hang_by_customer_pivot').id, 'pivot'),
                      (False, 'graph'),
                      (False, 'tree')],
            'domain': [('trang_thai', '=', 'hoan_thanh')],
            'target': 'current',
        }
    
    # ============ INTERACTIVE TILE ACTIONS ============
    
    def action_view_all_customers(self):
        """Xem tất cả khách hàng"""
        return {
            'name': '👥 Tất cả Khách hàng',
            'type': 'ir.actions.act_window',
            'res_model': 'khach_hang',
            'view_mode': 'kanban,tree,form',
            'target': 'current',
        }
    
    def action_view_new_customers(self):
        """Xem khách hàng mới"""
        thirty_days_ago = fields.Datetime.now() - timedelta(days=30)
        return {
            'name': '👥 Khách hàng mới (30 ngày)',
            'type': 'ir.actions.act_window',
            'res_model': 'khach_hang',
            'view_mode': 'kanban,tree,form',
            'domain': [('ngay_tao', '>=', thirty_days_ago)],
            'target': 'current',
        }
    
    def action_view_all_orders(self):
        """Xem tất cả đơn hàng"""
        return {
            'name': '📦 Tất cả Đơn hàng',
            'type': 'ir.actions.act_window',
            'res_model': 'don_hang',
            'view_mode': 'kanban,tree,form',
            'target': 'current',
        }
    
    def action_view_processing_orders(self):
        """Xem đơn hàng đang xử lý"""
        return {
            'name': '📦 Đơn hàng đang xử lý',
            'type': 'ir.actions.act_window',
            'res_model': 'don_hang',
            'view_mode': 'kanban,tree,form',
            'domain': [('trang_thai', 'in', ['dang_xu_ly', 'dang_giao'])],
            'target': 'current',
        }
    
    def action_view_completed_orders(self):
        """Xem đơn hàng hoàn thành"""
        return {
            'name': '📦 Đơn hàng hoàn thành',
            'type': 'ir.actions.act_window',
            'res_model': 'don_hang',
            'view_mode': 'tree,form',
            'domain': [('trang_thai', '=', 'hoan_thanh')],
            'target': 'current',
        }
    
    def action_view_open_tickets(self):
        """Xem tickets đang mở"""
        return {
            'name': '🎫 Tickets đang mở',
            'type': 'ir.actions.act_window',
            'res_model': 'ho_tro_khach_hang',
            'view_mode': 'kanban,tree,form',
            'domain': [('trang_thai', 'in', ['moi', 'dang_xu_ly'])],
            'target': 'current',
        }
    
    def action_view_overdue_orders(self):
        """Xem đơn hàng quá hạn"""
        seven_days_ago = fields.Date.today() - timedelta(days=7)
        return {
            'name': '🚨 Đơn hàng quá hạn',
            'type': 'ir.actions.act_window',
            'res_model': 'don_hang',
            'view_mode': 'tree,form',
            'domain': [
                ('trang_thai', 'in', ['moi', 'dang_xu_ly']),
                ('ngay_dat_hang', '<=', seven_days_ago)
            ],
            'target': 'current',
        }
    
    # ============ QUICK ACTIONS ============
    
    def action_create_customer(self):
        """Tạo khách hàng mới"""
        return {
            'name': '➕ Tạo Khách hàng mới',
            'type': 'ir.actions.act_window',
            'res_model': 'khach_hang',
            'view_mode': 'form',
            'target': 'new',
        }
    
    def action_create_order(self):
        """Tạo đơn hàng mới"""
        return {
            'name': '🛒 Tạo Đơn hàng mới',
            'type': 'ir.actions.act_window',
            'res_model': 'don_hang',
            'view_mode': 'form',
            'target': 'new',
        }
    
    def action_create_ticket(self):
        """Tạo ticket hỗ trợ mới"""
        return {
            'name': '🎫 Tạo Ticket hỗ trợ',
            'type': 'ir.actions.act_window',
            'res_model': 'ho_tro_khach_hang',
            'view_mode': 'form',
            'target': 'new',
        }
