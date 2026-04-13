import os
import json
import re
import tempfile
import traceback
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    MessagingApiBlob,
    ReplyMessageRequest,
    TextMessage,
    AudioMessage
)
from linebot.v3.webhooks import MessageEvent, ImageMessageContent
from google.cloud import vision, texttospeech, translate_v2 as translate
from pypinyin import pinyin, Style
import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor
import hashlib

load_dotenv()

app = Flask(__name__)

# Tạo thư mục static ngay khi import (cần thiết khi chạy bằng gunicorn)
os.makedirs('static', exist_ok=True)

# --- CONFIGURATION ---
channel_access_token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
channel_secret = os.getenv('LINE_CHANNEL_SECRET')

configuration = Configuration(access_token=channel_access_token)
handler = WebhookHandler(channel_secret)

CACHE_FILE = 'learning_cache.json'

def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_cache(cache_data):
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(cache_data, f, ensure_ascii=False, indent=4)

cloudinary.config(
    cloud_name=os.getenv('CLOUDINARY_NAME'),
    api_key=os.getenv('CLOUDINARY_API_KEY'),
    api_secret=os.getenv('CLOUDINARY_API_SECRET')
)

# Hỗ trợ load credentials từ biến môi trường (cho cloud deployment)
_creds_json_str = os.getenv('GOOGLE_CREDENTIALS_JSON')
if _creds_json_str:
    _tmp_creds = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
    _tmp_creds.write(_creds_json_str)
    _tmp_creds.close()
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = _tmp_creds.name
else:
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = os.getenv('GOOGLE_APPLICATION_CREDENTIALS', 'credentials.json')

# --- LOGIC MODULES ---

def clean_ocr_text(text, lang_code):
    """
    Expert Sanitization (V6 - Absolute Purist): 
    For Chinese, strictly keep ONLY Han characters, Chinese punctuation, and minimal spaces.
    This is the only way to safeguard against Bopomofo/OCR noise.
    """
    if not text:
        return ""

    # Detect if it contains Chinese characters (CJK Unified)
    has_chinese = any('\u4e00' <= c <= '\u9fff' or '\u3400' <= c <= '\u4dbf' for c in text)
    
    if has_chinese:
        def is_pure_learning_char(c):
            cp = ord(c)
            # Han characters
            if (0x4E00 <= cp <= 0x9FFF) or (0x3400 <= cp <= 0x4DBF):
                return True
            # Essential punctuation & spacing
            if c in "，。！？（）【】“”《》、. \n\t":
                return True
            # Numeric values
            if c.isdigit():
                return True
            # Reject everything else: Latin a-z, Bopomofo symbols, etc.
            return False

        filtered = "".join([c for c in text if is_pure_learning_char(c)])
        # Collapse whitespace
        filtered = re.sub(r' +', ' ', filtered)
        filtered = re.sub(r'\n+', '\n', filtered).strip()
        return filtered
    
    # Non-Chinese (English/etc): Keep original but trim
    return text.strip()

# --- B+ STRUCTURED OCR MODULE ---

def is_bopomofo(char):
    """Check if character is Bopomofo (注音符號) or tone mark."""
    cp = ord(char)
    if 0x3100 <= cp <= 0x312F or 0x31A0 <= cp <= 0x31BF:
        return True
    if cp in (0x02D9, 0x02CA, 0x02C7, 0x02CB):  # ˙ˊˇˋ
        return True
    return False

def is_han_char(char):
    """Check if character is CJK Unified Ideograph."""
    cp = ord(char)
    return (0x4E00 <= cp <= 0x9FFF) or (0x3400 <= cp <= 0x4DBF)

def extract_structured_text(annotation):
    """
    B+ OCR: Parse full_text_annotation by block/paragraph.
    Filters Bopomofo at symbol level, detects vertical/horizontal layout.
    """
    if not annotation or not annotation.pages:
        return ""

    KEEP_CHARS = set("，。！？、：；\"\"（）《》【】 ")
    blocks_data = []

    for page in annotation.pages:
        for block in page.blocks:
            vertices = block.bounding_box.vertices if block.bounding_box else []
            if vertices:
                xs = [v.x for v in vertices]
                ys = [v.y for v in vertices]
                cx, cy = sum(xs) / 4, sum(ys) / 4
                w, h = max(xs) - min(xs), max(ys) - min(ys)
            else:
                cx, cy, w, h = 0, 0, 0, 0

            para_texts = []
            for paragraph in block.paragraphs:
                chars = []
                for word in paragraph.words:
                    for symbol in word.symbols:
                        c = symbol.text
                        if is_bopomofo(c):
                            continue
                        if is_han_char(c) or c in KEEP_CHARS or c.isdigit():
                            chars.append(c)
                para_text = "".join(chars).strip()
                if para_text:
                    para_texts.append(para_text)

            if para_texts:
                blocks_data.append({
                    'cx': cx, 'cy': cy, 'w': w, 'h': h,
                    'text': "\n".join(para_texts)
                })

    if not blocks_data:
        return ""

    # Vertical text: columns taller than wide → sort right-to-left
    if len(blocks_data) >= 2:
        vert = sum(1 for b in blocks_data if b['h'] > b['w'] * 1.5)
        if vert > len(blocks_data) / 2:
            blocks_data.sort(key=lambda b: b['cx'], reverse=True)
            print("--- [B+] Vertical text detected, sorting R→L ---")
        else:
            blocks_data.sort(key=lambda b: b['cy'])

    return "\n".join(b['text'] for b in blocks_data)

