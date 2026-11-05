import shutil
from pathlib import Path

import pytest
import yaml

from privatebench.schema import ContractError, ExpectedBehavior, load_contract

CONTRACTS = Path(__file__).resolve().parent.parent / "contracts"


@pytest.fixture
def contract_copy(tmp_path):
    dest = tmp_path / "contracts"
    shutil.copytree(CONTRACTS, dest)
    return dest


def edit_yaml(path, mutate):
    data = yaml.safe_load(path.read_text())
    mutate(data)
    path.write_text(yaml.safe_dump(data))


def test_pilot_contract_loads():
    contract = load_contract(CONTRACTS)
    assert {f.id for f in contract.families} == {
        "eligible_refund", "ineligible_refund", "ambiguous_order", "already_refunded",
    }
    assert {f.expected_behavior for f in contract.families} == set(ExpectedBehavior)


def test_every_pilot_rule_is_marked_assumed_and_synthetic():
    contract = load_contract(CONTRACTS)
    for rule in contract.rules:
        assert rule.provenance.kind == "assumed"
        assert rule.provenance.synthetic


def test_family_referencing_unknown_rule_is_rejected(contract_copy):
    edit_yaml(contract_copy / "families.yaml",
              lambda d: d["families"][0]["rule_ids"].append("R99"))
    with pytest.raises(ContractError, match="R99"):
        load_contract(contract_copy)


def test_assertion_rule_must_belong_to_its_family(contract_copy):
    def mutate(d):
        d["families"][0]["required_outcomes"][0]["rule_id"] = "R4"
    edit_yaml(contract_copy / "families.yaml", mutate)
    with pytest.raises(ContractError, match="R4"):
        load_contract(contract_copy)


def test_process_constraint_must_name_a_workload_tool(contract_copy):
    def mutate(d):
        d["families"][2]["process_constraints"][0]["params"]["tool"] = "phone_customer"
    edit_yaml(contract_copy / "families.yaml", mutate)
    with pytest.raises(ContractError, match="phone_customer"):
        load_contract(contract_copy)


def test_rule_open_question_must_exist(contract_copy):
    edit_yaml(contract_copy / "rules.yaml",
              lambda d: d["rules"][0]["open_questions"].append("Q42"))
    with pytest.raises(ContractError, match="Q42"):
        load_contract(contract_copy)


def test_contract_versions_must_match(contract_copy):
    edit_yaml(contract_copy / "rules.yaml",
              lambda d: d.update(contract_version="9.9.9"))
    with pytest.raises(ContractError, match="contract_version"):
        load_contract(contract_copy)
