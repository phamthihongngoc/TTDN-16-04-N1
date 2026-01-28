# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class WizardTuChoiDonNghiPhep(models.TransientModel):
    _name = 'wizard.tu_choi_don_nghi_phep'
    _description = 'Wizard từ chối đơn nghỉ phép'

    don_nghi_phep_id = fields.Many2one('don_nghi_phep', string='Đơn nghỉ phép', required=True)
    ly_do = fields.Text('Lý do từ chối', required=True)
    
    def action_tu_choi(self):
        """Xác nhận từ chối đơn nghỉ phép"""
        self.ensure_one()
        self.don_nghi_phep_id.write({
            'trang_thai': 'tu_choi',
            'ly_do_tu_choi': self.ly_do,
            'nguoi_duyet_id': self.env.user.id,
            'ngay_duyet': fields.Datetime.now()
        })
        
        # Gửi thông báo
        self.don_nghi_phep_id.message_post(
            body=_('Đơn nghỉ phép đã bị từ chối bởi %s. Lý do: %s') % (
                self.env.user.name, self.ly_do),
            message_type='notification'
        )
        
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
