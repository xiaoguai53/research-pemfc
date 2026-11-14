# GitHub 科研项目调研与实际融合（非写作）

采集：2026-11-14 13:36，北京时间。总 Star 来自 GitHub REST API；周增量与顺位来自 [GitHub 官方 weekly 页面](https://github.com/trending?since=weekly)。原始结构化快照保存在 `reports/research-radar/`，页面哈希保留在快照中。

## 筛选原则

按热度发现项目，再检查许可证、维护、方法适配和能否在本项目复现。总 Star、周增 Star 和最近推送时间分别记录；未出现在周榜中的项目，其周增量留空。API 未识别许可不等于没有许可，本次不从这些仓库复制实现。

| 项目 | 总 Star | 周榜顺位 / 周增 | 采用方式 | 对本项目的具体作用 |
| --- | ---: | --- | --- | --- |
| [scipy/scipy](https://github.com/scipy/scipy) | 15,216 | — | 实际接入 | 有界校准、重复单位统计、LHS；原生数值算法 |
| [optuna/optuna](https://github.com/optuna/optuna) | 15,043 | — | 实际接入 | 约束 ask/tell；保留真实历史和待测候选 |
| [SALib/SALib](https://github.com/SALib/SALib) | 1,026 | — | 实际接入 | 有序 Sobol 设计、原模型响应、置信估计 |
| [streamlit/streamlit](https://github.com/streamlit/streamlit) | 46,349 | — | 实际接入 | 本地上传、参数操作、结果查看与证据导出 |
| [K-Dense-AI/scientific-agent-skills](https://github.com/K-Dense-AI/scientific-agent-skills) | 57,088 | — | 方法借鉴 | 真实实验单位、效应与区间、假设边界、只读数据检查；未导入写作技能 |
| [karpathy/autoresearch](https://github.com/karpathy/autoresearch) | 100,019 | — | 流程借鉴 | 固定评估、基准、实验记录与保留失败；未移植 GPU 训练器 |
| [NVIDIA/auto-ontology](https://github.com/NVIDIA/auto-ontology) | 12,618 | #7 / +4,108 | 设计借鉴 | 记录数据语义、来源与方法；没有安装 NIM/知识图谱服务 |
| [mlflow/mlflow](https://github.com/mlflow/mlflow) | 28,798 | — | 设计借鉴 | 逐次运行的输入、指标、版本与产物记录；未宣称调用 MLflow |
| [treeverse/dvc](https://github.com/treeverse/dvc) | 15,973 | — | 设计借鉴 | 数据哈希与可追溯派生物；未配置 DVC 远端 |
| [meta-pytorch/botorch](https://github.com/meta-pytorch/botorch) | 3,651 | — | 暂缓 | 方法合适但 PyTorch 依赖更重；本版先用轻量 TPE |
| [meta/Ax](https://github.com/meta/Ax) | 2,842 | — | 暂缓 | 适合更复杂自适应实验；本版先完成有观测历史的约束候选链路 |
| [Future-House/paper-qa](https://github.com/Future-House/paper-qa) | 9,597 | — | 暂缓 | 带引用 QA 需额外模型/检索配置；本版用无需模型 Key 的 Crossref 元数据 |
| [docling-project/docling](https://github.com/docling-project/docling) | 70,561 | — | 暂缓 | 文档解析可用于后续全文证据；本次没有实际接入该解析器 |
| [marimo-team/marimo](https://github.com/marimo-team/marimo) | 23,542 | — | 暂缓 | 反应式研究笔记本有价值；首版操作入口选 Streamlit |
| [microsoft/RD-Agent](https://github.com/microsoft/RD-Agent) | 15,366 | — | 流程参考 | 研究—实验—评估闭环；未直接运行其金融/ML任务环境 |
| [wanshuiyin/Auto-claude-code-research-in-sleep](https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep) | 19,161 | — | 流程参考 | 实验与交叉复核；不导入自动写作模块 |
| [HKUDS/AI-Researcher](https://github.com/HKUDS/AI-Researcher) | 5,885 | — | 未采用 | 未整体导入自动科研/论文流水线；当前聚焦可检验的实验工具 |
| [SakanaAI/AI-Scientist](https://github.com/SakanaAI/AI-Scientist) | 14,992 | — | 未采用 | 不导入论文生成模块，也不以其整套 ML 实验替代燃料电池研究 |
| [google-deepmind/mujoco](https://github.com/google-deepmind/mujoco) | 17,897 | #8 / +1,764 | 未采用 | 周榜中的通用刚体动力学项目，不对应 PEMFC 电化学/热水实现 |
| [anthropics/skills](https://github.com/anthropics/skills) | 194,213 | #2 / +6,169 | 规范参考 | 技能目录和接口组织；不整体安装包含的写作能力 |

## 读到的原始材料与复用边界

- [Optuna README 与官方 API](https://github.com/optuna/optuna)：真实接入 5.0.0 的 `Trial.set_constraint`、`study.ask/tell` 与 TPE。没有把未观测候选写成满足约束的结果。
- [SALib README](https://github.com/SALib/SALib)：真实接入 1.6.0 的 Sobol sample/analyze。用原模型响应，保留顺序设计和置信估计；不把任意实测表当作 Sobol 设计。
- [Scientific Agent Skills: statistical-analysis](https://github.com/K-Dense-AI/scientific-agent-skills/blob/main/skills/statistical-analysis/SKILL.md) 与 [EDA](https://github.com/K-Dense-AI/scientific-agent-skills/blob/main/skills/exploratory-data-analysis/SKILL.md)：借鉴实验单位、显式设计、效应区间、缺失/变换边界，不把数据检查当作科学结论。没有复制其写作能力或声称整个技能库已安装。
- [autoresearch program.md](https://github.com/karpathy/autoresearch/blob/master/program.md)：研究了固定预算、固定评估和记录循环。本项目只采用对应的工程原则；没有运行无限循环，也没有运行其单 GPU 语言模型训练。
- [NVIDIA Auto Ontology README](https://github.com/NVIDIA/auto-ontology)：借鉴“数据是什么、来自哪里、如何使用”的显式语义。当前没有安装它的数据库、NIM 或图服务。
- 实际依赖、源文件来源和数值参照在 `reports/workbench-v2/source-provenance.json`、`source-bindings.json` 和 `reference.json`；新增校准组合明确为 SciPy 优化器＋原始 OPEM 物理函数。

## 对论文和专利研究的实际交付

本版交付可复核的表格、效应和区间、训练/留出误差、模型参数诊断、采样设计、下一轮待测候选、DOI 元数据、逐项已有技术查证矩阵和可导出的 PNG/SVG/JSON。用户自己的实验数据与验证仍是结果依据。当前不包含论文、专利交底书或投稿写作。

专利部分目前是检索链接与待查证表，尚未自动搜索专利正文或判断新颖性。元数据／摘要不是全文审阅；模型计算与合成验证样例不是用户实验。

当前 GitHub 周榜不是专门的科研榜。原始榜单的全部条目都保留在 JSON 中，这里只列与能力选择相关的项目；未对周榜顺位按 Star 增量另行排序。
