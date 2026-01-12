# Module Quản lý Văn bản với Ký Điện tử

## 📋 Tổng quan

Module quản lý văn bản điện tử với quy trình duyệt và ký điện tử tích hợp. Hỗ trợ quản lý văn bản đến, văn bản đi, và các loại văn bản nội bộ như hợp đồng, báo giá, phụ lục...

## ✨ Tính năng chính

### 1. Quản lý Văn bản
- ✅ Tạo và quản lý văn bản điện tử
- ✅ Phân loại văn bản (Hợp đồng, Báo giá, Phụ lục...)
- ✅ Quản lý văn bản đến/đi
- ✅ Liên kết với Khách hàng và Đơn hàng

### 2. Quy trình Duyệt (Workflow)
- ✅ **Nháp** → **Chờ duyệt** → **Đã duyệt** → **Chờ ký** → **Đã ký**
- ✅ Phân quyền theo vai trò:
  - Nhân viên: Soạn thảo
  - Trưởng phòng: Duyệt
  - Giám đốc: Ký
- ✅ Thông báo tự động cho người liên quan
- ✅ Theo dõi lịch sử thay đổi (Audit Trail)

### 3. Ký Điện tử
#### Ký nội bộ:
- ✅ Người có quyền ký điện tử trong hệ thống
- ✅ Tự động ghi nhận thời gian, người ký
- ✅ Hash file để đảm bảo tính toàn vẹn

#### Ký khách hàng:
- ✅ Gửi email yêu cầu ký với link bảo mật
- ✅ Xác thực OTP qua email
- ✅ Theo dõi trạng thái ký (Chờ ký/Đã ký/Từ chối)
- ✅ Quản lý thời hạn yêu cầu ký

### 4. Bảo mật Văn bản

#### 🔒 Cơ chế Khóa Văn bản (Document Locking)

**Tự động khóa:**
- Văn bản **TỰ ĐỘNG khóa** khi khách hàng ký xong (nếu có yêu cầu ký khách)
- Văn bản **TỰ ĐỘNG khóa** ngay sau khi ký nội bộ (nếu không cần khách ký)

**Khi văn bản bị khóa:**
- ❌ **KHÔNG THỂ** chỉnh sửa các trường quan trọng:
  - Tên văn bản
  - Loại văn bản
  - File đính kèm
  - Khách hàng liên quan
  - Đơn hàng liên quan
  - Giá trị hợp đồng
  - Ngày hiệu lực/hết hạn
  - Mô tả

- ✅ **VẪN CÓ THỂ** cập nhật:
  - Trạng thái văn bản
  - Thông tin ký (do hệ thống tự động)
  - Ghi chú bổ sung
  - Lý do hủy

**Mở khóa:**
- Chỉ **Quản trị viên** có quyền mở khóa
- Cần xác nhận cẩn thận trước khi mở khóa
- Ghi lại lịch sử mở khóa

### 5. Quản lý Thời hạn
- ✅ Tự động tính số ngày còn lại
- ✅ Cảnh báo văn bản sắp hết hạn (30 ngày)
- ✅ Cron job kiểm tra và gửi thông báo
- ✅ Tự động đánh dấu văn bản hết hiệu lực

### 6. Lịch sử và Audit Trail
- ✅ Ghi lại mọi thay đổi quan trọng
- ✅ Theo dõi người thực hiện, thời gian
- ✅ Ghi nhận địa chỉ IP
- ✅ Không thể xóa lịch sử

## 🔐 Phân quyền

### 1. Nhân viên soạn thảo
- Tạo văn bản nháp
- Xem văn bản của mình
- Chỉnh sửa văn bản chưa khóa

### 2. Trưởng phòng
- Tất cả quyền của Nhân viên
- Duyệt/Từ chối văn bản
- Gửi yêu cầu ký cho khách hàng
- Xem tất cả văn bản

### 3. Giám đốc
- Tất cả quyền của Trưởng phòng
- Ký điện tử văn bản

### 4. Quản trị văn bản
- Toàn quyền
- Mở khóa văn bản
- Xóa văn bản
- Quản lý cấu hình

## 📊 Báo cáo và Dashboard

