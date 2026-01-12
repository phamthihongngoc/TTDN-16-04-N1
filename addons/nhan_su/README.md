# Module Quản lý Nhân sự - Tài liệu Hướng dẫn

## Tổng quan

Module này đã được nâng cấp với các tính năng quản lý hồ sơ nhân viên và phân quyền vai trò trong quy trình xử lý văn bản.

## 📋 Các chức năng đã thêm

### 1. Quản lý hồ sơ nhân viên (nhan_vien.py)

#### Thông tin cơ bản đã có:
- Mã nhân viên
- Họ và tên
- Ngày sinh, quê quán, địa chỉ
- Email nội bộ
- Số điện thoại
- Chức vụ, phòng ban
- Thông tin lương

#### Thông tin mới được thêm:
- **Trạng thái làm việc** (`trang_thai_lam_viec`):
  - Đang làm việc
  - Nghỉ việc
  - Tạm nghỉ
  
- **Ngày vào làm** (`ngay_vao_lam`): Ngày bắt đầu làm việc
- **Ngày nghỉ việc** (`ngay_nghi_viec`): Ngày kết thúc làm việc

- **Vai trò** (`vai_tro_ids`): Many2many với model vai_tro - Một nhân viên có thể có nhiều vai trò

- **Người dùng hệ thống** (`user_id`): Liên kết với tài khoản đăng nhập Odoo

### 2. Quản lý vai trò & quyền hạn (vai_tro.py)

Model mới: `vai_tro` - Định nghĩa vai trò và quyền hạn trong hệ thống

#### Thông tin vai trò:
- Tên vai trò (VD: Nhân viên kinh doanh)
- Mã vai trò (VD: NVKD)
- Mô tả
- Thứ tự ưu tiên
- Trạng thái hoạt động

#### Quyền xử lý văn bản:
- ✏️ **Quyền soạn thảo**: Tạo và soạn thảo văn bản mới
- ✅ **Quyền duyệt**: Duyệt văn bản (cấp trưởng phòng)
- ✔️ **Quyền phê duyệt**: Phê duyệt cuối cùng (cấp giám đốc)
- ❌ **Quyền hủy**: Hủy bỏ văn bản đã được duyệt
- 👁️ **Quyền xem tất cả**: Xem toàn bộ văn bản trong hệ thống

#### Quyền quản lý khách hàng:
- ➕ **Quyền thêm khách hàng**: Tạo mới khách hàng
- 📋 **Quyền phân công**: Phân công khách hàng cho nhân viên
- 👥 **Xem tất cả khách hàng**: Xem được tất cả, không chỉ của mình

#### Quyền quản trị:
- 👤 **Quản lý nhân sự**: Thêm/sửa/xóa nhân viên
- 🔐 **Phân quyền**: Gán vai trò cho nhân viên khác

#### Vai trò mặc định:
Module cung cấp 3 vai trò mặc định:

1. **Nhân viên kinh doanh (NVKD)**
   - Soạn thảo văn bản
   - Quản lý khách hàng được phân công
   - Thứ tự: 30

2. **Trưởng phòng (TP)**
   - Tất cả quyền của nhân viên
   - Duyệt văn bản
   - Phân công nhân viên
   - Xem tất cả khách hàng và văn bản
   - Thứ tự: 20

3. **Giám đốc (GD)**
   - Tất cả quyền của trưởng phòng
   - Phê duyệt cuối cùng
   - Hủy văn bản
   - Quản lý nhân sự và phân quyền
   - Thứ tự: 10

### 3. Phân quyền và bảo mật (nhan_su_security.xml)

#### Nhóm quyền (Security Groups):
1. **Nhân viên kinh doanh** (`group_nhan_vien_kinh_doanh`)
2. **Trưởng phòng** (`group_truong_phong`)
3. **Giám đốc** (`group_giam_doc`)
4. **Quản trị nhân sự** (`group_quan_tri_nhan_su`)

#### Record Rules:

**Nhân viên:**
- Nhân viên KD: Chỉ xem nhân viên đang làm việc (read only)
- Trưởng phòng: Xem và sửa nhân viên trong cùng phòng
- Giám đốc: Xem tất cả, tạo mới (không xóa)
- Quản trị: Toàn quyền

