# LOGIC QUY TRÌNH KÝ ĐIỆN TỬ - PHIÊN BẢN MỚI

## 📅 Cập nhật: 2026-01-12

## 🎯 YÊU CẦU CHÍNH

**KÝ ĐIỆN TỬ LÀ BẮT BUỘC TRƯỚC KHI GỬI VĂN BẢN**

---

## 📋 QUY TRÌNH MỚI

### Workflow đầy đủ:

```
┌─────────┐     ┌────────────┐     ┌──────────┐     ┌─────────┐
│  Nháp   │────▶│ Chờ duyệt  │────▶│ Đã duyệt │────▶│ Chờ ký  │
└─────────┘     └────────────┘     └──────────┘     └─────────┘
                                                           │
                                                           ▼
                                    ┌──────────────────────────────────┐
                                    │  KÝ ĐIỆN TỬ NỘI BỘ (BẮT BUỘC)  │
                                    │      ✍️ Người có quyền ký       │
                                    └──────────────────────────────────┘
                                                           │
                                                           ▼
                                                     ┌─────────┐
                                                     │ Đã ký   │
                                                     └─────────┘
                                                           │
                            ┌──────────────────────────────┴───────────────────────────┐
                            │                                                          │
                    ┌───────▼────────┐                                      ┌─────────▼────────┐
                    │  CÓ khách ký?  │                                      │ KHÔNG khách ký?  │
                    │                │                                      │                  │
                    │  ⚠️  CHỜ       │                                      │  ✓ READY         │
                    └───────┬────────┘                                      └─────────┬────────┘
                            │                                                          │
                    ┌───────▼──────────────┐                                         │
                    │ Gửi yêu cầu ký cho KH│                                         │
                    └───────┬──────────────┘                                         │
                            │                                                          │
                    ┌───────▼────────┐                                                │
                    │ Khách hàng ký  │                                                │
                    │     (OTP)      │                                                │
                    └───────┬────────┘                                                │
                            │                                                          │
                            └──────────────────────┬───────────────────────────────────┘
                                                   │
                                        ┌──────────▼────────────┐
                                        │  CLICK "GỬI VĂN BẢN" │
                                        │   ⚠️  CHECK ĐIỀU KIỆN │
                                        └──────────┬────────────┘
                                                   │
                                        ┌──────────▼────────────┐
                                        │     🔒 KHÓA VĂN BẢN   │
                                        │      ▼                │
                                        │    📤 GỬI ĐI         │
                                        │      ▼                │
                                        │   ✅ ĐÃ GỬI          │
                                        └───────────────────────┘
```

---

## 🔐 ĐIỂM KHÓA VĂN BẢN

### ⚡ LOGIC MỚI - KHÓA KHI GỬI:

```python
Nháp           → bi_khoa = False ✓ Có thể sửa
Chờ duyệt      → bi_khoa = False ✓ Có thể sửa
Đã duyệt       → bi_khoa = False ✓ Có thể sửa
Chờ ký         → bi_khoa = False ✓ Có thể sửa
Đã ký          → bi_khoa = False ✓ VẪN CÓ THỂ SỬA (chưa gửi)
Đã gửi         → bi_khoa = True  🔒 KHÓA - Không sửa được
```

**Lý do:**
- Cho phép chỉnh sửa cuối cùng sau khi ký nhưng chưa gửi
- Đảm bảo văn bản hoàn hảo trước khi gửi đi
- Một khi đã gửi (da_gui) → KHÓA VĨNH VIỄN

---

## ✅ KIỂM TRA KHI GỬI

### Method: `action_gui_van_ban()`

**Kiểm tra bắt buộc:**

```python
1. ✓ Đã ký điện tử nội bộ? (da_ky_noi_bo = True)
   ❌ Nếu chưa → "KHÔNG THỂ GỬI! Văn bản chưa được ký điện tử"

2. ✓ Trạng thái = 'da_ky'?
   ❌ Nếu không → "Chỉ có thể gửi văn bản đã ký!"

3. ✓ Nếu có khách hàng → Khách đã ký? (da_khach_ky = True)
   ❌ Nếu chưa → "CHƯA THỂ GỬI! Văn bản cần chữ ký của khách hàng"

4. ✅ Tất cả OK → GỬI VĂN BẢN + KHÓA
```

---

## 📚 CÁC TRƯỜNG HỢP SỬ DỤNG

### Trường hợp 1: Văn bản nội bộ (KHÔNG cần khách ký)

**Ví dụ:** Quyết định nội bộ, Công văn nội bộ

```
Bước 1: Nhân viên tạo văn bản (không chọn khách hàng)
Bước 2: Gửi duyệt
Bước 3: Trưởng phòng duyệt
Bước 4: Giám đốc click "Ký điện tử"
        → da_ky_noi_bo = True
        → trang_thai = 'da_ky'
        → bi_khoa = False (vẫn sửa được)

Bước 5: (Tùy chọn) Kiểm tra lại, sửa nếu cần

Bước 6: Trưởng phòng click "Gửi văn bản"
        → trang_thai = 'da_gui'
        → ngay_gui = hôm nay
        → bi_khoa = True 🔒
        → Gửi email thông báo (nếu cần)

✅ HOÀN TẤT - Văn bản đã gửi và bị khóa
```