- Dashboard tổng quan văn bản
- Báo cáo theo trạng thái
- Báo cáo theo loại văn bản
- Văn bản sắp hết hạn
- Thống kê ký điện tử

## 🔧 Cấu hình

### Dependencies
```python
'depends': ['base', 'mail', 'nhan_su', 'khach_hang']
```

### Sequence
- Mã văn bản: `VB2025-00001`
- Văn bản đến: `VBĐ2025-00001`
- Văn bản đi: `VBĐi2025-00001`

### Email Templates
- Template yêu cầu ký khách hàng
- Template gửi OTP
- Template xác nhận đã ký

## 🚀 Hướng dẫn sử dụng

### Tạo và ký văn bản (Không cần khách ký)

1. **Nhân viên:** Tạo văn bản nháp
2. **Nhân viên:** Click "Gửi duyệt"
3. **Trưởng phòng:** Click "Duyệt"
4. **Giám đốc:** Click "Ký điện tử"
5. ✅ **Văn bản tự động khóa** - Hoàn tất!

### Tạo và ký văn bản (Có khách hàng ký)

1. **Nhân viên:** Tạo văn bản, chọn Khách hàng
2. **Nhân viên:** Click "Gửi duyệt"
3. **Trưởng phòng:** Click "Duyệt"
4. **Giám đốc:** Click "Ký điện tử" (văn bản CHƯA khóa)
5. **Trưởng phòng:** Click "Gửi yêu cầu ký cho KH"
6. **Khách hàng:** Nhận email, nhập OTP, ký văn bản
7. ✅ **Văn bản tự động khóa** sau khi khách ký - Hoàn tất!

### Mở khóa văn bản (Trường hợp đặc biệt)

1. Chỉ **Quản trị viên** mới có quyền
2. Vào tab "Bảo mật"
3. Click "Mở khóa văn bản"
4. Xác nhận cẩn thận
5. Văn bản có thể chỉnh sửa lại

## ⚠️ Lưu ý quan trọng

### Về khóa văn bản
- Văn bản khóa để đảm bảo tính toàn vẹn sau khi ký
- Chỉ mở khóa khi thực sự cần thiết
- Mọi thao tác mở khóa đều được ghi lại

### Về ký điện tử
- Hiện tại chưa tích hợp chữ ký số theo chuẩn PKI
- Cần tích hợp với nhà cung cấp chứng thư số để sử dụng thực tế
- OTP có hiệu lực 5 phút
- Tối đa 5 lần nhập sai OTP

### Về bảo mật
- Hash MD5 để kiểm tra file không bị thay đổi
- Ghi log đầy đủ với IP address
- Không thể xóa lịch sử thay đổi

## 🐛 Xử lý lỗi thường gặp

### "Văn bản đã bị khóa, không thể chỉnh sửa!"

**Nguyên nhân:** Văn bản đã được ký và tự động khóa

**Giải pháp:**
- Kiểm tra xem văn bản đã ký chưa (tab "Trạng thái ký")
- Nếu cần sửa, liên hệ Quản trị viên để mở khóa
- Sau khi sửa xong, nên khóa lại để bảo mật

### "Văn bản chưa được duyệt!"

**Nguyên nhân:** Cố gắng ký văn bản chưa được duyệt

**Giải pháp:**
- Đảm bảo văn bản ở trạng thái "Đã duyệt" hoặc "Chờ ký"
- Kiểm tra quy trình duyệt

### "Vui lòng chọn khách hàng liên quan!"

**Nguyên nhân:** Gửi yêu cầu ký mà chưa chọn khách hàng

**Giải pháp:**
- Cập nhật trường "Khách hàng liên quan" trước khi gửi yêu cầu ký

## 📝 Changelog

### Version 1.0.0
- ✅ Quản lý văn bản cơ bản
- ✅ Quy trình duyệt
- ✅ Ký điện tử nội bộ
- ✅ Ký điện tử khách hàng
- ✅ Cơ chế khóa văn bản thông minh
- ✅ Audit trail đầy đủ
- ✅ Dashboard và báo cáo

## 👥 Tác giả

**FIT-DNU**

## 📄 License

LGPL-3
