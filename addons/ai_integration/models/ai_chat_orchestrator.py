# -*- coding: utf-8 -*-

from odoo import models, api
import json
import time
import logging

_logger = logging.getLogger(__name__)


class AIChatOrchestrator(models.AbstractModel):
    """
    Orchestrator điều phối hội thoại chatbot
    - Quản lý context
    - Gọi LLM với function calling
    - Thực thi tools
    - Xử lý luồng confirm
    """
    _name = 'ai.chat.orchestrator'
    _description = 'AI Chat Orchestrator'

    # ==================== MAIN ENTRY POINTS ====================

    @api.model
    def send_message(self, session_id, user_message, context=None):
        """
        Gửi tin nhắn và nhận phản hồi từ AI
        
        Args:
            session_id: ID của ai.chat.session
            user_message: Nội dung tin nhắn từ user
            context: Dict chứa active_model, active_res_id, etc.
            
        Returns:
            Dict với response từ AI, tool results, pending actions
        """
        context = context or {}
        start_time = time.time()
        
        try:
            # Get/validate session
            session = self.env['ai.chat.session'].browse(session_id)
            if not session.exists():
                return self._error_response("Session không tồn tại")
            
            # Update session context if provided
            if context.get('active_model'):
                module = context.get('module') or session._infer_module_from_model(context.get('active_model'))
                values = {
                    'active_model': context.get('active_model'),
                    'active_res_id': context.get('active_res_id'),
                }
                if module:
                    values['module'] = module
                session.write(values)
            
            # Create user message
            self.env['ai.chat.message'].create_user_message(
                session_id=session.id,
                content=user_message,
                context_model=context.get('active_model'),
                context_res_id=context.get('active_res_id'),
            )
            
            # Build full prompt with context
            messages = self._build_messages(session, user_message, context)
            
            # Get available tools (catch errors here)
            try:
                tools = self._get_tools_for_session(session, context)
                tools_schema = [t.get_openai_schema() for t in tools] if tools else []
            except Exception as e:
                _logger.warning(f"Error getting tools: {e}")
                tools = []
                tools_schema = []
            
            # Call LLM
            ai_service = self.env['ai.service']
            try:
                response = ai_service.chat_completion_with_tools(
                    messages=messages,
                    tools=tools_schema if tools_schema else None,
                    temperature=0.2,
                )
            except Exception as e:
                _logger.exception("Error calling AI service")
                return self._error_response(f"Lỗi gọi AI: {str(e)}")
            
            if not response.get('success'):
                return self._error_response(response.get('error', 'Lỗi gọi AI'))
            
            # Process response
            result = self._process_llm_response(session, response, tools, context)
            
            # Update session activity
            session.update_activity()
            
            latency = (time.time() - start_time) * 1000
            result['latency'] = latency
            
            return result
            
        except Exception as e:
            _logger.exception("Error in send_message")
            return self._error_response(str(e))

    @api.model
    def confirm_action(self, session_id, message_id):
        """Xác nhận thực hiện action đang pending"""
        try:
            message = self.env['ai.chat.message'].browse(message_id)
            if not message.exists() or message.session_id.id != session_id:
                return self._error_response("Message không hợp lệ")
            
            result = message.confirm_action()
            
            if result.get('success'):
                # Clear pending action from session
                message.session_id.clear_pending_action()
                
                # Create follow-up message about result
                action_result = result.get('result', {})
                if action_result.get('message'):
                    self.env['ai.chat.message'].create_assistant_message(
                        session_id=session_id,
                        content=action_result['message'],
                    )
            
            return result
            
        except Exception as e:
            _logger.exception("Error confirming action")
            return self._error_response(str(e))

    @api.model
    def reject_action(self, session_id, message_id):
        """Từ chối action đang pending"""
        try:
            message = self.env['ai.chat.message'].browse(message_id)
            if not message.exists() or message.session_id.id != session_id:
                return self._error_response("Message không hợp lệ")
            
            return message.reject_action()
            
        except Exception as e:
            return self._error_response(str(e))

    @api.model
    def execute_confirmed_action(self, action_type, payload, session):
        """Thực thi action đã được confirm"""
        # Route to appropriate handler based on action_type
        handler_map = {
            'create_support_ticket': self._action_create_support_ticket,
            'create_outgoing_document': self._action_create_outgoing_document,
            'send_email': self._action_send_email,
            'update_record': self._action_update_record,
        }
        
        handler = handler_map.get(action_type)
        if not handler:
            return {'success': False, 'error': f'Unknown action type: {action_type}'}
        
        return handler(payload, session)

    # ==================== MESSAGE BUILDING ====================

    def _build_messages(self, session, user_message, context):
        """Xây dựng messages array cho LLM"""
        messages = []
        
        # System prompt
        system_prompt = self._get_system_prompt(session, context)
        messages.append({
            "role": "system",
            "content": system_prompt
        })
        
        # Add business context
        business_context = self._get_business_context(session, context)
        if business_context:
            messages.append({
                "role": "system",
                "content": f"[CONTEXT]\n{business_context}"
            })
        
        # Add conversation history
        history = session.get_conversation_history(limit=10)
        messages.extend(history)
        
        # Add current user message (if not already in history)
        if not history or history[-1].get('content') != user_message:
            messages.append({
                "role": "user",
                "content": user_message
            })
        
        return messages

    def _get_system_prompt(self, session, context):
        """Tạo system prompt theo context"""
        active_model = session.active_model or context.get('active_model')
        
        base_prompt = """Bạn là trợ lý AI thông minh trong hệ thống quản lý doanh nghiệp Odoo.

NGUYÊN TẮC:
- Trả lời bằng tiếng Việt, ngắn gọn, chuyên nghiệp
- Sử dụng tools khi cần truy vấn hoặc thao tác dữ liệu
- KHÔNG bịa dữ liệu - chỉ trả lời dựa trên thông tin từ tools
- Với câu hỏi cần số liệu, danh sách, trạng thái, thống kê: BẮT BUỘC gọi tool để truy vấn dữ liệu trước khi trả lời
- Với các thao tác ghi dữ liệu (tạo, sửa, gửi), phải xác nhận với user trước
- Khi không chắc chắn, hãy hỏi lại để làm rõ

PHẠM VI DỮ LIỆU:
- Có thể truy vấn dữ liệu của cả 3 module: Khách hàng, Văn bản, Nhân sự

CÁCH SỬ DỤNG TOOLS:
- Dùng tool để tìm kiếm, đọc dữ liệu trước khi trả lời
- Giải thích kết quả tool cho user một cách dễ hiểu
- Nếu tool trả về lỗi, thông báo cho user và gợi ý cách khác

ĐỊNH DẠNG OUTPUT:
- Sử dụng bullet points cho danh sách
- Highlight thông tin quan trọng bằng **bold**
- Chia đoạn rõ ràng cho câu trả lời dài
"""
        
        # Add module-specific instructions
        # Get module from session first
        module = session.module
        if not module and active_model:
            if 'khach_hang' in active_model or 'don_hang' in active_model or 'ho_tro' in active_model:
                module = 'khach_hang'
            elif 'van_ban' in active_model:
                module = 'van_ban'
            elif 'nhan_vien' in active_model or 'phong_ban' in active_model or 'cham_cong' in active_model or 'bang_luong' in active_model:
                module = 'nhan_su'
        
        if module == 'khach_hang':
            base_prompt += """

CONTEXT: Quản lý Khách hàng
Bạn có thể truy vấn dữ liệu KHÁCH HÀNG:
- Tìm kiếm, tóm tắt thông tin khách hàng
- Xem lịch sử đơn hàng, hỗ trợ
- Soạn email chăm sóc/nhắc việc
- Tạo phiếu hỗ trợ (cần xác nhận)
- Đề xuất bước tiếp theo với khách hàng

LƯU Ý: Khi cần dữ liệu cụ thể, hãy gọi tool trước khi trả lời.
"""
        elif module == 'van_ban':
            base_prompt += """

CONTEXT: Quản lý Văn bản
Bạn có thể truy vấn dữ liệu VĂN BẢN:
- Tóm tắt nội dung văn bản
- Trích xuất thông tin (người, cơ quan, deadline...)
- Phân loại văn bản
- Soạn văn bản đi từ văn bản đến (cần xác nhận)
- Đề xuất luồng xử lý/ký duyệt
- Tạo checklist việc cần làm

LƯU Ý: Khi cần dữ liệu cụ thể, hãy gọi tool trước khi trả lời.
"""
        elif module == 'nhan_su':
            base_prompt += """

CONTEXT: Quản lý Nhân sự
Bạn có thể truy vấn dữ liệu NHÂN SỰ:
- Tra cứu thông tin nhân viên (họ tên, phòng ban, chức vụ, liên hệ)
- Xem cơ cấu phòng ban, số lượng nhân viên
- Kiểm tra chấm công, nghỉ phép
- Xem thông tin bảng lương (nếu được phép)
- Thống kê nhân sự theo phòng ban, loại hợp đồng
- Tìm kiếm nhân viên theo tên, mã NV, email, SĐT
- Báo cáo chấm công theo tháng

LƯU Ý: Khi cần dữ liệu cụ thể, hãy gọi tool trước khi trả lời.
"""
        
        return base_prompt

    def _get_business_context(self, session, context):
        """Lấy context nghiệp vụ từ record hiện tại"""
        active_model = session.active_model or context.get('active_model')
        active_res_id = session.active_res_id or context.get('active_res_id')
        
        if not active_model or not active_res_id:
            return None
        
        try:
            # Get context provider based on session.module first
            module = session.module
            
            if module == 'khach_hang':
                provider = self.env['ai.context.khach_hang']
                return provider.get_context(active_model, active_res_id)
            elif module == 'van_ban':
                provider = self.env['ai.context.van_ban']
                return provider.get_context(active_model, active_res_id)
            elif module == 'nhan_su':
                provider = self.env['ai.context.nhan_su']
                return provider.get_context(active_model, active_res_id)
            elif 'khach_hang' in active_model or 'don_hang' in active_model or 'ho_tro' in active_model:
                provider = self.env['ai.context.khach_hang']
                return provider.get_context(active_model, active_res_id)
            elif 'van_ban' in active_model:
                provider = self.env['ai.context.van_ban']
                return provider.get_context(active_model, active_res_id)
            elif 'nhan_vien' in active_model or 'phong_ban' in active_model or 'cham_cong' in active_model or 'bang_luong' in active_model or 'hop_dong' in active_model:
                provider = self.env['ai.context.nhan_su']
                return provider.get_context(active_model, active_res_id)
            else:
                # Generic context
                record = self.env[active_model].browse(active_res_id)
                if record.exists():
                    return f"Đang xem: {record.display_name} (Model: {active_model})"
                
        except Exception as e:
            _logger.warning(f"Error getting business context: {e}")
        
        return None

    # ==================== TOOLS ====================

    def _get_tools_for_session(self, session, context):
        """Lấy tools phù hợp với session context"""
        active_model = session.active_model or context.get('active_model', '') or ''
        
        try:
            return self.env['ai.chat.tool'].get_tools_for_context(
                module=None,
                active_model=active_model
            )
        except Exception as e:
            _logger.warning(f"Error getting tools for context: {e}")
            return self.env['ai.chat.tool']  # Empty recordset

    def _process_llm_response(self, session, response, tools, context):
        """Xử lý response từ LLM"""
        data = response.get('data', {})
        message = data.get('message', {})
        content = message.get('content', '')
        tool_calls = message.get('tool_calls', [])
        tokens_info = data.get('usage', {})
        
        # If there are tool calls, execute them
        if tool_calls:
            return self._handle_tool_calls(session, tool_calls, tools, tokens_info, context)
        
        # No tool calls - just a text response
        msg = self.env['ai.chat.message'].create_assistant_message(
            session_id=session.id,
            content=content,
            tokens_info=tokens_info,
            model_used=data.get('model'),
        )
        
        return {
            'success': True,
            'message': content,
            'message_id': msg.id,
            'tokens': tokens_info,
        }

    def _handle_tool_calls(self, session, tool_calls, tools, tokens_info, context):
        """Xử lý và thực thi tool calls"""
        tool_results = []
        requires_confirmation = False
        pending_action = None
        
        # Map tools by name
        tools_by_name = {t.name: t for t in tools}
        
        for call in tool_calls:
            func = call.get('function', {})
            tool_name = func.get('name')
            tool_call_id = call.get('id')
            
            try:
                arguments = json.loads(func.get('arguments', '{}'))
            except json.JSONDecodeError:
                arguments = {}
            
            tool = tools_by_name.get(tool_name)
            if not tool:
                result = {'success': False, 'error': f'Tool không tìm thấy: {tool_name}'}
            else:
                # Add context to arguments
                arguments['_context'] = {
                    'active_model': session.active_model,
                    'active_res_id': session.active_res_id,
                    'user_id': self.env.uid,
                }
                
                result = tool.execute(arguments, session=session)
                
                # Check if requires confirmation
                if result.get('requires_confirmation') and result.get('success'):
                    requires_confirmation = True
                    pending_action = {
                        'type': tool_name,
                        'data': result.get('data', {}),
                    }
            
            # Store tool result
            self.env['ai.chat.message'].create_tool_result_message(
                session_id=session.id,
                tool_name=tool_name,
                tool_call_id=tool_call_id,
                arguments=arguments,
                result=result,
            )
            
            tool_results.append({
                'tool_call_id': tool_call_id,
                'name': tool_name,
                'result': result,
            })
        
        # If requires confirmation, save pending and ask user
        if requires_confirmation and pending_action:
            session.set_pending_action(
                pending_action['type'],
                pending_action['data']
            )
            
            # Create message asking for confirmation
            preview = pending_action['data'].get('preview', 'Thao tác cần xác nhận')
            msg = self.env['ai.chat.message'].create_action_message(
                session_id=session.id,
                content=f"**Xác nhận thao tác:**\n\n{preview}\n\nBạn có muốn thực hiện không?",
                action_type=pending_action['type'],
                action_payload=pending_action['data'],
            )
            
            return {
                'success': True,
                'message': msg.content,
                'message_id': msg.id,
                'requires_confirmation': True,
                'action_type': pending_action['type'],
                'preview': preview,
                'tokens': tokens_info,
            }
        
        # Call LLM again with tool results to get final response
        return self._get_final_response_after_tools(session, tool_results, tokens_info, context)

    def _get_final_response_after_tools(self, session, tool_results, tokens_info, context):
        """Gọi LLM lần nữa với kết quả tools để có câu trả lời cuối"""
        messages = []
        
        # System prompt
        messages.append({
            "role": "system",
            "content": self._get_system_prompt(session, context)
        })
        
        # Conversation history including tool results
        history = session.get_conversation_history(limit=15)
        messages.extend(history)
        
        # Add tool results as context
        tool_context = "Kết quả từ tools:\n"
        for tr in tool_results:
            result = tr['result']
            if result.get('success'):
                tool_context += f"- {tr['name']}: {json.dumps(result.get('data', {}), ensure_ascii=False)}\n"
            else:
                tool_context += f"- {tr['name']}: Lỗi - {result.get('error')}\n"
        
        messages.append({
            "role": "user",
            "content": f"[TOOL_RESULTS]\n{tool_context}\n\nHãy tổng hợp kết quả trên và trả lời cho người dùng."
        })
        
        # Call LLM without tools
        ai_service = self.env['ai.service']
        response = ai_service.chat_completion_with_tools(
            messages=messages,
            tools=None,
            temperature=0.7,
        )
        
        if not response.get('success'):
            return self._error_response(response.get('error', 'Lỗi tổng hợp kết quả'))
        
        data = response.get('data', {})
        content = data.get('message', {}).get('content', '')
        new_tokens = data.get('usage', {})
        
        # Merge token counts
        total_tokens = {
            'prompt_tokens': tokens_info.get('prompt_tokens', 0) + new_tokens.get('prompt_tokens', 0),
            'completion_tokens': tokens_info.get('completion_tokens', 0) + new_tokens.get('completion_tokens', 0),
            'total_tokens': tokens_info.get('total_tokens', 0) + new_tokens.get('total_tokens', 0),
        }
        
        msg = self.env['ai.chat.message'].create_assistant_message(
            session_id=session.id,
            content=content,
            tokens_info=total_tokens,
            model_used=data.get('model'),
        )
        
        return {
            'success': True,
            'message': content,
            'message_id': msg.id,
            'tool_results': tool_results,
            'tokens': total_tokens,
        }

    # ==================== ACTION HANDLERS ====================

    def _action_create_support_ticket(self, payload, session):
        """Tạo phiếu hỗ trợ khách hàng"""
        try:
            vals = {
                'khach_hang_id': payload.get('customer_id'),
                'tieu_de': payload.get('subject'),
                'mo_ta': payload.get('description'),
                'muc_do_uu_tien': payload.get('priority', 'normal'),
            }
            ticket = self.env['ho_tro_khach_hang'].create(vals)
            return {
                'success': True,
                'message': f"✅ Đã tạo phiếu hỗ trợ: {ticket.display_name}",
                'record_id': ticket.id,
                'record_model': 'ho_tro_khach_hang',
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _action_create_outgoing_document(self, payload, session):
        """Tạo văn bản đi"""
        try:
            vals = {
                'trich_yeu': payload.get('subject'),
                'noi_dung': payload.get('content'),
                'loai_van_ban_id': payload.get('document_type_id'),
                'nguoi_ky_id': payload.get('signer_id') or self.env.uid,
            }
            doc = self.env['van_ban_di'].create(vals)
            return {
                'success': True,
                'message': f"✅ Đã tạo văn bản đi: {doc.display_name}",
                'record_id': doc.id,
                'record_model': 'van_ban_di',
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _action_send_email(self, payload, session):
        """Gửi email"""
        try:
            template_id = payload.get('template_id')
            record_id = payload.get('record_id')
            model = payload.get('model')
            
            if template_id:
                template = self.env['mail.template'].browse(template_id)
                template.send_mail(record_id, force_send=True)
            else:
                # Send custom email
                record = self.env[model].browse(record_id)
                record.message_post(
                    body=payload.get('body'),
                    subject=payload.get('subject'),
                    message_type='email',
                    partner_ids=payload.get('partner_ids', []),
                )
            
            return {
                'success': True,
                'message': "✅ Đã gửi email thành công",
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _action_update_record(self, payload, session):
        """Cập nhật record"""
        try:
            model = payload.get('model')
            record_id = payload.get('record_id')
            values = payload.get('values', {})
            
            record = self.env[model].browse(record_id)
            record.write(values)
            
            return {
                'success': True,
                'message': f"✅ Đã cập nhật: {record.display_name}",
                'record_id': record_id,
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    # ==================== HELPERS ====================

    def _error_response(self, error_message):
        """Tạo response lỗi chuẩn"""
        return {
            'success': False,
            'error': error_message,
            'message': f"❌ Lỗi: {error_message}",
        }
