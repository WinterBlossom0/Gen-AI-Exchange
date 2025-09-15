from __future__ import annotations

import json
from typing import Any, Optional


def _find_json_block(text: str) -> Optional[str]:
    if not text:
        return None
    # quick path: already pure JSON
    s = text.strip()
    if (s.startswith("{") and s.endswith("}")) or (s.startswith("[") and s.endswith("]")):
        return s
    # scan for first JSON block
    opens = ['{', '[']
    pairs = {'{': '}', '[': ']'}
    for i, ch in enumerate(text):
        if ch in opens:
            stack = [ch]
            for j in range(i + 1, len(text)):
                cj = text[j]
                if cj in opens:
                    stack.append(cj)
                elif cj in (']', '}'):
                    if not stack:
                        break
                    top = stack[-1]
                    if pairs[top] == cj:
                        stack.pop()
                        if not stack:
                            return text[i:j + 1]
            # if we get here, unmatched—continue scanning
    return None


def extract_json(text: str) -> Optional[Any]:
    block = _find_json_block(text)
    if not block:
        return None
    try:
        return json.loads(block)
    except Exception:
        return None


def extract_json_array(text: str) -> list:
    data = extract_json(text)
    if isinstance(data, list):
        return data
    # If first block was an object, check common keys
    if isinstance(data, dict):
        for key in ("legal_risks", "risks", "items", "mitigations", "data", "list"):
            val = data.get(key)
            if isinstance(val, list):
                return val
    # Fallback: scan for the first balanced JSON array block within the text
    if isinstance(text, str):
        s = text
        # quick strip of code fences if present
        st = s.strip()
        if st.startswith("```"):
            nl = st.find("\n")
            if nl >= 0:
                st = st[nl+1:]
            st = st.rstrip('`')
            s = st
        # scan for '[' ... matching ']'
        for i, ch in enumerate(s):
            if ch == '[':
                stack = ['[']
                for j in range(i+1, len(s)):
                    cj = s[j]
                    if cj == '[':
                        stack.append('[')
                    elif cj == ']':
                        if not stack:
                            break
                        stack.pop()
                        if not stack:
                            block = s[i:j+1]
                            try:
                                arr = json.loads(block)
                                return arr if isinstance(arr, list) else []
                            except Exception:
                                return []
        # as a last resort, try naive slice between first '[' and last ']'
        start = s.find('[')
        end = s.rfind(']')
        if start >= 0 and end > start:
            try:
                arr = json.loads(s[start:end+1])
                return arr if isinstance(arr, list) else []
            except Exception:
                return []
    return []


def extract_json_object(text: str) -> dict:
    data = extract_json(text)
    return data if isinstance(data, dict) else {}
