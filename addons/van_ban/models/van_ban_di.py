# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
import base64
import io
import shutil

_logger = logging.getLogger(__name__)

try:
    import pytesseract
    from PIL import Image
    from PIL import ImageOps, ImageFilter
    import pdfplumber
except ImportError as e:
    _logger.warning("Missing OCR libraries: %s", e)

from .ocr_utils import ocr_image_bytes


class VanBanDi(models.Model):
    _name = 'van_ban_di'
    _description = 'Văn bản đi'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'ngay_ban_hanh desc'

    # === THÔNG TIN CƠ BẢN ===
    name = fields.Char('Số ký hiệu', required=True, copy=False, tracking=True)
    so_di = fields.Char('Số đi', required=True, copy=False, 
                        default=lambda self: _('New'), tracking=True)
    
    ngay_ban_hanh = fields.Date('Ngày ban hành', 
                                 default=fields.Date.context_today, 
                                 required=True, tracking=True)
    ngay_gui = fields.Date('Ngày gửi', tracking=True)
    
    trich_yeu = fields.Char('Trích yếu', required=True, tracking=True)
    noi_dung = fields.Text('Nội dung')
    
    # === NƠI NHẬN ===
    noi_nhan = fields.Text('Nơi nhận', required=True, tracking=True)
    khach_hang_ids = fields.Many2many('khach_hang', 
                                      'van_ban_di_khach_hang_rel',
                                      'van_ban_di_id', 'khach_hang_id',
                                      string='Khách hàng nhận')
    
    # === LOẠI VÀ ĐỘ ƯU TIÊN ===
    loai_van_ban_id = fields.Many2one('loai_van_ban', string='Loại văn bản')
    
    do_khan = fields.Selection([
        ('thuong', 'Thường'),
        ('khan', 'Khẩn'),
        ('hoa_toc', 'Hỏa tốc'),
        ('tuc_thi', 'Tức thì')
    ], string='Độ khẩn', default='thuong', required=True, tracking=True)
    
    do_mat = fields.Selection([
        ('thuong', 'Thường'),
        ('mat', 'Mật'),
        ('tuyet_mat', 'Tuyệt mật')
    ], string='Độ mật', default='thuong', required=True, tracking=True)
    
    # === NGƯỜI XỬ LÝ ===
    nguoi_soan_thao_id = fields.Many2one('nhan_vien', string='Người soạn thảo', 
                                          required=True, tracking=True)
    nguoi_ky_id = fields.Many2one('nhan_vien', string='Người ký', 
                                   required=True, tracking=True)
    nguoi_duyet_id = fields.Many2one('nhan_vien', string='Người duyệt', 
                                      tracking=True)
    
    # === QUY TRÌNH ===
    trang_thai = fields.Selection([
        ('soan_thao', 'Soạn thảo'),
        ('cho_duyet', 'Chờ duyệt'),
        ('cho_ky', 'Chờ ký'),
        ('da_ky', 'Đã ký'),
        ('da_gui', 'Đã gửi'),
        ('huy', 'Đã hủy')
    ], string='Trạng thái', default='soan_thao', required=True, tracking=True)
    
    ngay_duyet = fields.Date('Ngày duyệt', tracking=True)
    ngay_ky = fields.Date('Ngày ký', tracking=True)
    
    y_kien_duyet = fields.Text('Ý kiến duyệt')
    ly_do_huy = fields.Text('Lý do hủy')
    
    # Workflow phê duyệt đa cấp
    phe_duyet_chain = fields.Many2many('nhan_vien', string='Chuỗi phê duyệt', help='Danh sách người phê duyệt theo thứ tự')
    
    # === FILE ĐÍNH KÈM ===
    file_dinh_kem = fields.Binary('File văn bản', attachment=True)
    ten_file = fields.Char('Tên file')
    
    file_da_ky = fields.Binary('File đã ký', attachment=True)
    ten_file_da_ky = fields.Char('Tên file đã ký')

    # === KÝ ĐIỆN TỬ ===
    da_ky_dien_tu = fields.Boolean('Đã ký điện tử', readonly=True, tracking=True)
    ngay_ky_dien_tu = fields.Datetime('Ngày ký điện tử', readonly=True, tracking=True)
    chu_ky_dien_tu = fields.Binary('Chữ ký điện tử', readonly=True)

    signature_log_ids = fields.One2many(
        'van_ban.signature.log', 'van_ban_di_id',
        string='Lịch sử ký', readonly=True
    )
    
    # OCR và AI phân tích
    noi_dung_ocr = fields.Text('Nội dung OCR', help='Text được trích xuất từ file đính kèm')
    
    # === THÔNG TIN BỔ SUNG ===
    so_trang = fields.Integer('Số trang')
    so_ban = fields.Integer('Số bản phát hành', default=1)
    
    hinh_thuc_gui = fields.Selection([
        ('truc_tiep', 'Trực tiếp'),
        ('buu_dien', 'Bưu điện'),
        ('email', 'Email'),
        ('fax', 'Fax')
    ], string='Hình thức gửi', default='email', tracking=True)
    
    ghi_chu = fields.Text('Ghi chú')
    
    # === VĂN BẢN LIÊN QUAN ===
    van_ban_den_id = fields.Many2one('van_ban_den', string='Trả lời văn bản đến')
    
    # === HỆ THỐNG ===
    nguoi_tao_id = fields.Many2one('res.users', string='Người tạo', 
                                    default=lambda self: self.env.uid, 
                                    readonly=True)
    ngay_tao = fields.Datetime('Ngày tạo', default=fields.Datetime.now, 
                                readonly=True)
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('so_di', _('New')) == _('New'):
                vals['so_di'] = self.env['ir.sequence'].next_by_code('van_ban_di') or _('New')

        records = super(VanBanDi, self).create(vals_list)

        # Run OCR server-side after create when a file is uploaded.
        for record in records:
            if record.file_dinh_kem and record.ten_file:
                try:
                    record.noi_dung_ocr = record._extract_text_from_file() or False
                except Exception as e:
                    _logger.warning("OCR processing failed (create): %s", e)
                    record.noi_dung_ocr = False

        return records

    def write(self, vals):
        res = super(VanBanDi, self).write(vals)

        # Run OCR server-side on updates when attachment/filename changes.
        if 'file_dinh_kem' in vals or 'ten_file' in vals:
            for record in self:
                if record.file_dinh_kem and record.ten_file:
                    try:
                        record.noi_dung_ocr = record._extract_text_from_file() or False
                    except Exception as e:
                        _logger.warning("OCR processing failed (write): %s", e)
                        record.noi_dung_ocr = False
                else:
                    record.noi_dung_ocr = False

        return res
    
    def action_gui_duyet(self):
        """Gửi văn bản đi duyệt"""
        self.ensure_one()
        if not self.nguoi_duyet_id:
            raise UserError(_('Vui lòng chỉ định người duyệt!'))
        self.write({'trang_thai': 'cho_duyet'})
        self.message_post(body=_('Gửi văn bản đi duyệt'))
        
        # Tạo activity cho người duyệt
        self.activity_schedule(
            'mail.mail_activity_data_todo',
            user_id=self.nguoi_duyet_id.user_id.id,
            summary=_('Duyệt văn bản đi: %s') % self.name
        )
    
    def action_duyet(self):
        """Duyệt văn bản"""
        self.ensure_one()
        # Không bắt buộc nhập ý kiến duyệt, chỉ ghi log
        self.write({
            'trang_thai': 'cho_ky',
            'ngay_duyet': fields.Date.context_today(self)
        })
        self.message_post(body=_('Đã duyệt văn bản'))
        
        # Tạo activity cho người ký
        self.activity_schedule(
            'mail.mail_activity_data_todo',
            user_id=self.nguoi_ky_id.user_id.id,
            summary=_('Ký văn bản đi: %s') % self.name
        )
    
    def action_gui_reminder(self):
        """Gửi reminder cho người duyệt nếu quá hạn"""
        today = fields.Date.context_today(self)
        for record in self:
            # van_ban_di không có trường han_xu_ly, bỏ qua
            if record.trang_thai == 'cho_duyet' and record.nguoi_duyet_id and record.nguoi_duyet_id.user_id:
                record.activity_schedule(
                    'mail.mail_activity_data_todo',
                    user_id=record.nguoi_duyet_id.user_id.id,
                    summary=_('Reminder: Duyệt văn bản %s') % record.name,
                    date_deadline=fields.Date.today()
                )
    
    def action_tu_choi(self):
        """Từ chối duyệt văn bản"""
        self.ensure_one()
        self.write({'trang_thai': 'soan_thao'})
        self.message_post(body=_('Từ chối duyệt: %s') % self.y_kien_duyet)
    
    def action_ky(self):
        """Ký văn bản (kí điện tử + xác minh họ tên)"""
        self.ensure_one()

        if self.trang_thai != 'cho_ky':
            raise UserError(_('Văn bản chưa ở trạng thái Chờ ký!'))

        if not self.file_dinh_kem:
            raise UserError(_('Vui lòng đính kèm file văn bản!'))

        return {
            'name': _('Ký điện tử - Vẽ chữ ký'),
            'type': 'ir.actions.act_window',
            'res_model': 'wizard.ky.dien.tu',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_van_ban_di_id': self.id,
            }
        }
    
    def action_gui(self):
        """Gửi văn bản đi"""
        self.ensure_one()
        if self.trang_thai != 'da_ky':
            raise UserError(_('Chỉ có thể gửi văn bản đã ký!'))
        self.write({
            'trang_thai': 'da_gui',
            'ngay_gui': fields.Date.context_today(self)
        })
        self.message_post(body=_('Đã gửi văn bản'))
    
    def action_huy(self):
        """Hủy văn bản"""
        self.ensure_one()
        if not self.ly_do_huy:
            raise UserError(_('Vui lòng nhập lý do hủy!'))
        self.write({'trang_thai': 'huy'})
        self.message_post(body=_('Hủy văn bản: %s') % self.ly_do_huy)
    
    @api.onchange('file_dinh_kem')
    def _onchange_file_dinh_kem(self):
        """Tự động trích xuất text từ file khi upload"""
        if self.file_dinh_kem and self.ten_file:
            try:
                self.noi_dung_ocr = self._extract_text_from_file()
            except Exception as e:
                _logger.warning("OCR processing failed: %s", e)
                self.noi_dung_ocr = False
    
    def _extract_text_from_file(self):
        """Trích xuất text từ file PDF hoặc ảnh"""
        if not self.file_dinh_kem or not self.ten_file:
            return False

        # Hard requirements for OCR (make failure explicit for real usage)
        missing_python = []
        if 'pdfplumber' not in globals():
            missing_python.append('pdfplumber')
        if 'Image' not in globals():
            missing_python.append('Pillow')
        if 'pytesseract' not in globals():
            missing_python.append('pytesseract')
        if missing_python:
            raise UserError(_(
                'Thiếu thư viện OCR (%s). Cài bằng: pip install -r addons/van_ban/requirements.txt'
            ) % ', '.join(missing_python))

        if not shutil.which('tesseract'):
            raise UserError(_(
                'Thiếu chương trình "tesseract" trên hệ điều hành. Trên Ubuntu/Debian: '
                'sudo apt-get install -y tesseract-ocr tesseract-ocr-vie'
            ))
        
        file_data = base64.b64decode(self.file_dinh_kem)
        file_name = (self.ten_file or '').lower()

        # Detect file type robustly (some storages/flows may not preserve extension)
        header = file_data[:16] if file_data else b''
        is_pdf = file_name.endswith('.pdf') or header.startswith(b'%PDF')
        is_image = file_name.endswith(('.png', '.jpg', '.jpeg', '.tiff', '.bmp')) or (
            header.startswith(b'\x89PNG\r\n\x1a\n') or
            header.startswith(b'\xff\xd8\xff') or
            header.startswith(b'GIF87a') or
            header.startswith(b'GIF89a') or
            header[:2] == b'BM'
        )
        
        try:
            if is_pdf:
                # Xử lý PDF
                with pdfplumber.open(io.BytesIO(file_data)) as pdf:
                    text = ""
                    for page in pdf.pages:
                        page_text = page.extract_text() or ''
                        if page_text:
                            text += page_text + "\n"
                    return text.strip()

            elif is_image:
                # Xử lý ảnh với OCR
                return ocr_image_bytes(Image, ImageOps, ImageFilter, pytesseract, file_data, lang='vie+eng')
            
            else:
                return False
        except Exception as e:
            _logger.error("Text extraction error: %s", e)
            return False
