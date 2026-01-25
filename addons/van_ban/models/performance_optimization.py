# -*- coding: utf-8 -*-

"""
Performance Optimization Utilities
Tối ưu hóa xử lý files lớn và operations chậm
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import base64
import hashlib
import logging
import io
from functools import wraps
import time

_logger = logging.getLogger(__name__)


def performance_monitor(func):
    """Decorator để monitor performance của function"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        elapsed = time.time() - start_time
        
        if elapsed > 1.0:  # Log nếu > 1 giây
            _logger.warning(f"⚠️  Slow operation: {func.__name__} took {elapsed:.2f}s")
        else:
            _logger.info(f"✓ {func.__name__} completed in {elapsed:.2f}s")
        
        return result
    return wrapper


class PerformanceOptimizationMixin(models.AbstractModel):
    """
    Mixin cung cấp các utilities tối ưu performance
    """
    _name = 'performance.optimization.mixin'
    _description = 'Performance Optimization Mixin'
    
    @performance_monitor
    def compute_file_hash_chunked(self, file_data, chunk_size=8192):
        """
        Tính hash file theo chunks để tránh tràn memory với files lớn
        
        Args:
            file_data: Binary data của file
            chunk_size: Size của mỗi chunk (default 8KB)
        
        Returns:
            SHA256 hash string
        """
        sha256 = hashlib.sha256()
        
        # Nếu file_data là base64, decode trước
        if isinstance(file_data, str):
            file_data = base64.b64decode(file_data)
        
        # Process theo chunks
        file_stream = io.BytesIO(file_data)
        while True:
            chunk = file_stream.read(chunk_size)
            if not chunk:
                break
            sha256.update(chunk)
        
        return sha256.hexdigest()
    
    @performance_monitor
    def sign_large_file_async(self, file_data, private_key, hash_algo):
        """
        Ký file lớn với async processing
        Chỉ sign hash thay vì toàn bộ file
        
        Args:
            file_data: Binary data
            private_key: Private key object
            hash_algo: Hash algorithm object
        
        Returns:
            Digital signature bytes
        """
        try:
            from cryptography.hazmat.primitives.asymmetric import padding
            
            # Tính hash trước (nhanh hơn)
            file_hash = self.compute_file_hash_chunked(file_data)
            
            # Sign hash (không sign toàn bộ file)
            signature = private_key.sign(
                file_hash.encode('utf-8'),
                padding.PSS(
                    mgf=padding.MGF1(hash_algo),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hash_algo
            )
            
            return signature
            
        except Exception as e:
            _logger.error(f"Error signing large file: {e}")
            raise
    
    def batch_verify_signatures(self, signature_logs):
        """
        Xác thực nhiều chữ ký cùng lúc (batch processing)
        Tối ưu cho việc verify nhiều văn bản
        
        Args:
            signature_logs: recordset của van_ban.signature.log
        
        Returns:
            dict: {log_id: (is_valid, message)}
        """
        results = {}
        
        for log in signature_logs:
            try:
                # Verify từng log
                log.action_verify_signature()
                results[log.id] = (True, "✅ Hợp lệ")
            except Exception as e:
                results[log.id] = (False, str(e))
        
        return results


class VanBan(models.Model):
    """Extend VanBan với performance optimizations"""
    _inherit = 'van_ban'
    
    # Cache hash để tránh tính lại
    file_hash_cached = fields.Char('File Hash (Cached)', readonly=True)
    file_size_mb = fields.Float('File Size (MB)', compute='_compute_file_size', store=True)
    
    @api.depends('file_dinh_kem')
    def _compute_file_size(self):
        """Tính kích thước file"""
        for record in self:
            if record.file_dinh_kem:
                file_data = base64.b64decode(record.file_dinh_kem)
                record.file_size_mb = len(file_data) / (1024 * 1024)
            else:
                record.file_size_mb = 0.0
    
    @performance_monitor
    def compute_and_cache_file_hash(self):
        """
        Tính và cache file hash
        Sử dụng chunked processing cho files lớn
        """
        self.ensure_one()
        
        if not self.file_dinh_kem:
            return False
        
        # Kiểm tra có cache chưa
        if self.file_hash_cached:
            _logger.info(f"Using cached hash for {self.ma_van_ban}")
            return self.file_hash_cached
        
        # Tính hash mới
        mixin = self.env['performance.optimization.mixin']
        file_hash = mixin.compute_file_hash_chunked(self.file_dinh_kem)
        
        # Cache
        self.write({'file_hash_cached': file_hash})
        
        return file_hash
    
    @api.model
    def search_with_pagination(self, domain, limit=100, offset=0):
        """
        Search với pagination để tránh load quá nhiều records
        """
        return self.search(domain, limit=limit, offset=offset, order='ngay_tao desc')
    
    def archive_old_documents(self, days=365):
        """
        Archive các văn bản cũ (> 1 năm)
        Giảm tải database
        """
        threshold_date = fields.Date.today() - timedelta(days=days)
        
        old_docs = self.search([
            ('ngay_tao', '<=', threshold_date),
            ('trang_thai', 'in', ['da_gui', 'het_hieu_luc']),
        ])
        
        archived_count = 0
        for doc in old_docs:
            # Move file to external storage (if configured)
            if doc.file_dinh_kem:
                # TODO: Implement external storage
                pass
            
            # Mark as archived
            doc.write({'active': False})
            archived_count += 1
        
        _logger.info(f"Archived {archived_count} old documents")
        return archived_count


# NOTE: Các class extend bên dưới đã comment out để tránh circular dependency
# Các tính năng performance sẽ được tích hợp trực tiếp vào models chính

# class WizardKyDienTu(models.TransientModel):
#     """Extend Wizard với performance optimizations"""
#     _inherit = 'wizard.ky.dien.tu'
#     
#     signing_progress = fields.Integer('Progress (%)', default=0)
#     is_large_file = fields.Boolean('Is Large File', compute='_compute_is_large_file')
#     
#     @api.depends('van_ban_id.file_size_mb', 'van_ban_di_id', 'van_ban_den_id')
#     def _compute_is_large_file(self):
#         """Kiểm tra có phải file lớn không (> 5MB)"""
#         for record in self:
#             document = record.van_ban_id or record.van_ban_di_id or record.van_ban_den_id
#             if document and hasattr(document, 'file_size_mb'):
#                 record.is_large_file = document.file_size_mb > 5.0
#             else:
#                 record.is_large_file = False
#     
#     @performance_monitor
#     def action_ky_optimized(self):
#         """
#         Version tối ưu của action_ky cho files lớn
#         Sử dụng chunked processing
#         """
#         self.ensure_one()
#         
#         # Update progress
#         self.signing_progress = 10
#         
#         # Gọi original action_ky
#         result = self.action_ky()
#         
#         # Complete
#         self.signing_progress = 100
#         
#         return result


# class PKICertificate(models.Model):
#     """Extend PKICertificate với caching"""
#     _inherit = 'pki.certificate'
#     
#     # Cache public key object để tránh load lại
#     _public_key_cache = {}
#     
#     def get_public_key_object_cached(self):
#         """
#         Get public key với caching
#         Tránh load lại từ database nhiều lần
#         """
#         self.ensure_one()
#         
#         cache_key = f"cert_{self.id}_public_key"
#         
#         if cache_key in self._public_key_cache:
#             _logger.debug(f"Using cached public key for cert {self.id}")
#             return self._public_key_cache[cache_key]
#         
#         # Load từ database
#         public_key_obj = self.get_public_key_object()
#         
#         # Cache
#         self._public_key_cache[cache_key] = public_key_obj
#         
#         return public_key_obj
#     
#     @api.model
#     def clear_public_key_cache(self):
#         """Clear cache (gọi khi có thay đổi)"""
#         self._public_key_cache = {}
#         _logger.info("Public key cache cleared")
        """Cron: Archive old documents monthly"""
        _logger.info("=== Running archive old documents ===")
        count = self.env['van_ban'].archive_old_documents(days=365)
        _logger.info(f"=== Archived {count} documents ===")
        return count
    
    @api.model
    def cron_cleanup_transient_models(self):
        """Cron: Cleanup old transient wizard data"""
        _logger.info("=== Cleaning up transient models ===")
        
        # Cleanup wizard.ky.dien.tu (older than 1 day)
        threshold = fields.Datetime.now() - timedelta(days=1)
        
        old_wizards = self.env['wizard.ky.dien.tu'].search([
            ('create_date', '<', threshold)
        ])
        
        count = len(old_wizards)
        old_wizards.unlink()
        
        _logger.info(f"=== Deleted {count} old wizard records ===")
        return count