def detect_and_format_poem(text):
    """
    Detect classical Chinese poetry (五言/七言) and auto-format.
    Safety checks: skip if OCR data looks corrupted (adjacent duplicates).
    Returns original text if no confident pattern match.
    """
    if not text:
        return text

    han_chars = [c for c in text if is_han_char(c)]
    total = len(han_chars)

    if total < 12 or total > 120:
        return text

    # Safety: adjacent duplicate chars = OCR read columns incorrectly
    adj_dupes = sum(1 for i in range(1, len(han_chars)) if han_chars[i] == han_chars[i-1])
    if adj_dupes > 0:
        print(f"--- [POEM SKIP] {adj_dupes} adjacent duplicate(s) detected → OCR noise ---")
        return text

    best = None
    for title_len in range(2, 6):  # Title must be 2-5 chars (no single-char)
        body = total - title_len
        if body <= 0:
            continue
        for cpl in (5, 7):  # chars per line
            if body % cpl != 0:
                continue
            num_lines = body // cpl
            if num_lines not in (4, 8):  # Only 絕句(4) and 律詩(8)
                continue
            score = 0
            if num_lines == 4: score += 10
            elif num_lines == 8: score += 7
            if 2 <= title_len <= 4: score += 5
            if cpl == 5: score += 1
            if best is None or score > best['score']:
                best = {'score': score, 'title_len': title_len,
                        'cpl': cpl, 'num_lines': num_lines}

    if not best or best['score'] < 14:  # High threshold: need 4-line + good title
        return text

    tl, cpl, nl = best['title_len'], best['cpl'], best['num_lines']
    title = "".join(han_chars[:tl])
    lines = [title]
    for i in range(nl):
        line = "".join(han_chars[tl + i * cpl : tl + (i + 1) * cpl])
        line += "，" if i % 2 == 0 else "。"
        lines.append(line)

    formatted = "\n".join(lines)
    print(f"--- [POEM DETECTED] {cpl}-char, {nl} lines, title='{title}' ---")
    return formatted

def translate_text(text, target_lang='vi'):
    """
    Expert Translation: Uses Google Cloud Translation Basic (v2).
    More stable and requires fewer specific IAM permissions than v3.
    """
    client = translate.Client()
    result = client.translate(text, target_language=target_lang)
    return result.get('translatedText', text)

def get_ocr_details(image_path):
    """
    Expert OCR (B+ Enhanced):
    - Chinese: Structured block/paragraph parsing + Bopomofo filter + poem detection
    - Other languages: Standard document_text_detection with clean_ocr_text
    """
    client = vision.ImageAnnotatorClient()
    with open(image_path, 'rb') as image_file:
        content = image_file.read()
    image = vision.Image(content=content)

    # B+ Enhancement: language hints help Vision API prioritize
    # Traditional Chinese over Bopomofo annotations
    image_context = vision.ImageContext(language_hints=['zh-Hant'])
    response = client.document_text_detection(image=image, image_context=image_context)

    if response.error.message:
        raise Exception(f"Vision API Error: {response.error.message}")

    # Smart Language Detection
    lang_code = 'zh-CN'
    if response.full_text_annotation and response.full_text_annotation.pages:
        page = response.full_text_annotation.pages[0]
        if page.property and page.property.detected_languages:
            lang_code = page.property.detected_languages[0].language_code

    is_chinese = lang_code and (
        lang_code.lower().startswith('zh') or lang_code.lower().startswith('cmn')
    )

    # Fallback: detect Chinese from actual content if lang_code missed it
    if not is_chinese and response.full_text_annotation:
        raw_text = response.full_text_annotation.text or ""
        han_count = sum(1 for c in raw_text if is_han_char(c))
        if han_count >= 3:
            is_chinese = True
            lang_code = 'zh-TW'
            print(f"--- [B+ FALLBACK] {han_count} Han chars found, forcing Chinese path ---")

    if is_chinese and response.full_text_annotation:
        # B+ Path: structured extraction → poem formatting
        structured_text = extract_structured_text(response.full_text_annotation)
        final_text = detect_and_format_poem(structured_text)
        print(f"--- [EXPERT OCR B+] ---")
        print(f"Structured: {repr(structured_text[:100])}")
        print(f"Final: {repr(final_text[:100])}")
    else:
        # Original path for non-Chinese
        raw = response.full_text_annotation.text if response.full_text_annotation else ""
        final_text = clean_ocr_text(raw, lang_code)

    print(f"Detected Lang: {lang_code}")
    return final_text.strip(), lang_code

