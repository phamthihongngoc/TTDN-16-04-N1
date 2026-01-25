# -*- coding: utf-8 -*-

"""
External Storage Integration
Hỗ trợ lưu trữ files trên S3/MinIO để giảm tải database
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import base64
import logging
import uuid
import io
from datetime import timedelta

_logger = logging.getLogger(__name__)

# Try import boto3 for S3
try:
    import boto3
    from botocore.exceptions import ClientError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False
    _logger.warning("boto3 not available. S3 storage will not work. Install: pip install boto3")


class ExternalStorageConfig(models.Model):
    """
    Cấu hình External Storage
    Hỗ trợ S3, MinIO, hoặc các object storage tương thích
    """
    _name = 'external.storage.config'
    _description = 'External Storage Configuration'
    
    name = fields.Char('Tên cấu hình', required=True)
    active = fields.Boolean('Active', default=True)
    
    # === STORAGE TYPE ===
    storage_type = fields.Selection([
        ('s3', 'Amazon S3'),
        ('minio', 'MinIO'),
        ('compatible', 'S3-Compatible Storage'),
    ], string='Storage Type', required=True, default='s3')
    
    # === CONNECTION INFO ===
    endpoint_url = fields.Char('Endpoint URL', 
                               help='S3 endpoint. Leave empty for AWS S3. Required for MinIO.')
    region_name = fields.Char('Region', default='us-east-1')
    bucket_name = fields.Char('Bucket Name', required=True)
    
    access_key_id = fields.Char('Access Key ID', required=True)
    secret_access_key = fields.Char('Secret Access Key', required=True)
    
    # === OPTIONS ===
    use_ssl = fields.Boolean('Use SSL', default=True)
    path_prefix = fields.Char('Path Prefix', default='odoo/van_ban/',
                              help='Prefix cho object keys. VD: odoo/van_ban/')
    
    # === STATUS ===
    is_connected = fields.Boolean('Connected', compute='_compute_is_connected')
    last_test_date = fields.Datetime('Last Test', readonly=True)
    last_test_result = fields.Text('Test Result', readonly=True)
    
    # === STATISTICS ===
    total_files = fields.Integer('Total Files', compute='_compute_statistics')
    total_size_gb = fields.Float('Total Size (GB)', compute='_compute_statistics')
    
    def _compute_is_connected(self):
        """Check connection status"""
        for record in self:
            # Simple check - có credentials không
            record.is_connected = bool(record.access_key_id and record.secret_access_key)
    
    def _compute_statistics(self):
        """Tính thống kê files"""
        for record in self:
            stored_files = self.env['external.storage.file'].search([
                ('storage_config_id', '=', record.id)
            ])
            record.total_files = len(stored_files)
            record.total_size_gb = sum(stored_files.mapped('file_size')) / (1024**3)
    
    def get_s3_client(self):
        """
        Tạo S3 client connection
        """
        self.ensure_one()
        
        if not BOTO3_AVAILABLE:
            raise UserError('boto3 library not installed! Run: pip install boto3')
        
        try:
            # Config
            config_params = {
                'aws_access_key_id': self.access_key_id,
                'aws_secret_access_key': self.secret_access_key,
                'region_name': self.region_name,
            }
            
            # MinIO hoặc custom endpoint
            if self.endpoint_url:
                config_params['endpoint_url'] = self.endpoint_url
                config_params['config'] = boto3.session.Config(signature_version='s3v4')
            
            # Create client
            s3_client = boto3.client('s3', **config_params)
            
            return s3_client
            
        except Exception as e:
            _logger.error(f"Failed to create S3 client: {e}")
            raise UserError(f'Không thể kết nối S3: {str(e)}')
    
    def action_test_connection(self):
        """Test kết nối đến storage"""
        self.ensure_one()
        
        try:
            s3 = self.get_s3_client()
            
            # Test: List bucket
            response = s3.head_bucket(Bucket=self.bucket_name)
            
            # Success
            result = f'''
✅ Kết nối thành công!

Bucket: {self.bucket_name}
Region: {self.region_name}
Response: {response['ResponseMetadata']['HTTPStatusCode']}
            '''
            
            self.write({
                'last_test_date': fields.Datetime.now(),
                'last_test_result': result,
            })
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('✅ Kết nối thành công!'),
                    'message': f'Bucket "{self.bucket_name}" có thể truy cập',
                    'type': 'success',
                }
            }
            
        except ClientError as e:
            error_msg = f"❌ Lỗi: {e.response['Error']['Message']}"
            self.write({
                'last_test_date': fields.Datetime.now(),
                'last_test_result': error_msg,
            })
            raise UserError(error_msg)
        except Exception as e:
            error_msg = f"❌ Lỗi: {str(e)}"
            self.write({
                'last_test_date': fields.Datetime.now(),
                'last_test_result': error_msg,
            })
            raise UserError(error_msg)
    
    @api.model
    def get_default_storage(self):
        """Lấy storage config mặc định"""
        storage = self.search([('active', '=', True)], limit=1)
        if not storage:
            raise UserError('Chưa cấu hình External Storage! Vui lòng cấu hình tại Settings.')
        return storage
    
    def upload_file(self, file_data, filename, metadata=None):
        """
        Upload file lên S3/MinIO
        
        Args:
            file_data: Binary data hoặc base64 string
            filename: Tên file
            metadata: Dict metadata (optional)
        
        Returns:
            object_key: Key của object trên S3
        """
        self.ensure_one()
        
        try:
            s3 = self.get_s3_client()
            
            # Decode nếu là base64
            if isinstance(file_data, str):
                file_data = base64.b64decode(file_data)
            
            # Generate unique object key
            object_key = f"{self.path_prefix}{uuid.uuid4()}_{filename}"
            
            # Upload
            s3.put_object(
                Bucket=self.bucket_name,
                Key=object_key,
                Body=file_data,
                Metadata=metadata or {},
            )
            
            _logger.info(f"✓ Uploaded file to S3: {object_key}")
            
            return object_key
            
        except Exception as e:
            _logger.error(f"Failed to upload file: {e}")
            raise UserError(f'Lỗi khi upload file: {str(e)}')
    
    def download_file(self, object_key):
        """
        Download file từ S3/MinIO
        
        Args:
            object_key: Key của object
        
        Returns:
            file_data: Binary data
        """
        self.ensure_one()
        
        try:
            s3 = self.get_s3_client()
            
            # Download
            response = s3.get_object(Bucket=self.bucket_name, Key=object_key)
            file_data = response['Body'].read()
            
            _logger.info(f"✓ Downloaded file from S3: {object_key}")
            
            return file_data
            
        except Exception as e:
            _logger.error(f"Failed to download file: {e}")
            raise UserError(f'Lỗi khi download file: {str(e)}')
    
    def delete_file(self, object_key):
        """Xóa file từ S3/MinIO"""
        self.ensure_one()
        
        try:
            s3 = self.get_s3_client()
            s3.delete_object(Bucket=self.bucket_name, Key=object_key)
            _logger.info(f"✓ Deleted file from S3: {object_key}")
            return True
        except Exception as e:
            _logger.error(f"Failed to delete file: {e}")
            return False


class ExternalStorageFile(models.Model):
    """
    Tracking files được lưu trên External Storage
    """
    _name = 'external.storage.file'
    _description = 'External Storage File Tracking'
    _order = 'uploaded_at desc'
    
    name = fields.Char('Filename', required=True)
    object_key = fields.Char('Object Key', required=True, index=True)
    
    storage_config_id = fields.Many2one('external.storage.config', 
                                       string='Storage Config',
                                       required=True, ondelete='cascade')
    
    # === FILE INFO ===
    file_size = fields.Integer('File Size (bytes)')
    file_type = fields.Char('File Type')
    content_type = fields.Char('Content Type')
    
    # === METADATA ===
    uploaded_at = fields.Datetime('Uploaded At', default=fields.Datetime.now, readonly=True)
    uploaded_by = fields.Many2one('res.users', string='Uploaded By',
                                  default=lambda self: self.env.user, readonly=True)
    
    # === LINKS ===
    van_ban_id = fields.Many2one('van_ban', string='Văn bản', ondelete='cascade')
    van_ban_di_id = fields.Many2one('van_ban_di', string='Văn bản đi', ondelete='cascade')
    van_ban_den_id = fields.Many2one('van_ban_den', string='Văn bản đến', ondelete='cascade')
    
    # === STATUS ===
    is_accessible = fields.Boolean('Is Accessible', default=True)
    
    def action_download(self):
        """Download file từ S3"""
        self.ensure_one()
        
        try:
            file_data = self.storage_config_id.download_file(self.object_key)
            
            # Return file
            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/content/?model=external.storage.file&id={self.id}&field=file_data&filename={self.name}',
                'target': 'new',
            }
        except Exception as e:
            raise UserError(f'Không thể download file: {str(e)}')
    
    def action_delete(self):
        """Xóa file từ S3 và database"""
        self.ensure_one()
        
        try:
            # Delete từ S3
            self.storage_config_id.delete_file(self.object_key)
            
            # Delete record
            self.unlink()
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('✅ Đã xóa'),
                    'message': 'File đã được xóa khỏi storage',
                    'type': 'success',
                }
            }
        except Exception as e:
            raise UserError(f'Lỗi khi xóa file: {str(e)}')


class VanBan(models.Model):
    """Extend VanBan với External Storage"""
    _inherit = 'van_ban'
    
    use_external_storage = fields.Boolean('Use External Storage', default=False,
                                         help='Lưu file trên S3/MinIO thay vì database')
    external_storage_file_id = fields.Many2one('external.storage.file',
                                               string='External File',
                                               readonly=True)
    
    def action_move_to_external_storage(self):
        """
        Di chuyển file từ database sang external storage
        """
        self.ensure_one()
        
        if not self.file_dinh_kem:
            raise UserError('Văn bản chưa có file đính kèm!')
        
        if self.external_storage_file_id:
            raise UserError('File đã được lưu trên external storage rồi!')
        
        try:
            # Get storage config
            storage = self.env['external.storage.config'].get_default_storage()
            
            # Upload file
            file_data = base64.b64decode(self.file_dinh_kem)
            object_key = storage.upload_file(
                file_data,
                self.ten_file or f"van_ban_{self.id}.pdf",
                metadata={
                    'van_ban_id': str(self.id),
                    'ma_van_ban': self.ma_van_ban,
                }
            )
            
            # Create tracking record
            external_file = self.env['external.storage.file'].create({
                'name': self.ten_file,
                'object_key': object_key,
                'storage_config_id': storage.id,
                'file_size': len(file_data),
                'van_ban_id': self.id,
            })
            
            # Update van_ban
            self.write({
                'external_storage_file_id': external_file.id,
                'use_external_storage': True,
                # Optionally: Xóa file từ database để tiết kiệm
                # 'file_dinh_kem': False,
            })
            
            self.message_post(
                body=f'''
                    <p><strong>📦 File đã được chuyển sang External Storage</strong></p>
                    <p>Object Key: {object_key}</p>
                    <p>Storage: {storage.name}</p>
                '''
            )
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('✅ Thành công!'),
                    'message': 'File đã được chuyển sang external storage',
                    'type': 'success',
                }
            }
            
        except Exception as e:
            _logger.error(f"Failed to move file to external storage: {e}")
            raise UserError(f'Lỗi: {str(e)}')
    
    def action_restore_from_external_storage(self):
        """Restore file từ external storage về database"""
        self.ensure_one()
        
        if not self.external_storage_file_id:
            raise UserError('Văn bản không có file trên external storage!')
        
        try:
            # Download file
            file_data = self.external_storage_file_id.storage_config_id.download_file(
                self.external_storage_file_id.object_key
            )
            
            # Save to database
            self.write({
                'file_dinh_kem': base64.b64encode(file_data),
                'use_external_storage': False,
            })
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('✅ Restored!'),
                    'message': 'File đã được restore về database',
                    'type': 'success',
                }
            }
        except Exception as e:
            raise UserError(f'Lỗi khi restore file: {str(e)}')