**Chấm công:**
- Nhân viên KD: Chỉ xem chấm công của mình
- Trưởng phòng: Xem nhân viên trong phòng
- Quản trị: Xem tất cả

**Bảng lương:**
- Nhân viên KD: Chỉ xem lương của mình (read only)
- Trưởng phòng: Xem và duyệt lương trong phòng
- Quản trị: Toàn quyền

## 🎨 Giao diện (Views)

### View Nhân viên (nhan_vien.xml)

#### Form View:
- **Header**: Hiển thị trạng thái làm việc dạng statusbar
- **Thông tin cá nhân**: Email, SĐT, địa chỉ
- **Thông tin công việc**: 
  - Chức vụ, phòng ban
  - Ngày vào làm, nghỉ việc
  - Vai trò và quyền hạn (many2many tags)
  - Liên kết tài khoản người dùng
- **Tabs**: Chấm công, Bảng lương

#### Tree View:
- Hiển thị trạng thái làm việc với màu sắc:
  - Đang làm: màu xanh lá
  - Tạm nghỉ: màu vàng
  - Nghỉ việc: màu xám mờ
- Hiển thị vai trò dạng tags

#### Search View:
- Filter theo trạng thái (Đang làm/Nghỉ việc)
- Group by trạng thái, phòng ban, chức vụ

### View Vai trò (vai_tro.xml)

#### Form View:
- Button archive/unarchive
- **Tabs**:
  - 📄 Quyền xử lý văn bản
  - 👥 Quyền quản lý khách hàng
  - ⚙️ Quyền quản trị
  - 👤 Danh sách nhân viên có vai trò này
- Có hướng dẫn chi tiết cho từng quyền

#### Tree View:
- Sắp xếp thứ tự bằng handle
- Toggle nhanh các quyền
- Hiển thị số nhân viên

#### Kanban View:
- Hiển thị dạng card
- Badge cho các quyền chính

## 📁 Cấu trúc thư mục

```
addons/nhan_su/
├── models/
│   ├── __init__.py          # Import các model
│   ├── nhan_vien.py         # Model nhân viên (đã nâng cấp)
│   ├── vai_tro.py           # Model vai trò (MỚI)
│   ├── cham_cong.py         # Model chấm công
│   └── bang_luong.py        # Model bảng lương
├── views/
│   ├── nhan_vien.xml        # Views nhân viên (đã nâng cấp)
│   ├── vai_tro.xml          # Views vai trò (MỚI)
│   ├── cham_cong.xml        # Views chấm công
│   ├── bang_luong.xml       # Views bảng lương
│   └── menu.xml             # Menu (đã nâng cấp)
├── security/
│   ├── nhan_su_security.xml # Security groups và rules (MỚI)
│   └── ir.model.access.csv  # Access rights (đã nâng cấp)
├── __init__.py
└── __manifest__.py          # Manifest (đã nâng cấp)
```

## 🚀 Cách sử dụng

### 1. Cài đặt/Nâng cấp module

```bash
# Nâng cấp module
./odoo-bin -u nhan_su -d your_database

# Hoặc từ giao diện Odoo: Apps > Nâng cấp
```

### 2. Tạo vai trò mặc định

Sau khi cài đặt, vào menu:
**Quản lý nhân sú > Quản lý > Vai trò & Quyền hạn**

Chạy Server Action "Tạo vai trò mặc định" để tạo 3 vai trò cơ bản.

### 3. Gán vai trò cho nhân viên

1. Vào **Quản lý nhân sú > Quản lý > Nhân viên**
2. Chọn nhân viên cần gán vai trò
3. Trong tab "Thông tin công việc", chọn vai trò tại trường "Vai trò"
4. Có thể chọn nhiều vai trò cho một nhân viên

### 4. Gán nhóm quyền cho người dùng

1. Vào **Cài đặt > Người dùng & Công ty > Người dùng**
2. Chọn người dùng
3. Tab "Quyền truy cập" > "Quản lý nhân sự"
4. Chọn quyền tương ứng:
   - Nhân viên kinh doanh
   - Trưởng phòng
   - Giám đốc
   - Quản trị nhân sự

### 5. Liên kết nhân viên với tài khoản người dùng

