"""
排布算法核心模块
实现样本到芯片和文库的排布逻辑
"""
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta, date
import re
import random


class LibraryPlanner:
    """文库排布规划器"""
    
    def __init__(
        self,
        rules: Dict[str, Any],
        species_info: Optional[Dict[str, Any]] = None,
        adapter_start: str = "A01",
        default_chip_data_amount: str = "420M",
        pc_list: Optional[List[Dict[str, Any]]] = None,
        nc_list: Optional[List[Dict[str, Any]]] = None,
        pc_spike_rpm_range: str = "",
        nc_spike_rpm_range: str = "",
    ):
        """
        初始化文库规划器
        
        Args:
            rules: 规则字典
            species_info: 物种信息字典
            adapter_start: 接头起点（例如 A01）
        """
        self.rules = rules
        self.species_info = species_info or {}
        self.adapter_start = adapter_start
        self.default_chip_data_amount = default_chip_data_amount
        self.pc_list = pc_list or []
        self.nc_list = nc_list or []
        self.pc_spike_rpm_range = pc_spike_rpm_range or ""
        self.nc_spike_rpm_range = nc_spike_rpm_range or ""
        
    @staticmethod
    def _yymmdd_to_yyyymmdd_str(yymmdd: Any) -> str:
        """
        输入: 260113 (YYMMDD)
        输出: 20260113 (固定 20 + YYMMDD)
        """
        s = str(yymmdd).strip()
        s = re.sub(r"[^\d]", "", s)
        if len(s) != 6:
            raise ValueError(f"非法测序日期(期望YYMMDD 6位数字): {yymmdd}")
        return "20" + s

    @staticmethod
    def _yyyymmdd_to_dot_date(yyyymmdd: str) -> str:
        return f"{yyyymmdd[0:4]}.{yyyymmdd[4:6]}.{yyyymmdd[6:8]}"

    @staticmethod
    def _sn_last3_digits(sn: str) -> str:
        digits = re.sub(r"\D", "", sn or "")
        if len(digits) < 3:
            raise ValueError(f"测序仪SN中无法提取后三位数字: {sn}")
        return digits[-3:]

    @staticmethod
    def _next_adapter(adapter: str) -> str:
        """
        A01..A48, 然后 B01..B48, 然后回到 A01（循环）
        """
        m = re.match(r"^([AB])(\d{2})$", adapter.strip().upper())
        if not m:
            raise ValueError(f"非法接头号: {adapter} (期望A01/B01等)")
        grp, num_s = m.group(1), m.group(2)
        num = int(num_s)
        if num < 1 or num > 48:
            raise ValueError(f"非法接头号: {adapter} (01-48)")
        if num < 48:
            return f"{grp}{num+1:02d}"
        if grp == "A":
            return "B01"
        # grp == "B" and num == 48
        return "A01"

    def _lookup_species(self, name: str) -> Dict[str, Any]:
        if not name:
            return {}
        return self.species_info.get(name, {})

    @staticmethod
    def _parse_range(range_str: str) -> Optional[tuple]:
        """
        支持: 1~10, 1-10, 1～10, 1,10
        返回 (low, high) float
        """
        if range_str is None:
            return None
        s = str(range_str).strip()
        if s == "":
            return None
        s = s.replace("～", "~").replace("-", "~").replace(",", "~")
        parts = [p.strip() for p in s.split("~") if p.strip() != ""]
        if len(parts) == 1:
            try:
                v = float(parts[0])
                return (v, v)
            except Exception:
                return None
        if len(parts) >= 2:
            try:
                a = float(parts[0])
                b = float(parts[1])
                return (min(a, b), max(a, b))
            except Exception:
                return None
        return None

    @staticmethod
    def _rand_in_range(r: Optional[tuple]) -> Optional[float]:
        if not r:
            return None
        low, high = r
        if low == high:
            return low
        # 默认生成1位小数（如果需要整数可改为 randint）
        v = random.uniform(low, high)
        return round(v, 1)
    
    def plan_libraries(
        self,
        samples: List[Dict[str, Any]],
        chips: List[Dict[str, Any]],
        research_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        规划文库排布（按规则生成文库编号/index/日期等）
        
        Args:
            samples: 样本列表
            chips: 用户确认后的芯片表列表（顺序即输出顺序）
            
        Returns:
            文库列表
        """
        libraries: List[Dict[str, Any]] = []

        # 接头号全局连续：跨芯片不重置
        adapter = self.adapter_start

        for chip in chips:
            chip_sn = str(chip.get("芯片SN", "")).strip()
            seq_sn = str(chip.get("测序仪SN", "")).strip()
            yymmdd = chip.get("测序日期")

            if not chip_sn:
                # 如果芯片SN未给，至少用占位避免空
                chip_sn = "UNKNOWN_CHIP_SN"

            yyyymmdd = self._yymmdd_to_yyyymmdd_str(yymmdd)
            up_time = self._yyyymmdd_to_dot_date(yyyymmdd)
            sn_last3 = self._sn_last3_digits(seq_sn)

            # 1) 普通样本（输入表行）——接头号按行顺序递增
            for sample in samples:
                sample_id = str(sample.get("sample_id", "")).strip()
                species_list = sample.get("species", []) or []
                # 兼容旧结构：species可能是字符串列表
                for species in (species_list or [""]):
                    if isinstance(species, dict):
                        species_name = str(species.get("name", "")).strip()
                        rpm_range_s = species.get("rpm_range", "")
                        spike_range_s = species.get("spike_rpm_range", "")
                    else:
                        species_name = str(species).strip()
                        rpm_range_s = ""
                        spike_range_s = ""

                    rpm_v = self._rand_in_range(self._parse_range(rpm_range_s))
                    spike_v = self._rand_in_range(self._parse_range(spike_range_s))

                    library_id = f"{sample_id}-{sn_last3}-{adapter}-{yyyymmdd}"
                    extra = self._lookup_species(species_name)

                    row: Dict[str, Any] = {
                        "芯片": chip_sn,
                        "芯片数据量": self.default_chip_data_amount,
                        "上机时间": up_time,
                        "样本名称": sample_id,
                        "文库编号": library_id,
                        "index": adapter,
                        "Clean Reads": "",
                        "≥Q20%": "",
                        "Q30": "",
                        "物种名称": species_name,
                        # 新输入要求：按范围随机生成
                        "rpm": rpm_v if rpm_v is not None else "",
                        # 模板列名是这个（示例输出也有）
                        "内部对照spike.1RPM值": spike_v if spike_v is not None else "",
                        "分类": extra.get("分类", ""),
                        "taxid": extra.get("taxid", ""),
                        "拉丁文": extra.get("拉丁文", ""),
                    }
                    libraries.append(row)

                    adapter = self._next_adapter(adapter)

            # 2) PC/NC 质控：接头继续顺延，不重置
            # 命名：F-{研究编号}-CN-PC / F-{研究编号}-CN-NC
            rid = (research_id or "").strip()
            if rid:
                pc_name = f"F-{rid}-CN-PC"
                nc_name = f"F-{rid}-CN-NC"
            else:
                pc_name = "PC"
                nc_name = "NC"

            # PC：同一个 index/文库编号，展开成多条病原体行（与你截图一致）
            if self.pc_list:
                pc_index = adapter
                pc_lib_id = f"{pc_name}-{pc_index}-{yyyymmdd}"
                pc_spike_v = self._rand_in_range(self._parse_range(self.pc_spike_rpm_range))
                for pc in self.pc_list:
                    species_name = str(pc.get("物种名称", "")).strip()
                    extra = self._lookup_species(species_name)
                    # rpm 参考 PC.xlsx 的 rpm 列（通常是范围字符串，如 50~100）
                    pc_rpm_v = self._rand_in_range(self._parse_range(pc.get("rpm", "")))
                    libraries.append(
                        {
                            "芯片": chip_sn,
                            "芯片数据量": self.default_chip_data_amount,
                            "上机时间": up_time,
                            "样本名称": pc_name,
                            "文库编号": pc_lib_id,
                            "index": pc_index,
                            "Clean Reads": "",
                            "≥Q20%": "",
                            "Q30": "",
                            "物种名称": species_name,
                            "分类": pc.get("分类", extra.get("分类", "")),
                            "taxid": pc.get("taxid", extra.get("taxid", "")),
                            "拉丁文": extra.get("拉丁文", ""),
                            "rpm": pc_rpm_v if pc_rpm_v is not None else "",
                            "内部对照spike.1RPM值": pc_spike_v if pc_spike_v is not None else "",
                        }
                    )
                adapter = self._next_adapter(adapter)

            # NC：一条记录（物种名称通常为 /），占用一个 index
            # 取 NC列表第一行；若为空则用默认 “/”
            nc_index = adapter
            nc_lib_id = f"{nc_name}-{nc_index}-{yyyymmdd}"
            nc_species = "/"
            if self.nc_list:
                nc_species = str(self.nc_list[0].get("物种名称", "/")).strip() or "/"
            nc_spike_v = self._rand_in_range(self._parse_range(self.nc_spike_rpm_range))
            libraries.append(
                {
                    "芯片": chip_sn,
                    "芯片数据量": self.default_chip_data_amount,
                    "上机时间": up_time,
                    "样本名称": nc_name,
                    "文库编号": nc_lib_id,
                    "index": nc_index,
                    "Clean Reads": "",
                    "≥Q20%": "",
                    "Q30": "",
                    "物种名称": nc_species,
                    "分类": "",
                    "taxid": "",
                    "拉丁文": "",
                    "rpm": "",
                    "内部对照spike.1RPM值": nc_spike_v if nc_spike_v is not None else "",
                }
            )
            adapter = self._next_adapter(adapter)

        return libraries


class ChipPlanner:
    """芯片排布规划器"""
    
    def __init__(self, rules: Dict[str, Any], sequencer_info: Optional[Dict[str, Any]] = None):
        """
        初始化芯片规划器
        
        Args:
            rules: 规则字典
            sequencer_info: 测序仪信息字典
        """
        self.rules = rules
        self.sequencer_info = sequencer_info or {}

    @staticmethod
    def _parse_yymmdd(yymmdd: Any) -> date:
        s = str(yymmdd).strip()
        s = re.sub(r"[^\d]", "", s)
        if len(s) != 6:
            raise ValueError(f"非法实验启动时间(期望YYMMDD 6位数字): {yymmdd}")
        yy = int(s[0:2])
        mm = int(s[2:4])
        dd = int(s[4:6])
        return date(2000 + yy, mm, dd)

    @staticmethod
    def _date_to_yymmdd_int(d: date) -> int:
        return int(d.strftime("%y%m%d"))

    @staticmethod
    def _run_to_4digits(run: Any) -> str:
        s = str(run).strip()
        s = re.sub(r"[^\d]", "", s)
        if s == "":
            return "0000"
        return f"{int(s):04d}"

    @staticmethod
    def build_chip_sn(yymmdd: Any, sequencer_sn: str, run: Any) -> str:
        run4 = ChipPlanner._run_to_4digits(run)
        s = str(yymmdd).strip()
        s = re.sub(r"[^\d]", "", s)
        if len(s) != 6:
            raise ValueError(f"非法测序日期(期望YYMMDD 6位数字): {yymmdd}")
        return f"{s}_{sequencer_sn}_{run4}_AXXXXXXXXX"
    
    def plan_chips_from_input(self, meta: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        根据输入表meta规划芯片表（严格按规则字段）
        
        Args:
            meta: InputParser.parse() 的 meta 字段
            
        Returns:
            芯片列表
        """
        research_id = str(meta.get("研究编号", "")).strip()
        research_list = str(meta.get("研究列表", "")).strip()
        research_desc = str(meta.get("研究说明", "")).strip()
        project = f"{research_id}-{research_list}-{research_desc}".strip("-")

        start_yymmdd = meta.get("实验启动时间")
        days = int(meta.get("实验时间（天）") or 1)
        sequencers = meta.get("sequencers", []) or []

        start_date = self._parse_yymmdd(start_yymmdd)

        # 每台测序仪的Run值：使用一次 +1
        run_map: Dict[str, int] = {}
        for seq in sequencers:
            sn = str(seq.get("sn", "")).strip()
            run_start = seq.get("run", "")
            if not sn:
                continue
            run_map[sn] = int(re.sub(r"\D", "", str(run_start)) or "0")

        chips: List[Dict[str, Any]] = []
        for day_offset in range(days):
            d = start_date + timedelta(days=day_offset)
            yymmdd_int = self._date_to_yymmdd_int(d)
            for seq in sequencers:
                sn = str(seq.get("sn", "")).strip()
                run = run_map.get(sn, 0)
                model = ""
                if sn in self.sequencer_info:
                    model = self.sequencer_info[sn].get("设备型号", "") or ""

                chip = {
                    "实验项目": project,
                    "测序日期": yymmdd_int,
                    "测序仪SN": sn,
                    # 展示为数字（Excel里通常显示 143 而不是 0143），芯片SN内部会按4位补零
                    "Run数": int(run),
                    "芯片SN": self.build_chip_sn(yymmdd_int, sn, int(run)),
                    "测序仪型号": model,
                    "试验结果": "",
                    "备注2": "",
                }
                chips.append(chip)
                # 使用一次后+1
                if sn:
                    run_map[sn] = int(run) + 1
        return chips
