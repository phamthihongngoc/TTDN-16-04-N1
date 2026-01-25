# -*- coding: utf-8 -*-
from odoo import models, fields, api


class WizardTuChoiHoSo(models.TransientModel):
    _name = 'wizard.tu_choi_ho_so'
    _description = 'Wizard từ chối hồ sơ'

    ly_do_tu_choi = fields.Text('Lý do từ chối', required=True)
    ho_so_id = fields.Many2one('ho_so.nhan_vien', string='Hồ sơ', required=True)

    def action_confirm(self):
        """Xác nhận từ chối hồ sơ"""
        self.ensure_one()
        if self.ho_so_id:
            self.ho_so_id.write({
                'trang_thai': 'tu_choi',
                'ly_do_tu_choi': self.ly_do_tu_choi,
                'nguoi_duyet_id': self.env.user.id,
                'ngay_duyet': fields.Datetime.now(),
            })
            
            # Gửi thông báo
            self.ho_so_id._send_rejected_notification()
            
            # Hoàn thành activity
            self.ho_so_id._complete_approval_activity()
            
        return {'type': 'ir.actions.act_window_close'}
