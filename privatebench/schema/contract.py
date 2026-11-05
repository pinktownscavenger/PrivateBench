"""Workload contract: workload.yaml, rules.yaml, families.yaml."""

from enum import Enum
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict


class ContractError(ValueError):
    pass


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ExpectedBehavior(str, Enum):
    act = "act"            # make the required change
    deny = "deny"          # refuse with a reason, no mutation
    clarify = "clarify"    # ask before any write, then act
    noop = "noop"          # idempotent: nothing left to change


class Provenance(_Model):
    kind: Literal["user_supplied", "document_derived", "assumed"]
    source: str
    synthetic: bool = False


class Rule(_Model):
    id: str
    text: str
    provenance: Provenance
    confidence: Literal["low", "medium", "high"]
    review_status: Literal["proposed", "team_approved", "owner_approved"]
    open_questions: list[str] = []


class OpenQuestion(_Model):
    id: str
    question: str


class ToolSpec(_Model):
    access: Literal["read", "write", "interaction"]
    params: dict[str, str]
    returns: str
    errors: list[str] = []
    effects: list[str] = []
    preconditions: list[str] = []


class Workload(_Model):
    contract_version: str
    workload_id: str
    synthetic: bool
    review_status: str
    description: str
    clock: dict[str, str]
    entities: dict[str, dict[str, Any]]
    tools: dict[str, ToolSpec]
    permissions: dict[str, list[str]]
    workflow_frequencies: dict[str, Any]


class AssertionTemplateRef(_Model):
    template: str
    params: dict[str, Any] = {}
    rule_id: str


class Family(_Model):
    id: str
    description: str
    expected_behavior: ExpectedBehavior
    rule_ids: list[str]
    required_outcomes: list[AssertionTemplateRef]
    forbidden_effects: list[AssertionTemplateRef]
    process_constraints: list[AssertionTemplateRef] = []

    def assertions(self) -> list[AssertionTemplateRef]:
        return self.required_outcomes + self.forbidden_effects + self.process_constraints


class Contract(_Model):
    workload: Workload
    rules: list[Rule]
    open_questions: list[OpenQuestion]
    families: list[Family]

    def rule(self, rule_id: str) -> Rule:
        return next(r for r in self.rules if r.id == rule_id)

    def family(self, family_id: str) -> Family:
        return next(f for f in self.families if f.id == family_id)


def _read(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text())


def load_contract(directory: str | Path) -> Contract:
    """Load and cross-validate the three contract files."""
    d = Path(directory)
    workload, rules, families = (_read(d / n) for n in ("workload.yaml", "rules.yaml", "families.yaml"))

    versions = {workload["contract_version"], rules["contract_version"], families["contract_version"]}
    if len(versions) != 1:
        raise ContractError(f"contract_version differs across files: {sorted(versions)}")

    contract = Contract(
        workload=Workload(**workload),
        rules=rules["rules"],
        open_questions=rules.get("open_questions", []),
        families=families["families"],
    )
    _check_references(contract)
    return contract


def _check_references(c: Contract) -> None:
    errors: list[str] = []
    rule_ids = {r.id for r in c.rules}
    question_ids = {q.id for q in c.open_questions}
    tools = set(c.workload.tools)

    for rule in c.rules:
        for q in set(rule.open_questions) - question_ids:
            errors.append(f"rule {rule.id} references unknown open question {q}")

    for fam in c.families:
        for r in set(fam.rule_ids) - rule_ids:
            errors.append(f"family {fam.id} references unknown rule {r}")
        for a in fam.assertions():
            if a.rule_id not in fam.rule_ids:
                errors.append(f"family {fam.id}: assertion {a.template} cites {a.rule_id}, not in its rule_ids")
        for a in fam.process_constraints:
            tool = a.params.get("tool")
            if tool is not None and tool not in tools:
                errors.append(f"family {fam.id}: process constraint names unknown tool {tool}")

    for role, allowed in c.workload.permissions.items():
        for t in set(allowed) - tools:
            errors.append(f"permissions.{role} names unknown tool {t}")

    if errors:
        raise ContractError("; ".join(errors))
