# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

try:
    import stripe
    import paypalrestsdk
except ImportError as e:
    _logger.warning("Missing payment libraries: %s", e)


class DonHang(models.Model):
    _name = 'don_hang'
    _description = 'Đơn hàng'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'ngay_dat_hang desc'

    # Thông tin cơ bản
    ma_don_hang = fields.Char(
        'Mã đơn hàng',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
    )
    khach_hang_id = fields.Many2one('khach_hang', string='Khách hàng', required=True,
                                      ondelete='cascade', tracking=True)
    ngay_dat_hang = fields.Date('Ngày đặt hàng', required=True, default=fields.Date.context_today,
                                  tracking=True)
    
    # Trạng thái
    trang_thai = fields.Selection([
        ('moi', 'Mới'),
        ('dang_xu_ly', 'Đang xử lý'),
        ('dang_giao', 'Đang giao'),
        ('hoan_thanh', 'Hoàn thành'),
        ('huy', 'Hủy')
    ], string='Trạng thái', default='moi', required=True, tracking=True)
    
    # Chi tiết đơn hàng
    line_ids = fields.One2many('don_hang.line', 'don_hang_id', string='Chi tiết đơn hàng',
                                 copy=True)
    
    # Currency for monetary fields
    currency_id = fields.Many2one('res.currency', string='Currency', 
                                  default=lambda self: self.env.company.currency_id)
    
    # Tổng tiền
    tong_tien = fields.Monetary('Tổng tiền', compute='_compute_tong_tien', store=True,
                                 currency_field='currency_id', tracking=True)
    thanh_tien = fields.Monetary('Thành tiền', compute='_compute_tong_tien', store=True,
                                  currency_field='currency_id')
    
    # Ghi chú
    ghi_chu = fields.Text('Ghi chú')
    
    # Nhân viên xử lý
    nhan_vien_xu_ly_id = fields.Many2one('nhan_vien', string='Nhân viên xử lý', tracking=True,
                                         default=lambda self: self._default_nhan_vien_xu_ly())
    
    # Thanh toán
    phuong_thuc_thanh_toan = fields.Selection([
        ('tien_mat', 'Tiền mặt'),
        ('stripe', 'Stripe'),
        ('paypal', 'PayPal')
    ], string='Phương thức thanh toán', default='tien_mat', tracking=True)
    
    trang_thai_thanh_toan = fields.Selection([
        ('chua_thanh_toan', 'Chưa thanh toán'),
        ('dang_thanh_toan', 'Đang thanh toán'),
        ('da_thanh_toan', 'Đã thanh toán'),
        ('thanh_toan_that_bai', 'Thanh toán thất bại')
    ], string='Trạng thái thanh toán', default='chua_thanh_toan', tracking=True)
    
    payment_url = fields.Char('Link thanh toán', readonly=True)
    
    _sql_constraints = [
        ('ma_don_hang_unique', 'unique(ma_don_hang)', 'Mã đơn hàng đã tồn tại!')
    ]

    def _is_placeholder_ma_don_hang(self, value):
        return not value or value in {'New', 'Mới', _('New')}

    def _generate_unique_ma_don_hang(self):
        """Generate a unique order code.

        In real databases the sequence counter can be behind existing data (e.g. after imports
        or switching sequence definitions). This method retries until it finds a free value.
        """
        for _i in range(100):
            candidate = self.env['ir.sequence'].next_by_code('don_hang')
            if self._is_placeholder_ma_don_hang(candidate):
                continue
            if not self.sudo().search_count([('ma_don_hang', '=', candidate)]):
                return candidate
        return self.env['ir.sequence'].next_by_code('don_hang') or 'New'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            ma_don_hang = vals.get('ma_don_hang')
            if self._is_placeholder_ma_don_hang(ma_don_hang):
                vals['ma_don_hang'] = self._generate_unique_ma_don_hang()
        return super().create(vals_list)

    def action_assign_ma_don_hang(self):
        for record in self:
            if not self._is_placeholder_ma_don_hang(record.ma_don_hang):
                continue
            record.ma_don_hang = record._generate_unique_ma_don_hang()
        return True

    @api.model
    def cron_assign_missing_ma_don_hang(self, batch_size=200):
        orders = self.sudo().search([
            '|', ('ma_don_hang', '=', False), ('ma_don_hang', 'in', ['New', 'Mới', _('New')])
        ], limit=batch_size)
        for order in orders:
            order.ma_don_hang = order._generate_unique_ma_don_hang()
        return True
    
    @api.model
    def _default_nhan_vien_xu_ly(self):
        """Mặc định nhân viên xử lý từ khách hàng trong context"""
        khach_hang_id = self.env.context.get('default_khach_hang_id')
        if khach_hang_id:
            khach_hang = self.env['khach_hang'].browse(khach_hang_id)
            return khach_hang.nhan_vien_phu_trach_id.id if khach_hang.nhan_vien_phu_trach_id else False
        return False
    
    @api.onchange('khach_hang_id')
    def _onchange_khach_hang_id(self):
        """Tự động gán nhân viên xử lý khi chọn khách hàng"""
        if self.khach_hang_id and not self.nhan_vien_xu_ly_id:
            self.nhan_vien_xu_ly_id = self.khach_hang_id.nhan_vien_phu_trach_id
    
    @api.depends('line_ids', 'line_ids.thanh_tien')
    def _compute_tong_tien(self):
        """Tính tổng tiền đơn hàng"""
        for record in self:
            record.tong_tien = sum(record.line_ids.mapped('thanh_tien'))
            record.thanh_tien = record.tong_tien
    
    def action_xac_nhan(self):
        """Xác nhận đơn hàng"""
        for record in self:
            if not record.line_ids:
                raise ValidationError('Vui lòng thêm sản phẩm vào đơn hàng!')
            record.trang_thai = 'dang_xu_ly'
    
    def action_giao_hang(self):
        """Chuyển trạng thái đang giao"""
        for record in self:
            record.trang_thai = 'dang_giao'
    
    def action_hoan_thanh(self):
        """Hoàn thành đơn hàng"""
        for record in self:
            record.trang_thai = 'hoan_thanh'
            # Cập nhật tồn kho
            for line in record.line_ids:
                if line.san_pham_id:
                    line.san_pham_id.so_luong_ton_kho -= line.so_luong
    
    def action_huy(self):
        """Hủy đơn hàng"""
        for record in self:
            record.trang_thai = 'huy'
    
    def action_tao_link_thanh_toan(self):
        """Tạo link thanh toán online"""
        for record in self:
            if record.phuong_thuc_thanh_toan == 'stripe':
                record._create_stripe_payment()
            elif record.phuong_thuc_thanh_toan == 'paypal':
                record._create_paypal_payment()
            else:
                raise ValidationError('Chọn phương thức thanh toán online!')
    
    def _create_stripe_payment(self):
        """Tạo payment intent với Stripe"""
        try:
            # Cần config API key trong system parameters
            stripe.api_key = self.env['ir.config_parameter'].sudo().get_param('stripe.api_key')
            if not stripe.api_key:
                raise ValidationError('Cần cấu hình Stripe API key!')
            
            intent = stripe.PaymentIntent.create(
                amount=int(self.thanh_tien * 100),  # Stripe sử dụng cent
                currency=self.currency_id.name.lower(),
                metadata={'order_id': self.id}
            )
            self.payment_url = f"https://checkout.stripe.com/pay/{intent.client_secret}"
            self.trang_thai_thanh_toan = 'dang_thanh_toan'
        except Exception as e:
            _logger.error("Stripe payment error: %s", e)
            raise ValidationError(f"Lỗi tạo thanh toán Stripe: {e}")
    
    def _create_paypal_payment(self):
        """Tạo payment với PayPal"""
        try:
            # Config PayPal
            paypalrestsdk.configure({
                "mode": self.env['ir.config_parameter'].sudo().get_param('paypal.mode', 'sandbox'),
                "client_id": self.env['ir.config_parameter'].sudo().get_param('paypal.client_id'),
                "client_secret": self.env['ir.config_parameter'].sudo().get_param('paypal.client_secret')
            })
            
            payment = paypalrestsdk.Payment({
                "intent": "sale",
                "payer": {"payment_method": "paypal"},
                "transactions": [{
                    "amount": {
                        "total": str(self.thanh_tien),
                        "currency": self.currency_id.name
                    },
                    "description": f"Thanh toán đơn hàng {self.ma_don_hang}"
                }],
                "redirect_urls": {
                    "return_url": f"{self.env['ir.config_parameter'].sudo().get_param('web.base.url')}/payment/success",
                    "cancel_url": f"{self.env['ir.config_parameter'].sudo().get_param('web.base.url')}/payment/cancel"
                }
            })
            
            if payment.create():
                self.payment_url = payment.links[1].href  # approval_url
                self.trang_thai_thanh_toan = 'dang_thanh_toan'
            else:
                raise ValidationError(f"Lỗi PayPal: {payment.error}")
        except Exception as e:
            _logger.error("PayPal payment error: %s", e)
            raise ValidationError(f"Lỗi tạo thanh toán PayPal: {e}")