Để các Record Rules hoạt động đúng:
1. Vào form nhân viên
2. Chọn "Người dùng hệ thống" để liên kết với tài khoản Odoo
3. Điều này cho phép hệ thống biết ai đang đăng nhập để áp dụng quyền chính xác

## 🔗 Tích hợp với module khác

Module này đã sẵn sàng để tích hợp với:

### Module Quản lý Văn bản:
- Sử dụng `vai_tro_ids` để kiểm soát quyền trong workflow văn bản
- Kiểm tra `quyen_soan_thao`, `quyen_duyet`, `quyen_phe_duyet`
- Ví dụ:
```python
# Kiểm tra quyền duyệt
if any(vai_tro.quyen_duyet for vai_tro in nhan_vien.vai_tro_ids):
    # Cho phép duyệt văn bản
    pass
```

### Module Quản lý Khách hàng:
- Sử dụng `quyen_phan_cong_khach_hang` để phân công
- Sử dụng `quyen_xem_khach_hang_tat_ca` để lọc dữ liệu
- Ví dụ:
```python
# Lọc khách hàng theo quyền
if not nhan_vien.has_quyen_xem_tat_ca():
    domain.append(('nhan_vien_phu_trach', '=', nhan_vien.id))
```

## 📊 Workflow ví dụ

### Quy trình duyệt văn bản:

1. **Nhân viên kinh doanh** (NVKD):
   - Soạn thảo văn bản mới
   - Trạng thái: "Nháp"

2. **Trưởng phòng** (TP):
   - Xem văn bản cần duyệt
   - Kiểm tra và duyệt
   - Trạng thái: "Đã duyệt"

3. **Giám đốc** (GD):
   - Xem văn bản đã duyệt
   - Phê duyệt cuối cùng
   - Trạng thái: "Đã phê duyệt"

### Quy trình phân công khách hàng:

1. **Trưởng phòng**:
   - Xem danh sách khách hàng mới
   - Phân công cho nhân viên trong phòng

2. **Nhân viên**:
   - Nhận thông báo khách hàng được phân công
   - Chỉ xem được khách hàng của mình
   - Cập nhật thông tin tương tác

3. **Giám đốc**:
   - Xem tất cả khách hàng
   - Theo dõi tình hình xử lý

## ⚠️ Lưu ý quan trọng

1. **Security Groups**: Phải gán đúng nhóm quyền cho người dùng thì mới hoạt động

2. **Record Rules**: Một số rule dựa vào `user.employee_id.phong_ban`, cần đảm bảo:
   - Người dùng đã được liên kết với nhân viên
   - Phòng ban được điền đúng

3. **Vai trò mặc định**: Nên chạy action "Tạo vai trò mặc định" ngay sau khi cài đặt

4. **Quyền Menu**: 
   - Menu "Vai trò & Quyền hạn" chỉ hiển thị cho Giám đốc và Quản trị
   - Menu "Bảng lương" chỉ hiển thị cho Trưởng phòng trở lên

5. **Upgrade Module**: Sau khi thay đổi code, nhớ upgrade module:
   ```bash
   ./odoo-bin -u nhan_su -d your_database
   ```

## 🎯 Kế hoạch mở rộng

Có thể thêm các tính năng:

1. **Lịch sử thay đổi vai trò**: Theo dõi ai thay đổi vai trò của nhân viên, khi nào

2. **Quyền động**: Cho phép tạo quyền tùy chỉnh không chỉ cố định

3. **Workflow builder**: Giao diện kéo thả để thiết kế quy trình duyệt

4. **Dashboard**: Thống kê nhân viên theo vai trò, phòng ban, trạng thái

5. **Thông báo**: Tự động thông báo khi có văn bản cần duyệt dựa vào vai trò

## 📞 Hỗ trợ

Nếu có vấn đề khi sử dụng module, kiểm tra:

1. Log Odoo: Xem có lỗi gì không
2. Quyền truy cập: Đảm bảo người dùng có nhóm quyền phù hợp
3. Record Rules: Kiểm tra domain có đúng không

---

**Phiên bản**: 1.0  
**Tác giả**: FitDNU  
**Ngày cập nhật**: 11/01/2026
