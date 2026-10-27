import json
import re

import pytest

from customer_service_qa.config import PROJECT_ROOT
from customer_service_qa.tools.professional_rules import (
    UnknownCategoryError,
    get_professional_rules,
    load_rule_catalog,
)


def test_all_categories_preserve_original_rules_and_unique_ids():
    original = json.loads((PROJECT_ROOT / "data/raw/professional-rules.json").read_text("utf-8"))
    catalog = load_rule_catalog()
    assert len(catalog) == 22 and set(catalog) == set(original)
    ids = []
    for category, bundle in catalog.items():
        assert {rule.item_id for rule in bundle.rules} == {"PS-01", "PS-02", None}
        for rule in bundle.rules:
            assert rule.text in original[category]
            expected = re.search(r"扣(\d+)分", rule.text)
            assert rule.deduction == (int(expected[1]) if rule.item_id is not None else 0)
            ids.append(rule.rule_id)
    assert len(ids) == len(set(ids))


def test_lookup_is_exact_and_returns_an_isolated_copy():
    with pytest.raises(UnknownCategoryError):
        get_professional_rules("不存在的分类")
    bundle = get_professional_rules("账户安全")
    bundle.rules.clear()
    assert get_professional_rules("账户安全").rules
