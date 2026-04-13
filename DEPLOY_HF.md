# Hướng dẫn Deploy LINE Bot lên Hugging Face Spaces (FREE 100%)

## Tại sao Hugging Face?
*   **100% Miễn phí:** Không cần thẻ tín dụng.
*   **Cấu hình mạnh:** 16GB RAM, 2 vCPU.
*   **Always-on:** Không bao giờ ngủ, phản hồi bot cực nhanh.

---

## Bước 1: Lưu code lên GitHub
Hãy chạy lệnh sau để cập nhật code mới (đã sửa port 7860) lên GitHub của bạn:

```powershell
git add .
git commit -m "deploy: migrate to Hugging Face Spaces"
git push
```

---

## Bước 2: Tạo Space trên Hugging Face
1. Bạn vào [huggingface.co/new-space](https://huggingface.co/new-space).
2. **Space name**: Đặt tên bất kỳ (ví dụ: `line-ocr-bot`).
3. Dưới mục **Choose a Docker template**, chọn **Blank** (nằm bên trái cùng).
4. Nhấn **Create Space** ở cuối trang. 
*(Hugging Face không có nút "Kết nối GitHub" tự động như các nền tảng khác. Bản thân mỗi Hugging Face Space là một Git Repository).*

---

## Bước 3: Đẩy code tự động bằng GitHub Actions (Tối ưu nhất)
Tôi đã tạo sẵn một file tự động hóa (`.github/workflows/sync_to_hf.yml`). Nhiệm vụ của bạn chỉ là kết nối chìa khóa (Token) giữa GitHub và Hugging Face như sau:

1. **Lấy Token từ Hugging Face:**
   - Vào [https://huggingface.co/settings/tokens](https://huggingface.co/settings/tokens).
   - Nhấn **Create new token**, loại quyền chọn **Write** (để có thể ghi code mới).
   - Copy mã token đó lại.

2. **Cài đặt Token vào GitHub:**
   - Vào trang GitHub của bạn (`https://github.com/chipmoon/line-multilang-bot`).
   - Vào tab **Settings** -> Mở mục **Secrets and variables** (ở cột trái) -> Chọn **Actions**.
   - Bấm nút **New repository secret**.
   - **Name**: Nhập chữ `HF_TOKEN`
   - **Secret**: Dán cái token vừa copy ở Hugging Face vào.
   - Nhấn **Add secret**.

3. **Cập nhật link trong code:**
   - Bạn mở file `.github\workflows\sync_to_hf.yml` trong máy của bạn lên. Ở dòng 14, hãy sửa đoạn `TEN_USER_HF/TEN_SPACE_CUA_BAN` thành link thực tế trên Hugging Face của bạn.
   - Quá trình hoàn tất! Từ giờ, bạn cứ đẩy code bằng lệnh Git lên GitHub là code tự bay thẳng sang Hugging Face. Lệnh đẩy code:
     ```powershell
     git add .
     git commit -m "update code and github action"
     git push
     ```

---

## Bước 4: Cài đặt Secrets (Cực kỳ quan trọng)
Sau khi đẩy code lên, bạn vào trang quản lý Space của bạn trên Hugging Face, chọn tab **Settings**. Cuộn xuống phần **Variables and secrets** -> Nhấn **New secret** cho từng mục sau:

| Name | Value |
| :--- | :--- |
| `LINE_CHANNEL_ACCESS_TOKEN` | (Lấy từ .env) |
| `LINE_CHANNEL_SECRET` | (Lấy từ .env) |
| `CLOUDINARY_NAME` | (Lấy từ .env) |
| `CLOUDINARY_API_KEY` | (Lấy từ .env) |
| `CLOUDINARY_API_SECRET` | (Lấy từ .env) |
| `GOOGLE_CLOUD_PROJECT_ID` | `linebot-490113` |
| `GOOGLE_CREDENTIALS_JSON` | (Nội dung file JSON nén 1 dòng) |

> [!TIP]
> Để nén file `credentials.json` thành 1 dòng, chạy lệnh này trong PowerShell:
> ```powershell
> $json = Get-Content -Raw "credentials.json" -Encoding UTF8; ($json | ConvertFrom-Json | ConvertTo-Json -Compress) | Set-Clipboard
> ```
> Sau đó chỉ việc Paste vào ô Value của `GOOGLE_CREDENTIALS_JSON` trên Hugging Face.

---

## Bước 5: Cập nhật Webhook trên LINE
1. Chờ Hugging Face báo trạng thái **Running** màu xanh.
2. Lấy URL của Space. Có dạng: `https://ten_user_hf-ten_space.hf.space`
3. Vào LINE Developers Console -> Messaging API -> Cập nhật URL thành: `https://ten_user_hf-ten_space.hf.space/callback`
4. Bật Use Webhook và nhấn **Verify**.