### Trường hợp 2: Hợp đồng với khách hàng (CẦN khách ký)

**Ví dụ:** Hợp đồng mua bán, Hợp đồng dịch vụ

```
Bước 1: Nhân viên tạo văn bản
        - Chọn Khách hàng: Công ty ABC
        - Upload file hợp đồng

Bước 2: Gửi duyệt → Duyệt

Bước 3: Giám đốc click "Ký điện tử" (ký nội bộ trước)
        → da_ky_noi_bo = True
        → trang_thai = 'da_ky'
        → bi_khoa = False

Bước 4: Trưởng phòng click "Gửi yêu cầu ký cho KH"
        → Tạo yeu_cau_ky
        → Gửi email + link ký + OTP
        
Bước 5: Khách hàng mở email
        → Click link ký
        → Nhập OTP
        → Ký điện tử
        → da_khach_ky = True

Bước 6: Trưởng phòng click "Gửi văn bản"
        ✓ Check: da_ky_noi_bo = True
        ✓ Check: da_khach_ky = True
        ✓ Check: trang_thai = 'da_ky'
        → Gửi thành công
        → trang_thai = 'da_gui'
        → bi_khoa = True 🔒
        → Gửi email hợp đồng đã ký cho khách

✅ HOÀN TẤT - Hợp đồng đã có đầy đủ chữ ký và đã gửi
```

### Trường hợp 3: Văn bản cần sửa sau khi ký (trước khi gửi)

```
Bước 1-4: Quy trình bình thường đến "Đã ký"
          → bi_khoa = False

Bước 5: Phát hiện cần sửa (typo, số liệu...)
        ✅ VẪN SỬA ĐƯỢC vì chưa gửi (bi_khoa = False)

Bước 6: Sửa văn bản

Bước 7: KÝ LẠI (nếu sửa nội dung quan trọng)

Bước 8: Click "Gửi văn bản"
        → bi_khoa = True 🔒

✅ HOÀN TẤT - Văn bản đã hoàn hảo mới gửi
```

---

## ⚠️ CÁC LỖI THƯỜNG GẶP VÀ CÁCH XỬ LÝ

### Lỗi 1: "KHÔNG THỂ GỬI! Văn bản chưa được ký điện tử"

**Nguyên nhân:** Click "Gửi văn bản" mà chưa ký điện tử

**Giải pháp:**
```
1. Kiểm tra trạng thái văn bản
2. Click "Ký điện tử" (nút màu xanh lá)
3. Sau đó mới click "Gửi văn bản"
```

### Lỗi 2: "CHƯA THỂ GỬI! Văn bản cần chữ ký của khách hàng"

**Nguyên nhân:** Văn bản có liên kết khách hàng nhưng khách chưa ký

**Giải pháp:**
```
Tùy chọn A: Đợi khách ký
1. Click "Gửi yêu cầu ký cho KH"
2. Đợi khách hàng ký xong
3. Sau đó mới click "Gửi văn bản"

Tùy chọn B: Bỏ yêu cầu khách ký
1. Xóa liên kết khách hàng (nếu không cần)
2. Hoặc liên hệ admin để cấu hình
```

### Lỗi 3: "Văn bản đã bị khóa, không thể chỉnh sửa!"

**Nguyên nhân:** Văn bản đã được gửi (trang_thai = 'da_gui')

**Giải pháp:**
```
Văn bản đã gửi sẽ BỊ KHÓA VĨNH VIỄN để đảm bảo tính pháp lý

Nếu THỰC SỰ CẦN SỬA:
1. Liên hệ Quản trị viên
2. Admin vào tab "Bảo mật"
3. Click "Mở khóa văn bản"
4. Sửa văn bản
5. Nên KÝ LẠI sau khi sửa
6. GỬI LẠI nếu cần
7. Khóa lại
```

---

## 📊 SO SÁNH LOGIC CŨ VS MỚI

### Logic CŨ (SAI):

```
❌ Khóa ngay sau khi ký nội bộ (nếu không có khách)
❌ Khóa ngay khi khách ký xong
❌ Không có giai đoạn "Đã gửi"
❌ Không thể sửa sau khi ký (dù chưa gửi)
```

### Logic MỚI (ĐÚNG):

```
✅ CHỈ khóa khi GỬI VĂN BẢN
✅ Sau khi ký vẫn sửa được (nếu cần)
✅ Có giai đoạn "Đã gửi" riêng biệt
✅ Ký điện tử BẮT BUỘC trước khi gửi
✅ Khách ký xong vẫn có thể kiểm tra lại
✅ Một khi đã gửi → KHÓA VĨNH VIỄN
```

