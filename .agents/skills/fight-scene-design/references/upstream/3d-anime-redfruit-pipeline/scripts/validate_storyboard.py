#!/usr/bin/env python3
"""Validate the v4 native-multishot contract and optional source dialogue fidelity."""

from __future__ import annotations

import argparse
import re
import sys
import zipfile
from functools import lru_cache
from pathlib import Path
from xml.etree import ElementTree as ET


VISIBLE_CHAPTERS = [
    "一、场景与连续性",
    "四、内部镜头",
    "五、生成参数",
    "六、剪辑衔接总表",
    "七、特效对照表",
]
SECTION_ONE_FIELDS = [
    "大场景",
    "小场景",
    "时间／天气",
    "群像分层",
    "角色账本",
    "角色声音账本｜最多3人",
    "人物专属道具锚定",
    "轴线与运动方向",
    "空间位置与角色站位",
    "首帧参考",
    "尾帧参考",
]
SECTION_FIVE_FIELDS = ["风格词缀", "固定禁止项", "负面提示词"]
SECTION_SIX_FIELDS = ["镜头间衔接", "首帧参考", "尾帧参考", "验证重点"]
FINAL_FIELDS = ["角色／武器／伤势", "光线／声音", "节奏功能与状态变化"]
TITLE_RE = re.compile(
    r"^【镜号(\d{3})】·([^\n]+?)·单段整合版（约([0-9]+(?:\.[0-9]+)?)秒·([0-9]+)内部镜头）",
    re.MULTILINE,
)
SHOT_RE = re.compile(
    r"^【内部镜头([0-9]+)｜([0-9]+(?:\.[0-9]+)?)秒｜([^】]+)】",
    re.MULTILINE,
)
DIALOGUE_RE = re.compile(
    r"([^\s：；，。]+)\[(SYNC|OS-CONTINUE)\]\s*[：:]\s*[“\"]([^”\"]+)[”\"]"
)


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", "", value)


