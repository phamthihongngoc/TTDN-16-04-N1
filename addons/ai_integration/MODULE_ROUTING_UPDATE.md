# Cập nhật: AI Assistant phân tách theo Module

## Vấn đề trước đó
- Tất cả 3 AI Assistant (Khách hàng, Văn bản, Nhân sự) đều có thể truy vấn dữ liệu của nhau
- Không có cách phân biệt AI đang phục vụ module nào

## Giải pháp đã triển khai

### 1. Thêm field `module` vào Session
**File**: `ai_integration/models/ai_chat_session.py`

Thêm field để lưu module đang sử dụng AI:
```python
module = fields.Selection([
    ('khach_hang', 'Khách hàng'),
    ('van_ban', 'Văn bản'),
    ('nhan_su', 'Nhân sự'),
], string='Module', help='Module hiện tại')
```

### 2. Menu Actions truyền module context
**Files**: 
- `khach_hang/views/menu.xml`
- `van_ban/views/menu.xml`
- `nhan_su/views/menu.xml`

Mỗi action đã có context riêng:
```xml
<!-- Khách hàng -->
<field name="context">{'default_module': 'khach_hang'}</field>

<!-- Văn bản -->
<field name="context">{'default_module': 'van_ban'}</field>

<!-- Nhân sự -->
<field name="context">{'default_module': 'nhan_su'}</field>
```

### 3. Widget nhận và gửi module
**File**: `ai_integration/static/src/js/ai_chat_widget.js`

Widget nhận `default_module` từ action context:
```javascript
init: function (parent, action) {
    this.module = action.context && action.context.default_module;
    this.activeModel = action.context && action.context.active_model;
    this.activeResId = action.context && action.context.active_id;
}
```

Gửi module khi tạo session:
```javascript
_initChat: function () {
    return this._rpc({
        model: 'ai.chat.session',
        method: 'create_or_get_session',
        args: [{
            module: this.module,  // ← GỬI MODULE
            active_model: this.activeModel,
            active_res_id: this.activeResId,
        }],
    });
}
```

### 4. Orchestrator sử dụng session.module
**File**: `ai_integration/models/ai_chat_orchestrator.py`

#### 4.1. System Prompt theo module
```python
def _get_system_prompt(self, session, context):
    # Ưu tiên dùng session.module
    module = session.module
    
    if module == 'khach_hang':
        base_prompt += """
CONTEXT: Quản lý Khách hàng
Bạn CHỈ có thể truy vấn dữ liệu KHÁCH HÀNG:
- Tìm kiếm khách hàng, đơn hàng, hỗ trợ
LƯU Ý: Không trả lời câu hỏi về văn bản hay nhân sự.
"""
    elif module == 'van_ban':
        base_prompt += """
CONTEXT: Quản lý Văn bản
Bạn CHỈ có thể truy vấn dữ liệu VĂN BẢN:
- Tóm tắt văn bản, trích xuất thông tin
LƯU Ý: Không trả lời câu hỏi về khách hàng hay nhân sự.
"""
    elif module == 'nhan_su':
        base_prompt += """
CONTEXT: Quản lý Nhân sự
Bạn CHỈ có thể truy vấn dữ liệu NHÂN SỰ:
- Tra cứu nhân viên, chấm công, bảng lương
LƯU Ý: Không trả lời câu hỏi về khách hàng hay văn bản.
"""
```

#### 4.2. Tools theo module
```python
def _get_tools_for_session(self, session, context):
    # Ưu tiên dùng session.module
    module = session.module
    
    # Fallback nếu chưa có module
    if not module:
        active_model = session.active_model
        if 'khach_hang' in active_model:
            module = 'khach_hang'
        elif 'van_ban' in active_model:
            module = 'van_ban'
        elif 'nhan_vien' in active_model:
            module = 'nhan_su'
    
    return self.env['ai.chat.tool'].get_tools_for_context(
        module=module,  # ← CHỈ LOAD TOOLS CỦA MODULE ĐÓ
        active_model=active_model
    )
```

#### 4.3. Business Context theo module
```python
def _get_business_context(self, session, context):
    # Ưu tiên dùng session.module
    module = session.module
    
    if module == 'khach_hang':
        provider = self.env['ai.context.khach_hang']
    elif module == 'van_ban':
        provider = self.env['ai.context.van_ban']
    elif module == 'nhan_su':
        provider = self.env['ai.context.nhan_su']
```

## Kết quả

### AI Khách hàng (Menu: Quản lý Khách hàng → AI Assistant)
- ✅ CHỈ truy vấn: khach_hang, don_hang, ho_tro_khach_hang, san_pham
- ✅ CHỈ load 10 tools khách hàng
- ❌ KHÔNG trả lời câu hỏi về văn bản
- ❌ KHÔNG trả lời câu hỏi về nhân sự

### AI Văn bản (Menu: Quản lý văn bản → AI Assistant)
- ✅ CHỈ truy vấn: van_ban, van_ban_di, van_ban_den, loai_van_ban
- ✅ CHỈ load 8 tools văn bản
- ❌ KHÔNG trả lời câu hỏi về khách hàng
- ❌ KHÔNG trả lời câu hỏi về nhân sự

### AI Nhân sự (Menu: Quản lý nhân sự → AI Assistant)
- ✅ CHỈ truy vấn: nhan_vien, phong_ban, cham_cong, bang_luong
- ✅ CHỈ load 9 tools nhân sự
- ❌ KHÔNG trả lời câu hỏi về khách hàng
- ❌ KHÔNG trả lời câu hỏi về văn bản

## Test Case

### Test 1: AI Khách hàng
1. Vào **Quản lý Khách hàng** → **AI Assistant**
2. Hỏi: "Có bao nhiêu khách hàng?"
   - ✅ Trả lời được (dùng tool_search_customer)
3. Hỏi: "Có bao nhiêu văn bản?"
   - ❌ Trả lời: "Xin lỗi, tôi chỉ có thể truy vấn dữ liệu khách hàng"

### Test 2: AI Văn bản
1. Vào **Quản lý văn bản** → **AI Assistant**
2. Hỏi: "Có bao nhiêu văn bản đến?"
   - ✅ Trả lời được (dùng tool_count_van_ban_den)
3. Hỏi: "Có bao nhiêu nhân viên?"
   - ❌ Trả lời: "Xin lỗi, tôi chỉ có thể truy vấn dữ liệu văn bản"

### Test 3: AI Nhân sự
1. Vào **Quản lý nhân sự** → **AI Assistant**
2. Hỏi: "Có bao nhiêu nhân viên?"
   - ✅ Trả lời được (dùng tool_get_all_employees)
3. Hỏi: "Có bao nhiêu khách hàng?"
   - ❌ Trả lời: "Xin lỗi, tôi chỉ có thể truy vấn dữ liệu nhân sự"

## Files đã sửa

1. ✅ `ai_integration/models/ai_chat_session.py` - Thêm field module
2. ✅ `ai_integration/static/src/js/ai_chat_widget.js` - Nhận và gửi module
3. ✅ `ai_integration/models/ai_chat_orchestrator.py` - Routing theo module
4. ✅ Các menu.xml đã có sẵn context

## Migration Notes

- Field mới `module` đã được thêm vào `ai.chat.session`
- Module đã upgrade thành công
- Không cần data migration (field nullable, có fallback logic)

## Lưu ý khi test

1. **Xóa cache browser** sau khi upgrade module
2. **Clear session cũ**: Click nút "Xóa" trong AI Chat để tạo session mới với module đúng
3. **Test cross-module**: Đảm bảo AI từ chối trả lời câu hỏi về module khác
