"""Local, non-writing research workbench. Run: streamlit run app.py."""

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
LOCAL = ROOT / ".workbench"
LOCAL.mkdir(exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(LOCAL / "matplotlib"))
sys.path.insert(0, str(ROOT / "src"))
from research_core import calibration, data, design, evidence
from research_core.common import export_run, input_info, load_table, read_json, write_json


st.set_page_config(page_title="PEMFC 研究工作台", page_icon="🔬", layout="wide")
st.markdown("""<style>
.stApp {background:#f7f8f5} .block-container {padding-top:2.2rem;max-width:1280px}
h1,h2,h3 {letter-spacing:-.025em;color:#173b3f} [data-testid=stSidebar]{background:#eaf0ed}
div.stButton>button[kind=primary]{background:#1a7377;border-color:#1a7377}
[data-testid=stMetric]{background:white;padding:1rem;border:1px solid #dce6df;border-radius:12px}
</style>""", unsafe_allow_html=True)
EXAMPLES = ROOT / "examples" / "workbench"
TODAY_YEAR = datetime.now(ZoneInfo("Asia/Shanghai")).year
PAGES = ["开始", "实验数据与对比", "模型校准", "敏感性分析", "实验规划", "文献与专利证据", "开源方法雷达"]


def navigate(page):
    st.session_state["research_page"] = page


def stash(upload):
    raw = upload.getvalue()
    if len(raw) > 25 * 1024 * 1024:
        raise ValueError("当前支持 25 MiB 以内的表格。")
    name = re.sub(r"[^\w.\-]", "_", Path(upload.name).name)
    path = LOCAL / (hashlib.sha256(raw).hexdigest()[:16] + "-" + name)
    if not path.exists():
        path.write_bytes(raw)
    return path


def config_file(name, value):
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True).encode()
    path = LOCAL / (name + "-" + hashlib.sha256(payload).hexdigest()[:16] + ".json")
    if not path.exists():
        write_json(path, value)
    return path


def operation(key, function, *args, **kwargs):
    try:
        with st.spinner("正在计算并记录来源…"):
            st.session_state[key] = function(*args, **kwargs)
    except Exception as exc:
        st.error(f"未完成：{exc}")


def show_result(key):
    result = st.session_state.get(key)
    if not result:
        return
    st.success("上次已完成的运行 · 修改输入后需重新运行；结果按该次 inputs.json 记录")
    summary = result["summary"]
    kind = summary.get("data_kind")
    if kind:
        st.caption("该次结果的数据来源声明：" + ("合成软件验证，非实验测量" if "SYNTHETIC" in str(kind).upper() else str(kind)))
    metrics = []
    if "row_count" in summary:
        metrics += [("有效表格行数", summary["row_count"]), ("最大已观测整堆功率 / W", summary.get("max_observed_gross_power_W"))]
        if summary.get("max_observed_net_power_W") is not None:
            metrics.append(("已声明辅机边界下最大净功率 / W", summary["max_observed_net_power_W"]))
    elif "mean_difference" in summary:
        metrics += [("每组真实重复数", f"{summary['n_replicates_a']} / {summary['n_replicates_b']}"), ("B − A / 原指标单位", summary["mean_difference"])]
        interval = summary["inference"].get("mean_difference_ci")
        metrics.append(("95% 均值差区间", f"[{interval[0]:.4g}, {interval[1]:.4g}]" if interval else "推断退化，未给区间"))
    elif "train_metrics" in summary:
        metrics += [("训练误差 RMSE / V", summary["train_metrics"]["rmse_V"]), ("留出误差 RMSE / V", summary["holdout_metrics"]["rmse_V"]), ("拟合参数数", len(summary["fitted_parameters"]))]
    else:
        for name, label in [("model_evaluations", "原模型计算次数"), ("planned_count", "计划试验数"), ("candidate_count", "待测候选数"), ("observed_feasible_count", "已测满足约束数"), ("record_count", "文献记录数"), ("query_count", "待查证技术特征数")]:
            if name in summary:
                metrics.append((label, summary[name]))
    if metrics:
        for column, (label, value) in zip(st.columns(len(metrics)), metrics):
            column.metric(label, f"{value:.4g}" if isinstance(value, (int, float)) else str(value))
    with st.expander("完整数值、来源与方法边界", expanded=False):
        st.json(result["summary"])
        for note in result.get("warnings", []):
            st.caption(note)
    images = [item for item in result["artifacts"] if item["path"].endswith(".png")]
    for item in images:
        st.image(item["path"], caption=item["description"], width="stretch")
    tables = [item for item in result["artifacts"] if item["path"].endswith(".csv")]
    if tables:
        selected = st.selectbox("查看数据表", tables, format_func=lambda item: item["description"], key=key + "-table")
        try:
            table = pd.read_csv(selected["path"]).head(100)
            link_columns = {name: st.column_config.LinkColumn(name) for name in ("source_url", "google_patents_url", "espacenet_url") if name in table}
            st.dataframe(table, width="stretch", column_config=link_columns)
        except pd.errors.EmptyDataError:
            st.info("本次没有匹配记录；原始响应已保存在证据包中。")
        st.download_button("下载完整 CSV", Path(selected["path"]).read_bytes(), file_name=Path(selected["path"]).name, key=key + "-csv")
    bundle = export_run(result["run_dir"])
    st.download_button("下载研究证据包 ZIP", bundle.read_bytes(), file_name=Path(result["run_dir"]).name + ".zip", mime="application/zip", key=key + "-bundle")
    st.caption("包含结果、PNG/SVG、输入记录、方法与版本、文件哈希。可能包含你上传的数据派生值，保存在本机。")


