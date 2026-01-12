# THAY ĐỔI LOGIC - Cập nhật 2026-01-12

## 🔄 THAY ĐỔI CHÍNH

### ❌ LOGIC CŨ (Không đúng yêu cầu):
```
Nháp → Duyệt → Ký → [TỰ ĐỘNG KHÓA]
```
**Vấn đề:**
- Khóa quá sớm
- Không có giai đoạn "Gửi đi"
- Không linh hoạt

### ✅ LOGIC MỚI (Đúng yêu cầu):
```
Nháp → Duyệt → [KÝ ĐIỆN TỬ BẮT BUỘC] → Kiểm tra → GỬI ĐI → [KHÓA]
```
**Ưu điểm:**
- Ký điện tử BẮT BUỘC trước khi gửi
- Có thể sửa sau khi ký (trước khi gửi)
- Chỉ khóa khi thực sự gửi đi

---

## 📝 CHI TIẾT THAY ĐỔI

### 1. Model: van_ban.py

#### Thêm trạng thái mới:
```python
('da_gui', 'Đã gửi')  # Trạng thái sau khi gửi văn bản
```

#### Thêm field mới:
```python
ngay_gui = fields.Date('Ngày gửi', tracking=True, readonly=True,
                       help='Ngày gửi văn bản (sau khi ký điện tử)')
```

#### Thêm method mới:
```python
def action_gui_van_ban(self):
    """Gửi văn bản - CHỈ được gửi SAU KHI đã ký điện tử"""
    # Kiểm tra BẮT BUỘC:
    # 1. Đã ký điện tử nội bộ?
    # 2. Nếu có khách → Khách đã ký?
    # 3. Trạng thái = 'da_ky'?
    # → Gửi văn bản → KHÓA
```

#### Sửa method:
```python
def action_ky_noi_bo(self):
    # CŨ: 'bi_khoa': True hoặc not can_khach_ky
    # MỚI: 'bi_khoa': False  # KHÔNG khóa ngay
```

### 2. Model: yeu_cau_ky.py

#### Sửa method:
```python
def action_ky(self):
    # CŨ: 'bi_khoa': True
    # MỚI: 'bi_khoa': False  # Đợi đến khi gửi
```

### 3. Views: van_ban_views.xml

#### Thêm button mới:
```xml
<button name="action_gui_van_ban" 
        string="Gửi văn bản" 
        type="object"
        class="oe_highlight btn-primary"
        attrs="{'invisible': [('trang_thai', '!=', 'da_ky')]}"
        confirm="Xác nhận gửi văn bản? Văn bản sẽ bị KHÓA sau khi gửi."/>
```

#### Cập nhật statusbar:
```xml
<!-- CŨ -->
statusbar_visible="nhap,cho_duyet,da_duyet,cho_ky,da_ky"

<!-- MỚI -->
statusbar_visible="nhap,cho_duyet,da_duyet,cho_ky,da_ky,da_gui"
```

#### Thêm ribbon mới:
```xml
<widget name="web_ribbon" title="Đã gửi ✓" bg_color="bg-success"
        attrs="{'invisible': [('trang_thai', '!=', 'da_gui')]}"/>
```

#### Thêm field trong form:
```xml
<field name="ngay_gui" readonly="1" 
       attrs="{'invisible': [('ngay_gui', '=', False)]}"/>
```

#### Cập nhật tree view:
```xml
<field name="ngay_gui" optional="show"/>
<field name="bi_khoa" widget="boolean" optional="show"/>
```

### 4. Model: lich_su_van_ban.py

#### Thêm action mới:
```python
('gui', 'Gửi văn bản')  # Hành động gửi văn bản
```

---

## 🎯 WORKFLOW MỚI

### Kịch bản 1: Văn bản nội bộ

```
1. Tạo nháp → Gửi duyệt → Duyệt
2. Click "Ký điện tử" (bi_khoa=False, có thể sửa)
3. (Tùy chọn) Kiểm tra lại, sửa nếu cần
4. Click "Gửi văn bản" → bi_khoa=True, trang_thai='da_gui'
5. ✅ Hoàn tất
```

### Kịch bản 2: Hợp đồng với khách hàng

```
1. Tạo nháp (chọn khách hàng) → Gửi duyệt → Duyệt
2. Click "Ký điện tử" nội bộ (bi_khoa=False)
3. Click "Gửi yêu cầu ký cho KH"
4. Khách hàng nhận email → Nhập OTP → Ký
5. Click "Gửi văn bản" → bi_khoa=True, trang_thai='da_gui'
6. ✅ Hoàn tất
```

---

## 📊 BẢNG SO SÁNH

| Tiêu chí | Logic CŨ | Logic MỚI |
|----------|----------|-----------|
| Trạng thái "Đã gửi" | ❌ Không có | ✅ Có |
| Ký điện tử bắt buộc | ⚠️ Không rõ ràng | ✅ Rõ ràng, check khi gửi |
| Khóa văn bản | ❌ Khóa ngay khi ký | ✅ Khóa khi gửi |
| Sửa sau khi ký | ❌ Không được | ✅ Được (trước khi gửi) |
| Field ngay_gui | ❌ Không có | ✅ Có |
| Button "Gửi văn bản" | ❌ Không có | ✅ Có |

