import hashlib
import re
from collections.abc import Iterable


_NON_CODE_PATTERN = re.compile(r"[^a-z0-9]+")


def _normalize_part(value: str | None) -> str:
    text = str(value or "").strip().lower()
    slug = _NON_CODE_PATTERN.sub("-", text).strip("-")
    if slug:
        return slug
    if not text:
        return "item"
    return hashlib.md5(text.encode("utf-8")).hexdigest()[:8]


def build_project_code(project_name: str | None) -> str:
    """
    根据项目名称生成稳定的业务码。
    """
    return f"proj-{_normalize_part(project_name)}"


def build_module_code(project_code: str | None, module_name: str | None) -> str:
    """
    根据项目业务码和模块名称生成稳定的模块业务码。
    """
    return f"mod-{_normalize_part(project_code)}-{_normalize_part(module_name)}"


def ensure_unique_code(base_code: str, existing_codes: Iterable[str], current_code: str | None = None) -> str:
    """
    在已有业务码集合中补齐唯一后缀。
    """
    candidate = str(base_code or "").strip() or "item"
    normalized_existing = {str(item or "").strip() for item in existing_codes if str(item or "").strip()}
    current_code = str(current_code or "").strip() or None
    if candidate == current_code:
        return candidate

    index = 2
    while candidate in normalized_existing:
        candidate = f"{base_code}-{index}"
        index += 1
    return candidate
