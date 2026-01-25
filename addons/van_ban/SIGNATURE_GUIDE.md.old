# HƯỚNG DẪN KÝ ĐIỆN TỬ - VẼ CHỮ KÝ

## 📅 Cập nhật: 2026-01-12

---

## 🎨 TÍNH NĂNG MỚI: VẼ CHỮ KÝ ĐIỆN TỬ

### ✨ Điểm mới:

- ✅ **Vẽ chữ ký** trực tiếp trên màn hình (signature pad)
- ✅ **Lưu hình ảnh** chữ ký vào database
- ✅ **Hiển thị** chữ ký đã ký trong văn bản
- ✅ **Xác thực** bằng OTP cho khách hàng
- ✅ **Ghi log** đầy đủ (người ký, thời gian, IP)

---

## 🔄 QUY TRÌNH THỰC TẾ

### 1️⃣ SOẠN VĂN BẢN (Word/PDF)

```
Nhân viên:
- Soạn văn bản trên Word/Google Docs
- Xuất ra PDF
- Vào Odoo: Văn bản → Create
- Upload file PDF
- Điền thông tin: Tên, Loại, Khách hàng (nếu có)
- Save
```

### 2️⃣ GỬI DUYỆT

```
Nhân viên:
- Click nút "Gửi duyệt" (màu cam)
- Trạng thái: Nháp → Chờ duyệt
- Trưởng phòng nhận thông báo
```

### 3️⃣ DUYỆT NỘI DUNG

```
Trưởng phòng:
- Mở văn bản cần duyệt
- Đọc kỹ nội dung
- Kiểm tra file đính kèm

✅ Nếu OK:
   - Click "Duyệt"
   - Trạng thái: Chờ duyệt → Đã duyệt

❌ Nếu cần sửa:
   - Click "Từ chối"
   - Nhập lý do
   - Trạng thái quay về: Nháp
```

### 4️⃣ KÝ ĐIỆN TỬ - VẼ CHỮ KÝ ⭐ MỚI

```
Giám đốc (hoặc người có quyền ký):

Bước 1: Click nút "Ký điện tử" (màu xanh lá)

Bước 2: Popup hiện ra với form:
   ┌───────────────────────────────────┐
   │  🖊️  KÝ ĐIỆN TỬ                   │
   ├───────────────────────────────────┤
   │  Văn bản: [Tên văn bản]          │
   │  Người ký: [Họ tên - Chức vụ]    │
   ├───────────────────────────────────┤
   │  📝 VẼ CHỮ KÝ:                    │
   │  ┌─────────────────────────────┐ │
   │  │                             │ │
   │  │  [Canvas - Vẽ ở đây]       │ │
   │  │                             │ │
   │  └─────────────────────────────┘ │
   │  [Xóa và vẽ lại]                 │
   ├───────────────────────────────────┤
   │  ☑ Tôi xác nhận đã đọc và đồng   │
   │    ý với nội dung văn bản này    │
   ├───────────────────────────────────┤
   │  [Hủy]       [✓ Xác nhận ký]     │
   └───────────────────────────────────┘

Bước 3: VẼ CHỮ KÝ
   - Dùng chuột vẽ chữ ký trong canvas
   - Hoặc dùng stylus nếu có màn hình cảm ứng
   - Nếu vẽ sai → Click "Xóa" → Vẽ lại

Bước 4: Xác nhận
   - Đánh dấu vào ô "Tôi xác nhận..."
   - Click "Xác nhận ký"

Bước 5: Hoàn tất
   ✓ Chữ ký được lưu vào hệ thống
   ✓ Trạng thái: Đã duyệt → Đã ký
   ✓ Văn bản CHƯA khóa (chờ gửi)
   ✓ Hiển thị thông báo thành công
```

**Screenshot chữ ký sau khi ký:**
```
Trong form văn bản, xuất hiện:
┌─────────────────────────────────┐
│  CHỮ KÝ ĐIỆN TỬ               │
├─────────────────────────────────┤
│  Chữ ký nội bộ:                │
│  [Hình ảnh chữ ký đã vẽ]       │
│  👤 Nguyễn Văn A - Giám đốc    │
│  🕐 12/01/2026 10:30:00        │
└─────────────────────────────────┘
```

### 5️⃣ (NẾU CẦN) KHÁCH HÀNG KÝ