class DonHangLine(models.Model):
    _name = 'don_hang.line'
    _description = 'Chi tiết đơn hàng'
    _order = 'don_hang_id, sequence, id'

    sequence = fields.Integer('Thứ tự', default=10)
    don_hang_id = fields.Many2one('don_hang', string='Đơn hàng', required=True, ondelete='cascade')
    san_pham_id = fields.Many2one('san_pham', string='Sản phẩm', required=True)
    ten_san_pham = fields.Char('Tên sản phẩm', related='san_pham_id.ten_san_pham', store=True)
    so_luong = fields.Integer('Số lượng', required=True, default=1)
    don_gia = fields.Monetary('Đơn giá', required=True, currency_field='currency_id')
    thanh_tien = fields.Monetary('Thành tiền', compute='_compute_thanh_tien', store=True,
                                  currency_field='currency_id')
    ghi_chu = fields.Char('Ghi chú')
    
    currency_id = fields.Many2one(related='don_hang_id.currency_id', store=True)
    
    _sql_constraints = [
        ('check_so_luong', 'CHECK(so_luong > 0)', 'Số lượng phải lớn hơn 0!'),
        ('check_don_gia', 'CHECK(don_gia >= 0)', 'Đơn giá không được âm!')
    ]
    
    @api.depends('so_luong', 'don_gia')
    def _compute_thanh_tien(self):
        """Tính thành tiền"""
        for record in self:
            record.thanh_tien = record.so_luong * record.don_gia
    
    @api.onchange('san_pham_id')
    def _onchange_san_pham(self):
        """Tự động điền đơn giá khi chọn sản phẩm"""
        if self.san_pham_id:
            self.don_gia = self.san_pham_id.don_gia