def get_voice_params(lang_code):
    """
    Optimized Voice Mapping for Google Cloud TTS.
    Mandarin Chinese (zh-CN) often uses 'cmn-CN' in TTS Voice Names.
    """
    mapping = {
        'zh': ('cmn-CN', 'cmn-CN-Wavenet-A', texttospeech.SsmlVoiceGender.FEMALE), # Standard Mandarin
        'zh-cn': ('cmn-CN', 'cmn-CN-Wavenet-A', texttospeech.SsmlVoiceGender.FEMALE),
        'zh-hans': ('cmn-CN', 'cmn-CN-Wavenet-A', texttospeech.SsmlVoiceGender.FEMALE),
        'en': ('en-US', 'en-US-Neural2-F', texttospeech.SsmlVoiceGender.FEMALE),
        'ja': ('ja-JP', 'ja-JP-Wavenet-B', texttospeech.SsmlVoiceGender.FEMALE),
        'vi': ('vi-VN', 'vi-VN-Wavenet-C', texttospeech.SsmlVoiceGender.FEMALE), # Southern Accent
    }
    
    norm_code = lang_code.split('-')[0].lower()
    full_code = lang_code.lower()
    
    # Try full code first, then base code
    return mapping.get(full_code, mapping.get(norm_code, mapping['zh']))

def text_to_speech_url(text, lang, file_id):
    """
    Synthesize high-quality speech and host on Cloudinary.
    """
    client = texttospeech.TextToSpeechClient()
    language_code, voice_name, gender = get_voice_params(lang)

    input_text = texttospeech.SynthesisInput(text=text)
    voice = texttospeech.VoiceSelectionParams(
        language_code=language_code,
        name=voice_name,
        ssml_gender=gender
    )
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3,
        speaking_rate=0.75 # Even slower for better clarity for children
    )

    response = client.synthesize_speech(
        input=input_text, voice=voice, audio_config=audio_config
    )

    temp_file = f"static/{file_id}.mp3"
    with open(temp_file, "wb") as out:
        out.write(response.audio_content)

    try:
        upload_result = cloudinary.uploader.upload(
            temp_file, 
            resource_type="video",
            public_id=f"voice_{file_id}"
        )
        return upload_result['secure_url'], voice_name
    finally:
        if os.path.exists(temp_file):
            os.remove(temp_file)

# --- WEBHOOK ENDPOINT (v3) ---

@app.route("/", methods=['GET'])
def health_check():
    return 'LINE Bot OCR is running!', 200


