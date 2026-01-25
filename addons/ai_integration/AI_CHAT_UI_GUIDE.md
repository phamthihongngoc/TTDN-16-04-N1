# Hướng dẫn sử dụng giao diện AI Chat mới

## Đã thực hiện
1. ✅ Tạo template mới `ChatFullPage` với layout conversation cards
2. ✅ Cập nhật JavaScript widget để sử dụng template mới
3. ✅ Thêm CSS styles với màu sắc hài hòa cho Q&A sections
4. ✅ Server đang chạy ở chế độ development (`--dev=all`)

## Cấu trúc UI mới

### Conversation Card Layout
Mỗi cặp câu hỏi-trả lời được hiển thị trong một card với 2 sections:

**Question Section (Màu xanh nhạt)**
- Background: Gradient từ `#f8f9ff` đến `#f0f2ff`
- Border: `#e8ebff`
- Icon: User circle
- Header: "Câu hỏi của bạn" (màu `#667eea`)

**Answer Section (Màu trắng)**
- Background: Trắng
- Icon: Robot
- Header: "Trả lời của AI" (màu `#764ba2`)

### Animations
- **slideIn**: Cards xuất hiện với hiệu ứng trượt từ dưới lên
- **typing**: Indicator chấm chấm khi AI đang suy nghĩ

## Cách xóa cache và xem UI mới

### Bước 1: Xóa browser cache
Trong trình duyệt (Chrome/Firefox):
```
1. Mở DevTools (F12)
2. Nhấn giữ nút Reload
3. Chọn "Empty Cache and Hard Reload"

HOẶC

1. Nhấn Ctrl + Shift + Delete
2. Chọn "Cached images and files"
3. Chọn "All time"
4. Click "Clear data"
```

### Bước 2: Reload trang Odoo
```
1. Nhấn F5 hoặc Ctrl + R
2. Hoặc truy cập lại: http://localhost:8069
```

### Bước 3: Vào AI Chat
```
1. Vào menu "Quản lý Văn bản" > "AI Assistant"
   HOẶC "Quản lý Khách hàng" > "AI Assistant"  
   HOẶC "Quản lý Nhân sự" > "AI Assistant"

2. Gửi một câu hỏi thử nghiệm

3. UI mới sẽ hiển thị với:
   - Header màu gradient tím (purple gradient)
   - Conversation cards màu xanh nhạt (question) và trắng (answer)
   - Icons cho user và AI
   - Timestamps
```

## Troubleshooting

### Nếu vẫn thấy UI cũ:
```bash
# Xóa cache assets của Odoo
cd /home/hongngoc/odoo-fitdnu
rm -rf ~/.local/share/Odoo/filestore/ngoc/sessions/*

# Restart server
pkill -f "python3 odoo-bin"
python3 odoo-bin -c odoo.conf -d ngoc --dev=all
```

### Kiểm tra trong Browser DevTools:
1. Mở DevTools (F12)
2. Tab Console - Xem có lỗi JavaScript không
3. Tab Network - Kiểm tra `ai_chat.scss` đã load chưa
4. Tab Elements - Inspect `.ai-conversation-card` xem có CSS không

## File đã sửa

1. **ai_chat_widget.js** (dòng 17)
   - Đổi template: `ChatWidgetPage` → `ChatFullPage`

2. **ai_chat.scss** (dòng 536-818)
   - Thêm styles cho `.ai-chat-fullpage`
   - Thêm styles cho `.ai-conversation-card`
   - Thêm styles cho `.ai-question-section` và `.ai-answer-section`

3. **Server đang chạy**
   - Port: 8069
   - Database: ngoc  
   - Mode: development (`--dev=all`)

## Màu sắc UI
- **Header**: Gradient từ `#667eea` (xanh tím) đến `#764ba2` (tím)
- **Question Section**: Gradient từ `#f8f9ff` đến `#f0f2ff` (xanh nhạt)
- **Question Text**: `#667eea` (xanh tím)
- **Answer Section**: Background trắng
- **Answer Text**: `#764ba2` (tím)
- **Card Border**: `#e0e0e0` (xám nhạt)
- **Shadows**: `rgba(0,0,0,0.1)` (shadow mềm)

## Nếu cần sửa màu sắc

Chỉnh file `/home/hongngoc/odoo-fitdnu/addons/ai_integration/static/src/scss/ai_chat.scss`:

```scss
// Dòng ~680: Question section colors
.ai-question-section {
    background: linear-gradient(135deg, #YOUR_COLOR_1 0%, #YOUR_COLOR_2 100%);
    border-bottom: 2px solid #YOUR_BORDER_COLOR;
    
    .ai-section-header {
        color: #YOUR_TEXT_COLOR;
    }
}

// Dòng ~695: Answer section colors  
.ai-answer-section {
    background: #YOUR_BG_COLOR;
    
    .ai-section-header {
        color: #YOUR_TEXT_COLOR;
    }
}
```

Sau khi sửa, nhấn F5 trong browser (không cần restart server nếu đang ở chế độ `--dev=all`).
