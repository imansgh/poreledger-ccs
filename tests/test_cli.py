import json

import pytest

from ccs_screen.cli import build_parser, main


def test_default_run_exits_clean_and_reports_every_section(capsys):
    assert main([]) == 0
    out = capsys.readouterr().out
    for section in ("Capacity", "Linear surrogate", "Injectivity", "P10 / P50 / P90"):
        assert section in out


def test_json_output_is_parseable_and_structured(capsys):
    assert main(["--samples", "200", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["n_samples"] == 200
    cap = report["capacity_mt"]
    assert cap["p10"] < cap["p50"] < cap["p90"]
    assert 0.0 <= report["surrogate"]["r2"] <= 1.0
    assert set(report["sensitivity_mt_per_sigma"]) == {
        "area_m2",
        "thickness_m",
        "porosity",
        "pressure_pa",
        "temperature_k",
        "storage_efficiency",
    }


def test_runs_are_reproducible_for_a_fixed_seed(capsys):
    main(["--samples", "150", "--seed", "5", "--json"])
    first = json.loads(capsys.readouterr().out)
    main(["--samples", "150", "--seed", "5", "--json"])
    assert json.loads(capsys.readouterr().out) == first


def test_narrower_porosity_prior_lowers_capacity(capsys):
    main(["--samples", "400", "--porosity", "0.05", "0.08", "--json"])
    low = json.loads(capsys.readouterr().out)["capacity_mt"]["p50"]
    main(["--samples", "400", "--porosity", "0.25", "0.30", "--json"])
    high = json.loads(capsys.readouterr().out)["capacity_mt"]["p50"]
    assert high > low


#: Phase 14 (D1, rule B): no fracture criterion is approved or defaulted. These
#: arbitrary caller-supplied values exercise the NOT_VALIDATED arithmetic.
CALLER_CRITERION = ["--fracture-gradient-pa-m", "17000", "--safety-factor", "0.8"]
FRACTURE_OUTPUTS = ("fracture_pressure_pa", "allowable_delta_p_pa", "max_rate_m3_s",
                    "within_limit")


def test_overpressured_case_reports_no_injection_window(capsys):
    main(["--samples", "100", "--pressure-pa", "34e6", "35e6", "--depth-m", "2000", "--json",
          *CALLER_CRITERION])
    inj = json.loads(capsys.readouterr().out)["injectivity"]
    assert inj["allowable_delta_p_pa"] == 0.0
    assert inj["max_rate_m3_s"] == 0.0
    assert inj["within_limit"] is False
    assert inj["output_status"]["within_limit"] == "NOT_VALIDATED"


def test_excessive_rate_is_flagged_as_over_the_limit(capsys):
    main(["--samples", "100", "--rate-m3-s", "5.0", "--json", *CALLER_CRITERION])
    assert json.loads(capsys.readouterr().out)["injectivity"]["within_limit"] is False


# -- Phase 14: O1 and rule B labels -------------------------------------------


def test_every_output_is_labelled_not_validated(capsys):
    """O1: the CLI capacity path is outside the approved Model Contract."""
    assert main(["--samples", "100", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["validation_status"] == "NOT_VALIDATED"
    assert "owner decision O1" in report["scope"]
    assert report["capacity_mt"]["validation_status"] == "NOT_VALIDATED"
    assert report["surrogate"]["validation_status"] == "NOT_VALIDATED"
    assert report["sensitivity_validation_status"] == "NOT_VALIDATED"
    assert report["injectivity"]["validation_status"] == "NOT_VALIDATED"


def test_fracture_outputs_are_unavailable_without_a_supplied_criterion(capsys):
    """Rule B: no default criterion, so no fracture-dependent number is produced."""
    main(["--samples", "100", "--json"])
    inj = json.loads(capsys.readouterr().out)["injectivity"]
    for name in FRACTURE_OUTPUTS:
        assert inj[name] is None, name
        assert inj["output_status"][name] == "UNAVAILABLE", name
        assert "no default" in inj["unavailable_reasons"][name]
    assert inj["caller_supplied_criteria"] == {"fracture_gradient_pa_m": None,
                                               "safety_factor": None}
    # The Theis outputs remain, as NOT_VALIDATED diagnostics.
    assert inj["planned_delta_p_pa"] > 0
    assert inj["output_status"]["planned_delta_p_pa"] == "NOT_VALIDATED"
    assert inj["output_status"]["initial_pressure_pa"] == "NOT_VALIDATED"


def test_a_supplied_criterion_is_used_and_labelled_not_validated(capsys):
    main(["--samples", "100", "--json", *CALLER_CRITERION])
    inj = json.loads(capsys.readouterr().out)["injectivity"]
    assert inj["fracture_pressure_pa"] == 2000.0 * 17000.0
    for name in FRACTURE_OUTPUTS:
        assert inj["output_status"][name] == "NOT_VALIDATED", name
    assert inj["unavailable_reasons"] == {}


def test_a_gradient_without_a_safety_factor_leaves_the_headroom_unavailable(capsys):
    main(["--samples", "100", "--json", "--fracture-gradient-pa-m", "17000"])
    inj = json.loads(capsys.readouterr().out)["injectivity"]
    assert inj["fracture_pressure_pa"] == 2000.0 * 17000.0
    assert inj["output_status"]["fracture_pressure_pa"] == "NOT_VALIDATED"
    for name in ("allowable_delta_p_pa", "max_rate_m3_s", "within_limit"):
        assert inj[name] is None and inj["output_status"][name] == "UNAVAILABLE"


def test_fracture_flags_have_no_default():
    args = build_parser().parse_args([])
    assert args.fracture_gradient_pa_m is None
    assert args.safety_factor is None


def test_text_output_states_the_labels(capsys):
    main(["--samples", "100"])
    out = capsys.readouterr().out
    assert "NOT_VALIDATED demo output (owner decision O1)" in out
    assert "Capacity (NOT_VALIDATED)" in out
    assert "verdict                    : UNAVAILABLE" in out
    assert "no default" in out


def test_invalid_prior_range_exits_with_an_error(capsys):
    assert main(["--porosity", "0.4", "0.1"]) == 2
    assert "ccs-screen:" in capsys.readouterr().err


def test_parser_exposes_a_range_flag_per_prior():
    parser = build_parser()
    args = parser.parse_args(["--area-m2", "1e7", "2e7"])
    assert args.area_m2 == [1e7, 2e7]


@pytest.mark.parametrize(
    "args,fragment",
    [
        (["--porosity", "0.4", "0.1"], "upper bound must be >= lower bound"),
        (["--porosity", "-0.1", "0.2"], "lower bound must be positive"),
        (["--area-m2", "0", "1e8"], "lower bound must be positive"),
        (["--thickness-m", "50", "10"], "upper bound must be >= lower bound"),
        (["--samples", "0"], "--samples must be a positive integer"),
        (["--samples", "-5"], "--samples must be a positive integer"),
        (["--safety-factor", "1.5"], "safety_factor must be in (0, 1]"),
        (["--safety-factor", "0"], "safety_factor must be in (0, 1]"),
        (["--fracture-gradient-pa-m", "0"], "fracture_gradient_pa_m must be positive"),
    ],
)
def test_semantic_errors_report_exit_2_and_a_specific_reason(args, fragment, capsys):
    """Every rejected input names what was wrong, on stderr, with nothing on stdout."""
    assert main(args) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("ccs-screen:")
    assert fragment in captured.err


@pytest.mark.parametrize("args", [["--nope"], ["--porosity", "0.2"], ["--samples", "abc"]])
def test_argparse_rejects_malformed_invocations(args):
    """argparse exits via SystemExit(2) before main() can return."""
    with pytest.raises(SystemExit) as excinfo:
        main(args)
    assert excinfo.value.code == 2
