# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import base64
import hashlib
import logging
import re
import unicodedata

_logger = logging.getLogger(__name__)

try:
    from web3 import Web3
    from eth_account import Account
except ImportError as e:
    _logger.warning("Missing blockchain libraries: %s", e)


class WizardKyDienTu(models.TransientModel):
    _name = 'wizard.ky.dien.tu'
    _description = 'Wizard Ký điện tử'

    van_ban_id = fields.Many2one('van_ban', string='Văn bản')
    van_ban_di_id = fields.Many2one('van_ban_di', string='Văn bản đi')
    van_ban_den_id = fields.Many2one('van_ban_den', string='Văn bản đến')

    document_display_name = fields.Char(string='Tên văn bản', compute='_compute_document_info', readonly=True)
    document_display_type = fields.Char(string='Loại', compute='_compute_document_info', readonly=True)

    ten_van_ban = fields.Char(related='van_ban_id.ten_van_ban', string='Tên văn bản (nội bộ)')
    loai_van_ban = fields.Char(related='van_ban_id.loai_van_ban_id.ten_loai', string='Loại văn bản')
    
    # Chữ ký
    chu_ky = fields.Binary('Chữ ký', required=True, 
                           help='Vẽ chữ ký của bạn trên canvas')
    
    # Thông tin người ký
    nguoi_ky_id = fields.Many2one('nhan_vien', string='Người ký',
                                   default=lambda self: self._get_nhan_vien_hien_tai(),
                                   readonly=True)
    ten_nguoi_ky = fields.Char(related='nguoi_ky_id.ten_nv', string='Họ tên')
    chuc_vu = fields.Char(related='nguoi_ky_id.chuc_vu', string='Chức vụ')

    ho_ten_xac_nhan = fields.Char('Xác minh họ và tên',
                                 help='Nhập đúng họ và tên của bạn để xác minh trước khi ký.')
    
    # Xác nhận
    xac_nhan = fields.Boolean('Tôi xác nhận đã đọc và đồng ý với nội dung văn bản này', 
                               default=False)
    
    # Blockchain
    ky_blockchain = fields.Boolean('Ký trên Blockchain', default=True,
                                   help='Lưu hash chữ ký lên blockchain để đảm bảo tính toàn vẹn')
    blockchain_tx_hash = fields.Char('Blockchain Transaction Hash', readonly=True)
    
    def _get_nhan_vien_hien_tai(self):
        """Lấy nhân viên hiện tại"""
        nhan_vien = self.env['nhan_vien'].search([
            ('user_id', '=', self.env.uid)
        ], limit=1)
        return nhan_vien.id if nhan_vien else False

    @api.depends('van_ban_id', 'van_ban_di_id', 'van_ban_den_id')
    def _compute_document_info(self):
        for wizard in self:
            if wizard.van_ban_id:
                wizard.document_display_type = 'Văn bản'
                wizard.document_display_name = wizard.van_ban_id.ten_van_ban
            elif wizard.van_ban_di_id:
                wizard.document_display_type = 'Văn bản đi'
                wizard.document_display_name = wizard.van_ban_di_id.name or wizard.van_ban_di_id.trich_yeu
            elif wizard.van_ban_den_id:
                wizard.document_display_type = 'Văn bản đến'
                wizard.document_display_name = wizard.van_ban_den_id.name or wizard.van_ban_den_id.trich_yeu
            else:
                wizard.document_display_type = False
                wizard.document_display_name = False

    def _normalize_name(self, name):
        if not name:
            return ''
        name = name.strip().lower()
        name = unicodedata.normalize('NFKD', name)
        name = ''.join([c for c in name if not unicodedata.combining(c)])
        name = re.sub(r'\s+', ' ', name)
        return name

    def _get_target_document(self):
        self.ensure_one()
        if self.van_ban_id:
            return ('van_ban', self.van_ban_id)
        if self.van_ban_di_id:
            return ('van_ban_di', self.van_ban_di_id)
        if self.van_ban_den_id:
            return ('van_ban_den', self.van_ban_den_id)
        return (None, None)

    def _check_can_sign(self, model_name, document):
        """Enforce that only authorized users can sign, and (when configured) only the assigned signer can sign."""
        self.ensure_one()

        if not self.env.user.has_group('van_ban.group_giam_doc_ky') and not self.env.user.has_group('van_ban.group_quan_tri_van_ban') and not self.env.user.has_group('base.group_system'):
            raise UserError('Bạn không có quyền ký điện tử. Vui lòng liên hệ quản trị để cấp quyền.')

        expected_nv = False
        if model_name == 'van_ban':
            expected_nv = document.nguoi_ky_id
        elif model_name == 'van_ban_di':
            expected_nv = document.nguoi_ky_id
        elif model_name == 'van_ban_den':
            expected_nv = document.nguoi_ky_id

        # If document has an assigned signer with a linked user, enforce it (admins can override)
        if expected_nv and expected_nv.user_id and expected_nv.user_id.id != self.env.uid:
            if not self.env.user.has_group('van_ban.group_quan_tri_van_ban') and not self.env.user.has_group('base.group_system'):
                raise UserError('Bạn không phải là người được phân công ký cho văn bản này.')

    def _log_signature_attempt(self, model_name, document, *, is_valid, invalid_reason=False, tx_hash=False, file_sha256=False):
        self.ensure_one()
        vals = {
            'user_id': self.env.uid,
            'nhan_vien_id': self.nguoi_ky_id.id if self.nguoi_ky_id else False,
            'signer_name_entered': self.ho_ten_xac_nhan,
            'signer_name_expected': (self.nguoi_ky_id.ten_nv if self.nguoi_ky_id else self.env.user.name),
            'is_valid': bool(is_valid),
            'invalid_reason': invalid_reason or False,
            'ip_address': self.env['ir.http']._get_client_address() if hasattr(self.env['ir.http'], '_get_client_address') else 'N/A',
            'signature_image': self.chu_ky or False,
            'file_sha256': file_sha256 or False,
            'blockchain_tx_hash': tx_hash or False,
        }
        if model_name == 'van_ban':
            vals['van_ban_id'] = document.id
        elif model_name == 'van_ban_di':
            vals['van_ban_di_id'] = document.id
        elif model_name == 'van_ban_den':
            vals['van_ban_den_id'] = document.id
        self.env['van_ban.signature.log'].sudo().create(vals)
    
    @api.model
    def default_get(self, fields_list):
        """Khởi tạo giá trị mặc định"""
        res = super(WizardKyDienTu, self).default_get(fields_list)

        # Prefer explicit defaults
        if res.get('van_ban_id') or res.get('van_ban_di_id') or res.get('van_ban_den_id'):
            pass
        else:
            active_model = self.env.context.get('active_model')
            active_id = self.env.context.get('active_id')
            if active_model and active_id:
                if active_model == 'van_ban':
                    res['van_ban_id'] = active_id
                elif active_model == 'van_ban_di':
                    res['van_ban_di_id'] = active_id
                elif active_model == 'van_ban_den':
                    res['van_ban_den_id'] = active_id

        # Default full-name confirmation
        if 'ho_ten_xac_nhan' in fields_list:
            nhan_vien = self.env['nhan_vien'].search([('user_id', '=', self.env.uid)], limit=1)
            res['ho_ten_xac_nhan'] = (nhan_vien.ten_nv if nhan_vien else self.env.user.name) or ''

        return res
    
    def action_ky(self):
        """Thực hiện ký điện tử"""
        self.ensure_one()

        model_name, document = self._get_target_document()
        if not model_name or not document:
            raise UserError('Thiếu thông tin văn bản để ký.')

        # Validate preconditions per document
        if model_name == 'van_ban':
            if document.trang_thai not in ['da_duyet', 'cho_ky']:
                raise UserError('Văn bản chưa được duyệt! Không thể ký.')
            if not document.file_dinh_kem:
                raise UserError('Văn bản chưa có file đính kèm! Vui lòng upload file trước khi ký.')
        elif model_name == 'van_ban_di':
            if document.trang_thai != 'cho_ky':
                raise UserError('Văn bản đi chưa ở trạng thái Chờ ký!')
            if not document.file_dinh_kem:
                raise UserError('Vui lòng đính kèm file văn bản trước khi ký!')
        elif model_name == 'van_ban_den':
            if not document.file_dinh_kem:
                raise UserError('Vui lòng đính kèm file trước khi ký!')

        # Permission checks
        self._check_can_sign(model_name, document)
        
        # Kiểm tra xác nhận
        if not self.xac_nhan:
            raise UserError('Bạn phải xác nhận đã đọc và đồng ý với nội dung văn bản!')
        
        # Kiểm tra chữ ký
        if not self.chu_ky:
            raise UserError('Bạn chưa vẽ chữ ký! Vui lòng vẽ chữ ký trên canvas.')

        # Verify full name
        expected_name = (self.nguoi_ky_id.ten_nv if self.nguoi_ky_id else self.env.user.name) or ''
        if self._normalize_name(self.ho_ten_xac_nhan) != self._normalize_name(expected_name):
            self._log_signature_attempt(
                model_name, document,
                is_valid=False,
                invalid_reason='Họ tên xác minh không khớp.'
            )
            raise UserError('Họ tên xác minh không khớp với tài khoản ký. Vui lòng nhập đúng họ tên để tiếp tục.')
        
        # Lấy IP address
        ip_address = self.env['ir.http']._get_client_address() if hasattr(self.env['ir.http'], '_get_client_address') else 'N/A'

        # Hash file at signing time
        file_sha256 = False
        try:
            file_field = getattr(document, 'file_dinh_kem', False)
            if file_field:
                file_sha256 = hashlib.sha256(base64.b64decode(file_field)).hexdigest()
        except Exception:
            file_sha256 = False
        
        # Lưu hash chữ ký lên blockchain nếu được chọn
        tx_hash = False
        if self.ky_blockchain and model_name == 'van_ban':
            tx_hash = self._sign_on_blockchain()

        # Apply signing to the correct document model
        if model_name == 'van_ban':
            document.write({
                'da_ky_noi_bo': True,
                'ngay_ky_noi_bo': fields.Datetime.now(),
                'nguoi_ky_id': self.nguoi_ky_id.id,
                'chu_ky_noi_bo': self.chu_ky,
                'trang_thai': 'da_ky',
                'bi_khoa': False,  # Chưa khóa, đợi gửi
                'blockchain_tx_hash': tx_hash,
            })

            if document.file_dinh_kem:
                document.file_da_ky = document.file_dinh_kem
                document.ten_file_da_ky = f"SIGNED_{document.ten_file}" if document.ten_file else "SIGNED_document.pdf"

            document._ghi_lich_su(
                'ky',
                f'Ký điện tử văn bản bởi {self.nguoi_ky_id.ten_nv} ({self.chuc_vu or "N/A"}) từ IP: {ip_address}'
            )

            document.message_post(
                body=f'''
                    <p><strong>Văn bản đã được ký điện tử</strong></p>
                    <p>Người ký: {self.nguoi_ky_id.ten_nv} - {self.chuc_vu or "N/A"}</p>
                    <p>Thời gian: {fields.Datetime.now()}</p>
                    <p>IP: {ip_address}</p>
                '''
            )

        elif model_name == 'van_ban_di':
            document.write({
                'da_ky_dien_tu': True,
                'ngay_ky_dien_tu': fields.Datetime.now(),
                'chu_ky_dien_tu': self.chu_ky,
                'trang_thai': 'da_ky',
                'ngay_ky': fields.Date.context_today(self),
            })

            if document.file_dinh_kem:
                document.file_da_ky = document.file_dinh_kem
                document.ten_file_da_ky = f"SIGNED_{document.ten_file}" if document.ten_file else "SIGNED_document.pdf"

            document.message_post(
                body=f'''
                    <p><strong>Văn bản đi đã được ký điện tử</strong></p>
                    <p>Người ký: {self.nguoi_ky_id.ten_nv} - {self.chuc_vu or "N/A"}</p>
                    <p>Thời gian: {fields.Datetime.now()}</p>
                    <p>IP: {ip_address}</p>
                '''
            )

        elif model_name == 'van_ban_den':
            # If no signer assigned yet, assign current signer
            vals = {
                'da_ky_dien_tu': True,
                'ngay_ky_dien_tu': fields.Datetime.now(),
                'chu_ky_dien_tu': self.chu_ky,
            }
            if not document.nguoi_ky_id:
                vals['nguoi_ky_id'] = self.nguoi_ky_id.id
            document.write(vals)

            document.message_post(
                body=f'''
                    <p><strong>Văn bản đến đã được ký điện tử</strong></p>
                    <p>Người ký: {self.nguoi_ky_id.ten_nv} - {self.chuc_vu or "N/A"}</p>
                    <p>Thời gian: {fields.Datetime.now()}</p>
                    <p>IP: {ip_address}</p>
                '''
            )

        # Audit log (valid)
        self._log_signature_attempt(
            model_name, document,
            is_valid=True,
            tx_hash=tx_hash,
            file_sha256=file_sha256,
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Ký thành công!'),
                'message': f'Đã ký điện tử: {self.document_display_type} "{self.document_display_name}".' + (f' Blockchain TX: {tx_hash}' if tx_hash else ''),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }
    
    def _sign_on_blockchain(self):
        """Ký và lưu hash lên blockchain"""
        try:
            # Tạo hash của chữ ký và nội dung văn bản
            signature_data = f"{self.van_ban_id.ten_van_ban}_{self.nguoi_ky_id.ten_nv}_{fields.Datetime.now()}"
            signature_hash = hashlib.sha256(signature_data.encode()).hexdigest()
            
            # Kết nối đến Ethereum network (Infura)
            infura_url = self.env['ir.config_parameter'].sudo().get_param('blockchain.infura_url')
            private_key = self.env['ir.config_parameter'].sudo().get_param('blockchain.private_key')
            
            if not infura_url or not private_key:
                _logger.warning("Blockchain config missing")
                return False
            
            w3 = Web3(Web3.HTTPProvider(infura_url))
            
            # web3 v5 compatibility
            if hasattr(w3, 'isConnected'):
                connected = w3.isConnected()
            else:
                connected = w3.is_connected()

            if not connected:
                _logger.error("Cannot connect to blockchain")
                return False
            
            # Tạo transaction để lưu hash
            account = Account.from_key(private_key)
            
            # Gửi transaction đơn giản (có thể thay bằng smart contract)
            chain_id = self.env['ir.config_parameter'].sudo().get_param('blockchain.chain_id')
            try:
                chain_id = int(chain_id) if chain_id else None
            except Exception:
                chain_id = None

            tx_data = '0x' + signature_hash

            transaction = {
                'to': '0x0000000000000000000000000000000000000000',  # Burn address
                'value': 0,
                'gasPrice': w3.eth.gas_price,
                'nonce': w3.eth.get_transaction_count(account.address),
                'data': tx_data  # Hash trong data field
            }

            if chain_id:
                transaction['chainId'] = chain_id

            # Gas must include intrinsic cost for data; estimate it.
            try:
                transaction['gas'] = w3.eth.estimate_gas(transaction)
            except Exception as e:
                _logger.warning("estimate_gas failed, using safe fallback gas: %s", e)
                transaction['gas'] = 50000
            
            signed_tx = w3.eth.account.sign_transaction(transaction, private_key)
            raw_tx = getattr(signed_tx, 'rawTransaction', None) or getattr(signed_tx, 'raw_transaction', None)
            tx_hash = w3.eth.send_raw_transaction(raw_tx)
            
            return w3.to_hex(tx_hash)
            
        except Exception as e:
            _logger.error("Blockchain signing error: %s", e)
            return False
    
    def action_cancel(self):
        """Hủy ký"""
        return {'type': 'ir.actions.act_window_close'}
