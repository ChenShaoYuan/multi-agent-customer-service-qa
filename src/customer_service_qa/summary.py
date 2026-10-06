"""Deterministic score tools: validate, deduplicate with evidence, weight and grade."""

import hashlib
import json
from decimal import ROUND_HALF_UP, Decimal
from itertools import combinations
from uuid import uuid4

from customer_service_qa.config import load_scoring_config, load_summary_config
from customer_service_qa.schemas import PreflightReport, RedlineResult
from customer_service_qa.schemas.audit import (
    Alert,
    DuplicateResolution,
    Feedback,
    FinalAudit,
    FinalizeArguments,
    Finding,
)
from customer_service_qa.schemas.scoring import DIMENSIONS, DimensionResult


def money(value) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def grade_score(score) -> str:
    value = Decimal(str(score))
    if not value.is_finite() or not 0 <= value <= 100:
        raise ValueError("Score must be finite and between zero and 100")
    grades = load_scoring_config()["grades"]
    if value >= grades["excellent"]["min_inclusive"]:
        return grades["excellent"]["label"]
    if value >= grades["qualified"]["min_inclusive"]:
        return grades["qualified"]["label"]
    return grades["serious_issue"]["label"]


def calculate_total(raw_scores: dict[str, int]) -> tuple[float, dict[str, float]]:
    specs = load_scoring_config()["dimensions"]
    if set(raw_scores) != set(DIMENSIONS) or sum(s["weight"] for s in specs.values()) != 100:
        raise ValueError("Incomplete scores or invalid weights")
    exact = {}
    for name in DIMENSIONS:
        score, spec = raw_scores[name], specs[name]
        if type(score) is not int or not 0 <= score <= spec["raw_max_score"]:
            raise ValueError("Invalid raw score")
        exact[name] = Decimal(score) * Decimal(spec["weight"]) / Decimal(spec["raw_max_score"])
    return money(sum(exact.values())), {name: money(value) for name, value in exact.items()}


def issue_id(parts) -> str:
    canonical = json.dumps(parts, ensure_ascii=False, sort_keys=True)
    return "ISS-" + hashlib.sha256(canonical.encode()).hexdigest()[:12]


def collect_findings(dimensions: dict[str, DimensionResult]) -> list[Finding]:
    specs = load_scoring_config()["dimensions"]
    findings = []
    for name, dimension in dimensions.items():
        for item in dimension.items:
            if not item.deduction:
                continue
            business_rules = [rule for rule in item.rule_ids if rule != item.item_id]
            # Multiple professional clauses cannot safely be undone as one atomic issue.
            mergeable = name != "professional_service" or len(business_rules) <= 1
            reference = f"{name}:{item.item_id}"
            findings.append(
                Finding(
                    finding_id=reference,
                    issue_id=issue_id(
                        [reference, item.rule_ids, [e.model_dump() for e in item.evidence]]
                    ),
                    dimension=name,
                    item_id=item.item_id,
                    deduction=item.deduction,
                    weighted_deduction=money(
                        Decimal(item.deduction)
                        * specs[name]["weight"]
                        / Decimal(specs[name]["raw_max_score"])
                    ),
                    reason=item.reason,
                    rule_ids=item.rule_ids,
                    rule_texts=item.rule_texts,
                    evidence=item.evidence,
                    mergeable=mergeable,
                )
            )
    return findings


