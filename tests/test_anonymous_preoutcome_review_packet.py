from __future__ import annotations

import json
from pathlib import Path

from scripts.anonymous_preoutcome_review_packet import build_packet


def _episode(arm: str) -> dict[str, object]:
    return {"episode_id": f"EPISODE:{arm}:V4", "nested": {"arm": arm}}


def test_packet_hides_every_known_arm_identifier(tmp_path: Path) -> None:
    source = tmp_path / "source.md"
    source.write_text("cutoff-only fact", encoding="utf-8")
    arms = []
    for label, arm in zip(
        ("ANON_COBALT", "ANON_FERN", "ANON_IVORY", "ANON_TOPAZ"),
        ("A00_BASELINE", "A10_EXPERT_ONLY", "A01_INDUSTRY_ONLY", "A11_COMBINED"),
        strict=True,
    ):
        episode = tmp_path / f"{arm}.json"
        report = tmp_path / f"{arm}.md"
        episode.write_text(json.dumps(_episode(arm)), encoding="utf-8")
        report.write_text(f"report {arm}", encoding="utf-8")
        arms.append((label, episode, report))

    packet = build_packet(source_paths=[source], anonymous_arms=arms)
    text = json.dumps(packet, ensure_ascii=False)
    assert "A00" not in text and "A10" not in text
    assert "A01" not in text and "A11" not in text
    assert [item["label"] for item in packet["anonymous_arms"]] == [
        item[0] for item in arms
    ]


def test_packet_rejects_not_exactly_four_arms(tmp_path: Path) -> None:
    source = tmp_path / "source.md"
    source.write_text("cutoff-only fact", encoding="utf-8")
    episode = tmp_path / "episode.json"
    report = tmp_path / "report.md"
    episode.write_text(json.dumps(_episode("A00_BASELINE")), encoding="utf-8")
    report.write_text("report", encoding="utf-8")

    try:
        build_packet(
            source_paths=[source],
            anonymous_arms=[("ANON_ONE", episode, report)],
        )
    except ValueError as exc:
        assert str(exc) == "anonymous_packet_requires_exactly_four_arms"
    else:  # pragma: no cover
        raise AssertionError("expected exact-four-arm failure")


def test_packet_rejects_anonymous_label_that_contains_an_arm_identifier(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.md"
    source.write_text("cutoff-only fact", encoding="utf-8")
    episode = tmp_path / "episode.json"
    report = tmp_path / "report.md"
    episode.write_text(json.dumps(_episode("clean")), encoding="utf-8")
    report.write_text("report", encoding="utf-8")
    arms = [
        ("ANON_A00", episode, report),
        ("ANON_FERN", episode, report),
        ("ANON_IVORY", episode, report),
        ("ANON_TOPAZ", episode, report),
    ]

    try:
        build_packet(source_paths=[source], anonymous_arms=arms)
    except ValueError as exc:
        assert str(exc) == "anonymous_packet_label_contains_arm_identifier"
    else:  # pragma: no cover
        raise AssertionError("expected anonymous-label leak failure")


def test_packet_rejects_arm_identifier_in_shared_source_content(tmp_path: Path) -> None:
    source = tmp_path / "source.md"
    source.write_text("A00 hidden mapping", encoding="utf-8")
    episode = tmp_path / "episode.json"
    report = tmp_path / "report.md"
    episode.write_text(json.dumps(_episode("clean")), encoding="utf-8")
    report.write_text("report", encoding="utf-8")
    arms = [
        ("ANON_COBALT", episode, report),
        ("ANON_FERN", episode, report),
        ("ANON_IVORY", episode, report),
        ("ANON_TOPAZ", episode, report),
    ]

    try:
        build_packet(source_paths=[source], anonymous_arms=arms)
    except ValueError as exc:
        assert str(exc) == "anonymous_packet_arm_identifier_leak:A00"
    else:  # pragma: no cover
        raise AssertionError("expected shared-source leak failure")
