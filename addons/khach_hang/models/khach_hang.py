# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

try:
    import pandas as pd
    import numpy as np
    from sklearn.linear_model import LinearRegression
    from sklearn.cluster import KMeans
    import stripe
    import paypalrestsdk
except ImportError as e:
    _logger.warning("Missing libraries for advanced features: %s", e)


class KhachHang(models.Model):
    _name = 'khach_hang'
    _description = 'Khách hàng'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'ngay_tao desc'

    # Thông tin cơ bản
    ten_khach_hang = fields.Char('Tên khách hàng', required=True, tracking=True)
    so_dien_thoai = fields.Char('Số điện thoại', tracking=True)
    email = fields.Char('Email', tracking=True)
    cong_ty = fields.Char('Công ty')
    dia_chi = fields.Text('Địa chỉ')
    
    # Phân loại
    phan_loai = fields.Selection([
        ('tiem_nang_cao', 'Tiềm năng cao'),
        ('tiem_nang_thap', 'Tiềm năng thấp')
    ], string='Phân loại khách hàng', default='tiem_nang_thap', tracking=True)
    
    # Màu sắc cho Kanban view
    mau_sac = fields.Integer('Màu sắc', compute='_compute_mau_sac', store=True)
    
    trang_thai = fields.Selection([
        ('moi', 'Mới'),
        ('dang_giao_dich', 'Đang giao dịch'),
        ('cu', 'Cũ')
    ], string='Trạng thái', default='moi', required=True, tracking=True)
    
    # Thống kê
    so_lan_mua_hang = fields.Integer('Số lần mua hàng', compute='_compute_thong_ke', store=True)
    ngay_tao = fields.Datetime('Ngày tạo hồ sơ', default=fields.Datetime.now, readonly=True)
    tong_chi_tieu = fields.Monetary('Tổng tiền đã chi tiêu', compute='_compute_tong_chi_tieu', 
                                     store=True, currency_field='currency_id')
    
    # Smart Button Counts
    don_hang_count = fields.Integer('Số đơn hàng', compute='_compute_smart_button_counts')
    ho_tro_count = fields.Integer('Số tickets', compute='_compute_smart_button_counts')
    email_count = fields.Integer('Số email', compute='_compute_smart_button_counts')
    
    # RFM Analysis
    rfm_recency = fields.Integer('Recency (days)', compute='_compute_rfm_score', store=True,
                                  help='Số ngày kể từ lần mua hàng cuối')
    rfm_frequency = fields.Integer('Frequency', compute='_compute_rfm_score', store=True,
                                    help='Số lần mua hàng')
    rfm_monetary = fields.Monetary('Monetary Value', compute='_compute_rfm_score', store=True,
                                    currency_field='currency_id', help='Tổng giá trị đã mua')
    rfm_segment = fields.Selection([
        ('vip', 'VIP'),
        ('loyal', 'Loyal'),
        ('at_risk', 'At Risk'),
        ('lost', 'Lost'),
        ('new', 'New')
    ], string='RFM Segment', compute='_compute_rfm_score', store=True)
    
    # AI Insights
    churn_probability = fields.Float('Churn Risk (%)', compute='_compute_ai_insights',
                                      help='Xác suất khách hàng rời đi')
    purchase_probability = fields.Float('Purchase Probability (%)', compute='_compute_ai_insights',
                                         help='Xác suất mua hàng trong 30 ngày tới')
    sentiment_score = fields.Float('Sentiment Score', compute='_compute_sentiment_analysis',
                                    help='Điểm cảm xúc từ email và hỗ trợ (-1 đến 1)')
    next_best_action = fields.Text('Next Best Action', compute='_compute_ai_insights',
                                    help='Hành động đề xuất tiếp theo')
    
    # Nhân viên phụ trách
    nhan_vien_phu_trach_id = fields.Many2one('nhan_vien', string='Nhân viên phụ trách',
                                               tracking=True,
                                               help='Nhân viên được phân công chăm sóc khách hàng này')
    
    # Quan hệ
    don_hang_ids = fields.One2many('don_hang', 'khach_hang_id', string='Đơn hàng')
    ho_tro_ids = fields.One2many('ho_tro_khach_hang', 'khach_hang_id', string='Yêu cầu hỗ trợ')
    email_ids = fields.Many2many('email_khach_hang', string='Email đã nhận')
    
    # Engagement tracking
    last_activity_date = fields.Date('Last Activity', compute='_compute_last_activity')
    days_since_last_activity = fields.Integer('Days Since Last Activity', 
                                                compute='_compute_last_activity')
    
    # Dự đoán sản phẩm bằng AI
    san_pham_du_doan_ids = fields.Many2many('san_pham', string='Sản phẩm dự đoán', compute='_compute_du_doan_san_pham', store=True)
    
    # Tiền tệ
    currency_id = fields.Many2one('res.currency', string='Đơn vị tiền tệ',
                                   default=lambda self: self.env.company.currency_id)
    
    # === SYSTEM INTEGRATION - SYNC TỪ NHÂN SỰ ===
    # Computed fields để đồng bộ thông tin từ module nhan_su
    ten_nhan_vien_phu_trach = fields.Char('Tên NV phụ trách', compute='_compute_sync_nhan_su', store=True, tracking=True)
    email_nhan_vien_phu_trach = fields.Char('Email NV phụ trách', compute='_compute_sync_nhan_su', store=True)
    phong_ban_nhan_vien_phu_trach = fields.Char('Phòng ban NV phụ trách', compute='_compute_sync_nhan_su', store=True)
    
    _sql_constraints = [
        ('email_unique', 'unique(email)', 'Email khách hàng đã tồn tại!'),
    ]
    
    @api.depends('don_hang_ids')
    def _compute_thong_ke(self):
        """Tính thống kê mua hàng"""
        for record in self:
            record.so_lan_mua_hang = len(record.don_hang_ids)
    
    @api.depends('don_hang_ids', 'don_hang_ids.thanh_tien')
    def _compute_tong_chi_tieu(self):
        """Tính tổng tiền khách hàng đã chi tiêu"""
        for record in self:
            record.tong_chi_tieu = sum(record.don_hang_ids.mapped('thanh_tien'))
    
    @api.depends('phan_loai')
    def _compute_mau_sac(self):
        """Màu sắc cho kanban"""
        for record in self:
            if record.phan_loai == 'tiem_nang_cao':
                record.mau_sac = 3  # Xanh lá
            else:
                record.mau_sac = 0  # Mặc định
    
    @api.depends('don_hang_ids.line_ids.san_pham_id')
    def _compute_du_doan_san_pham(self):
        """Dự đoán sản phẩm dựa trên lịch sử mua hàng sử dụng Machine Learning"""
        for record in self:
            try:
                if not record.don_hang_ids:
                    record.san_pham_du_doan_ids = False
                    continue
                
                # Thu thập dữ liệu lịch sử mua hàng
                product_counts = {}
                for order in record.don_hang_ids:
                    for line in order.line_ids:
                        product_id = line.san_pham_id.id
                        if product_id:
                            product_counts[product_id] = product_counts.get(product_id, 0) + line.so_luong
                
                if not product_counts:
                    record.san_pham_du_doan_ids = False
                    continue
                
                # Chuyển thành DataFrame
                df = pd.DataFrame(list(product_counts.items()), columns=['product_id', 'quantity'])
                
                # Sử dụng KMeans để cluster sản phẩm dựa trên tần suất mua
                if len(df) > 1:
                    kmeans = KMeans(n_clusters=min(3, len(df)), random_state=42)
                    df['cluster'] = kmeans.fit_predict(df[['quantity']])
                    
                    # Dự đoán sản phẩm từ cluster có tần suất cao nhất
                    top_cluster = df.groupby('cluster')['quantity'].sum().idxmax()
                    predicted_products = df[df['cluster'] == top_cluster]['product_id'].tolist()
                else:
                    predicted_products = df['product_id'].tolist()
                
                record.san_pham_du_doan_ids = [(6, 0, predicted_products)]
                
            except Exception as e:
                _logger.warning("Error in ML prediction: %s", e)
                # Fallback to simple method
                last_orders = record.don_hang_ids.sorted('ngay_dat_hang', reverse=True)[:3]
                san_pham_ids = last_orders.mapped('line_ids.san_pham_id').ids
                record.san_pham_du_doan_ids = [(6, 0, list(set(san_pham_ids)))]
    
    @api.model
    def _cron_du_doan_san_pham(self):
        """Cron job cập nhật dự đoán sản phẩm cho khách hàng"""
        self.search([])._compute_du_doan_san_pham()
    
    # === SYSTEM INTEGRATION COMPUTE METHODS ===
    @api.depends('nhan_vien_phu_trach_id.ten_nv', 'nhan_vien_phu_trach_id.email', 'nhan_vien_phu_trach_id.phong_ban')
    def _compute_sync_nhan_su(self):
        """Đồng bộ thông tin từ module nhan_su để đảm bảo tính nhất quán dữ liệu"""
        for record in self:
            if record.nhan_vien_phu_trach_id:
                record.ten_nhan_vien_phu_trach = record.nhan_vien_phu_trach_id.ten_nv
                record.email_nhan_vien_phu_trach = record.nhan_vien_phu_trach_id.email
                record.phong_ban_nhan_vien_phu_trach = record.nhan_vien_phu_trach_id.phong_ban
            else:
                record.ten_nhan_vien_phu_trach = False
                record.email_nhan_vien_phu_trach = False
                record.phong_ban_nhan_vien_phu_trach = False
    
    # === SYSTEM INTEGRATION CONSTRAINTS ===
    @api.constrains('nhan_vien_phu_trach_id')
    def _check_nhan_vien_phu_trach_active(self):
        """Đảm bảo nhân viên phụ trách vẫn đang hoạt động"""
        for record in self:
            if record.nhan_vien_phu_trach_id and record.nhan_vien_phu_trach_id.trang_thai_lam_viec != 'dang_lam':
                raise ValidationError(f'Nhân viên phụ trách "{record.nhan_vien_phu_trach_id.ten_nv}" không còn hoạt động trong hệ thống!')
    
    def name_get(self):
        """Hiển thị tên khách hàng kèm công ty"""
        result = []
        for record in self:
            name = record.ten_khach_hang
            result.append((record.id, name))
        return result
    
    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        """Tìm kiếm theo tên hoặc công ty"""
        args = args or []
        if name:
            domain = ['|', ('ten_khach_hang', operator, name), ('cong_ty', operator, name)]
            return self._search(domain + args, limit=limit, access_rights_uid=name_get_uid)
        return super(KhachHang, self)._name_search(name, args, operator, limit, name_get_uid)
    
    def action_chuyen_trang_thai_giao_dich(self):
        """Chuyển trạng thái sang Đang giao dịch"""
        for record in self:
            record.trang_thai = 'dang_giao_dich'
    
    def action_gui_email(self):
        """Mở wizard gửi email cho khách hàng"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Gửi Email',
            'res_model': 'email_khach_hang',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_khach_hang_ids': [(6, 0, [self.id])],
            }
        }
    
    # ============ SMART BUTTON COUNTS ============
    
    @api.depends('don_hang_ids', 'ho_tro_ids', 'email_ids')
    def _compute_smart_button_counts(self):
        """Tính số lượng cho smart buttons"""
        for record in self:
            record.don_hang_count = len(record.don_hang_ids)
            record.ho_tro_count = len(record.ho_tro_ids)
            record.email_count = len(record.email_ids)
    
    # ============ RFM ANALYSIS ============
    
    @api.depends('don_hang_ids', 'don_hang_ids.ngay_dat_hang', 'don_hang_ids.tong_tien')
    def _compute_rfm_score(self):
        """Tính RFM score và phân loại khách hàng"""
        from datetime import timedelta
        
        for record in self:
            completed_orders = record.don_hang_ids.filtered(lambda o: o.trang_thai == 'hoan_thanh')
            
            if not completed_orders:
                record.rfm_recency = 999
                record.rfm_frequency = 0
                record.rfm_monetary = 0.0
                record.rfm_segment = 'new'
                continue
            
            # Recency: Số ngày kể từ lần mua cuối
            last_order_date = max(completed_orders.mapped('ngay_dat_hang'))
            record.rfm_recency = (fields.Date.today() - last_order_date).days
            
            # Frequency: Số lần mua hàng
            record.rfm_frequency = len(completed_orders)
            
            # Monetary: Tổng giá trị đã mua
            record.rfm_monetary = sum(completed_orders.mapped('tong_tien'))
            
            # Phân loại dựa trên RFM
            if record.rfm_recency <= 30 and record.rfm_frequency >= 5 and record.rfm_monetary >= 10000000:
                record.rfm_segment = 'vip'
            elif record.rfm_recency <= 60 and record.rfm_frequency >= 3:
                record.rfm_segment = 'loyal'
            elif record.rfm_recency > 90 and record.rfm_frequency >= 2:
                record.rfm_segment = 'at_risk'
            elif record.rfm_recency > 180:
                record.rfm_segment = 'lost'
            else:
                record.rfm_segment = 'new'
    
    # ============ AI INSIGHTS ============
    
    @api.depends('rfm_recency', 'rfm_frequency', 'rfm_monetary', 'ho_tro_ids')
    def _compute_ai_insights(self):
        """Tính AI insights: churn prediction, purchase probability, next best action"""
        for record in self:
            try:
                # Churn Prediction
                if record.rfm_recency > 180:
                    record.churn_probability = 90.0
                elif record.rfm_recency > 90:
                    record.churn_probability = 60.0
                elif record.rfm_recency > 60:
                    record.churn_probability = 30.0
                else:
                    record.churn_probability = 10.0
                
                # Purchase Probability
                if record.rfm_segment == 'vip':
                    record.purchase_probability = 85.0
                elif record.rfm_segment == 'loyal':
                    record.purchase_probability = 65.0
                elif record.rfm_segment == 'at_risk':
                    record.purchase_probability = 25.0
                else:
                    record.purchase_probability = 10.0
                
                # Next Best Action
                if record.rfm_segment == 'vip':
                    record.next_best_action = "✨ Gửi ưu đãi VIP đặc biệt\n📞 Gọi điện cảm ơn và giới thiệu sản phẩm mới"
                elif record.rfm_segment == 'loyal':
                    record.next_best_action = "🎁 Gửi chương trình loyalty rewards\n📧 Email khuyến mãi cho khách hàng trung thành"
                elif record.rfm_segment == 'at_risk':
                    record.next_best_action = "⚠️ GỌI NGAY để tìm hiểu nguyên nhân\n💰 Gửi voucher giảm giá đặc biệt"
                elif record.rfm_segment == 'lost':
                    record.next_best_action = "🔄 Gửi email win-back campaign\n🎯 Khảo sát lý do ngừng mua hàng"
                else:
                    record.next_best_action = "👋 Gửi email chào mừng\n📱 Giới thiệu sản phẩm phù hợp"
                    
            except Exception as e:
                _logger.warning("Error in AI insights: %s", e)
                record.churn_probability = 0.0
                record.purchase_probability = 0.0
                record.next_best_action = "Không có dữ liệu đủ để phân tích"
    
    @api.depends('ho_tro_ids', 'ho_tro_ids.mo_ta', 'ho_tro_ids.nhan_xet')
    def _compute_sentiment_analysis(self):
        """Phân tích cảm xúc từ tickets và feedback"""
        for record in self:
            try:
                # Simple sentiment analysis based on keywords
                positive_keywords = ['tốt', 'hài lòng', 'xuất sắc', 'tuyệt vời', 'tốt', 'cảm ơn', 'thanks', 'good', 'excellent']
                negative_keywords = ['tệ', 'không hài lòng', 'kém', 'chậm', 'bad', 'poor', 'disappointed', 'angry']
                
                sentiment_score = 0
                total_texts = 0
                
                for ticket in record.ho_tro_ids:
                    texts = []
                    if ticket.mo_ta:
                        texts.append(ticket.mo_ta.lower())
                    if ticket.nhan_xet:
                        texts.append(ticket.nhan_xet.lower())
                    
                    for text in texts:
                        total_texts += 1
                        positive_count = sum(1 for word in positive_keywords if word in text)
                        negative_count = sum(1 for word in negative_keywords if word in text)
                        
                        if positive_count > negative_count:
                            sentiment_score += 0.5
                        elif negative_count > positive_count:
                            sentiment_score -= 0.5
                
                if total_texts > 0:
                    record.sentiment_score = sentiment_score / total_texts
                else:
                    record.sentiment_score = 0.0
                    
            except Exception as e:
                _logger.warning("Error in sentiment analysis: %s", e)
                record.sentiment_score = 0.0
    
    @api.depends('don_hang_ids', 'don_hang_ids.ngay_dat_hang', 'ho_tro_ids', 'ho_tro_ids.ngay_tao')
    def _compute_last_activity(self):
        """Tính ngày hoạt động cuối cùng"""
        for record in self:
            dates = []
            
            if record.don_hang_ids:
                dates.extend(record.don_hang_ids.mapped('ngay_dat_hang'))
            
            if record.ho_tro_ids:
                dates.extend([d.date() for d in record.ho_tro_ids.mapped('ngay_tao') if d])
            
            if dates:
                record.last_activity_date = max(dates)
                record.days_since_last_activity = (fields.Date.today() - record.last_activity_date).days
            else:
                record.last_activity_date = False
                record.days_since_last_activity = 0
    
    # ============ SMART BUTTON ACTIONS ============
    
    def action_view_orders(self):
        """Xem tất cả đơn hàng của khách hàng"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Đơn hàng - {self.ten_khach_hang}',
            'res_model': 'don_hang',
            'view_mode': 'tree,form,kanban',
            'domain': [('khach_hang_id', '=', self.id)],
            'context': {'default_khach_hang_id': self.id}
        }
    
    def action_view_support_tickets(self):
        """Xem tất cả tickets của khách hàng"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Hỗ trợ - {self.ten_khach_hang}',
            'res_model': 'ho_tro_khach_hang',
            'view_mode': 'tree,form',
            'domain': [('khach_hang_id', '=', self.id)],
            'context': {'default_khach_hang_id': self.id}
        }
    
    def action_view_emails(self):
        """Xem tất cả email đã gửi"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Emails - {self.ten_khach_hang}',
            'res_model': 'email_khach_hang',
            'view_mode': 'tree,form',
            'domain': [('khach_hang_ids', 'in', self.id)]
        }
    
    def action_create_order(self):
        """Tạo đơn hàng mới cho khách hàng"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Tạo đơn hàng mới',
            'res_model': 'don_hang',
            'view_mode': 'form',
            'target': 'current',
            'context': {'default_khach_hang_id': self.id}
        }
    
    def action_create_support_ticket(self):
        """Tạo ticket hỗ trợ mới"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Tạo yêu cầu hỗ trợ',
            'res_model': 'ho_tro_khach_hang',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_khach_hang_id': self.id}
        }
    
    @api.model
    def cron_update_rfm_segments(self):
        """Cron job cập nhật RFM segments cho tất cả khách hàng"""
        customers = self.search([])
        customers._compute_rfm_score()
        customers._compute_ai_insights()
        _logger.info(f"Updated RFM segments for {len(customers)} customers")
