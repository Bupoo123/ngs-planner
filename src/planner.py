"""
排布算法核心模块
实现样本到芯片和文库的排布逻辑
"""
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta, date
import re
import random
import math


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
        chip_capacity: int = 96,
        include_controls_once: bool = False,
        include_controls_per_chip: bool = True,
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

        if chip_capacity <= 0:
            raise ValueError(f"芯片容量必须>0，当前: {chip_capacity}")

        # 每个“样本单位”占用一个接头：普通样本、PC、NC
        controls_units = (1 if self.pc_list else 0) + 1  # pc可选，nc必有
        if include_controls_per_chip and chip_capacity <= controls_units:
            raise ValueError(f"芯片容量({chip_capacity})不足以放入PC/NC质控({controls_units})")

        sample_slots = chip_capacity - controls_units if include_controls_per_chip else chip_capacity
        if sample_slots <= 0:
            raise ValueError(f"芯片容量({chip_capacity})不足以放入样本")

        # 每台测序仪“一轮”需要的芯片张数（用于在同一测序仪上重复分配样本）
        chips_per_round = max(1, math.ceil(len(samples) / sample_slots))

        # 每个测序仪当前处于一轮中的第几张芯片（0..chips_per_round-1），达到后回到0进入下一轮（重复）
        pos_by_sn: Dict[str, int] = {}

        # 接头号全局连续：跨芯片不重置
        adapter = self.adapter_start

        # 命名：F-{研究编号}-CN-PC / F-{研究编号}-CN-NC
        rid = (research_id or "").strip()
        pc_name = f"F-{rid}-CN-PC" if rid else "PC"
        nc_name = f"F-{rid}-CN-NC" if rid else "NC"

        for chip in chips:
            chip_sn = str(chip.get("芯片SN", "")).strip() or "UNKNOWN_CHIP_SN"
            seq_sn = str(chip.get("测序仪SN", "")).strip()
            yymmdd = chip.get("测序日期")

            yyyymmdd = self._yymmdd_to_yyyymmdd_str(yymmdd)
            up_time = self._yyyymmdd_to_dot_date(yyyymmdd)
            sn_last3 = self._sn_last3_digits(seq_sn)

            # 当前测序仪本轮第几张芯片：决定该芯片承载哪一段样本
            pos = pos_by_sn.get(seq_sn, 0)
            start = pos * sample_slots
            end = min(start + sample_slots, len(samples))
            assigned_samples = samples[start:end]
            pos_by_sn[seq_sn] = (pos + 1) % chips_per_round

            # 1) 普通样本段
            for sample in assigned_samples:
                sample_id = str(sample.get("sample_id", "")).strip()
                species_list = sample.get("species", []) or []

                # 一个样本只占用一个接头/一个文库编号
                sample_index = adapter
                library_id = f"{sample_id}-{sn_last3}-{sample_index}-{yyyymmdd}"

                # spike-rpm 与样本相关：每个样本单位只生成一次，所有病原体行共享
                # 取样本的 Value3：可能被解析到每个病原体dict里（多病原体时一般相同）；这里取第一个非空即可
                sample_spike_range = ""
                if isinstance(species_list, list):
                    for it in species_list:
                        if isinstance(it, dict) and str(it.get("spike_rpm_range", "")).strip() != "":
                            sample_spike_range = str(it.get("spike_rpm_range", "")).strip()
                            break
                sample_spike_v = self._rand_in_range(self._parse_range(sample_spike_range))

                species_iter = species_list if species_list else [""]
                for species in species_iter:
                    if isinstance(species, dict):
                        species_name = str(species.get("name", "")).strip()
                        rpm_range_s = species.get("rpm_range", "")
                    else:
                        species_name = str(species).strip()
                        rpm_range_s = ""

                    rpm_v = self._rand_in_range(self._parse_range(rpm_range_s))
                    extra = self._lookup_species(species_name)

                    libraries.append(
                        {
                            "芯片": chip_sn,
                            "芯片数据量": self.default_chip_data_amount,
                            "上机时间": up_time,
                            "样本名称": sample_id,
                            "文库编号": library_id,
                            "index": sample_index,
                            "Clean Reads": "",
                            "≥Q20%": "",
                            "Q30": "",
                            "内部对照spike.1RPM值": sample_spike_v if sample_spike_v is not None else "",
                            "物种名称": species_name,
                            "分类": extra.get("分类", ""),
                            "taxid": extra.get("taxid", ""),
                            "RC": "",
                            "RA": "",
                            "rpm": rpm_v if rpm_v is not None else "",
                            "uniq rpm": "",
                            "coverage": "",
                            "abundance": "",
                            "标准": "",
                            "参照背景": "",
                        }
                    )

                adapter = self._next_adapter(adapter)

            # 2) 每张芯片都追加 PC/NC（按你确认）
            if include_controls_per_chip:
                # PC：同一index/文库编号，展开多条病原体
                if self.pc_list:
                    pc_index = adapter
                    pc_lib_id = f"{pc_name}-{pc_index}-{yyyymmdd}"
                    pc_spike_v = self._rand_in_range(self._parse_range(self.pc_spike_rpm_range))
                    for pc in self.pc_list:
                        species_name = str(pc.get("物种名称", "")).strip()
                        extra = self._lookup_species(species_name)
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
                                "内部对照spike.1RPM值": pc_spike_v if pc_spike_v is not None else "",
                                "物种名称": species_name,
                                "分类": pc.get("分类", extra.get("分类", "")),
                                "taxid": pc.get("taxid", extra.get("taxid", "")),
                                "RC": "",
                                "RA": "",
                                "rpm": pc_rpm_v if pc_rpm_v is not None else "",
                                "uniq rpm": "",
                                "coverage": "",
                                "abundance": "",
                                "标准": pc.get("标准", ""),
                                "参照背景": pc.get("参照背景", ""),
                            }
                        )
                    adapter = self._next_adapter(adapter)

                # NC：一条记录
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
                        "内部对照spike.1RPM值": nc_spike_v if nc_spike_v is not None else "",
                        "物种名称": nc_species,
                        "分类": "",
                        "taxid": "",
                        "RC": "",
                        "RA": "",
                        "rpm": "",
                        "uniq rpm": "",
                        "coverage": "",
                        "abundance": "",
                        "标准": "不检出",
                        "参照背景": "",
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
        two_per_day = str(meta.get("是否需要一天两次上机") or "").strip() == "是"
        sessions_per_day = 2 if two_per_day else 1

        # 芯片容量：来自Web/CLI参数（优先），否则用输入表或默认96
        chip_capacity = int(meta.get("chip_capacity") or 96)

        # 总样本单位（含PC/NC）：优先使用输入表显式字段
        total_units = meta.get("样本总数量（含PC/NC）")
        if total_units is None:
            total_units = meta.get("样本数量（含PC/NC）")
        if total_units is None:
            total_units = meta.get("样本数量（含PC/NC）")
        try:
            total_units_int = int(re.sub(r"\D", "", str(total_units)) or "0")
        except Exception:
            total_units_int = 0
        if total_units_int <= 0:
            # 兜底：至少按 54 处理（避免生成0张芯片）
            total_units_int = 54

        # “一轮”需要几张芯片
        chips_per_round = max(1, math.ceil(total_units_int / chip_capacity))

        # 重复次数：优先使用输入表字段（通常等于 上机次数，例如 3天*2次/天=6）
        repeats = meta.get("样本重复测试次数")
        try:
            repeats_int = int(re.sub(r"\D", "", str(repeats)) or "0")
        except Exception:
            repeats_int = 0
        if repeats_int <= 0:
            repeats_int = days * sessions_per_day
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

        # 按“重复次数”生成：每次重复（一次上机）在每台测序仪上跑完整一轮（可能需要多张芯片）
        for rep_idx in range(repeats_int):
            # 将重复次数映射到日期（每sessions_per_day次增加一天）
            day_offset = rep_idx // sessions_per_day
            d = start_date + timedelta(days=day_offset)
            yymmdd_int = self._date_to_yymmdd_int(d)

            for seq in sequencers:
                sn = str(seq.get("sn", "")).strip()
                model = ""
                if sn in self.sequencer_info:
                    model = self.sequencer_info[sn].get("设备型号", "") or ""

                # 一轮需要 chips_per_round 张芯片（每张芯片对应一次run）
                for _ in range(chips_per_round):
                    run = run_map.get(sn, 0)
                    chip = {
                        "实验项目": project,
                        "测序日期": yymmdd_int,
                        "测序仪SN": sn,
                        "Run数": int(run),
                        "芯片SN": self.build_chip_sn(yymmdd_int, sn, int(run)),
                        "测序仪型号": model,
                        "试验结果": "",
                        "备注2": "",
                    }
                    chips.append(chip)
                    if sn:
                        run_map[sn] = int(run) + 1

        return chips
