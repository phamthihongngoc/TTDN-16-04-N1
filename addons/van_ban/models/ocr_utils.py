# -*- coding: utf-8 -*-

import io
import re
import unicodedata


def fix_spacing_artifacts(text):
    """Best-effort cleanup for text extracted from PDFs/OCR.

    Common issue: some PDF extractors or OCR outputs insert spaces between every character
    (e.g. "V ũ  D u y" -> "Vũ Duy", "Th ái" -> "Thái"), which breaks matching and autofill.

    This function:
        - normalizes odd whitespace (NBSP, tabs)
        - removes zero-width characters
        - fixes character-by-character spacing WITHOUT adding new spaces
        - preserves original word boundaries as much as possible
    """
    if not text:
        return text

    # Normalize unicode so Vietnamese diacritics are in composed form.
    try:
        text = unicodedata.normalize('NFC', text)
    except Exception:
        pass

    def _fix_char_spacing(line):
        """Fix split syllables without adding new spaces."""
        if not line:
            return ''

        try:
            line = unicodedata.normalize('NFC', line)
        except Exception:
            pass

        # Normalize whitespace
        line = line.replace('\u00a0', ' ').replace('\t', ' ')
        line = line.replace('\u200b', '').replace('\u200c', '').replace('\u200d', '').replace('\ufeff', '')

        tokens = re.split(r'\s+', line.strip()) if line.strip() else []
        if not tokens:
            return ''

        _PUNCT_STRIP = "\"'“”‘’.,;:!?()[]{}<>"

        # Vietnamese vowels (uppercase, including diacritics). Used to detect split syllables in ALL-CAPS titles.
        _VOWELS_UPPER = set(
            "AEIOUY"
            "ĂÂÊÔƠƯ"
            "ÀÁẢÃẠ"
            "ẮẰẲẴẶ"
            "ẤẦẨẪẬ"
            "ÈÉẺẼẸ"
            "ẾỀỂỄỆ"
            "ÌÍỈĨỊ"
            "ÒÓỎÕỌ"
            "ỐỒỔỖỘ"
            "ỚỜỞỠỢ"
            "ÙÚỦŨỤ"
            "ỨỪỬỮỰ"
            "ỲÝỶỸỴ"
        )

        def _core(tok):
            return (tok or '').strip(_PUNCT_STRIP)

        def _starts_upper(tok):
            if not tok:
                return False
            c = tok[0]
            return c.isalpha() and c.isupper()

        def _starts_lower(tok):
            if not tok:
                return False
            c = tok[0]
            return c.isalpha() and c.islower()

        def _is_single_upper_letter(tok):
            return bool(tok) and len(tok) == 1 and tok.isalpha() and tok.isupper()

        def _is_alpha_word(tok):
            # Allows Vietnamese letters in the À-ỹ range.
            return bool(tok) and bool(re.fullmatch(r'[A-Za-zÀ-ỹ]+', tok))

        def _starts_vowel_upper(tok):
            if not tok:
                return False
            c = tok[0]
            return c in _VOWELS_UPPER

        def _should_merge(prev, curr):
            """Return True if space between prev/curr is likely an artifact.

            Key principle: do NOT merge when curr starts with uppercase (word boundary),
            except for safe uppercase fragment cases like "H ỢP" or "Đ ỒNG".
            """
            if not prev or not curr:
                return False

            prev_core = _core(prev)
            curr_core = _core(curr)
            if not (prev_core and curr_core):
                return False
            if not (_is_alpha_word(prev_core) and _is_alpha_word(curr_core)):
                return False

            # Protect patterns like "Bên B" / "BÊN A".
            if len(curr_core) == 1 and curr_core.isupper() and len(prev_core) >= 2:
                return False

            # Common Vietnamese split syllables: "Th ái" -> "Thái", "Ng ọc" -> "Ngọc", "Nguy ễn" -> "Nguyễn".
            # Only merge when the NEXT fragment begins with lowercase (vowel/diacritic chunk).
            if _starts_upper(prev_core) and _starts_lower(curr_core) and (1 <= len(prev_core) <= 4) and (1 <= len(curr_core) <= 6):
                return True

            # Uppercase text with character spacing: "H ỢP" -> "HỢP", "Đ ỒNG" -> "ĐỒNG".
            # Allow only when the previous token is a single uppercase letter.
            if _is_single_upper_letter(prev_core) and _starts_upper(curr_core) and (1 <= len(curr_core) <= 4):
                return True

            # ALL-CAPS title syllable splits: "ĐI ỆN" -> "ĐIỆN", "THO ẠI" -> "THOẠI".
            # Only merge when the second fragment starts with a Vietnamese vowel (incl. diacritics).
            if prev_core.isupper() and curr_core.isupper() and (1 <= len(prev_core) <= 3) and (1 <= len(curr_core) <= 3) and _starts_vowel_upper(curr_core):
                return True

            # Uppercase split like "TH Ị" -> "THỊ" (but avoid "BÊN A").
            if _starts_upper(prev_core) and _is_single_upper_letter(curr_core) and len(prev_core) <= 2:
                return True

            # Extreme char-by-char spacing: "N g ọ c" (rare, but keep safe)
            if len(prev_core) == 1 and len(curr_core) == 1 and prev_core.isalpha() and curr_core.isalpha():
                return True

            return False

        out = []
        for tok in tokens:
            if out and _should_merge(out[-1], tok):
                out[-1] = f"{out[-1]}{tok}"
            else:
                out.append(tok)

        return ' '.join(out).strip()

    def _clean_line(line):
        if not line:
            return ''
        
        # Normalize whitespace characters
        line = (line or '')
        line = line.replace('\u00a0', ' ').replace('\t', ' ')
        line = line.replace('\u200b', '').replace('\u200c', '').replace('\u200d', '').replace('\ufeff', '')
        
        # Fix character spacing if detected
        return _fix_char_spacing(line)

    # Preserve line structure but fix each line
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