def editor(label, filename, key):
    return st.text_area(label, (EXAMPLES / filename).read_text(encoding="utf-8"), height=250, key=key)


with st.sidebar:
    st.markdown("### 🔬 PEMFC Research Lab")
    st.caption("实验 · 模型 · 证据")
    page = st.radio("研究流程", PAGES, key="research_page")
    source = st.radio("数据来源", ["合成验证案例", "我的实验文件"])
    demo = source == "合成验证案例"
    uploaded = None if demo else st.file_uploader("实验 CSV / TSV / XLSX", type=["csv", "tsv", "xlsx"])
    st.divider()
    st.caption("本地计算，无需 LLM API Key。联网文献搜索只发送你填写的检索词。")
    st.caption("论文与专利写作由你的现有工具完成。")

context = (source, hashlib.sha256(uploaded.getvalue()).hexdigest() if uploaded else None)
if st.session_state.get("input_context") != context:
    for key in list(st.session_state):
        if key.endswith("-result"):
            del st.session_state[key]
    st.session_state["input_context"] = context

st.caption("RESEARCH PEMFC / EVIDENCE BEFORE CLAIMS")
st.title(page if page != "开始" else "把研究问题变成可检验的证据")
if demo:
    st.info("当前是合成软件验证案例，不是实验测量，也不是已验证的空冷电堆模型。上传自己的数据后，结果仍需结合实验设计与模型适用范围解释。")