```
Trưởng phòng:
- Click "Gửi yêu cầu ký cho KH"
- Hệ thống gửi email cho khách

Khách hàng:
- Nhận email với link ký
- Click link → Mở form ký

Form ký khách hàng:
   ┌───────────────────────────────────┐
   │  🖊️  KÝ ĐIỆN TỬ VĂN BẢN          │
   ├───────────────────────────────────┤
   │  Văn bản: [Tên văn bản]          │
   │  Khách hàng: [Tên công ty]       │
   ├───────────────────────────────────┤
   │  🔐 XÁC THỰC OTP                  │
   │  Mã OTP: [______]  [Gửi lại]    │
   ├───────────────────────────────────┤
   │  📝 VẼ CHỮ KÝ:                    │
   │  ┌─────────────────────────────┐ │
   │  │  [Canvas - Vẽ chữ ký]      │ │
   │  └─────────────────────────────┘ │
   ├───────────────────────────────────┤
   │  ☑ Tôi xác nhận đã đọc...        │
   ├───────────────────────────────────┤
   │  [Hủy]       [✓ Xác nhận ký]     │
   └───────────────────────────────────┘

Các bước:
1. Kiểm tra email → Lấy mã OTP (6 số)
2. Nhập OTP vào form
3. Vẽ chữ ký
4. Đánh dấu xác nhận
5. Click "Xác nhận ký"

Kết quả:
✓ Chữ ký khách được lưu
✓ Văn bản có đầy đủ 2 chữ ký
✓ Sẵn sàng gửi đi
```

### 6️⃣ GỬI VĂN BẢN

```
Trưởng phòng:
- Kiểm tra văn bản đã đủ chữ ký
- Click "Gửi văn bản" (màu xanh dương)
- Xác nhận popup

Kết quả:
✓ Trạng thái: Đã ký → Đã gửi
✓ Văn bản TỰ ĐỘNG KHÓA 🔒
✓ Email gửi cho khách hàng
✓ HOÀN TẤT!
```

---

## 🎨 CHI TIẾT SIGNATURE PAD

### Cách sử dụng:

#### 🖱️ **Trên máy tính:**
- Dùng chuột để vẽ
- Click và giữ chuột trái
- Di chuyển để vẽ chữ ký
- Thả chuột để hoàn tất nét vẽ

#### 📱 **Trên mobile/tablet:**
- Dùng ngón tay hoặc stylus
- Chạm và kéo để vẽ
- Nhấc tay ra để hoàn tất nét vẽ

#### ⚙️ **Các tính năng:**
- **Xóa:** Click "Xóa và vẽ lại" để vẽ lại từ đầu
- **Thu phóng:** Canvas tự động responsive
- **Màu:** Mặc định màu đen (có thể tùy chỉnh)
- **Độ dày:** Nét vẽ tự động theo tốc độ

### Lưu ý khi vẽ:

✅ **NÊN:**
- Vẽ chữ ký tự nhiên như khi ký tay
- Đảm bảo chữ ký rõ ràng, dễ nhận diện
- Vẽ trong khung canvas
- Kiểm tra lại trước khi xác nhận

❌ **KHÔNG NÊN:**
- Vẽ quá nhỏ (khó nhìn)
- Vẽ ra ngoài khung
- Vẽ lung tung, không giống chữ ký thật
- Để trống (bắt buộc phải vẽ)

---

## 🔒 BẢO MẬT

### Chữ ký nội bộ:

```
Khi Giám đốc ký:
✓ Lưu hình ảnh chữ ký (PNG base64)
✓ Ghi nhận người ký
✓ Ghi nhận thời gian chính xác
✓ Ghi nhận IP address
✓ Ghi vào Audit Trail (không xóa được)
```

### Chữ ký khách hàng:

```
Bảo mật 2 lớp:
1. OTP qua email (timeout 5 phút)
2. Link có token bảo mật

Khi khách ký:
✓ Xác thực OTP (max 5 lần thử)
✓ Lưu chữ ký + IP address
✓ Không thể ký lại sau khi đã ký
✓ Ghi log đầy đủ
```

---

## 📊 HIỂN THỊ CHỮ KÝ

### Trong form văn bản:

Sau khi ký, xuất hiện section "Chữ ký điện tử":

```
┌─────────────────────────────────────────┐
│  CHỮ KÝ ĐIỆN TỬ                        │
├─────────────────────────────────────────┤
│  ┌─────────────────┬─────────────────┐ │
│  │ CHỮ KÝ NỘI BỘ  │ CHỮ KÝ KHÁCH   │ │
│  ├─────────────────┼─────────────────┤ │
│  │ [Hình chữ ký]   │ [Hình chữ ký]   │ │
│  │                 │                 │ │
│  │ 👤 Nguyễn Văn A │ 👤 Công ty ABC  │ │
│  │ 🕐 12/01 10:30  │ 🕐 12/01 14:20  │ │
│  └─────────────────┴─────────────────┘ │
└─────────────────────────────────────────┘
```

