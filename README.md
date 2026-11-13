# Research PEMFC：氢燃料电池与空冷燃料电池 Paper2Agent

将论文方法整理为可追溯、可运行、能被编程智能体调用的研究工具。

这个首版已迁移 **OPEM Amphlett 静态 PEMFC 模型**，用于计算极化曲线、整堆功率、效率和电压损失，并保存原始结果、CSV 和 HTML 图表。研究方向配置、数据字段模板和后续论文转换提示词也已准备好。

**空冷研究的边界：** 当前工具给定温度和膜水含量，不求解风量耦合的热水动态，也不模拟风机功耗、吹扫或三维流场。它是研究基线；空冷专用模型的下一步路线见 [研究路线](docs/research-roadmap.zh-CN.md)。

## 先运行一次

需要 Python 3.12、Git 和可访问 PyPI/GitHub 的网络。基础计算不需要 GPU，也不需要 LLM API Key。

先获取项目：

```bash
git clone https://github.com/xiaoguai53/research-pemfc.git
cd research-pemfc
```

Linux/macOS：

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r src/requirements.txt
.venv/bin/python scripts/run_polarization.py --input examples/amphlett-official.json --output results
```

Windows PowerShell：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r src\requirements.txt
.\.venv\Scripts\python.exe scripts\run_polarization.py --input examples\amphlett-official.json --output results
```

命令通过 MCP 调用模型，输出摘要与新建结果目录；完整数组保存在 `native-result.json`。官方案例应有 750 个电流点，最大整堆功率约 29.399736 W。**这是官方单片纯氧参数的回归案例，不是你的空冷电堆预测。**

实际验证环境为 Linux/Python 3.12；Windows 命令按路径语法提供，尚未在 Windows 实机验证。

## 连接 Codex / 其他 MCP 客户端

先用刚安装的解释器打印本机路径：

```bash
.venv/bin/python scripts/print_mcp_config.py --client codex
```

Windows 用 `.\.venv\Scripts\python.exe`。运行打印出来的 `codex mcp add ...` 命令即可注册。脚本也支持 `--client json` 和 `--client toml`，只打印配置，不修改客户端设置。

连接后可以说：

> 使用 fuelcell 的 opem_simulate_polarization 工具。先按仓库官方示例验证环境，再用我给出的电堆参数计算极化曲线，说明单位、模型来源和空冷适用性限制。

参数表、安装包使用方法和完整启动步骤见 [USAGE.md](USAGE.md)。

## 用于自己的研究

1. 编辑 [research/project.json](research/project.json)，填写电堆结构、面积、单片数和下一篇论文。
2. 将实验数据放入 `research/inputs/`；字段说明见 [研究路线](docs/research-roadmap.zh-CN.md)。仓库里的 [测量模板](research/measurement-template.csv) 没有虚构实验数据。
3. 复制 `examples/amphlett-official.json`，填写自己的工况和参数，再运行上面的命令。注意氧气分压、温度 K、膜厚 cm 和水含量 lambda。
4. 将 [下一篇论文转换提示词](research/prompts/convert-paper.zh-CN.md) 交给支持本地 Skill、命令执行和子智能体的 Codex/Claude Code。上游完整 Skill 在 `.agents/skills/paper2agent/`。

## 项目研究与验证证据

- [Paper2Agent 项目分析](docs/paper2agent-study.zh-CN.md)：架构、迁移取舍与限制。
- [燃料电池研究路线](docs/research-roadmap.zh-CN.md) 与 [首批文献线索](docs/literature.csv)：区分可执行模型与尚未复现的空冷论文。
- `reports/`、`notebooks/amphlett_reference/`：来源、原始运行、独立验证、协议及安装验收记录。
- `sources.lock.json`、`THIRD_PARTY_NOTICES.md`：固定的上游版本与许可。

本次验证通过 52 项独立测试，覆盖 11 组源代码支持的参数场景。开发环境、全新运行环境和真实 ZIP 解压目录分别通过 6 项 stdio 验收；完整数值、CSV 与图表数据按 `1e-12` 容差比较。验证范围为 Linux 上的选定静态模型，没有使用用户电堆的实验测量。

开发时可运行 `python scripts/restore_sources.py` 恢复固定 OPEM 源码，然后使用带 pytest 的开发环境执行 `python -m pytest tests/code/`。用户运行只需 `src/requirements.txt`。

可分发 MCP 运行包生成在 `dist/opem-mcp.zip`。整个研究工作区还另有压缩备份，交付路径以本次任务结果为准。