---

## ✅ KIỂM TRA

### Test Case 1: Gửi mà chưa ký

```python
Bước 1: Tạo văn bản, duyệt
Bước 2: Click "Gửi văn bản" (bỏ qua ký)
Kết quả: ❌ Lỗi "KHÔNG THỂ GỬI! Văn bản chưa được ký điện tử"
✅ PASS
```

### Test Case 2: Ký xong, sửa được trước khi gửi

```python
Bước 1: Tạo văn bản, duyệt
Bước 2: Click "Ký điện tử"
Bước 3: Sửa tên văn bản
Kết quả: ✅ Sửa được (bi_khoa = False)
✅ PASS
```

### Test Case 3: Sau khi gửi, không sửa được

```python
Bước 1: Tạo văn bản, duyệt, ký
Bước 2: Click "Gửi văn bản"
Bước 3: Thử sửa tên văn bản
Kết quả: ❌ Lỗi "Văn bản đã bị khóa, không thể chỉnh sửa!"
✅ PASS
```

### Test Case 4: Khách chưa ký thì không gửi được

```python
Bước 1: Tạo văn bản có khách hàng, duyệt, ký nội bộ
Bước 2: Click "Gửi văn bản" (chưa gửi yêu cầu ký cho khách)
Kết quả: ❌ Lỗi "CHƯA THỂ GỬI! Văn bản cần chữ ký của khách hàng"
✅ PASS
```

---

## 📚 TÀI LIỆU LIÊN QUAN

Đã tạo các file tài liệu:

1. **README.md** - Hướng dẫn tổng quan module
2. **INSTALL.md** - Hướng dẫn cài đặt và cấu hình
3. **LOGIC_WORKFLOW.md** - Chi tiết logic workflow mới (⭐ ĐỌC FILE NÀY)
4. **SUMMARY.md** - Tóm tắt kiểm tra lần đầu
5. **CHANGELOG.md** - File này, tóm tắt thay đổi

---

## 🚀 CÁI MỚI SAU CẬP NHẬT

### Người dùng sẽ thấy:

1. **Nút mới:** "Gửi văn bản" (màu xanh dương, nổi bật)
2. **Trạng thái mới:** "Đã gửi" trong statusbar
3. **Ribbon mới:** "Đã gửi ✓" màu xanh lá
4. **Field mới:** "Ngày gửi" trong form
5. **Logic mới:** Phải ký trước khi gửi

### Developer cần biết:

1. **Trạng thái mới:** `('da_gui', 'Đã gửi')`
2. **Field mới:** `ngay_gui = fields.Date(...)`
3. **Method mới:** `action_gui_van_ban()`
4. **Method sửa:** `action_ky_noi_bo()`, `action_ky()`
5. **Action mới:** Lịch sử `('gui', 'Gửi văn bản')`

---

## 🔧 HƯỚNG DẪN CẬP NHẬT

### Bước 1: Backup database (QUAN TRỌNG!)

```bash
pg_dump your_database > backup_before_update.sql
```

### Bước 2: Cập nhật module

```bash
cd /home/hongngoc/odoo-fitdnu
python3 odoo-bin.py -c odoo.conf -d your_database -u van_ban --stop-after-init
```

### Bước 3: Kiểm tra

1. Vào menu Văn bản
2. Tạo văn bản test
3. Thử workflow: Nháp → Duyệt → Ký → Gửi
4. Kiểm tra nút "Gửi văn bản" xuất hiện
5. Kiểm tra lỗi khi gửi mà chưa ký

### Bước 4: Training user

1. Thông báo thay đổi workflow
2. Hướng dẫn nút "Gửi văn bản" mới
3. Giải thích: Phải ký trước khi gửi
4. Show demo quy trình mới

---

## ⚠️ LƯU Ý QUAN TRỌNG

### 1. Dữ liệu cũ

Văn bản cũ (trang_thai='da_ky') sẽ:
- Vẫn hiển thị bình thường
- Có nút "Gửi văn bản"
- Có thể click để chuyển sang 'da_gui'

### 2. Quy trình mới

TỪ BÂY GIỜ:
- **BẮT BUỘC** ký điện tử trước khi gửi
- **KHÔNG THỂ** gửi mà chưa ký
- **CÓ THỂ** sửa sau khi ký (trước khi gửi)
- **KHÓA VĨNH VIỄN** sau khi gửi

### 3. Phân quyền

- Nhân viên: Tạo, sửa (nếu chưa khóa)
- Trưởng phòng: Duyệt, Gửi văn bản
- Giám đốc: Ký điện tử
- Admin: Mở khóa (nếu cần)

---

## 📞 HỖ TRỢ

Nếu gặp vấn đề sau khi update:

1. Kiểm tra log Odoo
2. Kiểm tra database đã update đúng chưa
3. Test lại workflow đầy đủ
4. Đọc file LOGIC_WORKFLOW.md để hiểu rõ

---

**Version:** 2.0.0  
**Ngày cập nhật:** 2026-01-12  
**Người thực hiện:** FIT-DNU  
**Trạng thái:** ✅ ĐÃ HOÀN THÀNH VÀ TEST