def prepare_audit(state: dict) -> FinalAudit:
    """Always return a contract, including absent or malformed upstream state."""
    scoring = load_scoring_config()
    audit = FinalAudit(
        audit_id=state.get("audit_id") or str(uuid4()),
        ticket_id=str(state.get("ticket_id", "")),
        status="manual_review",
        grade=scoring["grades"]["manual_review"]["label"],
        scoring_version=scoring["version"],
        summary_version=load_summary_config()["version"],
        technical_errors=state.get("technical_errors", []),
        trace=state.get("node_traces", []),
    )
    for error in audit.technical_errors:
        audit.alerts.append(
            Alert(
                code="NODE_ATTEMPT_FAILED",
                severity="warning",
                node=error.get("node", "unknown"),
                message="节点曾发生受控异常。",
            )
        )
    try:
        preflight = PreflightReport.model_validate(state.get("preflight_report"))
        audit.preflight = preflight.model_dump(mode="json")
        if not preflight.input_valid:
            raise ValueError("Invalid input")
    except (ValueError, TypeError):
        audit.manual_review_reasons = ["预检结果缺失、无效或输入不完整。"]
        audit.alerts.append(
            Alert(
                code="PREFLIGHT_INVALID",
                severity="error",
                node="preflight",
                message=audit.manual_review_reasons[0],
            )
        )
        return audit
    try:
        redline = RedlineResult.model_validate(state.get("redline_result"))
        audit.redline = redline.model_dump(mode="json")
        if redline.gate_status == "review":
            raise ValueError("Gate requires review")
        if (
            len(redline.items) != 4
            or {i.rule_id for i in redline.items} != {"CR-01", "CR-02", "CR-03", "CR-04"}
            or redline.triggered != any(i.triggered for i in redline.items)
        ):
            raise ValueError("Inconsistent redline contract")
        if redline.triggered:
            if redline.gate_status != "blocked":
                raise ValueError("Inconsistent blocked gate")
            audit.status, audit.grade = "blocked", scoring["grades"]["redline"]["label"]
            audit.alerts.append(
                Alert(
                    code="REDLINE_TRIGGERED",
                    severity="error",
                    node="critical_gate",
                    message="红线命中，停止三维评分并优先人工核查。",
                )
            )
            audit.feedback = [
                Feedback(
                    advice="核对红线证据，立即纠正相关行为并开展专项培训。",
                    rule_ids=[i.rule_id for i in redline.items if i.triggered],
                    evidence_message_ids=sorted(
                        {e for i in redline.items if i.triggered for e in i.evidence_message_ids}
                    ),
                )
            ]
            return audit
        if redline.gate_status != "pass":
            raise ValueError("Inconsistent passed gate")
    except (ValueError, TypeError):
        audit.manual_review_reasons = ["红线主控未提供有效放行结果。"]
        audit.alerts.append(
            Alert(
                code="GATE_INVALID",
                severity="error",
                node="critical_gate",
                message=audit.manual_review_reasons[0],
            )
        )
        return audit
    for name in DIMENSIONS:
        try:
            result = DimensionResult.model_validate(state.get(f"{name}_result"))
            spec = scoring["dimensions"][name]
            if result.dimension != name or result.max_score != spec["raw_max_score"]:
                raise ValueError("Dimension identity mismatch")
            audit.dimensions[name] = result
            if result.status != "completed":
                audit.manual_review_reasons.extend(
                    f"{name}: {reason}" for reason in (result.review_reasons or ["维度未完成。"])
                )
                audit.alerts.append(
                    Alert(
                        code="DIMENSION_INCOMPLETE",
                        severity="warning",
                        node=name,
                        message="维度缺少资料或执行失败，不能形成有效总分。",
                    )
                )
                continue
            expected = {s["id"]: s["max_score"] for s in spec["items"]}
            ids = [item.item_id for item in result.items]
            if len(ids) != len(expected) or set(ids) != set(expected):
                raise ValueError("Incomplete items")
            for item in result.items:
                if (
                    item.status != "scored"
                    or type(item.score) is not int
                    or item.max_score != expected[item.item_id]
                    or not 0 <= item.score <= item.max_score
                    or item.deduction != item.max_score - item.score
                    or not item.evidence
                    or not item.rule_ids
                ):
                    raise ValueError("Invalid scored item")
            if result.raw_score != sum(item.score for item in result.items):
                raise ValueError("Invalid dimension total")
        except (ValueError, TypeError):
            audit.manual_review_reasons.append(f"{name}: 结果缺失或契约不一致。")
            audit.alerts.append(
                Alert(
                    code="DIMENSION_INVALID",
                    severity="error",
                    node=name,
                    message="维度结果缺失或未通过汇总校验。",
                )
            )
    audit.findings = collect_findings(audit.dimensions)
    audit.manual_review_reasons = list(dict.fromkeys(audit.manual_review_reasons))
    if preflight.role_source == "inferred":
        audit.alerts.append(
            Alert(
                code="ROLES_INFERRED",
                severity="warning",
                node="normalize_input",
                message="历史文本角色来自奇偶行推断，结果需结合原记录核验。",
            )
        )
    return audit