def current_table(for_calibration=False):
    if demo:
        return EXAMPLES / ("polarization-synthetic.csv" if for_calibration else "measurements-synthetic.csv")
    if uploaded is None:
        st.info("请在左侧上传实验表格。原始文件会保留，字段映射生成独立副本。")
        return None
    raw_path = stash(uploaded)
    sheet = 0
    if raw_path.suffix.lower() == ".xlsx":
        sheet = st.selectbox("工作表", pd.ExcelFile(raw_path, engine="openpyxl").sheet_names)
    frame = load_table(raw_path, sheet_name=sheet, string_columns=["replicate_id", "condition", "run_id", "sample_id"])
    st.caption(f"原文件：{uploaded.name} · {len(frame)} 行 · 请选择字段和单位；没有自动删行或补值。")
    columns = frame.columns.tolist()
    mapping = {}
    with st.expander("字段映射（原始文件只读）", expanded=not {"current_A", "stack_voltage_V"} <= set(columns)):
        for canonical, description in [("current_A", "电流 A"), ("stack_voltage_V", "整堆电压 V"),
                                       ("fan_power_W", "已测风机功耗 W"), ("other_aux_power_W", "已测其他辅机功耗 W"),
                                       ("condition", "工况标签"), ("replicate_id", "真实实验重复编号"),
                                       ("stack_temperature_C", "实测堆温 °C")]:
            options = ["不映射"] + columns
            selected = st.selectbox(description, options, index=options.index(canonical) if canonical in options else 0, key="map-" + canonical)
            if selected != "不映射":
                if selected in mapping:
                    st.error("同一原始列不能映射到两个不同物理量。")
                    return None
                mapping[selected] = canonical
    renamed = frame.rename(columns=mapping)
    if renamed.columns.duplicated().any():
        st.error("映射后有重复列名，请调整映射。")
        return None
    if not {"current_A", "stack_voltage_V"} <= set(renamed):
        st.info("至少要提供电流 A 和整堆电压 V；电流密度、单片电压请先按已知面积／片数明确换算。")
        return None
    identity = hashlib.sha256(json.dumps({"input": input_info(raw_path), "mapping": mapping, "sheet": sheet}, sort_keys=True).encode()).hexdigest()[:16]
    path = LOCAL / ("normalized-" + identity + ".csv")
    if not path.exists():
        renamed.to_csv(path, index=False)
        write_json(path.with_suffix(".provenance.json"), {"raw_source": input_info(raw_path), "selected_sheet": sheet, "column_mapping": mapping})
    return path


if page == "开始":
    st.write("从同负载下的实测差异出发，用模型校准和敏感性分析缩小问题，再规划下一轮试验。每一步保留输入、方法、结果和来源。")
    columns = st.columns(3)
    for column, title, text in zip(columns, ["01 / 可信数据", "02 / 可复现模型", "03 / 下一轮试验"],
                                   ["功率边界、真实重复、同负载对比和效应区间。", "原始 OPEM 函数、有界参数校准和完整组留出。", "LHS 初始设计、Sobol 筛查和历史反馈的约束 TPE。"]):
        with column:
            st.subheader(title)
            st.write(text)
    a, b = st.columns(2)
    a.button("开始分析实验数据 →", type="primary", on_click=navigate, args=("实验数据与对比",))
    b.button("查看模型校准 →", on_click=navigate, args=("模型校准",))
    st.subheader("交给你的写作工具的，是研究证据")
    st.write("导出原单位效应与区间、训练／留出误差、完整预测、参数诊断、采样设计、待测候选、DOI 记录、PNG/SVG 和 JSON 复现记录。这里不生成论文或专利文本。")
    st.caption("空冷热水动态尚未实现。堆温和膜水含量是已给定／实测输入，不能据此宣称已预测风机散热或证明机理。")

elif page == "实验数据与对比":
    path = current_table()
    if path:
        frame = load_table(path, string_columns=["condition", "replicate_id"])
        with st.expander(f"预览输入数据：{len(frame)} 行（显示前 30 行）", expanded=False):
            st.dataframe(frame.head(30), width="stretch")
        st.caption("仅有风机功耗时输出“电堆功率减已测风机功耗”；其他辅机未知时不会补 0 并称为系统净功率。")
        if st.button("检查数据并计算派生量", type="primary"):
            operation("analysis-result", data.analyze_measurements, str(path))
        show_result("analysis-result")
        st.subheader("同负载、真实重复的条件比较")
        if {"condition", "replicate_id"} <= set(frame):
            conditions = frame["condition"].dropna().astype(str).unique().tolist()
            derived, _, _, _ = data.derive_measurements(frame)
            numeric = derived.select_dtypes(include="number").columns.tolist()
            if len(conditions) >= 2:
                a, b, c = st.columns(3)
                group_a = a.selectbox("A / 基准", conditions)
                group_b = b.selectbox("B / 候选", conditions, index=1)
                metric = c.selectbox("预先指定比较指标", numeric, index=numeric.index("net_power_W") if "net_power_W" in numeric else numeric.index("gross_power_W"))
                a, b, c = st.columns(3)
                design_type = a.selectbox("实验设计", ["paired", "independent"], format_func=lambda x: "按重复编号配对" if x == "paired" else "独立重复 / Welch")
                target = b.number_input("目标电流 A", min_value=0., value=float(frame.current_A.median()))
                tolerance = c.number_input("允许电流偏差 A", min_value=0., value=0.1)
                st.caption("先在每个真实重复内聚合时间采样，再比较 B − A。只有单次实验的多行采样，不能当作多次独立重复。")
                if st.button("计算效应和 95% 区间"):
                    operation("comparison-result", data.compare_conditions, str(path), metric, group_a, group_b, design_type, target, tolerance)
                show_result("comparison-result")
        else:
            st.info("条件比较需要 condition 和真实 replicate_id；可在字段映射中指定。")