### Trong lịch sử:

```
📜 Lịch sử thay đổi:
12/01/2026 14:20 | Gửi văn bản        | Admin
12/01/2026 14:20 | Khách hàng ký      | Công ty ABC (IP: 42.119.x.x)
12/01/2026 10:30 | Ký điện tử văn bản | Nguyễn Văn A (IP: 192.168.1.5)
12/01/2026 09:15 | Duyệt văn bản      | Nguyễn Văn B
12/01/2026 08:00 | Tạo văn bản mới    | Nguyễn Văn C
```

---

## 🛠️ KỸ THUẬT

### Model: wizard.ky.dien.tu

```python
class WizardKyDienTu(models.TransientModel):
    _name = 'wizard.ky.dien.tu'
    
    van_ban_id = fields.Many2one('van_ban')
    chu_ky = fields.Binary('Chữ ký')  # Lưu PNG base64
    nguoi_ky_id = fields.Many2one('nhan_vien')
    xac_nhan = fields.Boolean()
    
    def action_ky(self):
        # Lưu chữ ký vào văn bản
        # Cập nhật trạng thái
        # Ghi log
```

### View: Signature widget

```xml
<field name="chu_ky" 
       widget="signature" 
       options="{'size': [600, 200], 'editable': true, 'clear': true}"/>
```

Widget `signature` của Odoo tự động:
- Tạo canvas HTML5
- Capture mouse/touch events
- Convert sang image base64
- Lưu vào Binary field

### CSS: Styling

```css
.o_signature_canvas {
    border: 2px solid #dee2e6;
    background: #ffffff;
    cursor: crosshair;
    width: 100%;
    height: 200px;
}
```

---

## ❓ FAQ

### ❓ Tôi vẽ xấu, có thể dùng ảnh chữ ký sẵn không?

Không được! Phải vẽ trực tiếp trên hệ thống. Điều này:
- Đảm bảo tính xác thực
- Ghi nhận thời gian thực tế
- Có giá trị pháp lý

### ❓ Làm sao để vẽ đẹp hơn?

- Dùng màn hình lớn
- Vẽ chậm rãi
- Dùng stylus nếu có tablet
- Luyện tập vài lần

### ❓ Chữ ký có thể xóa/sửa sau khi đã ký không?

Không! Sau khi click "Xác nhận ký", chữ ký được lưu vĩnh viễn.
Chỉ Admin mới có thể mở khóa văn bản để ký lại.

### ❓ Khách hàng không nhận được OTP?

Kiểm tra:
- Email có đúng không?
- Thư rác (Spam folder)
- SMTP server có hoạt động không?
- Click "Gửi lại OTP" trong form

### ❓ Văn bản đã ký có thể in ra được không?

Có! Chữ ký sẽ hiển thị khi in hoặc xuất PDF.

---

## ✅ CHECKLIST KÝ ĐIỆN TỬ

### Trước khi ký (Nội bộ):

```
☐ Văn bản đã được duyệt?
☐ File đã upload đầy đủ?
☐ Nội dung đã kiểm tra kỹ?
☐ Thông tin chính xác?
→ OK → Click "Ký điện tử"
```

### Khi vẽ chữ ký:

```
☐ Chữ ký rõ ràng, dễ nhận diện?
☐ Vẽ trong khung canvas?
☐ Giống chữ ký thật của bạn?
☐ Đã đánh dấu xác nhận?
→ OK → Click "Xác nhận ký"
```

### Trước khi gửi văn bản:

```
☐ Đã ký nội bộ?
☐ Nếu có khách → Khách đã ký?
☐ Đã kiểm tra lần cuối?
☐ Sẵn sàng KHÓA văn bản?
→ OK → Click "Gửi văn bản"
```

---

## 🎓 KẾT LUẬN

### Ưu điểm của VẼ CHỮ KÝ:

✅ **Trực quan:** Giống ký tay thật
✅ **Dễ dùng:** Không cần USB token, thiết bị đặc biệt
✅ **Nhanh:** Ký trong vài giây
✅ **Bảo mật:** Có OTP, ghi log đầy đủ
✅ **Pháp lý:** Có giá trị như chữ ký tay

### Lưu ý:

⚠️ Đây là chữ ký điện tử đơn giản, KHÔNG phải chữ ký số theo chuẩn PKI
⚠️ Phù hợp cho văn bản nội bộ, hợp đồng doanh nghiệp
⚠️ Nếu cần chữ ký số chuẩn → Tích hợp với nhà cung cấp chứng thư số

---

**Phiên bản:** 2.0.0 (Signature Pad)  
**Tác giả:** FIT-DNU  
**Cập nhật:** 2026-01-12
