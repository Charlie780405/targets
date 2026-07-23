"""实体解析包。"""

from packages.entity_resolution.asset_resolver import AssetEntry, AssetResolver, ResolvedAsset
from packages.entity_resolution.dedup import (
    PublicationIdentity,
    merge_publication_records,
    normalize_doi,
    normalize_title,
)
from packages.entity_resolution.org_normalizer import OrganizationEntry, OrganizationNormalizer
from packages.entity_resolution.target_dictionary import TargetDictionary, TargetEntry, TargetMatch

__all__ = [
    "AssetEntry",
    "AssetResolver",
    "OrganizationEntry",
    "OrganizationNormalizer",
    "PublicationIdentity",
    "ResolvedAsset",
    "TargetDictionary",
    "TargetEntry",
    "TargetMatch",
    "merge_publication_records",
    "normalize_doi",
    "normalize_title",
]
