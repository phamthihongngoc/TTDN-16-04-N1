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
    
    # Nhân viên phụ trách
    nhan_vien_phu_trach_id = fields.Many2one('nhan_vien', string='Nhân viên phụ trách',
                                               tracking=True,
                                               help='Nhân viên được phân công chăm sóc khách hàng này')
    
    # Quan hệ
    don_hang_ids = fields.One2many('don_hang', 'khach_hang_id', string='Đơn hàng')
    ho_tro_ids = fields.One2many('ho_tro_khach_hang', 'khach_hang_id', string='Yêu cầu hỗ trợ')
    email_ids = fields.Many2many('email_khach_hang', string='Email đã nhận')
    
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
            if record.cong_ty:
                name = f"{record.ten_khach_hang} ({record.cong_ty})"
            else:
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
