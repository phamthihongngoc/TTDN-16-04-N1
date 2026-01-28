# -*- coding: utf-8 -*-

from odoo import models, fields, api
import json
import logging

_logger = logging.getLogger(__name__)


class AIChatTool(models.Model):
    """Định nghĩa các tools có thể gọi từ chatbot"""
    _name = 'ai.chat.tool'
    _description = 'AI Chat Tool Definition'
    _order = 'module, sequence, name'

    name = fields.Char(
        string='Tên Tool',
        required=True,
        help='Tên function (snake_case, vd: search_customer)'
    )
    display_name = fields.Char(
        string='Tên hiển thị',
        required=True
    )
    description = fields.Text(
        string='Mô tả',
        required=True,
        help='Mô tả chi tiết để AI hiểu khi nào dùng tool này'
    )
    
    module = fields.Selection([
        ('khach_hang', 'Quản lý Khách hàng'),
        ('van_ban', 'Quản lý Văn bản'),
        ('nhan_su', 'Quản lý Nhân sự'),
        ('general', 'Chung'),
    ], string='Module', required=True, default='general')
    
    # Schema cho function calling
    parameters_schema = fields.Text(
        string='Parameters Schema',
        help='JSON Schema cho parameters (OpenAI function calling format)',
        default='{}'
    )
    
    # Execution
    model_name = fields.Char(
        string='Model thực thi',
        help='Odoo model chứa method thực thi (vd: ai.chat.tool.khach_hang)'
    )
    method_name = fields.Char(
        string='Method thực thi',
        help='Tên method trong model (vd: tool_search_customer)'
    )
    
    # Permissions & Flags
    requires_confirmation = fields.Boolean(
        string='Cần xác nhận',
        default=False,
        help='Yêu cầu user xác nhận trước khi thực thi (cho create/write/send)'
    )
    is_read_only = fields.Boolean(
        string='Chỉ đọc',
        default=True,
        help='Tool chỉ đọc dữ liệu, không thay đổi'
    )
    required_group_id = fields.Many2one(
        'res.groups',
        string='Nhóm quyền yêu cầu',
        help='User phải thuộc nhóm này để dùng tool'
    )
    
    # UI
    sequence = fields.Integer(
        string='Thứ tự',
        default=10
    )
    active = fields.Boolean(
        string='Active',
        default=True
    )
    icon = fields.Char(
        string='Icon',
        default='fa-cog',
        help='Font Awesome icon class'
    )
    color = fields.Integer(
        string='Màu',
        default=0
    )
    
    # Quick suggestion
    is_quick_action = fields.Boolean(
        string='Gợi ý nhanh',
        default=False,
        help='Hiển thị như nút gợi ý nhanh trong chat'
    )
    quick_action_label = fields.Char(
        string='Label gợi ý',
        help='Text hiển thị trên nút gợi ý'
    )
    quick_action_prompt = fields.Text(
        string='Prompt gợi ý',
        help='Prompt tự động gửi khi click'
    )
    
    # Applicable contexts
    applicable_models = fields.Char(
        string='Models áp dụng',
        help='Danh sách models (comma-separated) mà tool này áp dụng'
    )

    _sql_constraints = [
        ('name_module_unique', 'unique(name, module)', 'Tên tool phải duy nhất trong mỗi module!')
    ]

    def get_openai_schema(self):
        """Trả về schema theo format OpenAI function calling"""
        self.ensure_one()
        try:
            params = json.loads(self.parameters_schema) if self.parameters_schema else {}
        except json.JSONDecodeError:
            params = {"type": "object", "properties": {}}
        
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": params,
            }
        }

    def execute(self, arguments, session=None):
        """Thực thi tool với arguments"""
        self.ensure_one()
        
        # Check permission
        if self.required_group_id:
            try:
                xml_ids = self.required_group_id.get_full_xml_id()
                group_xml_id = xml_ids.get(self.required_group_id.id, '')
                if group_xml_id and not self.env.user.has_group(group_xml_id):
                    return {
                        'success': False,
                        'error': f'Bạn không có quyền sử dụng tool: {self.display_name}'
                    }
            except Exception as e:
                _logger.warning(f"Error checking permission for tool {self.name}: {e}")
        
        # Find and call method
        if not self.model_name or not self.method_name:
            return {
                'success': False,
                'error': f'Tool {self.name} chưa được cấu hình method thực thi'
            }
        
        try:
            # Check if model exists
            if self.model_name not in self.env:
                return {
                    'success': False,
                    'error': f'Model {self.model_name} không tồn tại'
                }
            
            model = self.env[self.model_name]
            method = getattr(model, self.method_name, None)
            
            if not method:
                return {
                    'success': False,
                    'error': f'Không tìm thấy method {self.method_name} trong {self.model_name}'
                }
            
            # Call method with session context
            result = method(arguments, session=session)
            
            # Check if result contains error
            if isinstance(result, dict) and result.get('error'):
                return {
                    'success': False,
                    'error': result['error'],
                    'data': result,
                }
            
            return {
                'success': True,
                'data': result,
                'requires_confirmation': self.requires_confirmation,
            }
            
        except Exception as e:
            _logger.exception(f"Error executing tool {self.name}")
            return {
                'success': False,
                'error': str(e)
            }

    def is_applicable_for_model(self, model_name):
        """Kiểm tra tool có áp dụng cho model không"""
        if not self.applicable_models:
            return True  # Áp dụng cho tất cả
        
        applicable = [m.strip() for m in self.applicable_models.split(',')]
        return model_name in applicable

    @api.model
    def get_tools_for_context(self, module=None, active_model=None):
        """Lấy danh sách tools phù hợp với context"""
        domain = [('active', '=', True)]
        
        # Nếu có module cụ thể, lấy tools của module đó + general
        # Nếu không, lấy TẤT CẢ tools active
        if module:
            domain.append(('module', 'in', [module, 'general']))
        # Không filter theo module nếu module=None -> lấy tất cả tools
        
        tools = self.search(domain)
        
        # KHÔNG filter theo applicable_models nữa để cho phép truy vấn cross-module
        # AI sẽ tự quyết định tool nào phù hợp
        
        # Filter by user permission (with error handling)
        def check_permission(t):
            if not t.required_group_id:
                return True
            try:
                xml_ids = t.required_group_id.get_full_xml_id()
                group_xml_id = xml_ids.get(t.required_group_id.id, '')
                return self.env.user.has_group(group_xml_id) if group_xml_id else True
            except Exception:
                return True  # Allow if can't check
        
        tools = tools.filtered(check_permission)
        
        return tools

    @api.model
    def get_quick_actions_for_context(self, module=None, active_model=None):
        """Lấy các quick actions cho UI"""
        tools = self.get_tools_for_context(module, active_model)
        quick_tools = tools.filtered(lambda t: t.is_quick_action)
        
        return [{
            'id': t.id,
            'name': t.name,
            'label': t.quick_action_label or t.display_name,
            'prompt': t.quick_action_prompt,
            'icon': t.icon,
        } for t in quick_tools]
