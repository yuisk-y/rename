from pathlib import Path

from app.naming import NamingOptions, build_new_name, strip_old_sequence


def test_build_two_digit_number_and_separator() -> None:
    name = build_new_name(Path("需求与供给.pptx"), 0, NamingOptions(digits=2))
    assert name == "01. 需求与供给.pptx"


def test_keep_extension() -> None:
    name = build_new_name(Path("消费者理论.final.v2.pdf"), 1, NamingOptions(digits=2))
    assert name == "02. 消费者理论.final.v2.pdf"


def test_strip_common_old_sequences() -> None:
    samples = {
        "1. 消费者理论": "消费者理论",
        "01、消费者理论": "消费者理论",
        "01-消费者理论": "消费者理论",
        "01_消费者理论": "消费者理论",
        "第1章 消费者理论": "消费者理论",
        "第01章-消费者理论": "消费者理论",
    }
    for original, expected in samples.items():
        assert strip_old_sequence(original) == expected


def test_do_not_strip_meaningful_leading_numbers() -> None:
    assert strip_old_sequence("2026年度教学计划") == "2026年度教学计划"
    assert strip_old_sequence("500强企业案例") == "500强企业案例"


def test_chinese_filename_generation() -> None:
    name = build_new_name(Path("第01章-需求与供给.docx"), 2, NamingOptions(start_number=1, digits=2))
    assert name == "03. 需求与供给.docx"

