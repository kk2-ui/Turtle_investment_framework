from scripts.golden_action_policy import compile_golden_action


def test_baseline_required_return_price_is_the_only_price_gate() -> None:
    result = compile_golden_action(
        current_price=40.34,
        baseline_max_research_price=49.79,
        baseline_route_established=True,
        permanent_loss_state="MATERIAL_BUT_FINANCEABLE",
        stress_return_pct=3.18,
    )
    assert result["price_gate_passed"] is True
    assert result["stress_is_required_return_gate"] is False
    assert result["action"] == "BUILD_LIMITED_POSITION"


def test_negative_stress_return_does_not_replace_the_baseline_price_gate() -> None:
    result = compile_golden_action(
        current_price=8.0,
        baseline_max_research_price=10.0,
        baseline_route_established=True,
        permanent_loss_state="BOUNDED",
        stress_return_pct=-12.0,
    )
    assert result["action"] == "BUILD_POSITION"
    assert result["position_tier"] == "STANDARD"


def test_price_above_baseline_research_price_waits() -> None:
    result = compile_golden_action(
        current_price=11.0,
        baseline_max_research_price=10.0,
        baseline_route_established=True,
        permanent_loss_state="BOUNDED",
    )
    assert result["price_gate_passed"] is False
    assert result["action"] == "WAIT_FOR_PRICE_OR_VALUE"


def test_missing_baseline_route_is_not_mislabeled_as_overvaluation() -> None:
    result = compile_golden_action(
        current_price=11.0,
        baseline_max_research_price=None,
        baseline_route_established=False,
        permanent_loss_state="BOUNDED",
    )
    assert result["price_gate_passed"] is None
    assert result["action"] == "UNDERWRITING_INCOMPLETE"


def test_reachable_claim_or_solvency_break_is_a_real_veto() -> None:
    result = compile_golden_action(
        current_price=8.0,
        baseline_max_research_price=10.0,
        baseline_route_established=True,
        permanent_loss_state="CLAIM_OR_SOLVENCY_BREAK",
        stress_return_pct=-30.0,
    )
    assert result["price_gate_passed"] is True
    assert result["action"] == "AVOID_PERMANENT_LOSS"
    assert "not merely" in result["reason"]