elif page == "模型校准":
    path = current_table(for_calibration=True)
    st.write("用原始 Amphlett 点函数和 SciPy 优化器拟合 R／lambda。每行实测温度可作为模型输入；温度不是模型预测。")
    text = editor("校准配置：请填写实际电堆参数、拟合边界和留出规则", "calibration.json", "calibration-config")
    st.caption("只有一条曲线时，留出点只能检查插值；有 run_id／replicate_id 时默认整组留出，不能跨训练与验证集。")
    if path and st.button("校准并验证留出数据", type="primary"):
        try:
            conf = json.loads(text)
            operation("calibration-result", calibration.calibrate_amphlett, str(path), str(config_file("calibration", conf)))
        except ValueError as exc:
            st.error(str(exc))
    show_result("calibration-result")

elif page == "敏感性分析":
    st.write("计算给定原模型及独立均匀参数范围下，哪些参数影响固定电流点的电压。结果是模型条件下的敏感性，不是实验因果效应。")
    parameters = editor("模型参数（可粘贴上次校准导出的 parameters-fitted.json）", "model-parameters.json", "sensitivity-parameters")
    bounds = editor("待分析参数的范围与单位", "sensitivity-bounds.json", "sensitivity-bounds")
    a, b = st.columns(2)
    current = a.number_input("固定电流 A", min_value=0.01, value=40.)
    n_base = b.select_slider("Sobol 基础样本数", options=[32, 64, 128, 256, 512, 1024], value=128)
    if st.button("运行模型敏感性分析", type="primary"):
        try:
            operation("sensitivity-result", design.model_sensitivity, str(config_file("model", json.loads(parameters))), str(config_file("sensitivity", json.loads(bounds))), current, n_base)
        except ValueError as exc:
            st.error(str(exc))
    show_result("sensitivity-result")

elif page == "实验规划":
    mode = st.radio("当前阶段", ["初始试验 / LHS", "已有历史 / 下一轮推荐"], horizontal=True)
    text = editor("可控制输入的边界和单位（示例范围不是硬件允许工况）", "experiment-bounds.json", "experiment-bounds")
    if mode == "初始试验 / LHS":
        a, b = st.columns(2)
        count = a.number_input("筛查点数", min_value=2, max_value=256, value=12)
        centers = b.number_input("中心点重复次数", min_value=0, max_value=20, value=3)
        if st.button("生成待测实验表", type="primary"):
            try:
                operation("design-result", design.generate_design, str(config_file("design", json.loads(text))), count, centers)
            except ValueError as exc:
                st.error(str(exc))
        show_result("design-result")
    else:
        history_upload = None if demo else st.file_uploader("已完成试验历史表（每个 trial_id 一行）", type=["csv", "tsv", "xlsx"], key="history-upload")
        history_path = EXAMPLES / "history-synthetic.csv" if demo else stash(history_upload) if history_upload else None
        st.caption("历史每行需包含 trial_id、各输入因素、已测目标和已测约束。不满足约束的测量也应保留。")
        a, b = st.columns(2)
        objective = a.text_input("要最大化的已测指标列", "net_power_W")
        constraint = b.text_input("约束的已测结果列", "stack_temperature_C")
        a, b = st.columns(2)
        upper = a.number_input("结果约束上限（单位与该列一致；请填写实际研究边界）", value=55.)
        count = b.number_input("下一轮候选数", min_value=1, max_value=16, value=3)
        if history_path and st.button("推荐下一轮待测候选", type="primary"):
            try:
                operation("recommendation-result", design.suggest_experiments, str(history_path), str(config_file("optuna-bounds", json.loads(text))), objective, constraint, upper, count)
            except ValueError as exc:
                st.error(str(exc))
        st.caption("候选满足输入边界；温度等输出约束仍需实测验证。少于 10 条完成记录时会明确标为随机起始阶段。")
        show_result("recommendation-result")

