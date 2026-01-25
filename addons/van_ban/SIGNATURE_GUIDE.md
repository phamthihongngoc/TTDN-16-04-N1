# QUY TRÌNH CHỮ KÝ SỐ PKI - CHUẨN QUỐC TẾ

## 📅 Cập nhật: 2026-01-24

---

## 🎯 MỤC TIÊU CỦA CHỮ KÝ SỐ

Chữ ký số PKI (Public Key Infrastructure) được sử dụng nhằm đảm bảo:

### 1. **Xác thực người ký** 🔐
→ Xác định đúng danh tính chủ thể ký văn bản thông qua Certificate PKI

### 2. **Toàn vẹn dữ liệu** ✅
→ Nội dung văn bản không bị thay đổi sau khi ký (xác minh qua hash)

### 3. **Không thể chối bỏ** 🔒
→ Người ký không thể phủ nhận hành vi ký (private key chỉ người ký có)

### 4. **Tính pháp lý** ⚖️
→ Chữ ký số có giá trị pháp lý tương đương chữ ký tay

---

## 🏗️ THÀNH PHẦN HỆ THỐNG

### 1. **Người ký (Signer)**
- Có tài khoản trong hệ thống
- Được cấp Certificate PKI (Private Key + Public Key)
- Được phân quyền ký văn bản

### 2. **Người nhận / Bên xác thực (Verifier)**
- Có quyền truy cập văn bản đã ký
- Sử dụng Public Key để xác thực chữ ký
- Xác minh tính toàn vẹn của văn bản

### 3. **Hệ thống ký số / Module Văn Bản**
- Quản lý văn bản (tạo, duyệt, ký, gửi)
- Tích hợp PKI Certificate Management
- Quy trình workflow tự động

### 4. **Hạ tầng khóa công khai (PKI)**
- **Private Key**: Khóa riêng tư (bảo mật tuyệt đối) - dùng để KÝ
- **Public Key**: Khóa công khai (có thể chia sẻ) - dùng để XÁC THỰC
- **Certificate**: Chứng thư số X.509 xác thực danh tính

### 5. **File văn bản (PDF)**
- Văn bản cần ký ở định dạng PDF
- Upload vào hệ thống
- Được tạo hash trước khi ký

### 6. **Cơ chế xác thực bổ sung**
- **Xác thực 2 lớp (2FA)**: Password + OTP
- **OTP qua Email**: Mã xác thực gửi email
- **Xác minh họ tên**: Nhập đúng họ tên để xác nhận

---

## 🔄 QUY TRÌNH KÝ SỐ (SIGNING PROCESS)

### **GIAI ĐOẠN I: CHUẨN BỊ**

#### **Bước 0: Tạo Chứng thư số PKI** (Làm 1 lần duy nhất)

```
Người ký:
1. Vào: Cấu hình → Chứng thư số PKI
2. Click "Create"
3. Nhập thông tin:
   - Tên: "Certificate PKI - Giám đốc"
   - Người dùng: [Chọn user]
   - Common Name: Nguyễn Văn A
   - Organization: Công ty TNHH ABC
   - Email: director@company.com
   - Key Size: 2048 bits (khuyến nghị)
   - Hash Algorithm: SHA-256
   - Password: ****** (bảo vệ Private Key)
   - Thời hạn: 1 năm

4. Click "🔐 Tạo Certificate"
5. Hệ thống tự động:
   ✅ Tạo Private Key (mã hóa bằng password)
   ✅ Tạo Public Key
   ✅ Tạo Certificate X.509
   ✅ Lưu vào database
   ✅ Trạng thái: Đang hoạt động

→ Certificate này sẽ được dùng để ký TẤT CẢ văn bản
```

#### **Bước 1: Soạn thảo và chuẩn hóa văn bản**

```
Nhân viên:
1. Soạn văn bản trên Word/Google Docs
2. Xuất ra PDF (định dạng chuẩn)
3. Vào Odoo: Văn bản → Create
4. Upload file PDF
5. Điền thông tin:
   - Tên văn bản: "Hợp đồng thuê nhà số 001/2026"
   - Loại văn bản: Hợp đồng
   - Khách hàng: (nếu có)
   - Người ký: [Chọn Giám đốc]
6. Save
7. Trạng thái: Nháp
```

#### **Bước 2: Gửi duyệt**

```
Nhân viên:
1. Click nút "Gửi duyệt" (màu cam)
2. Trạng thái: Nháp → Chờ duyệt
3. Trưởng phòng nhận thông báo email
```

#### **Bước 3: Duyệt nội dung**

