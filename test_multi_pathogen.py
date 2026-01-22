#!/usr/bin/env python3
"""
测试：单个样本关注多个病原体（Value1/2/3 用分号分隔）时：
- InputParser 能正确解析为多个 species dict
- LibraryPlanner 会为每个病原体生成一行文库记录
"""

from pathlib import Path
import tempfile

import openpyxl
import random

from src.parser import InputParser
from src.planner import LibraryPlanner


def build_input_xlsx(path: Path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "输入表"
    # header
    ws.append([None, "Value1", "Value2", "Value3", "备注"])
    # meta
    ws.append(["研究编号", "F0020", None, None, None])
    ws.append(["研究列表", "分析性能", None, None, None])
    ws.append(["研究说明", "污染的控制措施", None, None, None])
    ws.append(["实验启动时间", 260113, None, None, None])
    ws.append(["实验时间（天）", 1, None, None, None])
    ws.append(["接头起点", "A01", None, None, None])
    ws.append(["需要用到的测序仪台数", 1, None, None, None])
    ws.append(["测序仪1-SN", "TPNB500477", None, None, None])
    ws.append(["测序仪1-RUN", "0143", None, None, None])
    # sample with multi pathogens
    ws.append(
        [
            "F-0020-01",
            "肺炎支原体;人疱疹病毒5型(CMV);铜绿假单胞菌",
            "1~10;1~10;10~100",
            "7000~10000;7000~10000;7000~10000",
            None,
        ]
    )
    wb.save(path)


def main():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "Input table.xlsx"
        build_input_xlsx(p)

        parsed = InputParser(str(p)).parse()
        samples = parsed["samples"]
        assert len(samples) == 1
        s0 = samples[0]
        assert s0["sample_id"] == "F-0020-01"
        assert len(s0["species"]) == 3, s0["species"]

        # use a single chip to generate libraries
        chips = [
            {"芯片SN": "260113_TPNB500477_0143_AXXXXXXXXX", "测序日期": 260113, "测序仪SN": "TPNB500477"}
        ]
        random.seed(1)
        libs = LibraryPlanner(rules={}, species_info={}, adapter_start="A01").plan_libraries(samples=samples, chips=chips)
        # 默认会追加一个NC行（即使未提供nc_list）
        assert len(libs) >= 3, libs
        # 单个样本多病原体：共享同一个接头/文库编号
        assert libs[0]["index"] == "A01"
        assert libs[1]["index"] == "A01"
        assert libs[2]["index"] == "A01"
        assert libs[0]["文库编号"] == libs[1]["文库编号"] == libs[2]["文库编号"]
        assert libs[0]["物种名称"] == "肺炎支原体"
        assert libs[1]["物种名称"] == "人疱疹病毒5型(CMV)"
        assert libs[2]["物种名称"] == "铜绿假单胞菌"
        # spike-rpm 与样本相关：三行应相同
        assert libs[0]["内部对照spike.1RPM值"] == libs[1]["内部对照spike.1RPM值"] == libs[2]["内部对照spike.1RPM值"]

    print("TEST MULTI PATHOGEN: OK")


if __name__ == "__main__":
    main()

