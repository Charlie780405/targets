"""实体解析包。"""

from packages.entity_resolution.dedup import (
    PublicationIdentity,
    merge_publication_records,
    normalize_doi,
    normalize_title,
)
from packages.entity_resolution.target_dictionary import TargetDictionary, TargetEntry, TargetMatch

__all__ = [
    "PublicationIdentity",
    "TargetDictionary",
    "TargetEntry",
    "TargetMatch",
    "merge_publication_records",
    "normalize_doi",
    "normalize_title",
]
