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


def test_overpressured_case_reports_no_injection_window(capsys):
    main(["--samples", "100", "--pressure-pa", "34e6", "35e6", "--depth-m", "2000", "--json"])
    inj = json.loads(capsys.readouterr().out)["injectivity"]
    assert inj["allowable_delta_p_pa"] == 0.0
    assert inj["max_rate_m3_s"] == 0.0
    assert inj["within_limit"] is False


def test_excessive_rate_is_flagged_as_over_the_limit(capsys):
    main(["--samples", "100", "--rate-m3-s", "5.0", "--json"])
    assert json.loads(capsys.readouterr().out)["injectivity"]["within_limit"] is False


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
