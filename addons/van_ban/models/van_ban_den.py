# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class VanBanDen(models.Model):
    _name = 'van_ban_den'
    _description = 'Văn bản đến'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'ngay_den desc'

    # === THÔNG TIN CƠ BẢN ===
    name = fields.Char('Số ký hiệu', required=True, copy=False, tracking=True)
    so_den = fields.Char('Số đến', required=True, copy=False, 
                         default=lambda self: _('New'), tracking=True)
    
    ngay_van_ban = fields.Date('Ngày văn bản', required=True, tracking=True)
    ngay_den = fields.Date('Ngày đến', default=fields.Date.context_today, 
                           required=True, tracking=True)
    
    trich_yeu = fields.Char('Trích yếu', required=True, tracking=True)
    noi_dung = fields.Text('Nội dung')
    
    # === ĐƠN VỊ GỬI ===
    don_vi_gui = fields.Char('Đơn vị gửi', tracking=True)
    khach_hang_id = fields.Many2one('khach_hang', string='Khách hàng (nếu có)', 
                                     tracking=True)
    nguoi_ky_ban_gui = fields.Char('Người ký (bên gửi)', tracking=True)
    
    # === LOẠI VÀ ĐỘ ƯU TIÊN ===
    loai_van_ban_id = fields.Many2one('loai_van_ban', string='Loại văn bản')
    
    do_khan = fields.Selection([
        ('thuong', 'Thường'),
        ('khan', 'Khẩn'),
        ('hoa_toc', 'Hỏa tốc'),
        ('tuc_thi', 'Tức thì')
    ], string='Độ khẩn', default='thuong', required=True, tracking=True)
    
    do_mat = fields.Selection([
        ('thuong', 'Thường'),
        ('mat', 'Mật'),
        ('tuyet_mat', 'Tuyệt mật')
    ], string='Độ mật', default='thuong', required=True, tracking=True)
    
    # === XỬ LÝ ===
    nguoi_nhan_id = fields.Many2one('nhan_vien', string='Người nhận', 
                                     tracking=True)
    don_vi_xu_ly = fields.Char('Đơn vị xử lý', tracking=True)
    nguoi_xu_ly_id = fields.Many2one('nhan_vien', string='Người xử lý chính', 
                                      tracking=True)
    nguoi_phoi_hop_ids = fields.Many2many('nhan_vien', 
                                           'van_ban_den_nhan_vien_rel',
                                           'van_ban_den_id', 'nhan_vien_id',
                                           string='Người phối hợp xử lý')
    
    han_xu_ly = fields.Date('Hạn xử lý', tracking=True)
    ngay_hoan_thanh = fields.Date('Ngày hoàn thành', tracking=True)
    
    trang_thai = fields.Selection([
        ('moi', 'Mới đến'),
        ('dang_xu_ly', 'Đang xử lý'),
        ('cho_y_kien', 'Chờ ý kiến'),
        ('hoan_thanh', 'Hoàn thành'),
        ('luu', 'Lưu')
    ], string='Trạng thái', default='moi', required=True, tracking=True)
    
    y_kien_xu_ly = fields.Text('Ý kiến xử lý', tracking=True)
    ket_qua_xu_ly = fields.Text('Kết quả xử lý')
    
    # === FILE ĐÍNH KÈM ===
    file_dinh_kem = fields.Binary('File đính kèm', attachment=True)
    ten_file = fields.Char('Tên file')
    
    file_phan_hoi = fields.Binary('File phản hồi', attachment=True)
    ten_file_phan_hoi = fields.Char('Tên file phản hồi')
    
    # === THÔNG TIN BỔ SUNG ===
    so_trang = fields.Integer('Số trang')
    so_ban = fields.Integer('Số bản', default=1)
    
    ghi_chu = fields.Text('Ghi chú')
    
    # === HỆ THỐNG ===
    nguoi_tao_id = fields.Many2one('res.users', string='Người tạo', 
                                    default=lambda self: self.env.uid, 
                                    readonly=True)
    ngay_tao = fields.Datetime('Ngày tạo', default=fields.Datetime.now, 
                                readonly=True)
    
    # === COMPUTED FIELDS ===
    qua_han = fields.Boolean('Quá hạn', compute='_compute_qua_han', store=True)
    so_ngay_con_lai = fields.Integer('Số ngày còn lại', 
                                      compute='_compute_so_ngay_con_lai')
    
    @api.depends('han_xu_ly', 'trang_thai')
    def _compute_qua_han(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.han_xu_ly and rec.trang_thai not in ['hoan_thanh', 'luu']:
                rec.qua_han = rec.han_xu_ly < today
            else:
                rec.qua_han = False
    
    @api.depends('han_xu_ly')
    def _compute_so_ngay_con_lai(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.han_xu_ly and rec.trang_thai not in ['hoan_thanh', 'luu']:
                delta = rec.han_xu_ly - today
                rec.so_ngay_con_lai = delta.days
            else:
                rec.so_ngay_con_lai = 0
    
    @api.model
    def create(self, vals):
        if vals.get('so_den', _('New')) == _('New'):
            vals['so_den'] = self.env['ir.sequence'].next_by_code('van_ban_den') or _('New')
        return super(VanBanDen, self).create(vals)
    
    def action_bat_dau_xu_ly(self):
        """Bắt đầu xử lý văn bản"""
        self.ensure_one()
        if not self.nguoi_xu_ly_id:
            raise UserError(_('Vui lòng chỉ định người xử lý chính!'))
        self.write({'trang_thai': 'dang_xu_ly'})
        self.message_post(body=_('Bắt đầu xử lý văn bản'))
    
    def action_hoan_thanh(self):
        """Hoàn thành xử lý văn bản"""
        self.ensure_one()
        if not self.ket_qua_xu_ly:
            raise UserError(_('Vui lòng nhập kết quả xử lý!'))
        self.write({
            'trang_thai': 'hoan_thanh',
            'ngay_hoan_thanh': fields.Date.context_today(self)
        })
        self.message_post(body=_('Hoàn thành xử lý văn bản'))
    
    def action_luu_tru(self):
        """Chuyển văn bản vào lưu trữ"""
        self.ensure_one()
        self.write({'trang_thai': 'luu'})
        self.message_post(body=_('Chuyển văn bản vào lưu trữ'))
