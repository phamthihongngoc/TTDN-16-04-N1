# Module `khach_hang` — ML Recommendation + Chatbot Webhook

## 1) Cài dependencies

```bash
python3 -m pip install -r addons/khach_hang/requirements.txt
```

## 2) ML dự đoán sản phẩm (KMeans)

**Logic:** dựa trên lịch sử mua hàng trong `don_hang.line` để fill field computed `san_pham_du_doan_ids`.

### Test nhanh trong UI

1. Tạo **Khách hàng** có `email`.
2. Tạo vài **Đơn hàng** cho khách hàng đó, mỗi đơn có line sản phẩm + số lượng.
3. Mở lại form khách hàng → kiểm tra field **Sản phẩm dự đoán**.

### Test bằng cron

`Settings → Technical → Automation → Scheduled Actions` → tìm cron dự đoán sản phẩm → **Run Manually**.

## 3) Chatbot webhook (Dialogflow fulfillment endpoint)

### Endpoint

- `POST /khach_hang/chatbot/webhook` (JSON)

### Bảo vệ webhook bằng token (khuyến nghị)

Set system parameter:

- Key: `khach_hang.chatbot_token`
- Value: `YOUR_SECRET`

Sau đó gọi webhook kèm:

- Header `X-Chatbot-Token: YOUR_SECRET`

hoặc query string `?token=YOUR_SECRET`.

### Test bằng curl

Ví dụ intent `product_recommendation`:

```bash
curl -s -X POST http://localhost:8069/khach_hang/chatbot/webhook \
  -H "Content-Type: application/json" \
  -H "X-Chatbot-Token: YOUR_SECRET" \
  -d '{
    "session":"projects/x/agent/sessions/test1",
    "queryResult":{
      "intent":{"displayName":"product_recommendation"},
      "parameters":{"email":"test@example.com"}
    }
  }'
```

Kỳ vọng: trả `fulfillmentText` có danh sách sản phẩm nếu khách hàng đã có `san_pham_du_doan_ids`.
