# -*- coding: utf-8 -*-

from odoo import models, api
import logging

_logger = logging.getLogger(__name__)


class AIContextVanBan(models.AbstractModel):
    """Context Provider cho module Quản lý Văn bản"""
    _name = 'ai.context.van_ban'
    _description = 'AI Context Provider - Văn bản'

    @api.model
    def get_context(self, model, res_id):
        """Lấy context nghiệp vụ cho chatbot"""
        if model == 'van_ban_den':
            return self._get_incoming_doc_context(res_id)
        elif model == 'van_ban_di':
            return self._get_outgoing_doc_context(res_id)
        elif model == 'van_ban':
            return self._get_document_context(res_id)
        elif model == 'yeu_cau_ky':
            return self._get_signing_request_context(res_id)
        return None

    def _get_document_context(self, doc_id):
        """Lấy context văn bản chung"""
        try:
            doc = self.env['van_ban'].sudo().browse(doc_id)
            if not doc.exists():
                return None
            
            context = f"""VĂN BẢN: {doc.display_name}
- Mã: {doc.ma_van_ban if hasattr(doc, 'ma_van_ban') else 'N/A'}
- Loại: {doc.loai_van_ban_id.display_name if hasattr(doc, 'loai_van_ban_id') and doc.loai_van_ban_id else 'N/A'}
- Ngày tạo: {doc.ngay_tao.strftime('%d/%m/%Y') if hasattr(doc, 'ngay_tao') and doc.ngay_tao else 'N/A'}
- Trạng thái: {dict(doc._fields['trang_thai'].selection).get(doc.trang_thai, 'N/A') if hasattr(doc, 'trang_thai') else 'N/A'}
"""
            
            # Trích yếu
            if hasattr(doc, 'trich_yeu') and doc.trich_yeu:
                context += f"""
TRÍCH YẾU:
{doc.trich_yeu}
"""
            
            # Nội dung (truncated)
            if hasattr(doc, 'noi_dung') and doc.noi_dung:
                content = doc.noi_dung
                # Strip HTML tags if present
                import re
                content = re.sub('<[^<]+?>', '', content)
                content = content[:1000] + '...' if len(content) > 1000 else content
                context += f"""
NỘI DUNG:
{content}
"""
            
            return context
            
        except Exception as e:
            _logger.warning(f"Error getting document context: {e}")
            return None

    def _get_incoming_doc_context(self, doc_id):
        """Lấy context văn bản đến"""
        try:
            doc = self.env['van_ban_den'].sudo().browse(doc_id)
            if not doc.exists():
                return None
            
            context = f"""VĂN BẢN ĐẾN: {doc.display_name}
- Số đến: {doc.so_den if hasattr(doc, 'so_den') else 'N/A'}
- Số ký hiệu: {doc.so_ky_hieu if hasattr(doc, 'so_ky_hieu') else 'N/A'}
- Ngày đến: {doc.ngay_den.strftime('%d/%m/%Y') if hasattr(doc, 'ngay_den') and doc.ngay_den else 'N/A'}
- Ngày ban hành: {doc.ngay_ban_hanh.strftime('%d/%m/%Y') if hasattr(doc, 'ngay_ban_hanh') and doc.ngay_ban_hanh else 'N/A'}
- Hạn xử lý: {doc.han_xu_ly.strftime('%d/%m/%Y') if hasattr(doc, 'han_xu_ly') and doc.han_xu_ly else 'Không có'}
- Loại văn bản: {doc.loai_van_ban_id.display_name if hasattr(doc, 'loai_van_ban_id') and doc.loai_van_ban_id else 'N/A'}
- Nơi gửi: {doc.don_vi_gui if hasattr(doc, 'don_vi_gui') else 'N/A'}
- Độ khẩn: {dict(doc._fields['do_khan'].selection).get(doc.do_khan, 'Bình thường') if hasattr(doc, 'do_khan') else 'N/A'}
- Độ mật: {dict(doc._fields['do_mat'].selection).get(doc.do_mat, 'Thường') if hasattr(doc, 'do_mat') else 'N/A'}
- Trạng thái: {dict(doc._fields['trang_thai'].selection).get(doc.trang_thai, 'N/A') if hasattr(doc, 'trang_thai') else 'N/A'}
- Người xử lý: {doc.nguoi_xu_ly_id.display_name if hasattr(doc, 'nguoi_xu_ly_id') and doc.nguoi_xu_ly_id else 'Chưa phân công'}
"""
            
            # Trích yếu
            if hasattr(doc, 'trich_yeu') and doc.trich_yeu:
                context += f"""
TRÍCH YẾU:
{doc.trich_yeu}
"""
            
            # Nội dung
            if hasattr(doc, 'noi_dung') and doc.noi_dung:
                import re
                content = re.sub('<[^<]+?>', '', doc.noi_dung)
                content = content[:1500] + '...' if len(content) > 1500 else content
                context += f"""
NỘI DUNG:
{content}
"""
            
            # Lịch sử xử lý
            if hasattr(doc, 'lich_su_ids') and doc.lich_su_ids:
                context += "\nLỊCH SỬ XỬ LÝ:\n"
                for history in doc.lich_su_ids.sorted('create_date', reverse=True)[:5]:
                    action = history.hanh_dong if hasattr(history, 'hanh_dong') else ''
                    user = history.nguoi_thuc_hien_id.display_name if hasattr(history, 'nguoi_thuc_hien_id') and history.nguoi_thuc_hien_id else ''
                    date = history.create_date.strftime('%d/%m/%Y %H:%M') if history.create_date else ''
                    context += f"  • {date} - {user}: {action}\n"
            
            return context
            
        except Exception as e:
            _logger.warning(f"Error getting incoming doc context: {e}")
            return None

    def _get_outgoing_doc_context(self, doc_id):
        """Lấy context văn bản đi"""
        try:
            doc = self.env['van_ban_di'].sudo().browse(doc_id)
            if not doc.exists():
                return None
            
            context = f"""VĂN BẢN ĐI: {doc.display_name}
- Số đi: {doc.so_di if hasattr(doc, 'so_di') else 'N/A'}
- Số ký hiệu: {doc.so_ky_hieu if hasattr(doc, 'so_ky_hieu') else 'N/A'}
- Ngày ban hành: {doc.ngay_ban_hanh.strftime('%d/%m/%Y') if hasattr(doc, 'ngay_ban_hanh') and doc.ngay_ban_hanh else 'N/A'}
- Loại văn bản: {doc.loai_van_ban_id.display_name if hasattr(doc, 'loai_van_ban_id') and doc.loai_van_ban_id else 'N/A'}
- Nơi nhận: {doc.don_vi_nhan if hasattr(doc, 'don_vi_nhan') else 'N/A'}
- Người ký: {doc.nguoi_ky_id.display_name if hasattr(doc, 'nguoi_ky_id') and doc.nguoi_ky_id else 'N/A'}
- Trạng thái: {dict(doc._fields['trang_thai'].selection).get(doc.trang_thai, 'N/A') if hasattr(doc, 'trang_thai') else 'N/A'}
"""
            
            # Trích yếu
            if hasattr(doc, 'trich_yeu') and doc.trich_yeu:
                context += f"""
TRÍCH YẾU:
{doc.trich_yeu}
"""
            
            # Nội dung
            if hasattr(doc, 'noi_dung') and doc.noi_dung:
                import re
                content = re.sub('<[^<]+?>', '', doc.noi_dung)
                content = content[:1500] + '...' if len(content) > 1500 else content
                context += f"""
NỘI DUNG:
{content}
"""
            
            # Signatures
            if hasattr(doc, 'signature_log_ids') and doc.signature_log_ids:
                context += "\nKÝ SỐ:\n"
                for sig in doc.signature_log_ids.sorted('create_date', reverse=True)[:5]:
                    signer = sig.signer_id.display_name if hasattr(sig, 'signer_id') and sig.signer_id else ''
                    date = sig.create_date.strftime('%d/%m/%Y %H:%M') if sig.create_date else ''
                    status = 'Đã ký' if sig.is_valid else 'Chờ ký' if hasattr(sig, 'is_valid') else ''
                    context += f"  • {date} - {signer}: {status}\n"
            
            return context
            
        except Exception as e:
            _logger.warning(f"Error getting outgoing doc context: {e}")
            return None

    def _get_signing_request_context(self, request_id):
        """Lấy context yêu cầu ký"""
        try:
            request = self.env['yeu_cau_ky'].browse(request_id)
            if not request.exists():
                return None
            
            context = f"""YÊU CẦU KÝ: {request.display_name}
- Văn bản: {request.van_ban_id.display_name if hasattr(request, 'van_ban_id') and request.van_ban_id else 'N/A'}
- Người ký: {request.nguoi_ky_id.display_name if hasattr(request, 'nguoi_ky_id') and request.nguoi_ky_id else 'N/A'}
- Trạng thái: {dict(request._fields['trang_thai'].selection).get(request.trang_thai, 'N/A') if hasattr(request, 'trang_thai') else 'N/A'}
- Hạn ký: {request.han_ky.strftime('%d/%m/%Y') if hasattr(request, 'han_ky') and request.han_ky else 'Không có'}
"""
            
            return context
            
        except Exception as e:
            _logger.warning(f"Error getting signing request context: {e}")
            return None

    # ==================== DATA RETRIEVAL METHODS ====================

    @api.model
    def search_documents(self, query, doc_type=None, filters=None, limit=10):
        """Tìm kiếm văn bản"""
        try:
            results = []
            
            # Search incoming documents
            if not doc_type or doc_type == 'incoming':
                domain = ['|', '|',
                    ('trich_yeu', 'ilike', query),
                    ('so_ky_hieu', 'ilike', query),
                    ('don_vi_gui', 'ilike', query),
                ]
                if filters:
                    if filters.get('trang_thai'):
                        domain.append(('trang_thai', '=', filters['trang_thai']))
                
                docs = self.env['van_ban_den'].sudo().search(domain, limit=limit)
                for doc in docs:
                    results.append({
                        'id': doc.id,
                        'type': 'incoming',
                        'name': doc.display_name,
                        'so_ky_hieu': doc.so_ky_hieu if hasattr(doc, 'so_ky_hieu') else None,
                        'trich_yeu': doc.trich_yeu if hasattr(doc, 'trich_yeu') else None,
                    })
            
            # Search outgoing documents
            if not doc_type or doc_type == 'outgoing':
                domain = ['|', '|',
                    ('trich_yeu', 'ilike', query),
                    ('so_ky_hieu', 'ilike', query),
                    ('don_vi_nhan', 'ilike', query),
                ]
                if filters:
                    if filters.get('trang_thai'):
                        domain.append(('trang_thai', '=', filters['trang_thai']))
                
                docs = self.env['van_ban_di'].sudo().search(domain, limit=limit)
                for doc in docs:
                    results.append({
                        'id': doc.id,
                        'type': 'outgoing',
                        'name': doc.display_name,
                        'so_ky_hieu': doc.so_ky_hieu if hasattr(doc, 'so_ky_hieu') else None,
                        'trich_yeu': doc.trich_yeu if hasattr(doc, 'trich_yeu') else None,
                    })
            
            return results[:limit]
            
        except Exception as e:
            _logger.warning(f"Error searching documents: {e}")
            return []

    @api.model
    def get_document_summary(self, model, res_id):
        """Lấy tóm tắt văn bản"""
        context = self.get_context(model, res_id)
        if not context:
            return {'error': 'Không tìm thấy văn bản'}
        
        return {
            'success': True,
            'summary': context,
        }

    @api.model
    def get_pending_documents(self, user_id=None, days=7):
        """Lấy danh sách văn bản đang chờ xử lý"""
        try:
            from datetime import datetime, timedelta
            
            user_id = user_id or self.env.uid
            since = datetime.now() - timedelta(days=days)
            pending = []
            
            # Incoming documents waiting for processing
            incoming = self.env['van_ban_den'].search([
                ('nguoi_xu_ly_id', '=', user_id),
                ('trang_thai', 'not in', ['done', 'cancel']),
            ])
            
            for doc in incoming:
                pending.append({
                    'type': 'incoming',
                    'id': doc.id,
                    'name': doc.display_name,
                    'deadline': doc.han_xu_ly.strftime('%d/%m/%Y') if hasattr(doc, 'han_xu_ly') and doc.han_xu_ly else None,
                    'urgent': doc.do_khan == 'urgent' if hasattr(doc, 'do_khan') else False,
                })
            
            # Outgoing documents waiting for signature
            outgoing = self.env['van_ban_di'].search([
                ('nguoi_ky_id', '=', user_id),
                ('trang_thai', 'in', ['draft', 'pending']),
            ])
            
            for doc in outgoing:
                pending.append({
                    'type': 'outgoing',
                    'id': doc.id,
                    'name': doc.display_name,
                    'action_needed': 'Cần ký duyệt',
                })
            
            return {
                'success': True,
                'pending_count': len(pending),
                'documents': pending,
            }
            
        except Exception as e:
            return {'error': str(e)}

    @api.model
    def get_document_workflow_status(self, model, res_id):
        """Lấy trạng thái workflow của văn bản"""
        try:
            doc = self.env[model].browse(res_id)
            if not doc.exists():
                return {'error': 'Không tìm thấy văn bản'}
            
            status = {
                'document': doc.display_name,
                'current_state': doc.trang_thai if hasattr(doc, 'trang_thai') else 'unknown',
                'steps': [],
                'next_actions': [],
            }
            
            # Get workflow steps based on document state
            if hasattr(doc, 'trang_thai'):
                state = doc.trang_thai
                if model == 'van_ban_den':
                    if state == 'moi':
                        status['next_actions'] = ['Tiếp nhận và phân công xử lý']
                    elif state == 'dang_xu_ly':
                        status['next_actions'] = ['Hoàn thành xử lý', 'Chuyển tiếp']
                elif model == 'van_ban_di':
                    if state == 'draft':
                        status['next_actions'] = ['Trình ký', 'Sửa nội dung']
                    elif state == 'pending':
                        status['next_actions'] = ['Ký duyệt', 'Từ chối']
                    elif state == 'signed':
                        status['next_actions'] = ['Ban hành', 'Gửi đi']
            
            return status
            
        except Exception as e:
            return {'error': str(e)}