```
Trưởng phòng:
1. Mở văn bản cần duyệt
2. Đọc kỹ nội dung
3. Kiểm tra file đính kèm

✅ Nếu OK:
   - Click "Duyệt"
   - Trạng thái: Chờ duyệt → Đã duyệt
   - Giám đốc nhận thông báo cần ký

❌ Nếu cần sửa:
   - Click "Từ chối"
   - Nhập lý do
   - Trạng thái quay về: Nháp
```

---

### **GIAI ĐOẠN II: KÝ ĐIỆN TỬ PKI** ⭐

#### **Bước 4: Mở wizard ký điện tử**

```
Giám đốc (hoặc người có quyền ký):
1. Mở văn bản đã duyệt
2. Click nút "Ký điện tử" (màu xanh lá)
3. Popup hiện ra với form ký điện tử

→ Hệ thống tự động load Certificate PKI còn hiệu lực
```

#### **Bước 5: Xác thực 2 lớp (2FA)** 🔐

```
┌─────────────────────────────────────────┐
│  🔒 XÁC THỰC 2 LỚP                      │
├─────────────────────────────────────────┤
│  ☑ Yêu cầu OTP (khuyến nghị)            │
│                                         │
│  [Gửi OTP qua Email]                    │
│                                         │
│  Nhập mã OTP: [______]                  │
│                                         │
│  [Xác thực OTP]                         │
└─────────────────────────────────────────┘

Quy trình:
1. Click "Gửi OTP qua Email"
2. Hệ thống gửi mã OTP 6 số đến email
3. Nhập mã OTP vào ô input
4. Click "Xác thực OTP"
5. ✅ Xác thực thành công → Cho phép tiếp tục ký
```

#### **Bước 6: Vẽ chữ ký tay**

```
┌─────────────────────────────────────────┐
│  🖊️  KÝ ĐIỆN TỬ PKI                     │
├─────────────────────────────────────────┤
│  Văn bản: Hợp đồng thuê nhà 001/2026    │
│  Người ký: Nguyễn Văn A - Giám đốc      │
│  Certificate: Certificate PKI - GĐ      │
│  Hết hạn: 15/01/2027                    │
├─────────────────────────────────────────┤
│  📝 VẼ CHỮ KÝ TAY:                      │
│  ┌─────────────────────────────────┐   │
│  │                                 │   │
│  │  [Canvas - Vẽ ở đây]           │   │
│  │                                 │   │
│  └─────────────────────────────────┘   │
│  [Xóa và vẽ lại]                       │
├─────────────────────────────────────────┤
│  Xác minh họ tên: [Nguyễn Văn A]       │
│                                         │
│  ☑ Tôi xác nhận đã đọc và đồng ý       │
│    với nội dung văn bản này            │
├─────────────────────────────────────────┤
│  [Hủy]       [✓ Xác nhận ký]           │
└─────────────────────────────────────────┘

Thao tác:
1. Vẽ chữ ký tay trên canvas (chuột hoặc stylus)
2. Nhập đúng họ tên để xác minh
3. Đánh dấu vào ô "Tôi xác nhận..."
4. Click "Xác nhận ký"
```

#### **Bước 7: Hệ thống thực hiện ký PKI** 🔐

```
Hệ thống tự động thực hiện (backend):

1️⃣ TẠO HASH CỦA FILE PDF
   - Đọc file PDF gốc
   - Tạo SHA-256 hash: 
     a7f8b2c3d4e5f6g7h8i9j0k1l2m3n4o5...
   
2️⃣ MÃ HÓA HASH BẰNG PRIVATE KEY
   - Lấy Private Key từ Certificate
   - Giải mã Private Key bằng password
   - Mã hóa hash bằng Private Key
   - Kết quả: CHỮ KÝ SỐ (Digital Signature)
   
3️⃣ GẮN CHỮ KÝ VÀO VĂN BẢN
   - Lưu chữ ký số vào database
   - Gắn kèm Public Key / Certificate
   - Lưu File Hash (SHA-256)
   - Lưu metadata: thời gian, IP, người ký
   
4️⃣ GHI LOG AUDIT TRAIL
   - Lưu vào Lịch sử ký điện tử
   - Certificate ID
   - Digital Signature
   - Hash Algorithm
   - Verification Status: "signed"
   
5️⃣ LƯU LÊN BLOCKCHAIN (TÙY CHỌN)
   - Tạo combined hash: file + signature
   - Gửi transaction lên Ethereum
   - Lưu Transaction Hash
   
✅ HOÀN TẤT
   - Trạng thái: Đã duyệt → Đã ký
   - File đã ký: SIGNED_HopDong001.pdf
   - Thông báo: "✅ Ký thành công!"
```