@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature')
    body = request.get_data(as_text=True)
    
    # In ra ID để người dùng có thể tra cứu trong Logs
    import json
    try:
        data = json.loads(body)
        for event in data.get('events', []):
            source = event.get('source', {})
            u_id = source.get('userId')
            g_id = source.get('groupId')
            if u_id: print(f"🔍 [LINE LOG] User ID: {u_id}", flush=True)
            if g_id: print(f"🔍 [LINE LOG] Group ID: {g_id}", flush=True)
    except:
        pass

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=ImageMessageContent)
def handle_image(event):
    with ApiClient(configuration) as api_client:
        line_bot_blob_api = MessagingApiBlob(api_client)
        line_bot_messaging_api = MessagingApi(api_client)
        
        # Step 1: Download image content
        message_content = line_bot_blob_api.get_message_content(event.message.id)
        temp_img = f"static/{event.message.id}.jpg"
        with open(temp_img, 'wb') as f:
            f.write(message_content)

        try:
            # Step 2: OCR with expert-level detection
            detected_text, lang_code = get_ocr_details(temp_img)
            
            if not detected_text:
                line_bot_messaging_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text="Bé ơi, chụp rõ chữ hơn chút nhé!")]
                    )
                )
                return

            # --- SMART CACHE CHECK ---
            cache = load_cache()
            # Create a unique key based on text and language
            cache_key = hashlib.md5(f"{detected_text}_{lang_code}".encode('utf-8')).hexdigest()
            
            if cache_key in cache:
                print(f"--- [SMART CACHED HIT] ---")
                cached_data = cache[cache_key]
                # Backward compatibility for old cache
                zhuyin_display = cached_data.get('zhuyin', "")
                line_bot_messaging_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[
                            TextMessage(text=f"✨ Bé đã học từ này rồi nè:\n\n📝 Chữ gốc: {detected_text}{zhuyin_display}{cached_data['pinyin']}{cached_data['translation']}"),
                            AudioMessage(original_content_url=cached_data['audio_url'], duration=5000)
                        ]
                    )
                )
                return

            # Step 3: Bopomofo and Pinyin (Speed Optimization)
            is_chinese = lang_code and (lang_code.startswith('zh') or lang_code.startswith('cmn'))
            is_japanese = lang_code and lang_code.startswith('ja')
            is_english = lang_code and lang_code.startswith('en')
            
            # Fallback: check actual text content for Chinese characters
            if not is_chinese and not is_japanese:
                han_count = sum(1 for c in detected_text if is_han_char(c))
                if han_count >= 3:
                    is_chinese = True
                    print(f"--- [HANDLER FALLBACK] {han_count} Han chars in text, enabling Chinese mode ---")
            
            pinyin_info = ""
            zhuyin_info = ""
            if is_chinese:
                # Zhuyin (Bopomofo)
                zhuyin_list = pinyin(detected_text, style=Style.BOPOMOFO)
                zhuyin_str = " ".join([z[0] for z in zhuyin_list])
                zhuyin_info = f"\nĐánh vần (Bopomofo): {zhuyin_str}"
                
                # Pinyin
                pinyin_list = pinyin(detected_text, style=Style.TONE)
                pinyin_str = " ".join([p[0] for p in pinyin_list])
                pinyin_info = f"\nPhiên âm (Pinyin): {pinyin_str}"

            with ThreadPoolExecutor(max_workers=4) as executor:
                # Start TTS Task immediately
                tts_future = executor.submit(text_to_speech_url, detected_text, lang_code, event.message.id)
                
                # Setup Translation Tasks
                vi_future = None
                en_future = None
                zh_future = None
                
                if is_chinese:
                    # Parallel ZH -> EN and ZH -> VI
                    en_future = executor.submit(translate_text, detected_text, 'en')
                    vi_future = executor.submit(translate_text, detected_text, 'vi')
                elif is_japanese:
                    # Parallel JA -> ZH-CN, JA -> EN, JA -> VI
                    zh_future = executor.submit(translate_text, detected_text, 'zh-CN')
                    en_future = executor.submit(translate_text, detected_text, 'en')
                    vi_future = executor.submit(translate_text, detected_text, 'vi')
                elif lang_code and not lang_code.startswith('vi'):
                    # Generic translation to VI
                    vi_future = executor.submit(translate_text, detected_text, 'vi')

                # GATHER RESULTS (This happens while tasks run in background)
                audio_url, voice_used = tts_future.result()
                
                translation_info = ""
                if is_chinese:
                    en_text = en_future.result() if en_future else ""
                    vi_text = vi_future.result() if vi_future else ""
                    translation_info = f"\n🇬🇧 EN: {en_text}\n🇻🇳 Tiếng Việt: {vi_text}"
                elif is_japanese:
                    zh_text = zh_future.result() if zh_future else ""
                    en_text = en_future.result() if en_future else ""
                    vi_text = vi_future.result() if vi_future else ""
                    translation_info = f"\n🇨🇳 中文: {zh_text}\n🇬🇧 EN: {en_text}\n🇻🇳 Tiếng Việt: {vi_text}"
                elif vi_future:
                    vi_text = vi_future.result()
                    if vi_text != detected_text or is_english:
                        translation_info = f"\n🇻🇳 Tiếng Việt: {vi_text}"

            # --- SAVE TO SMART CACHE ---
            cache[cache_key] = {
                'zhuyin': zhuyin_info,
                'pinyin': pinyin_info,
                'translation': translation_info,
                'audio_url': audio_url
            }
            save_cache(cache)

            # Step 4: Professional Reply
            line_bot_messaging_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[
                        TextMessage(text=f"📚 Kết quả học tập:\n\n📝 Chữ gốc: {detected_text}{zhuyin_info}{pinyin_info}{translation_info}"),
                        AudioMessage(original_content_url=audio_url, duration=5000)
                    ]
                )
            )

        except Exception as e:
            # In toàn bộ chi tiết lỗi vào Logs của Hugging Face để debug
            print(f"❌ Critical Error: {e}")
            traceback.print_exc()
            line_bot_messaging_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="Có lỗi xảy ra, hãy thử lại sau / Error occurred.")]
                )
            )
        finally:
            if os.path.exists(temp_img):
                os.remove(temp_img)

if __name__ == "__main__":
    if not os.path.exists('static'):
        os.makedirs('static')
    
    # Cấu hình port: Ưu tiên PORT (cho Cloud Run), mặc định 5000 (cho local Ngrok)
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
