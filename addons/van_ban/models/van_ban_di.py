# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class VanBanDi(models.Model):
    _name = 'van_ban_di'
    _description = 'Văn bản đi'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'ngay_ban_hanh desc'

    # === THÔNG TIN CƠ BẢN ===
    name = fields.Char('Số ký hiệu', required=True, copy=False, tracking=True)
    so_di = fields.Char('Số đi', required=True, copy=False, 
                        default=lambda self: _('New'), tracking=True)
    
    ngay_ban_hanh = fields.Date('Ngày ban hành', 
                                 default=fields.Date.context_today, 
                                 required=True, tracking=True)
    ngay_gui = fields.Date('Ngày gửi', tracking=True)
    
    trich_yeu = fields.Char('Trích yếu', required=True, tracking=True)
    noi_dung = fields.Text('Nội dung')
    
    # === NƠI NHẬN ===
    noi_nhan = fields.Text('Nơi nhận', required=True, tracking=True)
    khach_hang_ids = fields.Many2many('khach_hang', 
                                      'van_ban_di_khach_hang_rel',
                                      'van_ban_di_id', 'khach_hang_id',
                                      string='Khách hàng nhận')
    
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
    
    # === NGƯỜI XỬ LÝ ===
    nguoi_soan_thao_id = fields.Many2one('nhan_vien', string='Người soạn thảo', 
                                          required=True, tracking=True)
    nguoi_ky_id = fields.Many2one('nhan_vien', string='Người ký', 
                                   required=True, tracking=True)
    nguoi_duyet_id = fields.Many2one('nhan_vien', string='Người duyệt', 
                                      tracking=True)
    
    # === QUY TRÌNH ===
    trang_thai = fields.Selection([
        ('soan_thao', 'Soạn thảo'),
        ('cho_duyet', 'Chờ duyệt'),
        ('cho_ky', 'Chờ ký'),
        ('da_ky', 'Đã ký'),
        ('da_gui', 'Đã gửi'),
        ('huy', 'Đã hủy')
    ], string='Trạng thái', default='soan_thao', required=True, tracking=True)
    
    ngay_duyet = fields.Date('Ngày duyệt', tracking=True)
    ngay_ky = fields.Date('Ngày ký', tracking=True)
    
    y_kien_duyet = fields.Text('Ý kiến duyệt')
    ly_do_huy = fields.Text('Lý do hủy')
    
    # === FILE ĐÍNH KÈM ===
    file_dinh_kem = fields.Binary('File văn bản', attachment=True)
    ten_file = fields.Char('Tên file')
    
    file_da_ky = fields.Binary('File đã ký', attachment=True)
    ten_file_da_ky = fields.Char('Tên file đã ký')
    
    # === THÔNG TIN BỔ SUNG ===
    so_trang = fields.Integer('Số trang')
    so_ban = fields.Integer('Số bản phát hành', default=1)
    
    hinh_thuc_gui = fields.Selection([
        ('truc_tiep', 'Trực tiếp'),
        ('buu_dien', 'Bưu điện'),
        ('email', 'Email'),
        ('fax', 'Fax')
    ], string='Hình thức gửi', default='email', tracking=True)
    
    ghi_chu = fields.Text('Ghi chú')
    
    # === VĂN BẢN LIÊN QUAN ===
    van_ban_den_id = fields.Many2one('van_ban_den', string='Trả lời văn bản đến')
    
    # === HỆ THỐNG ===
    nguoi_tao_id = fields.Many2one('res.users', string='Người tạo', 
                                    default=lambda self: self.env.uid, 
                                    readonly=True)
    ngay_tao = fields.Datetime('Ngày tạo', default=fields.Datetime.now, 
                                readonly=True)
    
    @api.model
    def create(self, vals):
        if vals.get('so_di', _('New')) == _('New'):
            vals['so_di'] = self.env['ir.sequence'].next_by_code('van_ban_di') or _('New')
        return super(VanBanDi, self).create(vals)
    
    def action_gui_duyet(self):
        """Gửi văn bản đi duyệt"""
        self.ensure_one()
        if not self.nguoi_duyet_id:
            raise UserError(_('Vui lòng chỉ định người duyệt!'))
        self.write({'trang_thai': 'cho_duyet'})
        self.message_post(body=_('Gửi văn bản đi duyệt'))
        
        # Tạo activity cho người duyệt
        self.activity_schedule(
            'mail.mail_activity_data_todo',
            user_id=self.nguoi_duyet_id.user_id.id,
            summary=_('Duyệt văn bản đi: %s') % self.name
        )
    
    def action_duyet(self):
        """Duyệt văn bản"""
        self.ensure_one()
        if not self.y_kien_duyet:
            raise UserError(_('Vui lòng nhập ý kiến duyệt!'))
        self.write({
            'trang_thai': 'cho_ky',
            'ngay_duyet': fields.Date.context_today(self)
        })
        self.message_post(body=_('Đã duyệt văn bản'))
        
        # Tạo activity cho người ký
        self.activity_schedule(
            'mail.mail_activity_data_todo',
            user_id=self.nguoi_ky_id.user_id.id,
            summary=_('Ký văn bản đi: %s') % self.name
        )
    
    def action_tu_choi(self):
        """Từ chối duyệt văn bản"""
        self.ensure_one()
        self.write({'trang_thai': 'soan_thao'})
        self.message_post(body=_('Từ chối duyệt: %s') % self.y_kien_duyet)
    
    def action_ky(self):
        """Ký văn bản"""
        self.ensure_one()
        if not self.file_dinh_kem:
            raise UserError(_('Vui lòng đính kèm file văn bản!'))
        self.write({
            'trang_thai': 'da_ky',
            'ngay_ky': fields.Date.context_today(self)
        })
        self.message_post(body=_('Đã ký văn bản'))
    
    def action_gui(self):
        """Gửi văn bản đi"""
        self.ensure_one()
        if self.trang_thai != 'da_ky':
            raise UserError(_('Chỉ có thể gửi văn bản đã ký!'))
        self.write({
            'trang_thai': 'da_gui',
            'ngay_gui': fields.Date.context_today(self)
        })
        self.message_post(body=_('Đã gửi văn bản'))
    
    def action_huy(self):
        """Hủy văn bản"""
        self.ensure_one()
        if not self.ly_do_huy:
            raise UserError(_('Vui lòng nhập lý do hủy!'))
        self.write({'trang_thai': 'huy'})
        self.message_post(body=_('Hủy văn bản: %s') % self.ly_do_huy)
