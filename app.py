#!/usr/bin/env python3
"""
mNGS实验排布工具 - Web前端
"""
from flask import Flask, render_template, request, send_file, jsonify, session
import os
import uuid
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
from werkzeug.utils import secure_filename
import tempfile
import shutil

from src.parser import InputParser, RulesParser, ReferenceParser
from src.planner import LibraryPlanner, ChipPlanner
from src.generator import OutputGenerator

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['OUTPUT_FOLDER'] = 'output'

# 确保上传和输出目录存在
Path(app.config['UPLOAD_FOLDER']).mkdir(exist_ok=True)
Path(app.config['OUTPUT_FOLDER']).mkdir(exist_ok=True)

ALLOWED_EXTENSIONS = {'xlsx', 'xls'}


def allowed_file(filename):
    """检查文件扩展名是否允许"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_default_file_path(filename):
    """获取默认文件路径：优先 ref/ 其次 attachments/；若传入包含路径分隔符则按原样解析"""
    p = Path(filename)
    if p.is_absolute() or str(filename).startswith("ref/") or str(filename).startswith("attachments/") or "/" in str(filename):
        if p.exists():
            return str(p)
        return None

    for base in ["ref", "attachments"]:
        default_path = Path(base) / filename
        if default_path.exists():
            return str(default_path)
    return None


def _save_json(path: Path, obj: Any):
    path.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


@app.route('/')
def index():
    """主页"""
    return render_template('index.html')


def save_uploaded_files(request, work_dir):
    """保存上传的文件并返回路径字典"""
    files = {}
    
    input_file = request.files.get('input_file')
    if input_file and input_file.filename and allowed_file(input_file.filename):
        filename = secure_filename(input_file.filename)
        files['input'] = str(work_dir / filename)
        input_file.save(files['input'])
    
    for file_key, default_name in [
        ('rules_file', '规则.xlsx'),
        ('nc_file', 'NC.xlsx'),
        ('pc_file', 'PC.xlsx'),
        ('species_file', '物种列表.xlsx'),
        ('sequencer_file', '测序仪对应关系.xlsx'),
        ('lib_template_file', '文库表模版.xlsx'),
        ('chip_template_file', '芯片表模版.xlsx')
    ]:
        uploaded_file = request.files.get(file_key)
        if uploaded_file and uploaded_file.filename and allowed_file(uploaded_file.filename):
            filename = secure_filename(uploaded_file.filename)
            files[file_key] = str(work_dir / filename)
            uploaded_file.save(files[file_key])
        else:
            default_path = get_default_file_path(default_name)
            if default_path:
                files[file_key] = default_path
    
    return files


@app.route('/api/generate-chips', methods=['POST'])
def generate_chips():
    """第一步：生成芯片表（供用户编辑）"""
    try:
        # 创建临时工作目录
        work_dir = Path(tempfile.mkdtemp())
        session_id = str(uuid.uuid4())
        session['work_dir'] = str(work_dir)
        session['session_id'] = session_id
        
        # 保存上传的文件
        files = save_uploaded_files(request, work_dir)
        
        if 'input' not in files:
            return jsonify({'success': False, 'error': '请上传输入表文件'}), 400
        
        # 解析输入文件
        input_parser = InputParser(files['input'])
        input_data = input_parser.parse()
        meta = input_data.get("meta", {})
        
        # 解析规则文件
        rules = {}
        if 'rules_file' in files and Path(files['rules_file']).exists():
            rules_parser = RulesParser(files['rules_file'])
            rules = rules_parser.parse()
        
        # 解析参考文件
        ref_parser = ReferenceParser(
            nc_file=files.get('nc_file'),
            pc_file=files.get('pc_file'),
            species_file=files.get('species_file'),
            sequencer_file=files.get('sequencer_file')
        )
        species_info = ref_parser.parse_species()
        sequencer_info = ref_parser.parse_sequencer()

        # IMPORTANT: Flask默认session是cookie存储，不能塞大对象（会超过浏览器4KB限制）
        # 所以把输入上下文落盘到 work_dir，仅在session里保存路径。
        # 记录芯片容量（每张芯片最多承载多少“样本单位/接头”）
        try:
            chip_capacity = int(request.form.get("chip_capacity", 96))
        except Exception:
            chip_capacity = 96

        # 把chip_capacity注入meta，供芯片表数量计算使用
        meta["chip_capacity"] = chip_capacity

        # 按输入表meta生成芯片表（RUN等允许用户后续编辑）
        chip_planner = ChipPlanner(rules=rules, sequencer_info=sequencer_info)
        chips = chip_planner.plan_chips_from_input(meta)

        input_ctx = {
            "samples": input_data["samples"],
            "rules": rules,
            "meta": {
                "研究编号": meta.get("研究编号"),
                "研究列表": meta.get("研究列表"),
                "研究说明": meta.get("研究说明"),
                "实验启动时间": meta.get("实验启动时间"),
                "实验时间（天）": meta.get("实验时间（天）"),
                "接头起点": meta.get("接头起点", "A01"),
                "chip_capacity": chip_capacity,
                # PC/NC 的 spike-rpm 范围来自输入表的 F-PC/F-NC 的 Value3
                "F-PC__value3": meta.get("F-PC__value3"),
                "F-NC__value3": meta.get("F-NC__value3"),
            },
            "files": {
                "input": files.get("input"),
                "nc_file": files.get("nc_file"),
                "pc_file": files.get("pc_file"),
                "species_file": files.get("species_file"),
                "sequencer_file": files.get("sequencer_file"),
                "lib_template_file": files.get("lib_template_file"),
                "chip_template_file": files.get("chip_template_file"),
            },
        }
        ctx_path = work_dir / "input_ctx.json"
        _save_json(ctx_path, input_ctx)
        session["input_ctx_path"] = str(ctx_path)
        
        # 将芯片数据转换为可编辑格式
        chip_data = []
        for chip in chips:
            chip_data.append({
                '实验项目': chip.get('实验项目', ''),
                '测序日期': chip.get('测序日期', ''),
                '测序仪SN': chip.get('测序仪SN', ''),
                'Run数': chip.get('Run数', ''),
                '芯片SN': chip.get('芯片SN', ''),
                '测序仪型号': chip.get('测序仪型号', ''),
                '试验结果': chip.get('试验结果', ''),
                '备注2': chip.get('备注2', '')
            })
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'chips': chip_data,
            'stats': {
                'samples': len(input_data['samples']),
                'chips': len(chips),
                'nc_count': 0,
                'pc_count': 0
            }
        })
        
    except Exception as e:
        import traceback
        error_msg = str(e)
        traceback.print_exc()
        return jsonify({'success': False, 'error': error_msg}), 500


@app.route('/api/generate-libraries', methods=['POST'])
def generate_libraries():
    """第二步：根据用户修改的芯片表生成文库表（预览/可编辑），不落盘"""
    try:
        # 获取用户修改后的芯片表数据
        chips_data = request.json.get('chips', [])
        
        if not chips_data:
            return jsonify({'success': False, 'error': '芯片表数据为空'}), 400
        
        # 从session获取之前保存的输入上下文路径（server-side）
        input_ctx_path = session.get("input_ctx_path")
        if not input_ctx_path:
            return jsonify({'success': False, 'error': '会话已过期，请重新开始'}), 400

        input_data = _load_json(Path(input_ctx_path))
        
        work_dir = Path(session.get('work_dir'))
        if not work_dir.exists():
            return jsonify({'success': False, 'error': '工作目录不存在'}), 400
        
        # 重新加载物种信息（避免把大对象塞进session）
        files = input_data.get("files", {})
        ref_parser = ReferenceParser(
            nc_file=files.get("nc_file"),
            pc_file=files.get("pc_file"),
            species_file=files.get("species_file"),
            sequencer_file=files.get("sequencer_file"),
        )
        species_info = ref_parser.parse_species()
        nc_list = ref_parser.parse_nc()
        pc_list = ref_parser.parse_pc()
        rules = input_data.get("rules", {})
        meta = input_data.get("meta", {})

        # 用用户修改后的芯片数据（可覆盖默认值）
        chips: List[Dict[str, Any]] = []
        for chip_data in chips_data:
            # 如果用户改了关键字段但没同步改芯片SN，允许直接用用户填写的芯片SN
            # 若芯片SN为空，则按规则重新生成
            chip_sn = str(chip_data.get("芯片SN", "")).strip()
            if not chip_sn:
                chip_sn = ChipPlanner.build_chip_sn(
                    chip_data.get("测序日期", ""),
                    str(chip_data.get("测序仪SN", "")).strip(),
                    chip_data.get("Run数", ""),
                )
            chips.append(
                {
                    "实验项目": chip_data.get("实验项目", ""),
                    "测序日期": chip_data.get("测序日期", ""),
                    "测序仪SN": chip_data.get("测序仪SN", ""),
                    "Run数": chip_data.get("Run数", ""),
                    "芯片SN": chip_sn,
                    "测序仪型号": chip_data.get("测序仪型号", ""),
                    "试验结果": chip_data.get("试验结果", ""),
                    "备注2": chip_data.get("备注2", ""),
                }
            )

        adapter_start = meta.get("接头起点") or "A01"
        research_id = meta.get("研究编号") or ""
        pc_spike = meta.get("F-PC__value3") or ""
        nc_spike = meta.get("F-NC__value3") or ""
        chip_capacity = int(meta.get("chip_capacity") or 96)

        library_planner = LibraryPlanner(
            rules=rules,
            species_info=species_info,
            adapter_start=str(adapter_start).strip(),
            pc_list=pc_list,
            nc_list=nc_list,
            pc_spike_rpm_range=str(pc_spike).strip(),
            nc_spike_rpm_range=str(nc_spike).strip(),
        )

        # 规划文库：默认每张芯片都跑同一套样本（符合“不同机型/不同天重复测试”的场景）
        libraries = library_planner.plan_libraries(
            samples=input_data["samples"],
            chips=chips,
            research_id=str(research_id).strip(),
            chip_capacity=chip_capacity,
            include_controls_once=False,
            include_controls_per_chip=True,
        )
        
        return jsonify(
            {
                'success': True,
                'stats': {
                    'libraries': len(libraries),
                    'chips': len(chips),
                },
                'chips': chips,        # 返回可能被重算过芯片SN的芯片表
                'libraries': libraries # 返回文库表供前端预览/编辑
            }
        )
        
    except Exception as e:
        import traceback
        error_msg = str(e)
        traceback.print_exc()
        return jsonify({'success': False, 'error': error_msg}), 500


@app.route('/api/generate-files', methods=['POST'])
def generate_files():
    """第三步：用户确认（可编辑后的）文库表后，生成Excel输出文件"""
    try:
        payload = request.json or {}
        libraries = payload.get('libraries', [])
        chips = payload.get('chips', [])

        if not libraries or not chips:
            return jsonify({'success': False, 'error': '缺少芯片表或文库表数据'}), 400

        work_dir = Path(session.get('work_dir'))
        if not work_dir.exists():
            return jsonify({'success': False, 'error': '工作目录不存在'}), 400

        input_ctx_path = session.get("input_ctx_path")
        if not input_ctx_path:
            return jsonify({'success': False, 'error': '会话已过期，请重新开始'}), 400
        input_data = _load_json(Path(input_ctx_path))
        files = input_data.get('files', {})

        output_dir = work_dir / 'output'
        output_dir.mkdir(exist_ok=True)
        generator = OutputGenerator(output_dir=str(output_dir))

        # 生成合并输出
        output_file = generator.generate_combined_output(
            libraries=libraries,
            chips=chips,
            lib_template_file=files.get("lib_template_file"),
            chip_template_file=files.get("chip_template_file"),
        )

        # 生成单独的文库表和芯片表
        lib_template_path = files.get('lib_template_file')
        chip_template_path = files.get('chip_template_file')

        lib_file = generator.generate_library_table(
            libraries=libraries,
            template_file=lib_template_path if lib_template_path and Path(lib_template_path).exists() else None
        )

        chip_file = generator.generate_chip_table(
            chips=chips,
            template_file=chip_template_path if chip_template_path and Path(chip_template_path).exists() else None
        )

        session['output_file'] = output_file
        session['lib_file'] = lib_file
        session['chip_file'] = chip_file

        return jsonify(
            {
                'success': True,
                'stats': {'libraries': len(libraries), 'chips': len(chips)},
                'files': {
                    'combined': os.path.basename(output_file),
                    'library': os.path.basename(lib_file),
                    'chip': os.path.basename(chip_file),
                },
            }
        )
    except Exception as e:
        import traceback
        error_msg = str(e)
        traceback.print_exc()
        return jsonify({'success': False, 'error': error_msg}), 500


@app.route('/api/download/<file_type>')
def download(file_type):
    """下载生成的文件"""
    try:
        if file_type == 'combined':
            file_path = session.get('output_file')
        elif file_type == 'library':
            file_path = session.get('lib_file')
        elif file_type == 'chip':
            file_path = session.get('chip_file')
        else:
            return jsonify({'error': '无效的文件类型'}), 400
        
        if not file_path or not Path(file_path).exists():
            return jsonify({'error': '文件不存在'}), 404
        
        return send_file(
            file_path,
            as_attachment=True,
            download_name=os.path.basename(file_path),
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/cleanup', methods=['POST'])
def cleanup():
    """清理临时文件"""
    try:
        work_dir = session.get('work_dir')
        if work_dir and Path(work_dir).exists():
            shutil.rmtree(work_dir)
        session.clear()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5123)
