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
    return data if isinstance(data, list) else []


def extract_json_object(text: str) -> dict:
    data = extract_json(text)
    return data if isinstance(data, dict) else {}