---

## ✅ GIAI ĐOẠN III: XÁC THỰC CHỮ KÝ (VERIFICATION)

### **Bước 8: Người nhận xác thực văn bản**

```
Người nhận / Kiểm toán viên:

1. Vào: Văn bản → Mở văn bản đã ký
2. Tab: Chữ ký điện tử → Xem log ký
3. Click vào log cụ thể
4. Click nút "🔍 Xác thực chữ ký số"
```

### **Bước 9: Hệ thống xác thực (backend)**

```
Quy trình xác thực PKI:

1️⃣ LẤY PUBLIC KEY TỪ CERTIFICATE
   - Đọc Public Key từ database
   - Load Certificate của người ký
   
2️⃣ LẤY DIGITAL SIGNATURE
   - Đọc chữ ký số đã lưu
   - Decode từ base64
   
3️⃣ TẠO LẠI HASH TỪ FILE HIỆN TẠI
   - Đọc file PDF hiện tại
   - Tạo SHA-256 hash mới
   
4️⃣ GIẢI MÃ CHỮ KÝ BẰNG PUBLIC KEY
   - Sử dụng Public Key
   - Giải mã Digital Signature
   - Lấy được hash gốc
   
5️⃣ SO SÁNH HAI HASH
   Hash gốc (từ chữ ký) == Hash mới (từ file)?
   
   ✅ TRÙNG NHAU:
      → Chữ ký hợp lệ
      → File không bị thay đổi
      → Người ký xác thực đúng
      → CÓ TÍNH PHÁP LÝ
   
   ❌ KHÁC NHAU:
      → Chữ ký KHÔNG hợp lệ
      → File đã bị thay đổi hoặc chữ ký giả mạo
      → KHÔNG CÓ TÍNH PHÁP LÝ
```

### **Bước 10: Kết quả xác thực**

```
✅ KẾT QUẢ HỢP LỆ:

┌─────────────────────────────────────────┐
│  ✅ XÁC THỰC THÀNH CÔNG                 │
├─────────────────────────────────────────┤
│  1. Chữ ký số hợp lệ                    │
│  2. File không bị thay đổi sau khi ký   │
│  3. Người ký: Nguyễn Văn A              │
│  4. Chứng thư số: Certificate PKI - GĐ  │
│  5. Thời gian ký: 24/01/2026 10:30      │
│  6. IP: 192.168.1.100                   │
│                                         │
│  → Văn bản này CÓ TÍNH PHÁP LÝ         │
│    và không thể chối bỏ.               │
└─────────────────────────────────────────┘

Status: ✅ verified


❌ KẾT QUẢ KHÔNG HỢP LỆ:

┌─────────────────────────────────────────┐
│  ❌ XÁC THỰC THẤT BẠI                   │
├─────────────────────────────────────────┤
│  Chữ ký số KHÔNG HỢP LỆ!               │
│                                         │
│  Nguyên nhân có thể:                    │
│  1. File đã bị thay đổi sau khi ký     │
│  2. Chữ ký bị giả mạo                  │
│  3. Sử dụng sai certificate            │
│                                         │
│  → Văn bản này KHÔNG CÓ TÍNH PHÁP LÝ!  │
└─────────────────────────────────────────┘

Status: ❌ invalid
```

---

## 📊 SƠ ĐỒ LUỒNG QUY TRÌNH

```
┌─────────────────────────────────────────────────────────────┐
│  GIAI ĐOẠN I: CHUẨN BỊ                                     │
└─────────────────────────────────────────────────────────────┘
                           │
     ┌─────────────────────┴─────────────────────┐
     │                                           │
[Tạo Certificate PKI]               [Soạn thảo văn bản]
 (Làm 1 lần duy nhất)                  → PDF → Upload
     │                                           │
     │                                    [Gửi duyệt]
     │                                           │
     │                                    [Trưởng phòng duyệt]
     │                                           │
     └───────────────────┬───────────────────────┘
                         │
┌─────────────────────────────────────────────────────────────┐
│  GIAI ĐOẠN II: KÝ ĐIỆN TỬ PKI                              │
└─────────────────────────────────────────────────────────────┘
                         │
                  [Giám đốc mở wizard ký]
                         │
                  [Xác thực 2FA/OTP]
                         │
                  [Vẽ chữ ký + Xác minh]
                         │
              ┌──────────┴──────────┐
              │  HỆ THỐNG XỬ LÝ    │
              ├─────────────────────┤
              │ 1. Tạo hash file    │
              │ 2. Mã hóa bằng      │
              │    Private Key      │
              │ 3. Tạo chữ ký số    │
              │ 4. Lưu + Public Key │
              │ 5. Blockchain (opt) │
              └──────────┬──────────┘
                         │
                  [✅ Đã ký thành công]
                         │
┌─────────────────────────────────────────────────────────────┐
│  GIAI ĐOẠN III: XÁC THỰC                                   │
└─────────────────────────────────────────────────────────────┘
                         │
              [Người nhận xem văn bản]
                         │
              [Click "Xác thực chữ ký"]
                         │
              ┌──────────┴──────────┐
              │  HỆ THỐNG XÁC THỰC │
              ├─────────────────────┤
              │ 1. Lấy Public Key   │
              │ 2. Giải mã chữ ký   │
              │ 3. Tạo lại hash     │
              │ 4. So sánh hash     │
              └──────────┬──────────┘
                         │
                 ┌───────┴───────┐
                 │               │
          ✅ Hợp lệ      ❌ Không hợp lệ
          (verified)        (invalid)
```

