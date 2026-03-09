from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_module():
    module_path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "generate_nested_modifier_matrix.py"
    )
    spec = importlib.util.spec_from_file_location(
        "generate_nested_modifier_matrix", module_path
    )
    assert spec
    assert spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_nested_modifier_matrix_case_ids_are_unique() -> None:
    module = _load_module()
    cases = (
        module.build_cases("plain")
        + module.build_cases("parens")
        + module.build_cases("quotes")
    )

    case_ids = [case["case_id"] for case in cases]
    assert len(case_ids) == len(set(case_ids))


def test_nested_modifier_matrix_contains_expected_reference_cases() -> None:
    module = _load_module()
    cases = {
        case["case_id"]: case
        for case in (
            module.build_cases("plain")
            + module.build_cases("parens")
            + module.build_cases("quotes")
        )
    }

    assert "plain__ja_tight__outer_bold__inner_code" in cases
    assert "plain__zh_tight__outer_bold__inner_code" in cases
    assert "plain__ko_tight__outer_bold__inner_code" in cases
    assert "parens__en_outer_zwsp__outer_bold__inner_italic" in cases
    assert "quotes__ja_spaces_both__outer_strike__inner_link" in cases
    assert (
        "(**INNER**)" in cases["parens__en_tight__outer_italic__inner_bold"]["markdown"]
    )
    assert "「`内側`」" in cases["quotes__ja_tight__outer_bold__inner_code"]["markdown"]


def test_nested_modifier_matrix_skips_same_marker_nesting() -> None:
    module = _load_module()
    cases = {
        case["case_id"]
        for case in (
            module.build_cases("plain")
            + module.build_cases("parens")
            + module.build_cases("quotes")
        )
    }

    assert "plain__ja_tight__outer_bold__inner_bold" not in cases
    assert "parens__ja_tight__outer_italic__inner_italic" not in cases
    assert "quotes__ja_tight__outer_strike__inner_strike" not in cases


def test_nested_modifier_matrix_can_filter_locales_and_inners() -> None:
    module = _load_module()
    cases = module.build_cases(
        "plain",
        locales={"ja", "zh", "ko"},
        inners={"plain", "code"},
    )

    assert cases
    assert all(case["locale"] in {"ja", "zh", "ko"} for case in cases)
    assert all(case["inner"] in {"plain", "code"} for case in cases)
    assert "plain__en_tight__outer_bold__inner_plain" not in {
        case["case_id"] for case in cases
    }
