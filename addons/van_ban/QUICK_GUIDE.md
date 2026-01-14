# QUICK GUIDE

## OCR (PDF/Ảnh → Text)

### 1) Cài dependencies Python

```bash
python3 -m pip install -r addons/van_ban/requirements.txt
```

### 2) Cài `tesseract` trên hệ điều hành

Ubuntu/Debian:

```bash
sudo apt-get update
sudo apt-get install -y tesseract-ocr tesseract-ocr-vie
```

### 3) Test trong UI

Vào **Văn bản đi** → upload file vào trường **File văn bản** (PDF hoặc ảnh `.png/.jpg/...`).

Kỳ vọng: trường **Nội dung OCR** tự động được điền.

Nếu thiếu dependency, hệ thống sẽ báo lỗi rõ ràng để bạn cài đúng gói.

## Blockchain signing (ghi hash lên blockchain)

### 1) Cài dependencies

```bash
python3 -m pip install -r addons/van_ban/requirements.txt
```

### 2) Cấu hình System Parameters

`Settings → Technical → Parameters → System Parameters`

- `blockchain.infura_url`: URL RPC (Infura/Alchemy/hoặc node riêng)
- `blockchain.private_key`: private key ví ký (cẩn thận bảo mật)
- (Tuỳ chọn) `blockchain.chain_id`: chain id (vd 1 mainnet, 11155111 sepolia)

### 3) Test

Mở văn bản `van_ban` (trạng thái `da_duyet` hoặc `cho_ky`) → chạy wizard ký điện tử.

- Nếu cấu hình đủ và kết nối được: field `blockchain_tx_hash` sẽ có giá trị.
- Nếu thiếu cấu hình hoặc không kết nối: hệ thống vẫn ký nội bộ, nhưng `blockchain_tx_hash` trống.

# HƯỚNG DẪN SỬ DỤNG NHANH - Module Văn bản

## 🚀 QUY TRÌNH CHUẨN

### ⚡ 6 BƯỚC ĐƠN GIẢN

```
1. TẠO     →  2. GỬI DUYỆT  →  3. DUYỆT  →  4. KÝ ĐIỆN TỬ  →  5. GỬI VĂN BẢN  →  6. XONG
   📝            📤               ✅            ✍️                📬                  ✓
```

---

## 📝 HƯỚNG DẪN CHI TIẾT

### 1️⃣ TẠO VĂN BẢN (Nhân viên)

```
Menu: Văn bản → Văn bản → Create

Điền thông tin:
✓ Tên văn bản
✓ Loại văn bản (Hợp đồng, Báo giá...)
✓ Khách hàng (nếu có)
✓ Upload file PDF
✓ Nhập mô tả, giá trị hợp đồng...

Click: Save
```

### 2️⃣ GỬI DUYỆT (Nhân viên)

```
Click nút: "Gửi duyệt" (màu cam)

→ Trạng thái: Chờ duyệt
→ Trưởng phòng nhận thông báo
```

### 3️⃣ DUYỆT (Trưởng phòng)

```
Vào văn bản cần duyệt

Kiểm tra nội dung → OK?

✅ Click: "Duyệt" → Trạng thái: Đã duyệt
❌ Click: "Từ chối" → Trả lại soạn thảo
```

### 4️⃣ KÝ ĐIỆN TỬ (Giám đốc) ⭐ QUAN TRỌNG

```
Vào văn bản đã duyệt

Click nút: "Ký điện tử" (màu xanh lá)

✅ Đã ký điện tử
✅ Trạng thái: Đã ký
⚠️  Văn bản CHƯA khóa - vẫn sửa được
```

**LƯU Ý:** Nếu phát hiện cần sửa → Sửa ngay → Ký lại

### 5️⃣ GỬI VĂN BẢN (Trưởng phòng) ⭐ BƯỚC MỚI

```
Kiểm tra lần cuối

Click nút: "Gửi văn bản" (màu xanh dương)

Xác nhận: "Văn bản sẽ bị KHÓA sau khi gửi"

→ Click OK

✅ Trạng thái: Đã gửi
🔒 Văn bản đã KHÓA - không sửa được nữa
📧 Email gửi cho khách hàng (nếu có)
```

### 6️⃣ HOÀN TẤT

```
✓ Văn bản đã gửi
✓ Đã có chữ ký điện tử
✓ Đã bị khóa
✓ Khách hàng đã nhận

→ XONG!
```

---

## 🔐 TRƯỜNG HỢP ĐẶC BIỆT

### 📝 Văn bản CÓ khách hàng ký

**Thêm bước giữa 4 và 5:**

```
4. Ký điện tử nội bộ
   ↓
4a. Click: "Gửi yêu cầu ký cho KH"
    → Khách nhận email
    → Khách nhập OTP
    → Khách ký điện tử
   ↓
5. Click: "Gửi văn bản"
```

### ✏️ Cần sửa sau khi ký (trước khi gửi)

