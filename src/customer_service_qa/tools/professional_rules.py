"""Exact category lookup with stable, source-linked rule identifiers."""

import hashlib
import json
import re
from functools import lru_cache

from customer_service_qa.config import PROJECT_ROOT
from customer_service_qa.schemas.scoring import BusinessRule, RuleBundle


class UnknownCategoryError(ValueError):
    """A category has no authoritative professional-service rubric."""


@lru_cache(maxsize=1)
def load_rule_catalog() -> dict[str, RuleBundle]:
    path = PROJECT_ROOT / "data/raw/professional-rules.json"
    raw = path.read_text(encoding="utf-8")
    version = hashlib.sha256(raw.encode()).hexdigest()[:12]
    catalog = {}
    for category, text in json.loads(raw).items():
        # Hashing the category avoids changing IDs when categories are reordered.
        prefix = "PS-" + hashlib.sha256(category.encode()).hexdigest()[:8].upper()
        section, counts, rules = "A", {"A": 0, "S": 0, "E": 0}, []
        for line in text.splitlines():
            line = line.strip()
            if "▌服务意识" in line:
                section = "S"
            elif "▌满分免责" in line:
                section = "E"
            elif re.match(r"^(?:\d+\.|-)\s*", line):
                clause = re.sub(r"^(?:\d+\.|-)\s*", "", line)
                counts[section] += 1
                deduction = re.search(r"扣(\d+)分", clause)
                if section != "E" and not deduction:
                    raise ValueError("Business deduction is missing from source rule")
                rules.append(
                    BusinessRule(
                        rule_id=f"{prefix}-{section}{counts[section]:02d}",
                        item_id={"A": "PS-01", "S": "PS-02", "E": None}[section],
                        text=clause,
                        deduction=int(deduction[1]) if section != "E" else 0,
                    )
                )
        if not all(counts.values()):
            raise ValueError("Incomplete professional rule category")
        catalog[category] = RuleBundle(
            parent_tag=category,
            source="data/raw/professional-rules.json",
            version=version,
            rules=rules,
        )
    return catalog


def get_professional_rules(parent_tag: str) -> RuleBundle:
    """Return a separate copy so parallel callers cannot mutate the cached catalog."""
    try:
        return load_rule_catalog()[parent_tag].model_copy(deep=True)
    except KeyError:
        raise UnknownCategoryError("No rules for this parent_tag") from None