---

## 🔒 BẢO MẬT & TUÂN THỦ

### **1. Quản lý Private Key**
- ✅ Mã hóa bằng password mạnh
- ✅ Chỉ lưu ở database, không export
- ✅ Chỉ admin & chủ sở hữu truy cập được
- ⚠️ KHÔNG BAO GIỜ chia sẻ Private Key

### **2. Quản lý Public Key**
- ✅ Có thể chia sẻ công khai
- ✅ Download để gửi cho đối tác xác thực
- ✅ Đính kèm trong Certificate

### **3. Certificate Lifecycle**
- ✅ Có thời hạn (thường 1 năm)
- ✅ Cảnh báo trước 30 ngày hết hạn
- ✅ Tự động expire khi hết hạn
- ✅ Có thể thu hồi (revoke) nếu cần

### **4. Audit Trail**
- ✅ Log đầy đủ mọi hành động ký
- ✅ Lưu IP, timestamp, certificate
- ✅ Không thể xóa log
- ✅ Có thể xác thực lại bất cứ lúc nào

### **5. Blockchain (Tùy chọn)**
- ✅ Lưu hash lên Ethereum
- ✅ Không thể thay đổi
- ✅ Minh chứng timestamp
- ✅ Tăng tính tin cậy

---

## 🎓 CHUẨN QUỐC TẾ & PHÁP LÝ

### **Tuân thủ theo:**
- ✅ **PKI (Public Key Infrastructure)**: Chuẩn quốc tế
- ✅ **X.509 Certificate**: Định dạng certificate chuẩn
- ✅ **RSA 2048-bit**: Thuật toán mã hóa khuyến nghị
- ✅ **SHA-256**: Thuật toán hash an toàn
- ✅ **PSS Padding**: Chuẩn padding cho RSA signature

### **Tính pháp lý:**
- ✅ Chữ ký số PKI có giá trị pháp lý
- ✅ Đảm bảo: Xác thực, Toàn vẹn, Không chối bỏ
- ✅ Audit trail đầy đủ
- ✅ Có thể xác thực độc lập

---

## 🚀 HƯỚNG DẪN TRIỂN KHAI

### **1. Cài đặt thư viện**
```bash
pip install cryptography
```

### **2. Tạo Certificate cho người ký**
- Vào menu: Cấu hình → Chứng thư số PKI
- Tạo certificate cho từng người có quyền ký
- Lưu password Private Key cẩn thận

### **3. Sử dụng**
- Soạn văn bản → Duyệt → Ký PKI → Gửi
- Người nhận có thể xác thực bất cứ lúc nào

### **4. Bảo trì**
- Gia hạn certificate trước khi hết hạn
- Backup database định kỳ
- Monitor log audit trail

---

## ❓ FAQ

**Q: Private Key có bị lộ không?**
A: Không. Private Key được mã hóa bằng password và chỉ lưu trong database. Không bao giờ export ra ngoài.

**Q: Nếu quên password Private Key?**
A: Phải tạo Certificate mới. Không thể khôi phục password.

**Q: Public Key có cần bảo mật không?**
A: Không. Public Key được thiết kế để chia sẻ công khai.

**Q: Certificate hết hạn thì sao?**
A: Không thể ký văn bản mới. Nhưng văn bản đã ký trước đó vẫn hợp lệ.

**Q: Có thể xác thực văn bản đã ký từ nhiều năm trước?**
A: Có. Miễn là còn lưu Public Key/Certificate và file gốc.

---

## 📞 HỖ TRỢ

Liên hệ: [Admin] hoặc [IT Support]
Email: support@company.com
Phone: 0123.456.789

---

**© 2026 - Module Văn Bản PKI v2.0**
