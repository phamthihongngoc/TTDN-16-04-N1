# -*- coding: utf-8 -*-

import io
import re


def fix_spacing_artifacts(text):
    """Best-effort cleanup for text extracted from PDFs/OCR.

    Common issue: some PDF extractors or OCR outputs insert spaces between every character
    (e.g. "V ũ  D u y" -> "Vũ Duy", "Th ái" -> "Thái"), which breaks matching and autofill.

    This function:
    - normalizes odd whitespace (NBSP, tabs)
    - removes zero-width characters
    - joins runs of small-character tokens (1-2 chars) into a word unless there are wide gaps
    - collapses remaining whitespace
    """
    if not text:
        return text

    def _clean_line(line):
        if not line:
            return ''

        # Normalize whitespace characters early
        line = (line or '')
        line = line.replace('\u00a0', ' ').replace('\t', ' ')
        line = line.replace('\u200b', '').replace('\u200c', '').replace('\u200d', '').replace('\ufeff', '')

        # Simple approach: join 1-2 char fragments, but use Vietnamese word length heuristics
        tokens = re.split(r'\s+', line.strip())
        if not tokens:
            return ''
        
        result_tokens = []
        current_word = []
        
        for token in tokens:
            if not token:
                continue
                
            # If this is a small fragment (1-2 chars), accumulate into current_word
            if len(token) <= 2 and re.match(r'^[a-zA-ZàáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđĐ]+$', token):
                current_word.append(token)
                
                # Vietnamese words are typically 1-8 characters. If we reach reasonable length, consider it a word.
                joined_word = ''.join(current_word)
                # Flush word when it's 3-7 chars (good Vietnamese word length)
                if len(joined_word) >= 3 and len(joined_word) <= 7:
                    result_tokens.append(joined_word)
                    current_word = []
                elif len(joined_word) > 7:
                    # Too long, likely multiple words joined, split at reasonable point
                    if len(joined_word) <= 10:
                        result_tokens.append(joined_word)
                    else:
                        # Split at 4-5 chars for first word
                        mid = 4 if len(joined_word) >= 8 else 3
                        result_tokens.append(joined_word[:mid])
                        result_tokens.append(joined_word[mid:])
                    current_word = []
            else:
                # Longer token or non-alphabetic: flush current_word first
                if current_word:
                    result_tokens.append(''.join(current_word))
                    current_word = []
                result_tokens.append(token)
        
        # Flush any remaining current_word
        if current_word:
            result_tokens.append(''.join(current_word))
        
        return ' '.join(result_tokens)

    # Preserve line structure but fix each line.
    lines = (text or '').splitlines()
    fixed_lines = [_clean_line(ln) for ln in lines]
    return ('\n'.join([ln for ln in fixed_lines if ln is not None])).strip()


def _otsu_threshold(gray_image):
    """Compute Otsu threshold for a grayscale (mode 'L') PIL image."""
    hist = gray_image.histogram()
    if not hist or len(hist) != 256:
        return 160

    total = sum(hist)
    if total <= 0:
        return 160

    sum_total = 0
    for i, h in enumerate(hist):
        sum_total += i * h

    sum_bg = 0
    weight_bg = 0
    max_var = -1.0
    threshold = 160

    for i in range(256):
        weight_bg += hist[i]
        if weight_bg == 0:
            continue

        weight_fg = total - weight_bg
        if weight_fg == 0:
            break

        sum_bg += i * hist[i]

        mean_bg = sum_bg / weight_bg
        mean_fg = (sum_total - sum_bg) / weight_fg

        between_var = weight_bg * weight_fg * (mean_bg - mean_fg) ** 2
        if between_var > max_var:
            max_var = between_var
            threshold = i

    return int(threshold)


def _extract_rotation_from_osd(osd_text):
    if not osd_text:
        return None
    m = re.search(r"Rotate:\s*(\d+)", osd_text)
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None


def preprocess_image_for_ocr(Image, ImageOps, ImageFilter, pytesseract, image_bytes, *, lang="vie+eng"):
    """Return a preprocessed PIL Image optimized for OCR."""
    image = Image.open(io.BytesIO(image_bytes))

    # Normalize mode & background
    if image.mode in ("RGBA", "LA"):
        bg = Image.new("RGB", image.size, (255, 255, 255))
        bg.paste(image, mask=image.split()[-1])
        image = bg
    elif image.mode not in ("RGB", "L"):
        image = image.convert("RGB")

    # Auto-rotate based on orientation detection if available
    try:
        osd = pytesseract.image_to_osd(image)
        rot = _extract_rotation_from_osd(osd)
        if rot in (90, 180, 270):
            image = image.rotate(-rot, expand=True, fillcolor=(255, 255, 255))
    except Exception:
        pass

    # Grayscale
    gray = ImageOps.grayscale(image)

    # Upscale small images for better OCR
    w, h = gray.size
    max_dim = max(w, h)
    if max_dim and max_dim < 1800:
        scale = 2
        new_size = (int(w * scale), int(h * scale))
        gray = gray.resize(new_size, resample=Image.BICUBIC)

    # Contrast + denoise + sharpen
    gray = ImageOps.autocontrast(gray)
    gray = gray.filter(ImageFilter.MedianFilter(size=3))
    gray = gray.filter(ImageFilter.UnsharpMask(radius=2, percent=160, threshold=3))

    # Binarize (Otsu)
    t = _otsu_threshold(gray)
    bw = gray.point(lambda x: 0 if x < t else 255, mode="1")

    # Convert back to L (tesseract works fine with L)
    return bw.convert("L")


def ocr_image_bytes(Image, ImageOps, ImageFilter, pytesseract, image_bytes, *, lang="vie+eng", config=None):
    processed = preprocess_image_for_ocr(
        Image, ImageOps, ImageFilter, pytesseract, image_bytes, lang=lang
    )

    # Professional-ish defaults: LSTM + assume a block of text
    if not config:
        config = "--oem 3 --psm 6 -c preserve_interword_spaces=1"
    text = pytesseract.image_to_string(processed, lang=lang, config=config)
    return fix_spacing_artifacts((text or "").strip())
