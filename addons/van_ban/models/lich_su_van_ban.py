# -*- coding: utf-8 -*-

from odoo import models, fields, api


class LichSuVanBan(models.Model):
    _name = 'lich_su_van_ban'
    _description = 'Lịch sử văn bản (Audit Trail)'
    _order = 'thoi_gian desc'

    van_ban_id = fields.Many2one('van_ban', string='Văn bản', required=True, 
                                  ondelete='cascade')
    
    hanh_dong = fields.Selection([
        ('tao', 'Tạo mới'),
        ('sua', 'Chỉnh sửa'),
        ('xoa', 'Xóa'),
        ('trang_thai', 'Đổi trạng thái'),
        ('file', 'Cập nhật file'),
        ('gui_duyet', 'Gửi duyệt'),
        ('duyet', 'Duyệt'),
        ('tu_choi', 'Từ chối duyệt'),
        ('gui_ky', 'Gửi ký'),
        ('ky', 'Ký nội bộ'),
        ('gui_yeu_cau_ky', 'Gửi yêu cầu ký khách'),
        ('khach_ky', 'Khách hàng ký'),
        ('khach_tu_choi', 'Khách từ chối ký'),
        ('gui', 'Gửi văn bản'),
        ('huy', 'Hủy'),
        ('het_han', 'Hết hạn'),
        ('mo_khoa', 'Mở khóa'),
        ('ai_analyze', 'Phân tích AI'),
        ('ai_apply', 'Áp dụng AI'),
        ('khac', 'Khác')
    ], string='Hành động', required=True)
    
    mo_ta = fields.Text('Mô tả chi tiết')
    nguoi_thuc_hien_id = fields.Many2one('res.users', string='Người thực hiện', 
                                          default=lambda self: self.env.uid)
    thoi_gian = fields.Datetime('Thời gian', default=fields.Datetime.now)
    ip_address = fields.Char('Địa chỉ IP')
    user_agent = fields.Text('User Agent', help='Browser/device information')
    session_id = fields.Char('Session ID', help='User session identifier')
    
    # Related fields
    ten_van_ban = fields.Char(related='van_ban_id.ten_van_ban', string='Tên văn bản', store=True)
    ma_van_ban = fields.Char(related='van_ban_id.ma_van_ban', string='Mã văn bản', store=True)
    ten_nguoi_thuc_hien = fields.Char(related='nguoi_thuc_hien_id.name', string='Tên người thực hiện')
