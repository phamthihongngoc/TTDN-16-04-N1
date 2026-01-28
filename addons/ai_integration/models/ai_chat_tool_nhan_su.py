# -*- coding: utf-8 -*-

from odoo import models, api
import json
import logging
from datetime import date, datetime

_logger = logging.getLogger(__name__)


class AIChatToolNhanSu(models.AbstractModel):
    """
    Tập hợp các tools cho module Quản lý Nhân sự
    Được gọi bởi AI Chat Orchestrator khi LLM yêu cầu
    """
    _name = 'ai.chat.tool.nhan_su'
    _description = 'AI Chat Tools - Nhân sự'

    # ==================== SEARCH & READ TOOLS ====================

    @api.model
    def tool_search_employee(self, arguments, session=None):
        """
        Tìm kiếm nhân viên theo query
        
        Arguments:
            query: Từ khóa tìm kiếm (tên, mã, email, SĐT)
            limit: Số lượng kết quả tối đa
        """
        query = arguments.get('query', '')
        limit = arguments.get('limit', 20)
        
        try:
            provider = self.env['ai.context.nhan_su']
            result = provider.search_employees(query)
            return result
        except Exception as e:
            _logger.error(f"Error in tool_search_employee: {e}")
            return {'error': str(e)}

    @api.model
    def tool_get_employee_info(self, arguments, session=None):
        """
        Lấy thông tin chi tiết nhân viên
        
        Arguments:
            employee_id: ID nhân viên
            ma_nhan_vien: Mã nhân viên (nếu không có ID)
        """
        employee_id = arguments.get('employee_id')
        ma_nhan_vien = arguments.get('ma_nhan_vien') or arguments.get('ma_dinh_danh')
        
        # If no employee_id, try to get from session context
        if not employee_id and not ma_nhan_vien and session:
            if session.active_model == 'nhan_vien':
                employee_id = session.active_res_id
        
        try:
            if employee_id:
                emp = self.env['nhan_vien'].sudo().browse(int(employee_id))
            elif ma_nhan_vien:
                emp = self.env['nhan_vien'].sudo().search([('ma_dinh_danh', '=', ma_nhan_vien)], limit=1)
            else:
                return {'error': 'Cần cung cấp employee_id hoặc ma_nhan_vien'}
            
            if not emp.exists():
                return {'error': 'Không tìm thấy nhân viên'}
            
            provider = self.env['ai.context.nhan_su']
            return provider.get_context('nhan_vien', emp.id)
            
        except Exception as e:
            _logger.error(f"Error in tool_get_employee_info: {e}")
            return {'error': str(e)}

    @api.model
    def tool_get_all_employees(self, arguments, session=None):
        """
        Lấy danh sách tất cả nhân viên
        
        Arguments:
            department: Lọc theo tên phòng ban (tùy chọn)
            status: Lọc theo trạng thái (dang_lam, nghi_viec, tam_nghi)
            limit: Số lượng tối đa
        """
        department = arguments.get('department')
        status = arguments.get('status')
        limit = arguments.get('limit', 50)
        
        try:
            provider = self.env['ai.context.nhan_su']
            return provider.get_all_employees_summary(limit)
        except Exception as e:
            _logger.error(f"Error in tool_get_all_employees: {e}")
            return {'error': str(e)}

    @api.model
    def tool_get_departments_summary(self, arguments, session=None):
        """
        Lấy tổng quan tất cả phòng ban
        
        Arguments: None
        """
        try:
            provider = self.env['ai.context.nhan_su']
            return provider.get_all_departments_summary()
        except Exception as e:
            _logger.error(f"Error in tool_get_departments_summary: {e}")
            return {'error': str(e)}

    @api.model
    def tool_get_department_info(self, arguments, session=None):
        """
        Lấy thông tin chi tiết phòng ban
        
        Arguments:
            department_id: ID phòng ban
            department_name: Tên phòng ban (nếu không có ID)
        """
        department_id = arguments.get('department_id')
        department_name = arguments.get('department_name')
        
        # If no dept_id, try to get from session context
        if not department_id and not department_name and session:
            if session.active_model in ['phong_ban', 'nhan_su.phong_ban']:
                department_id = session.active_res_id
        
        try:
            if department_id:
                dept = self.env['nhan_su.phong_ban'].sudo().browse(int(department_id))
            elif department_name:
                dept = self.env['nhan_su.phong_ban'].sudo().search([('name', 'ilike', department_name)], limit=1)
            else:
                return {'error': 'Cần cung cấp department_id hoặc department_name'}
            
            if not dept.exists():
                return {'error': 'Không tìm thấy phòng ban'}
            
            provider = self.env['ai.context.nhan_su']
            return provider.get_context('nhan_su.phong_ban', dept.id)
            
        except Exception as e:
            _logger.error(f"Error in tool_get_department_info: {e}")
            return {'error': str(e)}

    @api.model
    def tool_get_attendance_report(self, arguments, session=None):
        """
        Lấy báo cáo chấm công theo tháng
        
        Arguments:
            month: Tháng (1-12), mặc định tháng hiện tại
            year: Năm, mặc định năm hiện tại
            employee_id: ID nhân viên cụ thể (tùy chọn)
        """
        month = arguments.get('month', date.today().month)
        year = arguments.get('year', date.today().year)
        employee_id = arguments.get('employee_id')
        
        try:
            provider = self.env['ai.context.nhan_su']
            return provider.get_attendance_report(month, year)
        except Exception as e:
            _logger.error(f"Error in tool_get_attendance_report: {e}")
            return {'error': str(e)}

    @api.model
    def tool_get_hr_statistics(self, arguments, session=None):
        """
        Lấy thống kê tổng quan nhân sự
        
        Arguments: None
        """
        try:
            employees = self.env['nhan_vien'].sudo().search([])
            departments = self.env['nhan_su.phong_ban'].sudo().search([])
            
            total = len(employees)
            active = len(employees.filtered(
                lambda e: e.trang_thai_lam_viec == 'dang_lam'
                if hasattr(e, 'trang_thai_lam_viec') else e.trang_thai == 'dang_lam'
                if hasattr(e, 'trang_thai') else True
            ))
            
            # Contract types
            contract_stats = {}
            for emp in employees:
                if hasattr(emp, 'loai_hop_dong') and emp.loai_hop_dong:
                    try:
                        ct = dict(emp._fields['loai_hop_dong'].selection).get(emp.loai_hop_dong, 'Khác')
                    except:
                        ct = str(emp.loai_hop_dong)
                    contract_stats[ct] = contract_stats.get(ct, 0) + 1
            
            # Department distribution
            dept_stats = {}
            for emp in employees:
                if hasattr(emp, 'trang_thai_lam_viec') and emp.trang_thai_lam_viec != 'dang_lam':
                    continue
                if hasattr(emp, 'trang_thai') and emp.trang_thai != 'dang_lam':
                    continue
                dept = emp.phong_ban_id.display_name if hasattr(emp, 'phong_ban_id') and emp.phong_ban_id else 'Chưa phân phòng'
                dept_stats[dept] = dept_stats.get(dept, 0) + 1
            
            return {
                'summary': {
                    'total_employees': total,
                    'active_employees': active,
                    'inactive_employees': total - active,
                    'total_departments': len(departments),
                },
                'contract_distribution': contract_stats,
                'department_distribution': dept_stats,
                'message': f'Thống kê nhân sự: {total} nhân viên, {len(departments)} phòng ban'
            }
            
        except Exception as e:
            _logger.error(f"Error in tool_get_hr_statistics: {e}")
            return {'error': str(e)}

    @api.model
    def tool_get_payroll_info(self, arguments, session=None):
        """
        Lấy thông tin bảng lương
        
        Arguments:
            employee_id: ID nhân viên (tùy chọn)
            month: Tháng
            year: Năm
        """
        employee_id = arguments.get('employee_id')
        month = arguments.get('month', date.today().month)
        year = arguments.get('year', date.today().year)
        
        try:
            domain = []
            
            # Try different field names for month/year
            if 'bang_luong' in self.env:
                Bang_Luong = self.env['bang_luong']
                if 'thang' in Bang_Luong._fields:
                    domain.append(('thang', '=', month))
                if 'nam' in Bang_Luong._fields:
                    domain.append(('nam', '=', year))
                if employee_id and 'nhan_vien_id' in Bang_Luong._fields:
                    domain.append(('nhan_vien_id', '=', int(employee_id)))
                
                payrolls = Bang_Luong.search(domain, limit=50)
                
                if not payrolls:
                    return {'message': f'Không có dữ liệu bảng lương tháng {month}/{year}'}
                
                result = []
                total_salary = 0
                for p in payrolls:
                    emp_name = p.nhan_vien_id.display_name if p.nhan_vien_id else 'N/A'
                    net = p.thuc_linh if hasattr(p, 'thuc_linh') else 0
                    total_salary += net
                    result.append({
                        'employee': emp_name,
                        'net_salary': net,
                    })
                
                return {
                    'month': month,
                    'year': year,
                    'payrolls': result,
                    'total_salary': total_salary,
                    'message': f'Bảng lương tháng {month}/{year}: {len(payrolls)} nhân viên, tổng chi {total_salary:,.0f} VND'
                }
            else:
                return {'error': 'Module bang_luong chưa được cài đặt'}
            
        except Exception as e:
            _logger.error(f"Error in tool_get_payroll_info: {e}")
            return {'error': str(e)}

    @api.model  
    def tool_employee_count_by_department(self, arguments, session=None):
        """
        Đếm số nhân viên theo phòng ban
        
        Arguments: None
        """
        try:
            department_name = arguments.get('department_name')
            dept_model = self.env['nhan_su.phong_ban'].sudo()
            if department_name:
                departments = dept_model.search([('name', 'ilike', department_name)])
            else:
                departments = dept_model.search([])
            result = []
            employee_model = self.env['nhan_vien'].sudo()
            fields_map = employee_model._fields

            if department_name and not departments:
                if 'phong_ban' in fields_map:
                    count = employee_model.search_count([('phong_ban', 'ilike', department_name)])
                    return {
                        'departments': [{'department': department_name, 'count': count}],
                        'message': f'Không tìm thấy phòng ban, đếm theo tên văn bản: {department_name}'
                    }
                return {'error': f'Không tìm thấy phòng ban: {department_name}'}

            for dept in departments:
                count_domain = []
                if 'phong_ban_id' in fields_map:
                    count_domain = [('phong_ban_id', '=', dept.id)]
                if 'phong_ban' in fields_map:
                    if count_domain:
                        count_domain = ['|'] + count_domain + [('phong_ban', 'ilike', dept.name)]
                    else:
                        count_domain = [('phong_ban', 'ilike', dept.name)]

                if 'trang_thai_lam_viec' in fields_map:
                    count_domain.append(('trang_thai_lam_viec', '=', 'dang_lam'))
                elif 'trang_thai' in fields_map:
                    count_domain.append(('trang_thai', '=', 'dang_lam'))

                count = employee_model.search_count(count_domain)
                result.append({
                    'department': dept.display_name,
                    'count': count,
                })
            
            return {
                'departments': sorted(result, key=lambda x: -x['count']),
                'message': f'Có {len(departments)} phòng ban'
            }
            
        except Exception as e:
            _logger.error(f"Error in tool_employee_count_by_department: {e}")
            return {'error': str(e)}
