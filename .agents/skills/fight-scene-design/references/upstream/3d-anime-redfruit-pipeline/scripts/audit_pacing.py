#!/usr/bin/env python3
"""Audit Red Fruit pacing, true-cut coverage, dialogue motion, and peak scarcity."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

from validate_storyboard import (
    SHOT_RE,
    TITLE_RE,
    VISIBLE_CHAPTERS,
    chapter_slice,
    collect_dialogue_fragments,
    field_content,
    make_valid_fixture,
    shot_blocks,
    split_segments,
)


@dataclass
class SegmentMetrics:
    number: int
    duration: float
    internal_shots: int
    battle: bool
    redfruit_fast: bool
    state_transitions: int
    slow_shots: int
    dialogue_seconds: float
    dialogue_fragments: int


def metadata_value(text: str, key: str) -> str:
    match = re.search(rf"{re.escape(key)}(.*?)(?=；|;|。|\n|$)", text)
    return "" if not match else match.group(1).strip()


def block_line(block: str, field: str, following: str | None = None) -> str:
    if following:
        match = re.search(
            rf"^{re.escape(field)}：(.*?)(?=^{re.escape(following)}：)",
            block,
            re.MULTILINE | re.DOTALL,
        )
    else:
        match = re.search(rf"^{re.escape(field)}：(.*)$", block, re.MULTILINE)
    return "" if not match else match.group(1).strip()


def audit_segment(segment: str, index: int) -> tuple[list[str], list[str], SegmentMetrics | None]:
    errors: list[str] = []
    warnings: list[str] = []
    title = TITLE_RE.search(segment)
    if not title:
        return [f"段{index}: 标题不合法，无法节奏审计"], warnings, None
    number = int(title.group(1))
    duration = float(title.group(3))
    prefix = f"镜号{number:03d}"

    one = chapter_slice(segment, VISIBLE_CHAPTERS[0], VISIBLE_CHAPTERS[1])
    big_scene = field_content(one, "大场景") or ""
    scene_mode = metadata_value(big_scene, "场景模式：")
    pace_mode = metadata_value(big_scene, "节奏：")
    state_chain = metadata_value(big_scene, "状态变化：")
    states = [item.strip() for item in state_chain.split("→") if item.strip()]
    transitions = max(0, len(states) - 1)
    battle = "战斗" in scene_mode
    fast = any(marker in pace_mode for marker in ("连续动作密度", "快速连续动作", "快节拍动作", "按动作先后推进"))

    four = chapter_slice(segment, VISIBLE_CHAPTERS[1], VISIBLE_CHAPTERS[2])
    blocks = shot_blocks(four)
    slow_words = ("建立", "凝视", "蓄势", "恢复", "余波", "对峙", "静场")
    active_words = ("攻击", "突袭", "反击", "反转", "碰撞", "破防", "命中", "追击", "压制", "越刃")
    slow_count = 0
    previous_slow = False
    visuals: list[str] = []
    for position, (header, block) in enumerate(blocks, 1):
        shot_duration = float(header.group(2))
        name = header.group(3)
        motion = block_line(block, "运动")
        visual = block_line(block, "画面", "台词与口型")
        visuals.append(re.sub(r"\s+", "", visual))
        slow = any(word in name + visual for word in slow_words) and not any(
            word in name + visual for word in active_words
        )
        if slow:
            slow_count += 1
        if slow and previous_slow:
            warnings.append(f"{prefix}: 内部镜头{position - 1}与{position}连续处于建立/凝视/蓄势/恢复状态")
        previous_slow = slow
        if shot_duration > 6 and "固定" in motion and not any(
            word in name + visual for word in ("对白", "仪式", "召唤", "变身")
        ):
            warnings.append(f"{prefix}: 内部镜头{position}固定机位持续{shot_duration:g}秒且无对白/仪式理由")

    for position in range(1, len(visuals)):
        left, right = visuals[position - 1], visuals[position]
        if len(left) >= 20 and len(right) >= 20:
            similarity = SequenceMatcher(None, left, right).ratio()
            if similarity >= 0.94:
                warnings.append(f"{prefix}: 内部镜头{position}与{position + 1}画面描述相似度{similarity:.0%}，可能重复覆盖")

    fragments = [item for item in collect_dialogue_fragments(segment) if not item[1].startswith("INVALID")]
    fragment_seconds = [float(value) for value in re.findall(r"本片段需([0-9]+(?:\.[0-9]+)?)秒", four)]
    dialogue_seconds = sum(fragment_seconds)
    if dialogue_seconds > 6 and len(fragments) < 2:
        warnings.append(f"{prefix}: 长于6秒的对白只由一个切镜承载")
    if fragments and len(fragment_seconds) != len(fragments):
        warnings.append(f"{prefix}: 有{len(fragments)}个台词片段，但只解析到{len(fragment_seconds)}个片段时长")

    if battle and len(blocks) < 6:
        errors.append(f"{prefix}: 战斗镜号至少需要6个内部切镜，实际{len(blocks)}个")
    if not battle and not 4 <= len(blocks) <= 6:
        errors.append(f"{prefix}: 日常剧情应保持4—6个内部切镜，实际{len(blocks)}个")
    if fast and transitions < 3:
        warnings.append(f"{prefix}: 连续动作密度只有{transitions}次有效状态变化，低于每镜号3次")
    if battle and not fast:
        warnings.append(f"{prefix}: 战斗场景未标记连续动作密度")

    seven = chapter_slice(segment, VISIBLE_CHAPTERS[4], None)
    peak_count = seven.count("唯一峰值：")
    if peak_count != 1:
        errors.append(f"{prefix}: 应声明一个唯一峰值，实际{peak_count}个")

    metrics = SegmentMetrics(
        number=number,
        duration=duration,
        internal_shots=len(blocks),
        battle=battle,
        redfruit_fast=fast,
        state_transitions=transitions,
        slow_shots=slow_count,
        dialogue_seconds=dialogue_seconds,
        dialogue_fragments=len(fragments),
    )
    return errors, warnings, metrics


def audit_text(text: str) -> tuple[list[str], list[str], list[SegmentMetrics]]:
    segments = split_segments(text)
    if not segments:
        return ["未找到可审计镜号"], [], []
    errors: list[str] = []
    warnings: list[str] = []
    metrics: list[SegmentMetrics] = []
    for index, segment in enumerate(segments, 1):
        segment_errors, segment_warnings, segment_metrics = audit_segment(segment, index)
        errors.extend(segment_errors)
        warnings.extend(segment_warnings)
        if segment_metrics:
            metrics.append(segment_metrics)
    battle_metrics = [item for item in metrics if item.battle]
    if battle_metrics:
        duration = sum(item.duration for item in battle_metrics)
        transitions = sum(item.state_transitions for item in battle_metrics)
        density = 15 * transitions / duration if duration else 0.0
        if density < 3:
            warnings.append(f"全场: 战斗状态变化密度仅{density:.2f}次/15秒")
        slow = sum(item.slow_shots for item in battle_metrics)
        total_shots = sum(item.internal_shots for item in battle_metrics)
        if total_shots and slow / total_shots > 0.35:
            warnings.append(f"全场: 建立/凝视/蓄势/恢复镜头占{slow / total_shots:.0%}，可能拖慢")
    return errors, warnings, metrics


def self_test() -> int:
    valid, _source = make_valid_fixture()
    errors, warnings, metrics = audit_text(valid)
    if errors or warnings or not metrics:
        print("SELF-TEST FAILED: valid fixture")
        for message in errors + warnings:
            print(f"- {message}")
        return 1
    slow = valid.replace(
        "状态变化：均衡→沈夜持续下压→黑雾越过剑刃→林烬左脚前踏蓄力。",
        "状态变化：均衡→沈夜持续下压。",
        1,
    )
    _errors, slow_warnings, _metrics = audit_text(slow)
    if not slow_warnings:
        print("SELF-TEST FAILED: slow fixture produced no warning")
        return 1
    no_peak = valid.replace("唯一峰值：内部镜头4黑雾越刃。", "峰值未指定。", 1)
    peak_errors, _warnings, _metrics = audit_text(no_peak)
    if not peak_errors:
        print("SELF-TEST FAILED: missing-peak fixture accepted")
        return 1
    print("SELF-TEST PASSED")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("storyboards", nargs="*", type=Path)
    parser.add_argument("--strict", action="store_true", help="return non-zero when warnings exist")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    if not args.storyboards:
        parser.error("provide at least one storyboard or --self-test")

    failed = False
    warned = False
    for path in args.storyboards:
        try:
            text = path.read_text(encoding="utf-8-sig")
        except OSError as exc:
            print(f"PACING AUDIT FAILED: {path}: {exc}")
            failed = True
            continue
        errors, warnings, metrics = audit_text(text)
        duration = sum(item.duration for item in metrics)
        transitions = sum(item.state_transitions for item in metrics)
        internal = sum(item.internal_shots for item in metrics)
        density = 15 * transitions / duration if duration else 0.0
        print(
            f"PACING SUMMARY: {path} | segments={len(metrics)} | internal={internal} | "
            f"duration={duration:g}s | transitions={transitions} | density={density:.2f}/15s"
        )
        for error in errors:
            print(f"ERROR: {error}")
        for warning in warnings:
            print(f"WARNING: {warning}")
        failed |= bool(errors)
        warned |= bool(warnings)
    return 1 if failed or (args.strict and warned) else 0


if __name__ == "__main__":
    sys.exit(main())
