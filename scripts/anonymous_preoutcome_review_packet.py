#!/usr/bin/env python3
"""Build a self-contained, arm-anonymous pre-outcome review packet.

The packet is a transport artifact: it copies the fixed source text, each
canonical Episode and its first reader report, while removing only arm
identifiers.  It never scores an arm, selects a winner, reads an outcome, or
rewrites an economic judgment.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import Any


SCHEMA_VERSION = "enterprise-underwriting-anonymous-preoutcome-review-task.v1"
ARM_IDENTIFIERS = (
    "A00_BASELINE",
    "A10_EXPERT_ONLY",
    "A01_INDUSTRY_ONLY",
    "A11_COMBINED",
    "A00",
    "A10",
    "A01",
    "A11",
)
_OPAQUE_LABEL_PATTERN = re.compile(r"ANON_[BCDFGHJKLMNPQRSTVWXYZ]{12}")


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def _replace_arm_identifiers(value: Any, label: str) -> Any:
    if isinstance(value, dict):
        return {key: _replace_arm_identifiers(item, label) for key, item in value.items()}
    if isinstance(value, list):
        return [_replace_arm_identifiers(item, label) for item in value]
    if not isinstance(value, str):
        return value
    result = value
    for identifier in ARM_IDENTIFIERS:
        result = result.replace(identifier, label)
    return result


def _assert_anonymous(value: Any) -> None:
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True)
    leaked = [identifier for identifier in ARM_IDENTIFIERS if identifier in serialized]
    if leaked:
        raise ValueError("anonymous_packet_arm_identifier_leak:" + ",".join(leaked))


def build_packet(
    *,
    source_paths: list[Path],
    anonymous_arms: list[tuple[str, Path, Path]],
) -> dict[str, Any]:
    if len(anonymous_arms) != 4:
        raise ValueError("anonymous_packet_requires_exactly_four_arms")
    labels = [label for label, _, _ in anonymous_arms]
    if len(set(labels)) != 4 or any(
        _OPAQUE_LABEL_PATTERN.fullmatch(label) is None for label in labels
    ):
        raise ValueError("anonymous_packet_labels_invalid")
    if any(
        identifier in label for label in labels for identifier in ARM_IDENTIFIERS
    ):
        raise ValueError("anonymous_packet_label_contains_arm_identifier")

    sources = [
        {"source_ref": str(path), "content": path.read_text(encoding="utf-8")}
        for path in source_paths
    ]
    if len({item["source_ref"] for item in sources}) != len(sources):
        raise ValueError("anonymous_packet_sources_duplicate")
    arms = []
    for label, episode_path, report_path in anonymous_arms:
        arms.append({
            "label": label,
            "episode": _replace_arm_identifiers(_read_json(episode_path), label),
            "first_reader_report": _replace_arm_identifiers(
                report_path.read_text(encoding="utf-8"), label
            ),
        })
    packet = {
        "schema_version": SCHEMA_VERSION,
        "state": "ANONYMOUS_PREOUTCOME_REVIEW_READY",
        "reviewer_instructions": [
            "Read only this packet. Do not seek outcome, price, return, arm mapping, or other repository material.",
            "Compare source discipline, time/responsibility boundaries, industry-to-company transmission, survival/adaptation, normal earnings, ordinary-share cash, permanent loss, value route, strongest rival, reversals, and reader actionability.",
            "Do not treat length, field count, tone, pessimism, or the number of localized unknowns as improvement.",
            "A material difference must identify its economic impact, evidence support, prohibited assumption, reversal observation, and whether it changes a base/conditional/excluded/unresolved treatment.",
            "Return exactly one overall state: PREOUTCOME_COMPARABILITY_PASS, PAIRED_TEST_INVALID, or MATERIAL_PREOUTCOME_DIFFERENCE_CANDIDATE. If not PASS, classify each root cause as DATA_COVERAGE, ACQUISITION_MODULE, REASONING, MODEL, or WRITING and give executable remediation plus acceptance criteria.",
            "Do not read or infer the hidden mapping from anonymous labels to training inputs. Do not make an investment action, value, price, or return conclusion.",
        ],
        "shared_cutoff_sources": sources,
        "anonymous_arms": arms,
    }
    _assert_anonymous(packet)
    return packet


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, action="append", required=True)
    parser.add_argument(
        "--arm",
        action="append",
        nargs=3,
        metavar=("LABEL", "EPISODE", "REPORT"),
        required=True,
    )
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        packet = build_packet(
            source_paths=[path.expanduser().resolve() for path in args.source],
            anonymous_arms=[
                (label, Path(episode).expanduser().resolve(), Path(report).expanduser().resolve())
                for label, episode, report in args.arm
            ],
        )
        output = args.output.expanduser().resolve()
        _atomic_json(output, packet)
        print(json.dumps({
            "schema_version": SCHEMA_VERSION,
            "state": packet["state"],
            "packet_path": str(output),
            "anonymous_labels": [item["label"] for item in packet["anonymous_arms"]],
        }, ensure_ascii=False, sort_keys=True))
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({
            "schema_version": SCHEMA_VERSION,
            "state": "INVALID",
            "findings": [str(exc)],
        }, ensure_ascii=False, sort_keys=True))
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