elif page == "文献与专利证据":
    st.subheader("公开文献元数据与可用摘要")
    query = st.text_input("检索词（发送给 Crossref）", "open cathode air cooled PEM fuel cell thermal water management")
    a, b, c = st.columns(3)
    year_from = a.number_input("起始年份", min_value=1900, max_value=TODAY_YEAR, value=2018)
    year_to = b.number_input("截止年份", min_value=1900, max_value=TODAY_YEAR, value=TODAY_YEAR)
    limit = c.number_input("记录上限", min_value=1, max_value=50, value=15)
    if st.button("检索并保存 DOI 证据", type="primary"):
        operation("literature-result", evidence.search_literature, query, limit, year_from, year_to)
    st.caption("记录会区分 metadata 与 abstract；没有阅读全文的论文不会被标为“已验证全文”。")
    show_result("literature-result")
    st.subheader("技术特征与已有专利的查证表")
    topic = st.text_input("研究主题", "air cooled PEM fuel cell")
    features = st.text_area("逐项技术特征（每行一个）", "fan control net power\nmembrane water thermal management")
    if st.button("生成专利检索式与查证表"):
        operation("patent-plan-result", evidence.prior_art_plan, topic, [v.strip() for v in features.splitlines() if v.strip()])
    st.caption("此步骤生成检索链接和待查证矩阵，尚未实际检索专利或判断新颖性。请逐项阅读原始专利并记录差异和待验证效果。")
    show_result("patent-plan-result")

elif page == "开源方法雷达":
    st.write("按实时 Star、官方周榜、许可、维护状态和方法适配性筛选。只有周榜快照中实际出现的项目才显示周增量。")
    path = ROOT / "reports" / "research-radar"
    if st.button("刷新公开项目与官方周榜"):
        try:
            with st.spinner("正在请求 GitHub 公开数据…"):
                refresh = subprocess.run([sys.executable, str(ROOT / "scripts/refresh_research_radar.py"), "--output", str(path)], capture_output=True, text=True, timeout=100, check=True)
                st.json(json.loads(refresh.stdout))
        except Exception as exc:
            st.error(f"本次刷新未完成：{exc}")
    metadata = read_json(path / "github-metadata.json")
    weekly = read_json(path / "weekly-trending.json")
    week_map = {row["repository"].lower(): row for row in weekly.get("repositories", [])}
    rows = []
    seen = set()
    for record in metadata["repositories"]:
        name = record.get("full_name")
        if not name or name in seen:
            continue
        seen.add(name)
        week = week_map.get(name.lower(), {})
        rows.append({"项目": name, "总 Star": record.get("stargazers_count"), "周榜顺位": week.get("rank"), "周增 Star": week.get("weekly_stars"),
                     "许可": record.get("license") or "API 未识别", "最近推送": record.get("pushed_at"), "链接": record.get("html_url")})
    fetched = datetime.fromisoformat(metadata["fetched_at_utc"]).astimezone(ZoneInfo("Asia/Shanghai"))
    st.caption("快照抓取时间：" + fetched.strftime("%Y-%m-%d %H:%M（北京时间）"))
    if rows:
        st.dataframe(pd.DataFrame(rows).sort_values("总 Star", ascending=False), width="stretch", column_config={"链接": st.column_config.LinkColumn("项目")}, hide_index=True)
    else:
        st.warning("本次没有获得项目元数据。请查看刷新诊断或稍后重试；已有调研依据仍在下方链接的报告中。")
    st.subheader("本版采用方式")
    st.write("实际调用：SciPy（统计、校准、LHS）、SALib（Sobol）、Optuna 5（约束 ask/tell）、Streamlit（本地界面）。设计借鉴：科学分析 Skill 的实验单位与假设检查、autoresearch 的固定评估与记录、MLflow/DVC 的可追溯性、Auto Ontology 的来源和数据语义。")
    st.caption("完整筛选依据与未采用项目见 docs/github-research-2026-11-14.md。本版没有导入写作模块。")
