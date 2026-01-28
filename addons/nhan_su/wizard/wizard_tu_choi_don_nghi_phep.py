# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class WizardTuChoiDonNghiPhep(models.TransientModel):
    _name = 'wizard.tu_choi_don_nghi_phep'
    _description = 'Wizard từ chối đơn nghỉ phép'

    don_nghi_phep_id = fields.Many2one('don_nghi_phep', string='Đơn nghỉ phép', required=True)
    ly_do = fields.Text('Lý do từ chối', required=True)
    
    def action_tu_choi(self):
        """Xác nhận từ chối đơn nghỉ phép"""
        self.ensure_one()

        don = self.don_nghi_phep_id
        if don.nguoi_duyet_id and self.env.user.id != don.nguoi_duyet_id.id:
            if not (self.env.user.has_group('nhan_su.group_quan_tri_nhan_su') or self.env.user.has_group('base.group_system')):
                raise ValidationError(_('Bạn không phải người được phân công duyệt đơn này.'))

        self.don_nghi_phep_id.write({
            'trang_thai': 'tu_choi',
            'ly_do_tu_choi': self.ly_do,
            'nguoi_duyet_id': self.env.user.id,
            'ngay_duyet': fields.Datetime.now()
        })

        # Mark pending approval activities as done
        try:
            acts = self.env['mail.activity'].search([
                ('res_model', '=', 'don_nghi_phep'),
                ('res_id', '=', don.id),
                ('activity_type_id', '=', self.env.ref('mail.mail_activity_data_todo').id),
            ])
            if acts:
                acts.action_feedback(feedback=_('Đã từ chối'))
        except Exception:
            pass
        
        # Gửi thông báo
        self.don_nghi_phep_id.message_post(
            body=_('Đơn nghỉ phép đã bị từ chối bởi %s. Lý do: %s') % (
                self.env.user.name, self.ly_do),
            message_type='notification'
        )

        # Notify employee
        if don.nhan_vien_id and don.nhan_vien_id.user_id:
            try:
                don.activity_schedule(
                    'mail.mail_activity_data_todo',
                    user_id=don.nhan_vien_id.user_id.id,
                    summary=_('Đơn nghỉ phép bị từ chối'),
                    note=_('Đơn %s bị từ chối bởi %s. Lý do: %s') % (don.ma_don, self.env.user.name, self.ly_do),
                )
            except Exception:
                pass
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Đã từ chối'),
                'message': _('Đơn nghỉ phép đã bị từ chối!'),
                'type': 'warning',
                'sticky': False,
            }
        }