```
✅ ĐƯỢC PHÉP!

Điều kiện: Văn bản ở trạng thái "Đã ký" NHƯNG chưa "Gửi"

Cách làm:
1. Sửa văn bản như bình thường
2. Nên KÝ LẠI sau khi sửa
3. Click "Gửi văn bản"
```

### 🔓 Cần sửa SAU KHI ĐÃ GỬI

```
❌ KHÔNG ĐƯỢC!

Văn bản đã gửi → Đã khóa vĩnh viễn

Nếu THỰC SỰ CẦN:
1. Liên hệ Admin/Quản trị viên
2. Admin mở khóa (tab "Bảo mật")
3. Sửa văn bản
4. KÝ LẠI
5. GỬI LẠI
```

---

## ⚠️ LỖI THƯỜNG GẶP

### ❌ "KHÔNG THỂ GỬI! Văn bản chưa được ký điện tử"

**Nguyên nhân:** Bạn bỏ qua bước Ký điện tử

**Giải pháp:**
```
1. Tìm người có quyền Giám đốc
2. Họ click "Ký điện tử"
3. Sau đó mới click "Gửi văn bản"
```

### ❌ "Văn bản đã bị khóa, không thể chỉnh sửa!"

**Nguyên nhân:** Văn bản đã gửi (trang_thai = 'Đã gửi')

**Giải pháp:**
```
Văn bản đã gửi thì KHÓA rồi!

Nếu cần sửa:
→ Liên hệ Quản trị viên mở khóa
```

### ❌ "CHƯA THỂ GỬI! Văn bản cần chữ ký của khách hàng"

**Nguyên nhân:** Văn bản có liên kết khách hàng nhưng khách chưa ký

**Giải pháp:**
```
1. Click "Gửi yêu cầu ký cho KH"
2. Đợi khách ký xong
3. Sau đó mới "Gửi văn bản"
```

---

## 🎨 NHẬN BIẾT TRẠNG THÁI

### Màu sắc trên danh sách:

- **Trắng:** Nháp, Chờ duyệt
- **Xanh dương:** Đã ký
- **Xanh lá:** Đã gửi ✓
- **Vàng:** Sắp hết hạn ⚠️
- **Đỏ:** Hết hiệu lực
- **Xám:** Đã hủy

### Ribbon (góc phải form):

- **"Đã gửi ✓"** màu xanh lá → Văn bản đã gửi
- **"Đã ký"** màu xanh dương → Đã ký nhưng chưa gửi
- **"Đã khóa 🔒"** màu vàng → Văn bản bị khóa

---

## 🔘 CÁC NÚT CHÍNH

### Theo thứ tự workflow:

| Nút | Màu | Ai nhấn | Khi nào |
|-----|-----|---------|---------|
| **Gửi duyệt** | Cam | Nhân viên | Văn bản nháp |
| **Duyệt** | Xanh lá | Trưởng phòng | Chờ duyệt |
| **Từ chối** | Xám | Trưởng phòng | Chờ duyệt |
| **Ký điện tử** | Xanh lá đậm | Giám đốc | Đã duyệt |
| **Gửi yêu cầu ký cho KH** | Xanh dương | Trưởng phòng | Đã ký (nếu có KH) |
| **Gửi văn bản** | Xanh dương | Trưởng phòng | Đã ký |
| **Hủy** | Xám | Mọi người | Bất kỳ (trước khi gửi) |

---

## 📊 KIỂM TRA NHANH

### ✅ Checklist trước khi gửi:

```
□ Đã ký điện tử nội bộ?
□ Nếu có KH → Khách đã ký?
□ Đã kiểm tra nội dung lần cuối?
□ File đính kèm đúng?
□ Thông tin khách hàng đúng?

→ Tất cả OK? Click "Gửi văn bản"!
```

---

## 💡 MẸO VẶT

### 1. Tìm văn bản cần xử lý

```
Menu → Văn bản → Click các filter:
- "Chờ duyệt" → Văn bản cần duyệt
- "Đã ký" → Văn bản cần gửi
- "Văn bản của tôi" → Văn bản tôi tạo
```

### 2. Theo dõi lịch sử

```
Mở văn bản → Tab "Lịch sử"
→ Xem ai làm gì khi nào
```

### 3. Nhắc nhở

```
Hệ thống tự động gửi thông báo khi:
- Có văn bản cần duyệt
- Có văn bản cần ký
- Văn bản sắp hết hạn
```

---

## 🎓 QUY TẮC VÀNG

```
1. Phải KÝ ĐIỆN TỬ trước khi GỬI
2. Một khi đã GỬI → KHÓA vĩnh viễn
3. Kiểm tra KỸ trước khi click "Gửi văn bản"
```

---

## 📞 LIÊN HỆ

Gặp vấn đề? Liên hệ:
- Quản trị viên hệ thống
- Bộ phận IT
- Xem thêm: README.md, LOGIC_WORKFLOW.md

---

**Version:** 2.0.0  
**Cập nhật:** 2026-01-12
