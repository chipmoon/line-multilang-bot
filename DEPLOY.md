# Hướng dẫn Deploy LINE Bot lên Koyeb (Free · Always-On · 24/7)

## Tại sao Koyeb?
| Tiêu chí | Koyeb | Render Free | Fly.io |
|----------|-------|-------------|--------|
| Always-on (không sleep) | ✅ | ❌ sleep 15p | ✅ |
| RAM | 512MB | 512MB | 256MB |
| Docker | ✅ | ✅ | ✅ |
| Credit card | ❌ không cần | ❌ không cần | ✅ bắt buộc |
| Phù hợp LINE bot | ✅ | ⚠️ webhook timeout | ✅ |

> LINE webhook timeout = 30s. Nếu server đang sleep → cold start ~30s → **bot không trả lời được**.
> Koyeb luôn sống → không có vấn đề này.

---

## Bước 1: Chuẩn bị Google Credentials (dạng 1 dòng)

Koyeb nhận env var dạng string thuần → cần convert `credentials.json` thành 1 dòng:

**Trên PowerShell (Windows):**
```powershell
cd d:\Python_VS\line-bot-multilang-ocr
$json = Get-Content -Raw "credentials.json" -Encoding UTF8
# Minify thành 1 dòng và copy vào clipboard:
($json | ConvertFrom-Json | ConvertTo-Json -Compress) | Set-Clipboard
Write-Host "Copied to clipboard!"
```

---

## Bước 2: Đưa code lên GitHub

> ⚠️ KHÔNG commit `.env` và `credentials.json`

Tạo file `.gitignore` (nếu chưa có):
```
.env
credentials.json
linebot-*.json
venv/
venv_314_bak/
__pycache__/
*.pyc
learning_cache.json
static/*.jpg
static/*.mp3
```

```bash
cd line-bot-multilang-ocr
git init
git remote add origin https://github.com/YOUR_USERNAME/line-bot-multilang-ocr.git
git add .
git commit -m "deploy: initial"
git push -u origin main
```

---

## Bước 3: Deploy trên Koyeb

1. Vào [koyeb.com](https://www.koyeb.com) → Đăng ký (không cần credit card)
2. **Create App** → **Deploy from GitHub**
3. Connect repo `line-bot-multilang-ocr`
4. Cấu hình:
   - **Builder**: Dockerfile *(Koyeb tự detect)*
   - **Instance**: `free` (free — 512MB RAM, đủ dùng)
   - **Port**: `8080`
   - **Health check path**: `/`

5. Vào phần **Environment variables** → thêm:

| Key | Value |
|-----|-------|
| `LINE_CHANNEL_ACCESS_TOKEN` | *(lấy từ .env)* |
| `LINE_CHANNEL_SECRET` | *(lấy từ .env)* |
| `CLOUDINARY_NAME` | *(lấy từ .env)* |
| `CLOUDINARY_API_KEY` | *(lấy từ .env)* |
| `CLOUDINARY_API_SECRET` | *(lấy từ .env)* |
| `GOOGLE_CLOUD_PROJECT_ID` | `linebot-490113` |
| `GOOGLE_CREDENTIALS_JSON` | *(paste chuỗi JSON 1 dòng từ Bước 1)* |

6. **Deploy** → chờ build ~3-5 phút
7. Copy URL: `https://YOUR_APP-YOUR_ORG.koyeb.app`

---

## Bước 4: Cập nhật Webhook URL trên LINE Developers

1. Vào [LINE Developers Console](https://developers.line.biz)
2. Chọn channel → **Messaging API** → **Webhook URL**
3. Nhập: `https://YOUR_APP-YOUR_ORG.koyeb.app/callback`
4. Bật **Use webhook** → **Verify** → ✅ Success

---

## Bước 5: Kiểm tra

```powershell
# Test health check
Invoke-WebRequest -Uri "https://YOUR_APP-YOUR_ORG.koyeb.app/"
# Response: LINE Bot OCR is running!
```

Hoặc mở trình duyệt vào URL → thấy dòng chữ trên là deploy thành công.

---

## Lưu ý

- **Cache** (`learning_cache.json`): Mất khi redeploy — chấp nhận được cho bot nhỏ
- **Static temp files**: File ảnh/mp3 tạm được xóa tự động sau mỗi request
- **Koyeb nano instance** 256MB RAM: app này dùng ~80-120MB → an toàn
- **Không cần UptimeRobot** vì Koyeb không sleep