def apply_summary(audit: FinalAudit, arguments: FinalizeArguments) -> FinalAudit:
    result = audit.model_copy(deep=True)
    if result.status == "blocked" or result.manual_review_reasons:
        return result
    if arguments.review_reasons:
        result.manual_review_reasons = arguments.review_reasons
        result.alerts.append(
            Alert(
                code="SUMMARY_REVIEW",
                severity="warning",
                node="summary_agent",
                message="聚合Agent发现无法确定的跨维度问题，需人工复核。",
            )
        )
        return result
    if set(result.dimensions) != set(DIMENSIONS):
        raise ValueError("All dimensions are required")
    raw = {name: value.raw_score for name, value in result.dimensions.items()}
    by_id = {finding.finding_id: finding for finding in result.findings}
    used, restored = set(), set()
    allowed = {
        frozenset(pair) for pair in load_summary_config()["deduplication"]["allowed_item_pairs"]
    }
    for group in arguments.duplicate_groups:
        refs = group.finding_ids
        if len(set(refs)) != len(refs) or used.intersection(refs) or set(refs) - set(by_id):
            raise ValueError("Duplicate groups must reference unique existing deductions")
        members = [by_id[ref] for ref in refs]
        if len({m.dimension for m in members}) != len(members) or not all(
            m.mergeable for m in members
        ):
            raise ValueError("Only atomic cross-dimension issues can be merged")
        if any(
            frozenset([a.item_id, b.item_id]) not in allowed for a, b in combinations(members, 2)
        ):
            raise ValueError("Items are outside the permitted overlap families")
        shared = set.intersection(*[{e.message_id for e in member.evidence} for member in members])
        if not set(group.evidence_message_ids) <= shared or not group.reason.strip():
            raise ValueError("A merge needs shared evidence and a concrete rationale")
        kept = sorted(members, key=lambda m: (-m.weighted_deduction, m.finding_id))[0]
        combined_id = issue_id(sorted(refs))
        for member in members:
            member.issue_id = combined_id
            if member.finding_id != kept.finding_id:
                raw[member.dimension] += member.deduction
                restored.add(member.finding_id)
        result.duplicate_resolutions.append(
            DuplicateResolution(
                issue_id=combined_id,
                kept_finding_id=kept.finding_id,
                restored_finding_ids=sorted(set(refs) - {kept.finding_id}),
                reason=group.reason,
                evidence_message_ids=group.evidence_message_ids,
            )
        )
        used.update(refs)
    result.total_score, result.weighted_scores = calculate_total(raw)
    result.adjusted_raw_scores = raw
    result.grade, result.status = grade_score(result.total_score), "completed"
    feedback = load_summary_config()["feedback"]
    result.feedback = [
        Feedback(
            issue_id=f.issue_id,
            item_ids=[f.item_id],
            advice=feedback[f.item_id],
            rule_ids=f.rule_ids,
            evidence_message_ids=sorted({e.message_id for e in f.evidence}),
        )
        for f in result.findings
        if f.finding_id not in restored
    ]
    if not result.feedback:
        result.feedback = [Feedback(advice="保持现有服务表现，持续抽查规则、时效和记录完整性。")]
    result.feedback.append(Feedback(advice=load_summary_config()["grade_feedback"][result.grade]))
    return FinalAudit.model_validate(result.model_dump())
