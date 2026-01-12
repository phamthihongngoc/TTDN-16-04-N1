# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request


class KhachHangController(http.Controller):
    
    @http.route('/khach_hang/dashboard', type='json', auth='user')
    def get_dashboard_data(self):
        """API lấy dữ liệu dashboard"""
        KhachHang = request.env['khach_hang']
        HoTro = request.env['ho_tro_khach_hang']
        DonHang = request.env['don_hang']
        
        return {
            'tong_khach_hang': KhachHang.search_count([]),
            'khach_hang_moi': KhachHang.search_count([('trang_thai', '=', 'moi')]),
            'tong_ho_tro': HoTro.search_count([]),
            'ho_tro_chua_giai_quyet': HoTro.search_count([('trang_thai', '!=', 'da_giai_quyet')]),
            'tong_don_hang': DonHang.search_count([]),
            'don_hang_hoan_thanh': DonHang.search_count([('trang_thai', '=', 'hoan_thanh')]),
        }
