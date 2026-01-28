# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import timedelta
import logging

_logger = logging.getLogger(__name__)


class LoaiNghiPhep(models.Model):
    _name = 'loai_nghi_phep'
    _description = 'Loại nghỉ phép'
    _order = 'sequence, name'

    name = fields.Char('Tên loại phép', required=True)
    code = fields.Char('Mã', required=True)
    sequence = fields.Integer('Thứ tự', default=10)
    active = fields.Boolean('Hoạt động', default=True)
    
    # Cấu hình
    co_luong = fields.Boolean('Có lương', default=True,
                               help='Nghỉ phép có được hưởng lương không')
    so_ngay_mac_dinh = fields.Integer('Số ngày phép/năm', default=12,
                                       help='Số ngày phép mặc định mỗi năm')
    cho_phep_cong_don = fields.Boolean('Cho phép cộng dồn', default=False,
                                        help='Cho phép cộng dồn phép năm trước sang năm sau')
    
    ghi_chu = fields.Text('Ghi chú')
    
    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Mã loại phép đã tồn tại!')
    ]


class DonNghiPhep(models.Model):
    _name = 'don_nghi_phep'
    _description = 'Đơn nghỉ phép'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'ngay_tao desc'
    _rec_name = 'ma_don'

    ma_don = fields.Char('Mã đơn', readonly=True, copy=False, default='New')
    nhan_vien_id = fields.Many2one('nhan_vien', string='Nhân viên', required=True,
                                    default=lambda self: self._get_current_employee(),
                                    tracking=True, index=True)
    phong_ban_id = fields.Many2one('nhan_su.phong_ban', string='Phòng ban',
                                    related='nhan_vien_id.phong_ban_id', store=True)
    
    # Loại nghỉ phép
    loai_nghi_phep_id = fields.Many2one('loai_nghi_phep', string='Loại nghỉ phép',
                                         required=True, tracking=True)
    co_luong = fields.Boolean('Có lương', related='loai_nghi_phep_id.co_luong', store=True)
    
    # Thời gian nghỉ
    ngay_bat_dau = fields.Date('Ngày bắt đầu', required=True, tracking=True)
    ngay_ket_thuc = fields.Date('Ngày kết thúc', required=True, tracking=True)
    so_ngay_nghi = fields.Float('Số ngày nghỉ', compute='_compute_so_ngay', store=True)
    
    # Buổi nghỉ (nửa ngày)
    nghi_nua_ngay = fields.Boolean('Nghỉ nửa ngày', default=False)
    buoi_nghi = fields.Selection([
        ('sang', 'Buổi sáng'),
        ('chieu', 'Buổi chiều')
    ], string='Buổi nghỉ')
    
    # Lý do
    ly_do = fields.Text('Lý do nghỉ', required=True, tracking=True)
    
    # Trạng thái
    trang_thai = fields.Selection([
        ('nhap', 'Nháp'),
        ('cho_duyet', 'Chờ duyệt'),
        ('da_duyet', 'Đã duyệt'),
        ('tu_choi', 'Từ chối'),
        ('huy', 'Đã hủy')
    ], string='Trạng thái', default='nhap', required=True, tracking=True, index=True)
    
    # Người xử lý
    nguoi_duyet_id = fields.Many2one('res.users', string='Người duyệt', readonly=True)
    ngay_duyet = fields.Datetime('Ngày duyệt', readonly=True)
    ly_do_tu_choi = fields.Text('Lý do từ chối')
    
    # Thông tin bổ sung
    ngay_tao = fields.Datetime('Ngày tạo', default=fields.Datetime.now, readonly=True)
    ghi_chu = fields.Text('Ghi chú')
    
    # Thống kê phép còn lại
    so_phep_con_lai = fields.Float('Số phép còn lại', compute='_compute_so_phep_con_lai')
    
    _sql_constraints = [
        ('ma_don_unique', 'unique(ma_don)', 'Mã đơn đã tồn tại!')
    ]
    
    def _get_current_employee(self):
        """Lấy nhân viên hiện tại dựa trên user đăng nhập"""
        employee = self.env['nhan_vien'].search([('user_id', '=', self.env.uid)], limit=1)
        return employee.id if employee else False
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('ma_don', 'New') == 'New':
                vals['ma_don'] = self.env['ir.sequence'].next_by_code('don_nghi_phep') or 'New'
        return super().create(vals_list)
    
    @api.depends('ngay_bat_dau', 'ngay_ket_thuc', 'nghi_nua_ngay')
    def _compute_so_ngay(self):
        for rec in self:
            if rec.ngay_bat_dau and rec.ngay_ket_thuc:
                if rec.nghi_nua_ngay:
                    rec.so_ngay_nghi = 0.5
                else:
                    delta = rec.ngay_ket_thuc - rec.ngay_bat_dau
                    rec.so_ngay_nghi = delta.days + 1
            else:
                rec.so_ngay_nghi = 0
    
    @api.depends('nhan_vien_id', 'loai_nghi_phep_id')
    def _compute_so_phep_con_lai(self):
        """Tính số phép còn lại của nhân viên"""
        for rec in self:
            if rec.nhan_vien_id and rec.loai_nghi_phep_id:
                # Số phép mặc định theo loại
                so_phep_nam = rec.loai_nghi_phep_id.so_ngay_mac_dinh
                
                # Tính tổng số ngày đã nghỉ trong năm
                nam_hien_tai = fields.Date.today().year
                da_nghi = self.search([
                    ('nhan_vien_id', '=', rec.nhan_vien_id.id),
                    ('loai_nghi_phep_id', '=', rec.loai_nghi_phep_id.id),
                    ('trang_thai', '=', 'da_duyet'),
                    ('ngay_bat_dau', '>=', f'{nam_hien_tai}-01-01'),
                    ('ngay_bat_dau', '<=', f'{nam_hien_tai}-12-31'),
                    ('id', '!=', rec.id if rec.id else 0)
                ])
                tong_da_nghi = sum(da_nghi.mapped('so_ngay_nghi'))
                
                rec.so_phep_con_lai = so_phep_nam - tong_da_nghi
            else:
                rec.so_phep_con_lai = 0
    
    @api.constrains('ngay_bat_dau', 'ngay_ket_thuc')
    def _check_ngay(self):
        for rec in self:
            if rec.ngay_bat_dau and rec.ngay_ket_thuc:
                if rec.ngay_bat_dau > rec.ngay_ket_thuc:
                    raise ValidationError(_('Ngày bắt đầu phải trước ngày kết thúc!'))
    
    @api.constrains('so_ngay_nghi', 'so_phep_con_lai', 'loai_nghi_phep_id')
    def _check_so_phep(self):
        for rec in self:
            if rec.loai_nghi_phep_id and rec.loai_nghi_phep_id.co_luong:
                if rec.so_ngay_nghi > rec.so_phep_con_lai + rec.so_ngay_nghi:
                    raise ValidationError(_('Số ngày nghỉ vượt quá số phép còn lại!'))
    
    @api.onchange('nghi_nua_ngay')
    def _onchange_nghi_nua_ngay(self):
        if self.nghi_nua_ngay:
            self.ngay_ket_thuc = self.ngay_bat_dau
    
    # === ACTIONS ===
    
    def action_gui_duyet(self):
        """Gửi đơn đi duyệt"""
        self.ensure_one()
        if self.so_ngay_nghi <= 0:
            raise ValidationError(_('Số ngày nghỉ phải lớn hơn 0!'))
        
        self.write({'trang_thai': 'cho_duyet'})
        
        # Tạo activity cho quản lý
        self._create_approval_activity()
        
        # Gửi thông báo
        self.message_post(
            body=_('Đơn nghỉ phép đã được gửi đi duyệt.'),
            message_type='notification'
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Thành công'),
                'message': _('Đã gửi đơn nghỉ phép!'),
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_duyet(self):
        """Duyệt đơn nghỉ phép"""
        self.ensure_one()
        self.write({
            'trang_thai': 'da_duyet',
            'nguoi_duyet_id': self.env.user.id,
            'ngay_duyet': fields.Datetime.now()
        })
        
        # Tạo bản ghi chấm công nghỉ phép
        self._create_cham_cong_nghi_phep()
        
        self.message_post(
            body=_('Đơn nghỉ phép đã được duyệt bởi %s') % self.env.user.name,
            message_type='notification'
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Đã duyệt'),
                'message': _('Đơn nghỉ phép đã được duyệt!'),
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_tu_choi(self):
        """Từ chối đơn nghỉ phép"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Từ chối đơn nghỉ phép'),
            'res_model': 'wizard.tu_choi_don_nghi_phep',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_don_nghi_phep_id': self.id}
        }
    
    def action_huy(self):
        """Hủy đơn nghỉ phép"""
        self.ensure_one()
        if self.trang_thai == 'da_duyet':
            # Xóa bản ghi chấm công nghỉ phép
            self._delete_cham_cong_nghi_phep()
        
        self.write({'trang_thai': 'huy'})
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Đã hủy'),
                'message': _('Đơn nghỉ phép đã được hủy!'),
                'type': 'warning',
                'sticky': False,
            }
        }
    
    def action_nhap_lai(self):
        """Chuyển về nháp"""
        self.write({'trang_thai': 'nhap', 'ly_do_tu_choi': False})
    
    # === PRIVATE METHODS ===
    
    def _create_cham_cong_nghi_phep(self):
        """Tạo bản ghi chấm công cho các ngày nghỉ phép"""
        ChamCong = self.env['cham_cong']
        for rec in self:
            if rec.nghi_nua_ngay:
                # Nghỉ nửa ngày
                existing = ChamCong.search([
                    ('nhan_vien_id', '=', rec.nhan_vien_id.id),
                    ('ngay_cham_cong', '=', rec.ngay_bat_dau)
                ], limit=1)
                if not existing:
                    ChamCong.create({
                        'nhan_vien_id': rec.nhan_vien_id.id,
                        'ngay_cham_cong': rec.ngay_bat_dau,
                        'trang_thai': 'nghi_phep',
                        'ghi_chu': f'Nghỉ phép nửa ngày ({rec.buoi_nghi}) - {rec.ma_don}'
                    })
            else:
                # Nghỉ cả ngày
                current_date = rec.ngay_bat_dau
                while current_date <= rec.ngay_ket_thuc:
                    existing = ChamCong.search([
                        ('nhan_vien_id', '=', rec.nhan_vien_id.id),
                        ('ngay_cham_cong', '=', current_date)
                    ], limit=1)
                    if not existing:
                        ChamCong.create({
                            'nhan_vien_id': rec.nhan_vien_id.id,
                            'ngay_cham_cong': current_date,
                            'trang_thai': 'nghi_phep',
                            'ghi_chu': f'Nghỉ phép - {rec.ma_don}'
                        })
                    current_date += timedelta(days=1)
    
    def _delete_cham_cong_nghi_phep(self):
        """Xóa bản ghi chấm công nghỉ phép khi hủy đơn"""
        ChamCong = self.env['cham_cong']
        for rec in self:
            cham_cong_records = ChamCong.search([
                ('nhan_vien_id', '=', rec.nhan_vien_id.id),
                ('ngay_cham_cong', '>=', rec.ngay_bat_dau),
                ('ngay_cham_cong', '<=', rec.ngay_ket_thuc),
                ('trang_thai', '=', 'nghi_phep'),
                ('ghi_chu', 'ilike', rec.ma_don)
            ])
            cham_cong_records.unlink()
    
    def _create_approval_activity(self):
        """Tạo activity cho người duyệt"""
        for rec in self:
            # Tìm quản lý trực tiếp hoặc HR
            manager = rec.nhan_vien_id.manager_id.user_id if rec.nhan_vien_id.manager_id else False
            if not manager:
                # Fallback to HR managers
                hr_group = self.env.ref('nhan_su.group_quan_tri_nhan_su', raise_if_not_found=False)
                if hr_group:
                    manager = hr_group.users[:1]
            
            if manager:
                self.env['mail.activity'].create({
                    'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
                    'summary': f'Duyệt đơn nghỉ phép: {rec.ma_don}',
                    'note': f'{rec.nhan_vien_id.ten_nv} xin nghỉ từ {rec.ngay_bat_dau} đến {rec.ngay_ket_thuc}. Lý do: {rec.ly_do}',
                    'res_id': rec.id,
                    'res_model_id': self.env['ir.model']._get('don_nghi_phep').id,
                    'user_id': manager.id,
                    'date_deadline': rec.ngay_bat_dau,
                })
