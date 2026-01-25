# AI Integration Module cho Odoo

## Giới thiệu

Module `ai_integration` tích hợp OpenAI (ChatGPT) vào hệ thống Odoo, cung cấp các tính năng AI cho 3 module chính:
- **Quản lý Văn bản (van_ban)**: Tóm tắt, trích xuất metadata, phân tích rủi ro
- **Quản lý Nhân sự (nhan_su)**: Tóm tắt hồ sơ, kiểm tra tài liệu, đề xuất đào tạo
- **Quản lý Khách hàng (khach_hang)**: Customer 360°, phân tích churn, phân loại persona

## Cài đặt

### 1. Cài đặt thư viện Python cần thiết

```bash
pip install openai tiktoken
```

### 2. Cài đặt module trong Odoo

```bash
# Từ thư mục gốc Odoo
./odoo-bin -c odoo.conf -d <database_name> -i ai_integration --stop-after-init
```

### 3. Cập nhật các module liên quan

```bash
./odoo-bin -c odoo.conf -d <database_name> -u van_ban,nhan_su,khach_hang --stop-after-init
```

### 4. Thiết lập API Key

**Cách 1: Qua giao diện Odoo**
1. Đăng nhập với quyền admin
2. Vào Settings > AI Integration
3. Nhập OpenAI API Key
4. Click "Test Connection" để kiểm tra
5. Lưu cài đặt

**Cách 2: Qua Odoo shell**
```bash
./odoo-bin shell -c odoo.conf -d <database_name>
```
```python
env['ir.config_parameter'].sudo().set_param('ai_integration.openai_api_key', 'sk-...')
env.cr.commit()
```

**Cách 3: Qua biến môi trường**
```bash
export OPENAI_API_KEY="sk-..."
```

## Sử dụng

### Module Văn bản (van_ban)

| Tính năng | Mô tả |
|-----------|-------|
| 🤖 Tóm tắt AI | Tóm tắt nội dung văn bản |
| 📋 Trích xuất AI | Trích xuất thông tin từ hợp đồng (bên A, bên B, giá trị, ngày) |
| ⚠️ Phân tích rủi ro | Đánh giá rủi ro pháp lý (0-100) |
| 📝 Đề xuất quy trình | Đề xuất workflow phê duyệt |
| ✉️ Soạn email | Tự động soạn email thông báo |
| 💬 Hỏi AI | Hỏi đáp về văn bản |

### Module Nhân sự (nhan_su)

| Tính năng | Mô tả |
|-----------|-------|
| 🤖 Tóm tắt hồ sơ | Tóm tắt thông tin nhân viên |
| 📋 Kiểm tra hồ sơ | Liệt kê hồ sơ còn thiếu |
| 📚 Đề xuất đào tạo | Đề xuất khóa đào tạo phù hợp |
| ⭐ Viết đánh giá | Tự động viết đánh giá hiệu suất |
| 📄 Trích xuất từ file | Trích xuất thông tin từ CV/tài liệu |
| 💬 Hỏi AI | Hỏi đáp về nhân sự |

### Module Khách hàng (khach_hang)

| Tính năng | Mô tả |
|-----------|-------|
| 🤖 Customer 360° | Phân tích toàn diện khách hàng |
| 🎯 Hành động tiếp theo | Đề xuất NBA (Next Best Action) |
| ⚠️ Rủi ro rời bỏ | Phân tích churn risk |
| 👤 Phân loại Persona | Xác định persona khách hàng |
| ✉️ Soạn email | Soạn email chăm sóc |
| 📋 Tóm tắt ticket | Tóm tắt yêu cầu hỗ trợ |
| 🤖 Gợi ý phản hồi | Đề xuất câu trả lời |

## Cấu hình nâng cao

### Settings > AI Integration

| Tham số | Mô tả | Mặc định |
|---------|-------|----------|
| OpenAI API Key | API key từ OpenAI | (bắt buộc) |
| Model | GPT model sử dụng | gpt-4o-mini |
| Max Tokens | Số token tối đa response | 4096 |
| Temperature | Độ sáng tạo (0-1) | 0.7 |
| Enable Cache | Bật cache responses | True |
| Cache TTL | Thời gian cache (giây) | 3600 |

### API Models được hỗ trợ

- `gpt-4o` - Mạnh nhất, đắt nhất
- `gpt-4o-mini` - Cân bằng giữa chất lượng và giá (recommended)
- `gpt-4-turbo` - Tốc độ cao
- `gpt-3.5-turbo` - Rẻ nhất, phù hợp task đơn giản

## Phân quyền

| Group | Quyền hạn |
|-------|-----------|
| AI User | Sử dụng các tính năng AI cơ bản |
| AI Manager | Quản lý cấu hình, xem logs, quản lý jobs |

## Logging & Monitoring

- Xem logs: Settings > AI Integration > AI Logs
- Xem jobs: Settings > AI Integration > AI Jobs
- Xem cache: Settings > AI Integration > AI Cache

## Background Jobs

Module hỗ trợ xử lý batch qua cron jobs:
- `ir_cron_ai_process_jobs`: Xử lý jobs mỗi 5 phút
- `ir_cron_ai_cleanup_logs`: Dọn logs cũ hàng ngày
- `ir_cron_ai_cleanup_cache`: Dọn cache hết hạn hàng ngày

## Troubleshooting

### Lỗi "API key not configured"
- Kiểm tra API key đã được thiết lập
- Vào Settings > AI Integration để cấu hình

### Lỗi "Rate limit exceeded"
- Giảm số lượng requests
- Bật cache để tái sử dụng responses
- Chờ 1 phút rồi thử lại

### Lỗi "Connection timeout"
- Kiểm tra kết nối internet
- Thử lại sau

## Chi phí ước tính

| Operation | Tokens ước tính | Chi phí (GPT-4o-mini) |
|-----------|-----------------|------------------------|
| Tóm tắt văn bản | ~500 | ~$0.0003 |
| Phân tích rủi ro | ~800 | ~$0.0005 |
| Customer 360° | ~1000 | ~$0.0006 |
| Soạn email | ~600 | ~$0.0004 |

*Chi phí dựa trên pricing tháng 6/2024: $0.15/1M input tokens, $0.6/1M output tokens*

## Liên hệ

- **Author**: FIT-DNU
- **Website**: https://www.fitdnu.com
- **Email**: support@fitdnu.com

## License

LGPL-3
