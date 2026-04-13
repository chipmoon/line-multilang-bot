---
title: Line Multilang OCR Bot
emoji: 📚
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
---

# LINE Bot Multi-language OCR for Kids

Ứng dụng nhận diện chữ cái qua hình ảnh dành cho các bé học ngôn ngữ, tích hợp LINE Messaging API, Google Vision, Translate và Text-to-Speech.

## Triển khai trên Hugging Face Spaces

1. Tạo một New Space trên Hugging Face.
2. Chọn SDK là **Docker**.
3. Trong phần **Settings** -> **Variables and secrets**, hãy thêm các Secrets sau:
   - `LINE_CHANNEL_ACCESS_TOKEN`
   - `LINE_CHANNEL_SECRET`
   - `CLOUDINARY_NAME`
   - `CLOUDINARY_API_KEY`
   - `CLOUDINARY_API_SECRET`
   - `GOOGLE_CREDENTIALS_JSON` (Nội dung file JSON nén thành 1 dòng)
   - `GOOGLE_CLOUD_PROJECT_ID`

## Giấy phép
MIT
