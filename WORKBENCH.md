# 非写作科研工作台 v0.2

本版面向氢 PEMFC、空冷／开放阴极燃料电池的**实验数据与可复现计算**。支持数据检查、真实重复比较、模型校准、敏感性、试验规划、文献元数据和已有技术查证。导出的 CSV、PNG/SVG、JSON 与输入哈希可交给你已有的写作工具。

## 安装与打开界面

需要 Python 3.12、Git。科学计算在本机运行，无需 GPU 或 LLM API Key；安装依赖、文献检索和开源项目刷新需要网络。锁定依赖是 `requirements-research.txt`，与原始单模型版本的依赖分开。

Windows PowerShell：

```powershell
git clone https://github.com/xiaoguai53/research-pemfc.git
cd research-pemfc
py -3.12 -m venv research-env
.\research-env\Scripts\python.exe -m pip install -r requirements-research.txt
.\research-env\Scripts\python.exe -m streamlit run app.py
```

Linux：

```bash
python3.12 -m venv research-env
research-env/bin/python -m pip install -r requirements-research.txt
research-env/bin/python -m streamlit run app.py
```

打开终端显示的本机地址，默认 [http://127.0.0.1:8501](http://127.0.0.1:8501)。源码在 Linux/Python 3.12 验证；Windows 命令按该平台路径语法提供，未宣称完成 Windows 实机验收。

默认显示合成验证案例。切换左侧“我的实验文件”，上传 CSV、TSV 或 XLSX；支持选定 Excel 工作表与明确的字段映射。原文件不修改，也不自动删离群点或补缺失值。支持 25 MiB、100,000 行以内的表格。

## 推荐的第一次研究流程

1. **确定一个可测的问题。** 例如“相同电流与相同外部条件下，候选风机策略是否提高扣除已测辅机后的输出功率？”预先定义基准、候选、真实重复单位、主要指标和可控制边界。
2. **实验数据与对比。** 上传自己的数据，先检查功率边界和缺失，再在同负载下比较真实重复。查看原单位效应和 95% 区间，同时保留阴性结果。
3. **模型校准。** 输入电堆已知参数，选择 R／lambda 的拟合范围。优先按完整 run/replicate 留出验证，检查误差、残差、参数边界与可辨识性。
4. **敏感性。** 使用校准输出的 `parameters-fitted.json`，为真正参与模型计算的参数声明范围，比较模型条件下的敏感度。不能把不规则实测 CSV 直接当作 Sobol 设计。
5. **实验规划。** 初始阶段用 LHS 与中心点重复；已有独立试验历史后，用约束 TPE 推荐下一批候选。完成真实测量后再更新历史，而不是把推荐当结果。
6. **已有工作查证。** 检索带 DOI 的元数据／可用摘要，按技术特征生成专利检索链接与查证表。对重要技术差异阅读原始文件，并设计区分竞争解释的试验。
7. **导出证据。** 每次运行都可下载 ZIP，内含完整表格、图、参数、分组、数据来源、方法版本和文件哈希；不生成论文、专利交底书或投稿文本。

## 数据字段与推断单位

最低字段为 `current_A`（A）、`stack_voltage_V`（整堆 V）。可映射自己的列名。电流密度和单片电压需要已知面积／串联片数才能转换，不能静默猜测。

| 字段 | 含义 |
| --- | --- |
| `fan_power_W` | 已测风机耗电，不用 PWM 或转速代替 |
| `other_aux_power_W` | 已测或明确声明的其他辅机耗电；未知时留空 |
| `condition` | 实际基准／候选工况标签 |
| `replicate_id` | 真实独立实验或配对单位，不是时间采样行号 |
| `run_id` | 模型训练与留出时可用的完整运行组 |
| `stack_temperature_C` / `_K` | 每行的实测温度，单位由字段或配置明确声明 |
| `cell_count`、`active_area_cm2` | 片数与面积，存在时会核对，不当作示例默认 |
| `data_kind` | 数据来源声明；所有内置案例明确标为合成验证 |

功率处理分三种：只有 I/V 得到整堆电功率；再有风机功耗得到“整堆功率减已测风机功耗”；再明确其他辅机耗电，才输出该边界下的 `net_power_W`。缺失值不补成 0。

比较前先按工况和真实重复编号聚合时间行。配对检验按 ID 对齐；独立设计明确使用 Welch。不能用连续采样行扩大样本量。零方差等退化情况保留效应，明确不输出虚构的 p 值或置信区间。独立性、稳态与混杂因素需要实验设计支持，数值检验不能替你建立这些条件。

## 校准配置

样例见 `examples/workbench/calibration.json`。用自己的 `base_parameters` 替换温度 K、氢／氧气分压 atm、面积 cm²、膜厚 cm、片数、极限电流密度等已知值；氧分压不等于空气总压。官方纯氧示例 `PO2=1 atm` 不是常压空气条件。

只拟合原生电子电阻与膜水含量 lambda，后者按源模型域限定 14–23。校准是本项目新增的 **SciPy 优化＋原始 OPEM 函数组合**，不声称 OPEM 原论文已经提供了该校准方法。

- 有 `run_id`／`replicate_id` 时默认完整组留出，也可在 `group_column` 明确指定。
- `split_column` 可指定在拟合前确定的 `train`／`holdout` 标签。没有该列时，移除这项配置或设为 `null`，不要修改验证响应来选择划分。
- 只有一条曲线的点留出是插值检查，不是跨实验验证。
- 温度列可逐行输入；没有测温列时，只能假定显式给定的固定温度。它不是求解出的空冷堆温。
- 输出原尺度／列归一化 Jacobian 条件诊断、秩与触界标记。低误差不等于参数被唯一辨识，也不会凭残差自动制造物理参数置信区间。

## 下一轮实验的历史格式

示例 `history-synthetic.csv` 只检查软件管线，其目标和温度来自明确的非物理玩具函数；不是电堆性能数据。

自己的历史每个已完成独立试验一行，包含唯一 `trial_id`、范围 JSON 的全部输入变量、已测目标（如 `net_power_W`）及已测约束（如 `stack_temperature_C`）。先按真实试验聚合，不要直接把时间采样行输入优化器。不满足约束的测量保留，以便学习边界。

Optuna 5 使用原生 `Trial.set_constraint`，约束值 ≤0 表示该次测量满足上限。少于 10 条完成记录时明确标为随机起始阶段。推荐只包含输入和“待测”状态，没有编造的功率／温度，也不能保证未测候选满足结果约束。输入范围由研究者根据实际系统声明。

## 命令行与 MCP

不打开界面也能运行完整的离线合成验证流程：

```bash
research-env/bin/python scripts/run_research.py demo --output results/demo
```

单项操作：

```bash
research-env/bin/python scripts/run_research.py analyze --input my_measurements.csv
research-env/bin/python scripts/run_research.py compare --input my_measurements.csv --metric net_power_W --baseline baseline --candidate candidate --design paired --current 20
research-env/bin/python scripts/run_research.py calibrate --input my_polarization.csv --config my_calibration.json
research-env/bin/python scripts/run_research.py design --bounds my_bounds.json --samples 12 --centers 3
research-env/bin/python scripts/run_research.py search --query "open cathode fuel cell thermal water management" --limit 15
research-env/bin/python scripts/print_research_mcp_config.py --client codex
```

Windows 使用 `research-env\Scripts\python.exe`。最后一条只打印本机连接命令，也支持 `--client json` / `toml`；执行打印的命令后即可把 `src/research_mcp.py` 连接到自己的客户端。包含原始模型和八项新工具，共九项。这里不会改动你已有的写作客户端配置。

原始单模型版本仍保留在 `src/opem_mcp.py`，安装说明是 `USAGE.md`，旧依赖与已验收的 `dist/opem-mcp.zip` 不被覆盖。

## 开源项目与周榜

界面“开源方法雷达”读取有时间戳的 GitHub API 和官方周榜快照；可手动刷新，或运行：

```bash
research-env/bin/python scripts/refresh_research_radar.py
```

`GH_TOKEN` / `GITHUB_TOKEN` 可通过本机环境提供来提高 GitHub API 限额，未提供时使用公开请求；不需要在聊天中提供密钥。周增 Star 只来自实际周榜字段，未上榜项目留空。项目筛选与具体采用方式见 `docs/github-research-2026-11-14.md`。

## 范围与证据

本版本能产出可复核的数据证据和下一轮试验计划；真实效果依赖你自己的实验、边界条件与验证。尚未实现空冷热水动态、风机温升预测或 CFD，也不自动认定机理、专利新颖性或最终科研结论。专利工具当前是检索式／链接与查证矩阵，`live_patent_search_performed=false`；不是已搜索的专利库。

原 v0.1 的阶段报告仍对应原始单模型版本。新工作台的实现、独立复核、界面、stdio、全新安装与迁移验收统一记录在 `reports/workbench-v2/`，不刷新旧报告的哈希来假装验证过新功能。
