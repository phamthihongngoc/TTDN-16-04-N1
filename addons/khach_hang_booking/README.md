# Module Đặt lịch hẹn Khách hàng - Tích hợp Google Calendar & Zoom

## Tổng quan

Module này mở rộng hệ thống quản lý khách hàng với tính năng đặt lịch hẹn tích hợp:
- **Zoom Meeting**: Tự động tạo phòng họp Zoom khi đặt lịch hẹn trực tuyến
- **Google Calendar**: Đồng bộ lịch hẹn lên Google Calendar, gửi email mời

## Cấu trúc Module

```
khach_hang_booking/
├── __init__.py
├── __manifest__.py
├── controllers/
│   ├── __init__.py
│   └── main.py                    # Google OAuth callback
├── data/
│   └── sequence_data.xml          # Sequence cho mã lịch hẹn
├── models/
│   ├── __init__.py
│   ├── zoom_integration.py        # Cấu hình Zoom Server-to-Server OAuth
│   ├── google_calendar_integration.py  # Cấu hình Google OAuth 2.0
│   ├── customer_booking.py        # Model lịch hẹn khách hàng
│   └── khach_hang_extend.py       # Mở rộng model khach_hang
├── security/
│   ├── booking_security.xml       # Security groups và rules
│   └── ir.model.access.csv        # Access control
└── views/
    ├── zoom_integration_views.xml
    ├── google_calendar_integration_views.xml
    ├── customer_booking_views.xml
    ├── khach_hang_views_extend.xml
    └── menu.xml
```

## Hướng dẫn cài đặt

### 1. Cài đặt module

```bash
# Restart Odoo và update apps list
./odoo-bin -c odoo.conf -u khach_hang_booking
```

### 2. Cấu hình Zoom (Server-to-Server OAuth)

1. Truy cập [Zoom Marketplace](https://marketplace.zoom.us/)
2. Tạo app loại **Server-to-Server OAuth**
3. Lấy thông tin:
   - Account ID
   - Client ID
   - Client Secret
4. Cấp scope: `meeting:write:admin`
5. Trong Odoo: **Khách hàng > Lịch hẹn > Cấu hình > Cấu hình Zoom**
6. Nhập thông tin và bấm **Kiểm tra kết nối**

### 3. Cấu hình Google Calendar (OAuth 2.0)

1. Truy cập [Google Cloud Console](https://console.cloud.google.com/)
2. Tạo project hoặc chọn project có sẵn
3. Bật **Google Calendar API**
4. Tạo **OAuth 2.0 Client ID** (loại Web application)
5. Thêm Redirect URI: `http://your-odoo-domain/khach_hang_booking/google_callback`
6. Trong Odoo: **Khách hàng > Lịch hẹn > Cấu hình > Cấu hình Google Calendar**
7. Nhập Client ID, Client Secret, Redirect URI
8. Bấm **Authorize Google** và hoàn tất xác thực

## Luồng sử dụng

### Đặt lịch hẹn từ hồ sơ khách hàng

1. Mở hồ sơ khách hàng
2. Bấm nút **Đặt lịch hẹn** trên header
3. Điền thông tin:
   - Tiêu đề cuộc hẹn
   - Ngày, giờ, thời lượng
   - Hình thức: Trực tiếp hoặc Trực tuyến (Zoom)
4. Bấm **Xác nhận**

### Khi xác nhận lịch hẹn

Hệ thống tự động:
1. Tạo `calendar.event` trong Odoo Calendar
2. Nếu chọn **Trực tuyến (Zoom)**:
   - Gọi Zoom API tạo scheduled meeting
   - Lưu join URL, start URL, password
3. Đồng bộ lên Google Calendar (nếu đã cấu hình)
4. Gửi email mời đến attendees (nếu bật)

### Hủy lịch hẹn

Khi hủy, hệ thống tự động:
- Xóa Zoom meeting
- Xóa event trên Google Calendar
- Archive calendar event trong Odoo

## API Reference

### Zoom Integration

```python
# Lấy cấu hình active
zoom = env['zoom.integration'].get_active_integration()

# Tạo meeting
result = zoom.create_meeting(
    topic="Họp với khách hàng",
    start_time=datetime.now(),
    duration=60,  # phút
    attendees=["customer@email.com"]
)
# result = {
#     'zoom_meeting_id': '123456789',
#     'zoom_join_url': 'https://zoom.us/j/...',
#     'zoom_start_url': 'https://zoom.us/s/...',
#     'zoom_password': 'abc123'
# }

# Cập nhật meeting
zoom.update_meeting(meeting_id, topic="Tiêu đề mới")

# Xóa meeting
zoom.delete_meeting(meeting_id)
```

### Google Calendar Integration

```python
# Lấy cấu hình active
gcal = env['google.calendar.integration'].get_active_integration()

# Tạo event
result = gcal.create_event(
    summary="Họp với khách hàng",
    start_time=datetime(2026, 2, 1, 9, 0),
    end_time=datetime(2026, 2, 1, 10, 0),
    description="Chi tiết cuộc họp",
    location="Zoom: https://zoom.us/j/...",
    attendees=["customer@email.com"]
)
# result = {
#     'google_calendar_event_id': 'abc123...',
#     'google_calendar_link': 'https://calendar.google.com/...'
# }

# Cập nhật event
gcal.update_event(event_id, summary="Tiêu đề mới")

# Xóa event
gcal.delete_event(event_id)
```

## Troubleshooting

### Lỗi Zoom token

**Vấn đề**: `Không thể lấy Zoom access token`

**Giải pháp**:
- Kiểm tra Account ID, Client ID, Client Secret đúng
- Đảm bảo app đã được activate trên Zoom Marketplace
- Kiểm tra scope đã cấp đủ

### Lỗi Google Calendar authorize

**Vấn đề**: `Missing authorization code`

**Giải pháp**:
- Kiểm tra Redirect URI trong Google Cloud Console khớp 100% với cấu hình
- Đảm bảo Google Calendar API đã được bật
- Thử authorize lại với `prompt=consent`

### Không nhận được refresh_token từ Google

**Vấn đề**: Google chỉ trả refresh_token lần đầu authorize

**Giải pháp**:
1. Hủy quyền app tại https://myaccount.google.com/permissions
2. Authorize lại trong Odoo

## Security

- Chỉ Admin (group `base.group_system`) có quyền cấu hình Zoom/Google
- User thường chỉ xem được lịch hẹn của mình
- Booking Manager xem được tất cả lịch hẹn

## License

LGPL-3
