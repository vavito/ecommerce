import re
import unicodedata


def slugify(value: str) -> str:
    normalized_value = unicodedata.normalize("NFKD", value)
    ascii_value = normalized_value.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", ascii_value.lower()).strip("-")
