# 燃料电池 MCP 使用说明

## 能力与范围

交付工具 `opem_simulate_polarization` 直接调用 OPEM 1.4 的 `opem.Static.Amphlett.Static_Analysis`，来源固定在提交 `27d343fb966361a4e6cc99650241f651778fc50f`。它计算给定工况的静态极化扫描，返回结果摘要和独立输出目录中的文件。

这是通用 PEM 氢燃料电池基线。温度、膜水含量是输入；模型没有风机转速、风量、环境 RH、吹扫或热水动态方程。输出不构成实际空冷电堆的校准或实验验证。

## 安装

已测试 Linux x86_64、Python 3.12.14、FastMCP 4.0.3。需要 Python 3.12、Git、PyPI 和 GitHub 网络访问。运行依赖及其传递依赖已精确锁定在 `src/requirements.txt`，OPEM 从固定 Git 提交安装。无需 GPU、外部模型或 API Key。

从完整仓库或解压后的 `opem-mcp` 目录运行以下命令。无需激活虚拟环境：

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r src/requirements.txt
.venv/bin/python -m pip check
```

Windows PowerShell 对应命令：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r src\requirements.txt
.\.venv\Scripts\python.exe -m pip check
```

Windows 依赖条件已解析；当前执行验收覆盖 Linux，未声称完成 Windows 实机验证。

## 不连接 AI，也能直接计算

在运行目录新建 `parameters.json`，复制下面的**官方软件回归案例**：

```json
{
  "temperature_K": 343.15,
  "hydrogen_partial_pressure_atm": 1,
  "oxygen_partial_pressure_atm": 1,
  "active_area_cm2": 50.6,
  "membrane_thickness_cm": 0.0178,
  "membrane_water_content": 23,
  "cell_count": 1,
  "current_start_A": 0,
  "current_stop_A": 75,
  "current_step_A": 0.1,
  "max_current_density_A_cm2": 1.5,
  "electronic_resistance_ohm": 0
}
```

运行：

```bash
.venv/bin/python scripts/run_polarization.py --input parameters.json --output results
```

Windows 将解释器换成 `.\.venv\Scripts\python.exe`。如果使用完整仓库，已经有同一案例 `examples/amphlett-official.json` 可直接作为 `--input`。精简 MCP 运行 ZIP 不包含开发示例；使用上面的参数文件即可。

该案例输出 750 点，电流 0 至 74.9 A，最大整堆功率约 29.3997360503 W。`PO2=1 atm` 是纯氧参数，不能代表常压空气。请为自己的研究建立新的参数文件，保留实测/文献/待辨识参数的来源。

## MCP 服务与客户端连接

直接启动 stdio 服务：

```bash
.venv/bin/python src/opem_mcp.py
```

stdio 服务用于 MCP 客户端通信，终端等待输入属于正常运行。日志在 stderr，stdout 留给协议。

打印适用于当前目录和解释器的连接命令：

```bash
.venv/bin/python scripts/print_mcp_config.py --client codex
.venv/bin/python scripts/print_mcp_config.py --client json
.venv/bin/python scripts/print_mcp_config.py --client toml
```

`codex` 输出可执行的 `codex mcp add fuelcell -- <python> <server>` 命令；`json` 输出 `mcpServers` 配置；`toml` 输出 Codex 的 `[mcp_servers.fuelcell]` 片段。路径由脚本生成，包含空格时会正确引用。只执行自己需要的一种配置方式，之后重连客户端并检查 `opem_simulate_polarization` 是否出现。

本次没有修改你本机的客户端配置。当前 FastMCP 版本不提供 `fastmcp install codex`，请使用以上已核对的 Codex CLI 语法。

## 参数与单位

除 `electronic_resistance_ohm=0` 和可选 `output_dir` 外，科学参数需要明确提供。模型接口不填入电堆的隐藏示例参数。

| 参数 | 含义 |
| --- | --- |
| `temperature_K` | 给定工作温度，K |
| `hydrogen_partial_pressure_atm` | 氢气分压，atm，须大于 0 |
| `oxygen_partial_pressure_atm` | 氧气分压，atm，须大于 0；不是空气总压 |
| `active_area_cm2` | 单片活性面积，cm² |
| `membrane_thickness_cm` | 膜厚，cm |
| `membrane_water_content` | 膜水含量 lambda，无量纲，按源模型域限定 14 至 23 |
| `cell_count` | 串联单片数，正整数 |
| `current_start_A` | 扫描起点，A，允许 0 |
| `current_stop_A` | 扫描终点，A，不包含该端点；源模型还会限制在 `A × JMax` 以下 |
| `current_step_A` | 正电流步长，A；须能在源程序的舍入精度下推进 |
| `max_current_density_A_cm2` | 源模型的极限电流密度，A/cm² |
| `electronic_resistance_ohm` | 源模型额外电子电阻，Ω，原默认 0 |
| `output_dir` | 可选输出基目录；每次调用建立新的子目录 |

封装会拒绝 NaN/Infinity、无效扫描和源模型不支持的输入，避免源程序静默修正输入或不能推进。为保护一次交互调用的资源，扫描限制在 10,000 点以内。至少需要两个有效点以支持原程序的线性拟合。错误通过 MCP tool error 返回。

## 结果文件与解释

每次调用返回绝对路径的 `artifacts`。文件包括原始参数、来源记录、完整原模型结果 JSON、原始日志，以及 OPEM 原生的 CSV、HTML 图表和 `.opem` 报告。协议返回摘要，完整数组留在文件里，便于后续绘图或统计。

原模型结果中的 `I` 是电流 A；`V` 和 `P` 是整堆电压 V、功率 W；`Eta_Active`、`Eta_Ohmic`、`Eta_Conc` 是单片损失 V。`EFF` 保留上游效率约定。`Ph` 保留上游基于固定 `Eth=1.23 V` 的计算结果；不要将它当作已经验证的散热负荷或风机选型依据。整堆电功率没有扣除风机和其他辅助设备功耗。

原生 HTML 图表依赖上游远程 JavaScript；网络不可用时可读取本地 CSV 和 JSON。原始数组和文件完整保留，图表只是这些结果的展示。

## 验证与后续扩展

转换的验证范围是选定 Amphlett 静态工具：原始官方输入、改变温度和氧分压，以及独立验证记录覆盖的参数、错误输入、重复调用和文件隔离。参照来自固定源代码的直接运行，不能据此推断其他 OPEM 模型或整个研究论文已经被复现。

完整工作区的 `reports/` 保留逐阶段证据、独立验证和 stdio / 新环境 / 解压迁移验收。精简运行 ZIP 保留服务、薄封装、依赖、CLI 及许可；开发证据在完整工作区中查看。

下一篇空冷论文转换入口和测量字段模板在完整仓库的 `research/`。实现新的风量/热水/控制工具时，先找到对应代码和验证数据，再按 Paper2Agent 流程建立参照与独立验证。

## 引用

- [Paper2Agent](https://github.com/jmiao24/Paper2Agent)：Miao et al.，Nature 2026，DOI `10.1038/s41586-026-11044-y`。
- [OPEM](https://github.com/ECSIM/opem)：Haghighi et al.，JOSS 2018，DOI `10.21105/joss.00676`。

参见 `THIRD_PARTY_NOTICES.md` 与 `third_party/OPEM-LICENSE`。基于 Amphlett 模型发表研究时，也应引用其原模型文献。
