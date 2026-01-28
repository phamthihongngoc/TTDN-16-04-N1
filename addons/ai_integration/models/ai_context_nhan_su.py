# -*- coding: utf-8 -*-

from odoo import models, api
import logging

_logger = logging.getLogger(__name__)


class AIContextNhanSu(models.AbstractModel):
    """Context Provider cho module Quản lý Nhân sự"""
    _name = 'ai.context.nhan_su'
    _description = 'AI Context Provider - Nhân sự'

    @api.model
    def get_context(self, model, res_id):
        """Lấy context nghiệp vụ cho chatbot"""
        if model == 'nhan_vien':
            return self._get_employee_context(res_id)
        elif model in ['phong_ban', 'nhan_su.phong_ban']:
            return self._get_department_context(res_id)
        elif model == 'cham_cong':
            return self._get_attendance_context(res_id)
        elif model == 'bang_luong':
            return self._get_payroll_context(res_id)
        elif model == 'ho_so.nhan_vien':
            return self._get_employee_document_context(res_id)
        return None

    def _get_employee_context(self, employee_id):
        """Lấy context chi tiết nhân viên"""
        try:
            emp = self.env['nhan_vien'].browse(employee_id)
            if not emp.exists():
                return None
            
            ma_nv = emp.ma_dinh_danh if hasattr(emp, 'ma_dinh_danh') else emp.ma_nhan_vien if hasattr(emp, 'ma_nhan_vien') else 'N/A'
            phone = emp.so_dien_thoai if hasattr(emp, 'so_dien_thoai') else emp.dien_thoai if hasattr(emp, 'dien_thoai') else 'N/A'
            if hasattr(emp, 'trang_thai_lam_viec'):
                status = dict(emp._fields['trang_thai_lam_viec'].selection).get(emp.trang_thai_lam_viec, 'N/A')
            elif hasattr(emp, 'trang_thai'):
                status = dict(emp._fields['trang_thai'].selection).get(emp.trang_thai, 'N/A')
            else:
                status = 'N/A'

            context = f"""NHÂN VIÊN: {emp.display_name}
- Mã NV: {ma_nv}
- Email: {emp.email if hasattr(emp, 'email') else 'N/A'}
- Điện thoại: {phone}
- Phòng ban: {emp.phong_ban_id.display_name if hasattr(emp, 'phong_ban_id') and emp.phong_ban_id else 'N/A'}
- Chức vụ: {emp.chuc_vu_id.display_name if hasattr(emp, 'chuc_vu_id') and emp.chuc_vu_id else 'N/A'}
- Ngày vào làm: {emp.ngay_vao_lam.strftime('%d/%m/%Y') if hasattr(emp, 'ngay_vao_lam') and emp.ngay_vao_lam else 'N/A'}
- Trạng thái: {status}
"""
            
            # Thông tin hợp đồng
            if hasattr(emp, 'loai_hop_dong'):
                context += f"""
HỢP ĐỒNG:
- Loại: {dict(emp._fields['loai_hop_dong'].selection).get(emp.loai_hop_dong, 'N/A') if emp.loai_hop_dong else 'N/A'}
- Lương cơ bản: {emp.luong_co_ban:,.0f} VND
""" if hasattr(emp, 'luong_co_ban') else ""
            
            # Thông tin chấm công tháng hiện tại
            if hasattr(emp, 'cham_cong_ids'):
                from datetime import date
                current_month = date.today().month
                current_year = date.today().year
                
                monthly_attendance = emp.cham_cong_ids.filtered(
                    lambda c: c.ngay.month == current_month and c.ngay.year == current_year if hasattr(c, 'ngay') and c.ngay else False
                )
                
                work_days = len(monthly_attendance.filtered(lambda c: c.trang_thai == 'di_lam' if hasattr(c, 'trang_thai') else False))
                leave_days = len(monthly_attendance.filtered(lambda c: c.trang_thai == 'nghi_phep' if hasattr(c, 'trang_thai') else False))
                
                context += f"""
CHẤM CÔNG THÁNG {current_month}/{current_year}:
- Ngày công: {work_days} ngày
- Nghỉ phép: {leave_days} ngày
"""
            
            # Ghi chú
            if hasattr(emp, 'ghi_chu') and emp.ghi_chu:
                context += f"""
GHI CHÚ: {emp.ghi_chu[:200]}{'...' if len(emp.ghi_chu) > 200 else ''}
"""
            
            return context
            
        except Exception as e:
            _logger.warning(f"Error getting employee context: {e}")
            return None

    def _get_department_context(self, dept_id):
        """Lấy context phòng ban"""
        try:
            dept = self.env['nhan_su.phong_ban'].sudo().browse(dept_id)
            if not dept.exists():
                return None
            
            context = f"""PHÒNG BAN: {dept.display_name}
- Mã PB: {dept.ma_phong_ban if hasattr(dept, 'ma_phong_ban') else 'N/A'}
- Trưởng phòng: {dept.truong_phong_id.display_name if hasattr(dept, 'truong_phong_id') and dept.truong_phong_id else 'Chưa có'}
"""
            
            # Số nhân viên
            employees = self.env['nhan_vien'].sudo().search([('phong_ban_id', '=', dept.id)])
            active_emps = employees.filtered(
                lambda e: e.trang_thai_lam_viec == 'dang_lam'
                if hasattr(e, 'trang_thai_lam_viec') else e.trang_thai == 'dang_lam'
                if hasattr(e, 'trang_thai') else True
            )
            context += f"""
NHÂN SỰ:
- Tổng số: {len(employees)} người
- Đang làm: {len(active_emps)} người
"""
            # Liệt kê nhân viên
            if active_emps[:5]:
                context += "- Danh sách:\n"
                for emp in active_emps[:5]:
                    pos = emp.chuc_vu_id.display_name if hasattr(emp, 'chuc_vu_id') and emp.chuc_vu_id else ''
                    context += f"  • {emp.display_name} - {pos}\n"
                if len(active_emps) > 5:
                    context += f"  ... và {len(active_emps) - 5} người khác\n"
            
            return context
            
        except Exception as e:
            _logger.warning(f"Error getting department context: {e}")
            return None

    def _get_attendance_context(self, attendance_id):
        """Lấy context chấm công"""
        try:
            att = self.env['cham_cong'].browse(attendance_id)
            if not att.exists():
                return None
            
            context = f"""CHẤM CÔNG: {att.display_name}
- Nhân viên: {att.nhan_vien_id.display_name if hasattr(att, 'nhan_vien_id') and att.nhan_vien_id else 'N/A'}
- Ngày: {att.ngay.strftime('%d/%m/%Y') if hasattr(att, 'ngay') and att.ngay else 'N/A'}
- Trạng thái: {dict(att._fields['trang_thai'].selection).get(att.trang_thai, 'N/A') if hasattr(att, 'trang_thai') else 'N/A'}
- Giờ vào: {att.gio_vao if hasattr(att, 'gio_vao') else 'N/A'}
- Giờ ra: {att.gio_ra if hasattr(att, 'gio_ra') else 'N/A'}
"""
            
            if hasattr(att, 'ghi_chu') and att.ghi_chu:
                context += f"- Ghi chú: {att.ghi_chu}\n"
            
            return context
            
        except Exception as e:
            _logger.warning(f"Error getting attendance context: {e}")
            return None

    def _get_payroll_context(self, payroll_id):
        """Lấy context bảng lương"""
        try:
            payroll = self.env['bang_luong'].browse(payroll_id)
            if not payroll.exists():
                return None
            
            context = f"""BẢNG LƯƠNG: {payroll.display_name}
- Nhân viên: {payroll.nhan_vien_id.display_name if hasattr(payroll, 'nhan_vien_id') and payroll.nhan_vien_id else 'N/A'}
- Tháng: {payroll.thang}/{payroll.nam if hasattr(payroll, 'thang') else 'N/A'}
- Lương cơ bản: {payroll.luong_co_ban:,.0f} VND
- Phụ cấp: {payroll.phu_cap:,.0f} VND
- Thưởng: {payroll.thuong:,.0f} VND
- Khấu trừ: {payroll.khau_tru:,.0f} VND
- Thực lĩnh: {payroll.thuc_linh:,.0f} VND
- Trạng thái: {dict(payroll._fields['trang_thai'].selection).get(payroll.trang_thai, 'N/A') if hasattr(payroll, 'trang_thai') else 'N/A'}
"""
            
            return context
            
        except Exception as e:
            _logger.warning(f"Error getting payroll context: {e}")
            return None

    def _get_employee_document_context(self, doc_id):
        """Lấy context hồ sơ nhân viên"""
        try:
            doc = self.env['ho_so.nhan_vien'].browse(doc_id)
            if not doc.exists():
                return None
            
            context = f"""HỒ SƠ: {doc.display_name}
- Nhân viên: {doc.nhan_vien_id.display_name if hasattr(doc, 'nhan_vien_id') and doc.nhan_vien_id else 'N/A'}
- Loại hồ sơ: {dict(doc._fields['loai_ho_so'].selection).get(doc.loai_ho_so, 'N/A') if hasattr(doc, 'loai_ho_so') else 'N/A'}
- Trạng thái: {dict(doc._fields['trang_thai'].selection).get(doc.trang_thai, 'N/A') if hasattr(doc, 'trang_thai') else 'N/A'}
- Ngày nộp: {doc.ngay_nop.strftime('%d/%m/%Y') if hasattr(doc, 'ngay_nop') and doc.ngay_nop else 'N/A'}
"""
            
            return context
            
        except Exception as e:
            _logger.warning(f"Error getting employee document context: {e}")
            return None

    # ==================== QUERY METHODS ====================

    @api.model
    def get_all_employees_summary(self, limit=50):
        """Lấy tổng quan tất cả nhân viên"""
        try:
            employees = self.env['nhan_vien'].sudo().search([], limit=limit, order='create_date desc')
            
            if not employees:
                return "Không có nhân viên nào trong hệ thống."
            
            # Thống kê - check trang_thai_lam_viec first, then trang_thai
            total = len(employees)
            active = len(employees.filtered(
                lambda e: e.trang_thai_lam_viec == 'dang_lam' if hasattr(e, 'trang_thai_lam_viec') else (
                    e.trang_thai == 'dang_lam' if hasattr(e, 'trang_thai') else True
                )
            ))
            
            summary = f"""TỔNG QUAN NHÂN SỰ:
- Tổng số nhân viên: {total}
- Đang làm việc: {active}
- Nghỉ việc/Tạm nghỉ: {total - active}

DANH SÁCH NHÂN VIÊN:
"""
            
            for emp in employees[:20]:
                dept = emp.phong_ban_id.display_name if hasattr(emp, 'phong_ban_id') and emp.phong_ban_id else 'N/A'
                pos = emp.chuc_vu_id.display_name if hasattr(emp, 'chuc_vu_id') and emp.chuc_vu_id else 'N/A'
                if hasattr(emp, 'trang_thai_lam_viec'):
                    status = dict(emp._fields['trang_thai_lam_viec'].selection).get(emp.trang_thai_lam_viec, '')
                elif hasattr(emp, 'trang_thai'):
                    status = dict(emp._fields['trang_thai'].selection).get(emp.trang_thai, '')
                else:
                    status = ''
                summary += f"• {emp.display_name} - {dept} - {pos} ({status})\n"
            
            if total > 20:
                summary += f"\n... và {total - 20} nhân viên khác"
            
            return summary
            
        except Exception as e:
            _logger.warning(f"Error getting employees summary: {e}")
            return f"Lỗi khi truy vấn: {str(e)}"

    @api.model
    def get_all_departments_summary(self):
        """Lấy tổng quan tất cả phòng ban"""
        try:
            departments = self.env['nhan_su.phong_ban'].sudo().search([])
            
            if not departments:
                return "Không có phòng ban nào trong hệ thống."
            
            summary = f"""TỔNG QUAN PHÒNG BAN ({len(departments)} phòng ban):

"""
            
            for dept in departments:
                manager = dept.truong_phong_id.display_name if hasattr(dept, 'truong_phong_id') and dept.truong_phong_id else 'Chưa có'
                employees = self.env['nhan_vien'].sudo().search([('phong_ban_id', '=', dept.id)])
                emp_count = len(employees)
                summary += f"• {dept.display_name}\n"
                summary += f"  - Trưởng phòng: {manager}\n"
                summary += f"  - Số nhân viên: {emp_count}\n\n"
            
            return summary
            
        except Exception as e:
            _logger.warning(f"Error getting departments summary: {e}")
            return f"Lỗi khi truy vấn: {str(e)}"

    @api.model  
    def get_attendance_report(self, month=None, year=None):
        """Lấy báo cáo chấm công"""
        try:
            from datetime import date
            if not month:
                month = date.today().month
            if not year:
                year = date.today().year
            
            # Search attendance records for the month
            domain = [
                ('ngay', '>=', f'{year}-{month:02d}-01'),
                ('ngay', '<', f'{year}-{month+1:02d}-01' if month < 12 else f'{year+1}-01-01')
            ]
            
            attendances = self.env['cham_cong'].search(domain)
            
            if not attendances:
                return f"Không có dữ liệu chấm công tháng {month}/{year}"
            
            # Group by employee
            emp_data = {}
            for att in attendances:
                emp_name = att.nhan_vien_id.display_name if att.nhan_vien_id else 'Unknown'
                if emp_name not in emp_data:
                    emp_data[emp_name] = {'work': 0, 'leave': 0, 'absent': 0, 'late': 0}
                
                status = att.trang_thai if hasattr(att, 'trang_thai') else 'di_lam'
                if status == 'di_lam':
                    emp_data[emp_name]['work'] += 1
                elif status == 'nghi_phep':
                    emp_data[emp_name]['leave'] += 1
                elif status == 'vang_mat':
                    emp_data[emp_name]['absent'] += 1
                    
                if hasattr(att, 'di_tre') and att.di_tre:
                    emp_data[emp_name]['late'] += 1
            
            summary = f"""BÁO CÁO CHẤM CÔNG THÁNG {month}/{year}

"""
            for emp_name, data in emp_data.items():
                summary += f"• {emp_name}: Công {data['work']} ngày, Nghỉ phép {data['leave']}, Vắng {data['absent']}"
                if data['late'] > 0:
                    summary += f", Đi trễ {data['late']} lần"
                summary += "\n"
            
            return summary
            
        except Exception as e:
            _logger.warning(f"Error getting attendance report: {e}")
            return f"Lỗi khi truy vấn: {str(e)}"

    @api.model
    def search_employees(self, keyword):
        """Tìm kiếm nhân viên theo từ khóa"""
        try:
            employee_model = self.env['nhan_vien']
            fields_map = employee_model._fields
            or_parts = []
            if 'ten_nv' in fields_map:
                or_parts.append(('ten_nv', 'ilike', keyword))
            if 'name' in fields_map:
                or_parts.append(('name', 'ilike', keyword))
            if 'ma_dinh_danh' in fields_map:
                or_parts.append(('ma_dinh_danh', 'ilike', keyword))
            if 'ma_nhan_vien' in fields_map:
                or_parts.append(('ma_nhan_vien', 'ilike', keyword))
            if 'email' in fields_map:
                or_parts.append(('email', 'ilike', keyword))
            if 'so_dien_thoai' in fields_map:
                or_parts.append(('so_dien_thoai', 'ilike', keyword))
            if 'dien_thoai' in fields_map:
                or_parts.append(('dien_thoai', 'ilike', keyword))

            if not or_parts:
                return "Không thể tìm kiếm vì thiếu trường dữ liệu phù hợp."

            domain = ['|'] * (len(or_parts) - 1)
            domain += or_parts
            
            employees = self.env['nhan_vien'].sudo().search(domain, limit=20)
            
            if not employees:
                return f"Không tìm thấy nhân viên với từ khóa: {keyword}"
            
            result = f"TÌM THẤY {len(employees)} NHÂN VIÊN:\n\n"
            
            for emp in employees:
                dept = emp.phong_ban_id.display_name if hasattr(emp, 'phong_ban_id') and emp.phong_ban_id else 'N/A'
                email = emp.email if hasattr(emp, 'email') else 'N/A'
                phone = emp.so_dien_thoai if hasattr(emp, 'so_dien_thoai') else emp.dien_thoai if hasattr(emp, 'dien_thoai') else 'N/A'
                ma_nv = emp.ma_dinh_danh if hasattr(emp, 'ma_dinh_danh') else emp.ma_nhan_vien if hasattr(emp, 'ma_nhan_vien') else 'N/A'
                
                result += f"• **{emp.display_name}**\n"
                result += f"  - Mã NV: {ma_nv}\n"
                result += f"  - Phòng ban: {dept}\n"
                result += f"  - Email: {email}\n"
                result += f"  - ĐT: {phone}\n\n"
            
            return result
            
        except Exception as e:
            _logger.warning(f"Error searching employees: {e}")
            return f"Lỗi khi tìm kiếm: {str(e)}"