def field_content(section: str, field: str) -> str | None:
    pattern = re.compile(
        rf"^【{re.escape(field)}】\s*$\n?(.*?)(?=^【[^】]+】\s*$|^[一二三四五六七]、|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(section)
    return None if not match else match.group(1).strip()


def chapter_slice(segment: str, current: str, following: str | None) -> str:
    start = segment.find(current)
    if start < 0:
        return ""
    end = len(segment) if following is None else segment.find(following, start + len(current))
    return segment[start:] if end < 0 else segment[start:end]


def duration_label(value: float) -> str:
    return f"{value:g}"


def shot_blocks(section: str) -> list[tuple[re.Match[str], str]]:
    headers = list(SHOT_RE.finditer(section))
    blocks: list[tuple[re.Match[str], str]] = []
    for index, header in enumerate(headers):
        end = headers[index + 1].start() if index + 1 < len(headers) else len(section)
        blocks.append((header, section[header.start():end]))
    return blocks


def camera_signature(block: str) -> str | None:
    match = re.search(
        r"机位：(.*?)。\s*景别：(.*?)｜\s*高度角度：(.*?)｜\s*焦段：(.*?)。",
        block,
        re.DOTALL,
    )
    if not match:
        return None
    return "|".join(normalize_text(part) for part in match.groups())


def collect_dialogue_fragments(segment: str) -> list[tuple[str, str, str]]:
    four = chapter_slice(segment, VISIBLE_CHAPTERS[1], VISIBLE_CHAPTERS[2])
    fragments: list[tuple[str, str, str]] = []
    previous_speaker: str | None = None
    for _header, block in shot_blocks(four):
        line_match = re.search(r"^台词与口型：(.*)$", block, re.MULTILINE)
        if not line_match:
            continue
        line = line_match.group(1).strip()
        found = DIALOGUE_RE.findall(line)
        if ("“" in line or '"' in line) and not found and line != "无":
            fragments.append(("<INVALID>", "INVALID", line))
            continue
        for speaker, mode, text in found:
            if mode == "OS-CONTINUE" and speaker != previous_speaker:
                fragments.append((speaker, "INVALID-CONTINUE", text))
            else:
                fragments.append((speaker, mode, text))
            previous_speaker = speaker
    return fragments


def extract_source_text(path: Path) -> str:
    if path.suffix.lower() == ".docx":
        with zipfile.ZipFile(path) as archive:
            xml = archive.read("word/document.xml")
        root = ET.fromstring(xml)
        namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        paragraphs: list[str] = []
        for paragraph in root.iter(namespace + "p"):
            text = "".join(node.text or "" for node in paragraph.iter(namespace + "t"))
            if text:
                paragraphs.append(text)
        return "\n".join(paragraphs)
    if path.suffix.lower() in {".txt", ".md"}:
        return path.read_text(encoding="utf-8-sig")
    raise ValueError("source must be .txt, .md, or .docx")


def extract_source_quotes(source_text: str) -> list[str]:
    quotes: list[tuple[int, str]] = []
    for pattern in [r"“([^”]+)”", r'"([^"\n]+)"']:
        for match in re.finditer(pattern, source_text):
            quotes.append((match.start(), normalize_text(match.group(1))))
    quotes.sort(key=lambda item: item[0])
    return [text for _position, text in quotes if text]


def dialogue_partition_matches(
    fragments: list[tuple[str, str, str]], source_quotes: list[str]
) -> bool:
    clean = [(speaker, normalize_text(text)) for speaker, mode, text in fragments if not mode.startswith("INVALID")]
    if not clean:
        return True

    @lru_cache(maxsize=None)
    def solve(fragment_index: int, source_index: int) -> bool:
        if fragment_index == len(clean):
            return True
        speaker = clean[fragment_index][0]
        combined = ""
        for end in range(fragment_index, len(clean)):
            if clean[end][0] != speaker:
                break
            combined += clean[end][1]
            for quote_index in range(source_index, len(source_quotes)):
                quote = source_quotes[quote_index]
                if quote == combined and solve(end + 1, quote_index + 1):
                    return True
        return False

    return solve(0, 0)


def validate_segment(segment: str, index: int) -> list[str]:
    errors: list[str] = []
    prefix = f"段{index}"
    title = TITLE_RE.search(segment)
    declared_duration = declared_count = 0
    if not title:
        errors.append(f"{prefix}: 标题缺少镜号、总时长或内部镜头数")
    else:
        declared_duration = float(title.group(3))
        declared_count = int(title.group(4))
        if not 0 < declared_duration <= 15:
            errors.append(f"{prefix}: 总时长必须在0—15秒内")

    headings = re.findall(r"^[一二三四五六七]、[^\n\r]+", segment, re.MULTILINE)
    if headings != VISIBLE_CHAPTERS:
        errors.append(f"{prefix}: 可见章节必须且只能依次为一、四、五、六、七，实际为{headings}")
    if re.search(r"^#{1,6}\s", segment, re.MULTILINE):
        errors.append(f"{prefix}: 用户可见分镜含Markdown井号标题")
    for forbidden in [
        "二、本镜叙事参数",
        "三、镜头设计总图",
        "MASTER_SHOTS_CONSTRAINT_PACKET",
        "INTERNAL_SHOT_COVERAGE_MAP",
        "战斗母版",
        "即梦直接粘贴提示词",
        "可复制提示词",
        "完整提示词",
        "红果高速",
        "红果式",
        "红果节奏",
        "攻守反转",
        "红果动作簇",
    ]:
        if forbidden in segment:
            errors.append(f"{prefix}: 生成提示词不得出现抽象平台/流派标签“{forbidden}”，请改写为可见动作、镜头、声音或结果")

    one = chapter_slice(segment, VISIBLE_CHAPTERS[0], VISIBLE_CHAPTERS[1])
    for field in SECTION_ONE_FIELDS:
        value = field_content(one, field)
        if value is None or not value:
            errors.append(f"{prefix}: 第一节【{field}】缺失或为空")
    role_ledger = field_content(one, "角色账本") or ""
    if any(marker in role_ledger for marker in ("状态", "动机", "眼神", "眉", "嘴", "呼吸", "重心", "情绪")):
        errors.append(f"{prefix}: 【角色账本】只能列角色名字，人物表演与状态应写入内部镜头")
    big_scene = field_content(one, "大场景") or ""
    for marker in ["场景模式：", "节奏：", "状态变化："]:
        if marker not in big_scene:
            errors.append(f"{prefix}: 【大场景】缺少“{marker}”")
    scene_mode_match = re.search(r"场景模式：([^；。\n]+)", big_scene)
    is_battle = bool(scene_mode_match and "战斗" in scene_mode_match.group(1))

    four = chapter_slice(segment, VISIBLE_CHAPTERS[1], VISIBLE_CHAPTERS[2])
    blocks = shot_blocks(four)
    if not blocks:
        errors.append(f"{prefix}: 第四节没有合法内部镜头")
    else:
        numbers = [int(header.group(1)) for header, _block in blocks]
        durations = [float(header.group(2)) for header, _block in blocks]
        if numbers != list(range(1, len(numbers) + 1)):
            errors.append(f"{prefix}: 内部镜头编号不连续，实际为{numbers}")
        if title and declared_count != len(blocks):
            errors.append(f"{prefix}: 标题声明{declared_count}镜，实际{len(blocks)}镜")
        if title and abs(sum(durations) - declared_duration) > 0.15:
            errors.append(f"{prefix}: 内部时长合计{sum(durations):g}秒，与标题{declared_duration:g}秒不符")
        signatures: list[str | None] = []
        for position, (header, block) in enumerate(blocks, 1):
            duration = float(header.group(2))
            if duration < 1.2:
                errors.append(f"{prefix}: 内部镜头{position}仅{duration:g}秒，微动作应并入相邻镜头")
            for marker in [
                "机位：",
                "景别：",
                "高度角度：",
                "焦段：",
                "构图：",
                "运动：",
                "画面：",
                "台词与口型：",
                "【特效阶段】",
            ]:
                if marker not in block:
                    errors.append(f"{prefix}: 内部镜头{position}缺少“{marker}”")
            signature = camera_signature(block)
            if signature is None:
                errors.append(f"{prefix}: 内部镜头{position}机位行格式不合法")
            signatures.append(signature)
        for position in range(1, len(signatures)):
            if signatures[position] and signatures[position] == signatures[position - 1]:
                errors.append(f"{prefix}: 内部镜头{position}与{position + 1}为相同机位、景别、高度和焦段，属于假切")

    fragments = collect_dialogue_fragments(segment)
    for speaker, mode, _text in fragments:
        if speaker == "<INVALID>" or mode in {"INVALID", "INVALID-CONTINUE"}:
            errors.append(f"{prefix}: 台词标签无效，或[OS-CONTINUE]没有承接同一说话者的前一片段")
    visible_fragments = [fragment for fragment in fragments if not fragment[1].startswith("INVALID")]
    if visible_fragments:
        first_mode = visible_fragments[0][1]
        if first_mode == "OS-CONTINUE":
            errors.append(f"{prefix}: 本镜号第一段对白不能从[OS-CONTINUE]开始")

    five = chapter_slice(segment, VISIBLE_CHAPTERS[2], VISIBLE_CHAPTERS[3])
    if "比例：" not in five:
        errors.append(f"{prefix}: 第五节必须注明比例")
    for forbidden in ("平台模式：", "原生多镜", "切镜"):
        if forbidden in five:
            errors.append(f"{prefix}: 第五节不得输出“{forbidden}”平台或切镜提示")
    five_fields = re.findall(r"^【([^】]+)】\s*$", five, re.MULTILINE)
    if five_fields != SECTION_FIVE_FIELDS:
        errors.append(f"{prefix}: 第五节只允许{SECTION_FIVE_FIELDS}，实际为{five_fields}")
    for field in SECTION_FIVE_FIELDS:
        value = field_content(five, field)
        if value is None or not value:
            errors.append(f"{prefix}: 第五节【{field}】缺失或为空")
    style = field_content(five, "风格词缀") or ""
    if not style.startswith("4K画质，电影级3D游戏CG概念风格"):
        errors.append(f"{prefix}: 风格词缀必须以“4K画质，电影级3D游戏CG概念风格”开头")
    if not ("Continuously matching the previous shot" in style or "保持上一镜" in style or "继承上一镜" in style):
        errors.append(f"{prefix}: 风格词缀缺少具体的上一镜连续性锚点")
    negative = field_content(five, "负面提示词") or ""
    negative_items = [item.strip() for item in re.split(r"[；;，,、\n]+", negative) if item.strip()]
    if not 10 <= len(negative_items) <= 20:
        errors.append(f"{prefix}: 负面提示词应为10—20条，解析到{len(negative_items)}条")
    if is_battle and blocks and len(blocks) < 6:
        errors.append(f"{prefix}: 战斗原生多镜至少包含6个内部镜头，实际{len(blocks)}个")
    if not is_battle and blocks and not 4 <= len(blocks) <= 6:
        errors.append(f"{prefix}: 日常剧情原生多镜必须包含4—6个内部镜头，实际{len(blocks)}个")

    six = chapter_slice(segment, VISIBLE_CHAPTERS[3], VISIBLE_CHAPTERS[4])
    for field in SECTION_SIX_FIELDS:
        value = field_content(six, field)
        if value is None or not value:
            errors.append(f"{prefix}: 第六节【{field}】缺失或为空")
    transitions = field_content(six, "镜头间衔接") or ""
    if "拆分回退：" not in transitions:
        errors.append(f"{prefix}: 【镜头间衔接】缺少“拆分回退：”")
    if blocks:
        cumulative = 0.0
        for _header, block in blocks[:-1]:
            header = SHOT_RE.search(block)
            if header:
                cumulative += float(header.group(2))
                label = duration_label(cumulative)
                if not re.search(rf"切点\s*{re.escape(label)}(?:\.0)?秒", transitions):
                    errors.append(f"{prefix}: 第六节缺少累计切点{label}秒")

    seven = chapter_slice(segment, VISIBLE_CHAPTERS[4], None)
    for field in FINAL_FIELDS:
        value = field_content(seven, field)
        if value is None or not value:
            errors.append(f"{prefix}: 镜号末尾【{field}】缺失或为空")
    chain = field_content(seven, "特效资产与阶段总链")
    if chain is None or not chain:
        errors.append(f"{prefix}: 第七节缺少有效【特效资产与阶段总链】")
    elif chain.count("唯一峰值：") != 1:
        errors.append(f"{prefix}: 特效总链必须且只能声明一个“唯一峰值：”")
    if not re.search(r"\|\s*内部镜头\s*\|\s*时长\s*\|\s*主层\s*\|\s*反应层\s*\|\s*遗留层\s*\|", seven):
        errors.append(f"{prefix}: 第七节缺少主层/反应层/遗留层对照表")
    effect_rows = re.findall(r"^\|\s*镜头\d+[^\n]*\|\s*$", seven, re.MULTILINE)
    if blocks and len(effect_rows) != len(blocks):
        errors.append(f"{prefix}: 特效表{len(effect_rows)}行，与内部镜头{len(blocks)}个不一致")
    return errors


def split_segments(text: str) -> list[str]:
    starts = list(re.finditer(r"^【镜号\d{3}】", text, re.MULTILINE))
    return [
        text[start.start():(starts[index + 1].start() if index + 1 < len(starts) else len(text))].strip()
        for index, start in enumerate(starts)
    ]


def validate_text(text: str, source_text: str | None = None) -> list[str]:
    segments = split_segments(text)
    if not segments:
        return ["未找到【镜号XXX】段落"]
    errors: list[str] = []
    numbers: list[int] = []
    all_fragments: list[tuple[str, str, str]] = []
    for index, segment in enumerate(segments, 1):
        title = TITLE_RE.search(segment)
        if title:
            numbers.append(int(title.group(1)))
        errors.extend(validate_segment(segment, index))
        all_fragments.extend(collect_dialogue_fragments(segment))
    if numbers and numbers != list(range(numbers[0], numbers[0] + len(numbers))):
        errors.append(f"镜号不连续，实际为{numbers}")
    if source_text is not None:
        source_quotes = extract_source_quotes(source_text)
        valid_fragments = [fragment for fragment in all_fragments if not fragment[1].startswith("INVALID")]
        if valid_fragments and not source_quotes:
            errors.append("源文件未提取到引号内台词，无法核对跨镜片段")
        elif valid_fragments and not dialogue_partition_matches(valid_fragments, source_quotes):
            joined = "｜".join(fragment[2] for fragment in valid_fragments)
            errors.append(f"跨镜台词片段无法按顺序拼成源文件中的完整逐字台词：{joined}")
    return errors


def make_valid_fixture() -> tuple[str, str]:
    source = "沈夜：“玄门旧道，早已不适合末世生存。你的灵气，挡不住我的寂灭之力。”"
    shots = [
        (1, 2.6, "压刀起句", "咬合线左前方3.5米", "双人近景", "平视", "65mm", "沈夜[SYNC]：“玄门旧道，早已不适合末世生存。”（本片段需2.6秒）"),
        (2, 2.0, "刀剑蚀纹", "刀剑接触点侧上方1米", "武器特写", "轻俯", "85mm", "沈夜[OS-CONTINUE]：“你的灵气，”（本片段需2秒）"),
        (3, 2.6, "句尾压迫", "沈夜右侧前方2.8米", "人物近景", "略仰", "75mm", "沈夜[SYNC]：“挡不住我的寂灭之力。”（本片段需2.6秒）"),
        (4, 2.4, "黑雾越刃", "林烬右腕外侧0.8米", "手腕特写", "平视", "90mm", "无"),
        (5, 2.8, "半步蓄反", "战斗轴侧面6米", "双人中景", "平视", "40mm", "无"),
        (6, 2.6, "反制落点", "林烬左后方4米", "双人中远景", "轻俯", "50mm", "无"),
    ]
    blocks: list[str] = []
    for number, duration, name, camera, scale, angle, lens, dialogue in shots:
        blocks.append(
            f"""【内部镜头{number}｜{duration:g}秒｜{name}】
机位：{camera}。景别：{scale}｜高度角度：{angle}｜焦段：{lens}。
构图：林烬画左，沈夜画右，接触点清楚。
运动：主体动作牵引，接触前停止。
画面：{name}中，主体按本镜目标完成独立动作，目标点、受力结果与下一接口清楚可见。
台词与口型：{dialogue}
【特效阶段】：有源生成→传播→接触→反馈→遗留。"""
        )
    rows = "\n".join(
        f"| 镜头{number} {name} | {duration:g}秒 | 主层变化 | 受力与材质反馈 | 状态遗留 |"
        for number, duration, name, *_rest in shots
    )
    fixture = f"""【镜号006】·寂灭宣言·单段整合版（约15秒·6内部镜头）

一、场景与连续性
【大场景】
兵刃锁死，沈夜持续下压，黑雾越过剑刃，林烬左脚前踏蓄力。场景模式：战斗；节奏：连续动作密度；状态变化：均衡→沈夜持续下压→黑雾越过剑刃→林烬左脚前踏蓄力。
【小场景】
街心近距，双方兵刃居中。
【时间／天气】
黄昏烟尘。
【群像分层】
前景握柄，中景双人，后景烟尘。
【角色账本】
林烬、沈夜。
【角色声音账本｜最多3人】
沈夜、林烬。
【人物专属道具锚定】
青锋与寂灭持续咬合。
【轴线与运动方向】
林烬左、沈夜右。
【空间位置与角色站位】
接触距离。
【首帧参考】
沈夜压刀。
【尾帧参考】
林烬左脚前踏蓄反。

四、内部镜头
{chr(10).join(blocks)}

五、生成参数
比例：16:9
【风格词缀】
4K画质，电影级3D游戏CG概念风格，Continuously matching the previous shot，轴线稳定，连续声轨。
【固定禁止项】
no subtitles, no watermark, no logo, no random text, no background music generated
【负面提示词】
身份漂移，武器换手，伤势复原，越轴，假切，台词重复，台词漏字，口型错位，黑雾遮脸，无接触，受力反向，随机爆炸

六、剪辑衔接总表
【镜头间衔接】
镜头1尾帧（切点2.6秒）→镜头2首帧：兵刃形状匹配；声桥：[SYNC]→[OS-CONTINUE]。
镜头2尾帧（切点4.6秒）→镜头3首帧：声轨连续并切回口型。
镜头3尾帧（切点7.2秒）→镜头4首帧：台词落下后黑雾越刃。
镜头4尾帧（切点9.6秒）→镜头5首帧：林烬垂眼后前踏。
镜头5尾帧（切点12.4秒）→镜头6首帧：前踏后的反制落点。
拆分回退：若原生多镜失败，按镜头1—6分别生成并依上述切点顺序剪辑。
【首帧参考】
沈夜压刀。
【尾帧参考】
林烬左脚前踏蓄反。
【验证重点】
检查轴线、真实机位、连续台词、唯一峰值、武器和伤势。

七、特效对照表
【特效资产与阶段总链】
寂灭腐煞生成→沿接触线传播→越刃逼腕→林烬蓄反。唯一峰值：内部镜头4黑雾越刃。
| 内部镜头 | 时长 | 主层 | 反应层 | 遗留层 |
|---|---:|---|---|---|
{rows}
【角色／武器／伤势】
林烬持青锋，沈夜持寂灭，伤势与握持连续。
【光线／声音】
黄昏烟尘，金属挤压声和暗影腐蚀声连续。
【节奏功能与状态变化】
模式：战斗动作；功能：持续下压与半步蓄力；状态变化：均衡→持续下压→黑雾越刃→前踏蓄力；峰值：黑雾越刃；钩子：前踏后反击。
"""
    return fixture, source


def self_test() -> int:
    valid, source = make_valid_fixture()
    errors = validate_text(valid, source)
    if errors:
        print("SELF-TEST FAILED: valid fixture rejected")
        for error in errors:
            print(f"- {error}")
        return 1
    invalid_cases = {
        "duration mismatch": valid.replace("约15秒", "约14秒", 1),
        "dialogue duplicate": valid.replace("挡不住我的寂灭之力。", "你的灵气，挡不住我的寂灭之力。", 1),
        "fake cut": valid.replace(
            "机位：刀剑接触点侧上方1米。景别：武器特写｜高度角度：轻俯｜焦段：85mm。",
            "机位：咬合线左前方3.5米。景别：双人近景｜高度角度：平视｜焦段：65mm。",
            1,
        ),
        "two peaks": valid.replace("唯一峰值：内部镜头4黑雾越刃。", "唯一峰值：内部镜头4黑雾越刃。唯一峰值：内部镜头5蓄反。", 1),
        "missing fallback": valid.replace("拆分回退：", "备用说明：", 1),
    }
    for name, invalid in invalid_cases.items():
        if not validate_text(invalid, source):
            print(f"SELF-TEST FAILED: {name} fixture accepted")
            return 1
    print("SELF-TEST PASSED")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("storyboards", nargs="*", type=Path)
    parser.add_argument("--source", type=Path, help="source .txt, .md, or .docx for exact dialogue validation")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    if not args.storyboards:
        parser.error("provide at least one storyboard or --self-test")
    try:
        source_text = extract_source_text(args.source) if args.source else None
    except (OSError, ValueError, zipfile.BadZipFile, KeyError, ET.ParseError) as exc:
        print(f"VALIDATION FAILED\n- source: {exc}")
        return 1

    all_errors: list[str] = []
    checked = 0
    for path in args.storyboards:
        try:
            text = path.read_text(encoding="utf-8-sig")
        except OSError as exc:
            all_errors.append(f"{path}: 无法读取：{exc}")
            continue
        errors = validate_text(text, source_text)
        checked += len(split_segments(text))
        all_errors.extend(f"{path}: {error}" for error in errors)
    if all_errors:
        print("VALIDATION FAILED")
        for error in all_errors:
            print(f"- {error}")
        return 1
    print(f"VALIDATION PASSED: {checked} storyboard segment(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