---

## 🎓 WORKFLOW CHI TIẾT

### 1. NHÂN VIÊN SOẠN THẢO

**Quyền:** `group_nhan_vien_soan_thao`

**Có thể:**
- ✓ Tạo văn bản nháp
- ✓ Upload file
- ✓ Chọn loại văn bản, khách hàng
- ✓ Click "Gửi duyệt"

**Không thể:**
- ✗ Duyệt văn bản
- ✗ Ký điện tử
- ✗ Gửi văn bản

### 2. TRƯỞNG PHÒNG DUYỆT

**Quyền:** `group_truong_phong_duyet`

**Có thể:**
- ✓ Tất cả quyền của Nhân viên
- ✓ Click "Duyệt" hoặc "Từ chối"
- ✓ Gửi yêu cầu ký cho khách hàng
- ✓ Click "Gửi văn bản" (sau khi đã ký)

**Không thể:**
- ✗ Ký điện tử (chỉ Giám đốc mới ký)

### 3. GIÁM ĐỐC KÝ

**Quyền:** `group_giam_doc_ky`

**Có thể:**
- ✓ Tất cả quyền của Trưởng phòng
- ✓ Click "Ký điện tử" (**QUAN TRỌNG NHẤT**)

### 4. QUẢN TRỊ VIÊN

**Quyền:** `group_quan_tri_van_ban`

**Có thể:**
- ✓ Toàn quyền
- ✓ Mở khóa văn bản
- ✓ Xóa văn bản

---

## 🔧 CẤU HÌNH CODE

### Model: van_ban.py

**Trạng thái mới:**
```python
('da_gui', 'Đã gửi')  # THÊM MỚI
```

**Field mới:**
```python
ngay_gui = fields.Date('Ngày gửi')  # THÊM MỚI
```

**Method mới:**
```python
def action_gui_van_ban(self):
    """Gửi văn bản - CHỈ được gửi SAU KHI đã ký điện tử"""
    # Kiểm tra bắt buộc ký điện tử
    # Kiểm tra nếu có khách → khách phải ký xong
    # Gửi văn bản → KHÓA
```

**Method sửa:**
```python
def action_ky_noi_bo(self):
    # KHÔNG khóa nữa
    'bi_khoa': False  # Đợi đến khi gửi mới khóa
```

### Model: yeu_cau_ky.py

**Method sửa:**
```python
def action_ky(self):
    # Khách ký xong
    'bi_khoa': False  # KHÔNG khóa, đợi gửi
```

### Views: van_ban_views.xml

**Button mới:**
```xml
<button name="action_gui_van_ban" 
        string="Gửi văn bản" 
        type="object"
        class="oe_highlight btn-primary"
        attrs="{'invisible': [('trang_thai', '!=', 'da_ky')]}"
        confirm="Xác nhận gửi văn bản? Văn bản sẽ bị KHÓA sau khi gửi."/>
```

**Statusbar:**
```xml
statusbar_visible="nhap,cho_duyet,da_duyet,cho_ky,da_ky,da_gui"
```

---

## 📱 MENU CẤU TRÚC

```
📁 Văn bản
├── 📊 Dashboard
├── 📄 Văn bản
│   ├── Tất cả văn bản
│   ├── Nháp (trang_thai='nhap')
│   ├── Chờ duyệt (trang_thai='cho_duyet')
│   ├── Đã duyệt (trang_thai='da_duyet')
│   ├── Đã ký (trang_thai='da_ky')
│   ├── ✨ Đã gửi (trang_thai='da_gui') [MỚI]
│   └── Sắp hết hạn
├── 📥 Văn bản đến
├── 📤 Văn bản đi
├── ✍️ Yêu cầu ký
└── ⚙️ Cấu hình
```

---

## 🎯 KẾT LUẬN

### ✅ LOGIC MỚI HỢP LÝ VÌ:

1. **Ký điện tử BẮT BUỘC** trước khi gửi
2. **Cho phép sửa** sau khi ký nhưng trước khi gửi
3. **Khóa vĩnh viễn** sau khi gửi
4. **Đảm bảo tính pháp lý** của văn bản đã gửi
5. **Linh hoạt** trong quá trình xử lý

### 🎓 QUY TẮC VÀNG:

```
⚡ KÝ ĐIỆN TỬ → KIỂM TRA LẠI → GỬI ĐI → KHÓA
```

**Không được:**
- ✗ Gửi mà chưa ký
- ✗ Sửa sau khi đã gửi (trừ admin mở khóa)

**Được phép:**
- ✓ Ký xong sửa lại (trước khi gửi)
- ✓ Gửi yêu cầu ký cho khách trước khi gửi
- ✓ Kiểm tra kỹ trước khi click "Gửi văn bản"

---

**Phiên bản:** 2.0.0  
**Tác giả:** FIT-DNU  
**Cập nhật:** 2026-01-12
