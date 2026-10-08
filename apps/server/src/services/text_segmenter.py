"""
Intelligent Text Segmenter
Splits long-form text into sentence-level narration chunks respecting linguistic boundaries.
Optimized for Vietnamese (VieNeu-TTS < 250 chars) and Mandarin Chinese (Qwen3-TTS < 120 chars).
Preserves sentence-ending punctuations and protects abbreviations and decimal numbers.
"""

import re
from typing import List


# Common Vietnamese abbreviations that should NOT trigger a sentence split
VI_ABBREVIATIONS = (
    r"(?<!\bTP)"
    r"(?<!\bThS)"
    r"(?<!\bPGS)"
    r"(?<!\bTS)"
    r"(?<!\bGS)"
    r"(?<!\bBS)"
    r"(?<!\bv\.v)"
    r"(?<!\bVN)"
    r"(?<!\bông)"
    r"(?<!\bbà)"
    r"(?<!\b[A-Z])"
)

# Vietnamese sentence boundary regex: period, exclamation, question mark, ellipsis
# Followed by whitespace or end of string, not preceded by an abbreviation or digits
VI_SENTENCE_SPLIT_REGEX = re.compile(
    rf"{VI_ABBREVIATIONS}(?<!\d)([\.\?!…]+(?:\s+|$))"
)

# Chinese sentence boundary regex: standard Chinese punctuation marks
ZH_SENTENCE_SPLIT_REGEX = re.compile(r"([。！？；…]+)")


class TextSegmenter:
    @staticmethod
    def segment_vietnamese(text: str, max_chars: int = 220, min_chars: int = 10) -> List[str]:
        """
        Segments long-form Vietnamese text into sentence-level chunks.
        1. Splits by newline paragraphs.
        2. Splits by sentence boundaries preserving punctuation cleanly.
        3. Fuses tiny fragments (< min_chars) into the adjacent sentence.
        4. Sub-splits oversized sentences (> max_chars) at clause boundaries.
        """
        paragraphs = [p.strip() for p in text.splitlines() if p.strip()]
        result_segments: List[str] = []

        for p in paragraphs:
            raw_parts = VI_SENTENCE_SPLIT_REGEX.split(p)
            sentences: List[str] = []
            
            i = 0
            while i < len(raw_parts):
                part = raw_parts[i].strip()
                if not part:
                    i += 1
                    continue
                # If next part is delimiter, attach directly without leading space
                if i + 1 < len(raw_parts) and re.match(r"^[\.\?!…\s]+$", raw_parts[i + 1]):
                    delim = raw_parts[i + 1].strip()
                    sentences.append(f"{part}{delim}")
                    i += 2
                else:
                    sentences.append(part)
                    i += 1

            # Consolidate sentences
            for s in sentences:
                s_clean = s.strip()
                if not s_clean:
                    continue

                # If current segment is too short and previous exists, append if under max_chars
                if result_segments and len(s_clean) < min_chars and (len(result_segments[-1]) + len(s_clean) + 1 <= max_chars):
                    result_segments[-1] += " " + s_clean
                elif result_segments and len(result_segments[-1]) < min_chars and (len(result_segments[-1]) + len(s_clean) + 1 <= max_chars):
                    result_segments[-1] += " " + s_clean
                else:
                    result_segments.append(s_clean)

        # Handle any oversized segments
        final_segments: List[str] = []
        for seg in result_segments:
            if len(seg) <= max_chars:
                final_segments.append(seg)
            else:
                # Sub-split at commas or clause delimiters
                sub_parts = re.split(r"([,;:\-–—]\s*)", seg)
                sub_buf = ""
                for part in sub_parts:
                    if not part:
                        continue
                    if len(sub_buf) + len(part) <= max_chars:
                        sub_buf += part
                    else:
                        if sub_buf.strip():
                            final_segments.append(sub_buf.strip())
                        sub_buf = part
                if sub_buf.strip():
                    final_segments.append(sub_buf.strip())

        return final_segments

    @staticmethod
    def segment_mandarin(text: str, max_chars: int = 120, min_chars: int = 10) -> List[str]:
        """
        Segments Mandarin Chinese text using Chinese punctuation marks.
        """
        paragraphs = [p.strip() for p in text.splitlines() if p.strip()]
        result_segments: List[str] = []

        for p in paragraphs:
            parts = ZH_SENTENCE_SPLIT_REGEX.split(p)
            sentences: List[str] = []
            i = 0
            while i < len(parts):
                part = parts[i].strip()
                if not part:
                    i += 1
                    continue
                if i + 1 < len(parts) and re.match(r"^[。！？；…]+$", parts[i + 1]):
                    sentences.append(part + parts[i + 1].strip())
                    i += 2
                else:
                    sentences.append(part)
                    i += 1

            for s in sentences:
                s_clean = s.strip()
                if not s_clean:
                    continue

                if result_segments and len(s_clean) < min_chars and (len(result_segments[-1]) + len(s_clean) <= max_chars):
                    result_segments[-1] += s_clean
                elif result_segments and len(result_segments[-1]) < min_chars and (len(result_segments[-1]) + len(s_clean) <= max_chars):
                    result_segments[-1] += s_clean
                else:
                    result_segments.append(s_clean)

        # Handle sub-splitting at Chinese commas if needed
        final_segments: List[str] = []
        for seg in result_segments:
            if len(seg) <= max_chars:
                final_segments.append(seg)
            else:
                sub_parts = re.split(r"([，、])", seg)
                sub_buf = ""
                for part in sub_parts:
                    if len(sub_buf) + len(part) <= max_chars:
                        sub_buf += part
                    else:
                        if sub_buf:
                            final_segments.append(sub_buf)
                        sub_buf = part
                if sub_buf:
                    final_segments.append(sub_buf)

        return final_segments

    @classmethod
    def segment_text(cls, text: str, language: str = "vi", max_chars: int = 220) -> List[str]:
        lang = language.lower()
        if lang in ("zh", "mandarin", "chinese"):
            return cls.segment_mandarin(text, max_chars=min(max_chars, 120))
        return cls.segment_vietnamese(text, max_chars=max_chars)
