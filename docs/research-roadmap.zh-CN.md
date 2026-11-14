# 氢燃料电池与空冷氢燃料电池：使用路线

v0.2 已加入实验数据、重复单位统计、模型校准、敏感性与试验规划；操作入口和当前边界见 [WORKBENCH.md](../WORKBENCH.md)。以下保留领域研究任务的分层，空冷热水物理求解仍未实现。

## 第一阶段：通用 PEMFC 基线

先用 OPEM Amphlett 计算稳态极化、功率和电压损失，检查温度、反应气体分压、膜厚和膜水含量对结果的影响。模型的温度是输入条件，不是求解出来的电堆温度；膜水含量 lambda 也不能自动由环境 RH 推断。

建议把自己的实验条件放在 `research/project.json` 中，把输入数据留在 `research/inputs/`。后者默认不进入 Git。原始数据另行保留，清理、稳态筛选和单位转换应保留记录。

## 第二阶段：空冷适配的关键问题

强制对流开放阴极电堆的空气可能同时承担供氧与散热功能，因此风量变化会同时影响散热、供氧和水管理。应区分强制对流开放阴极、被动空气呼吸型，以及具有独立冷却通道的空冷结构。不同结构的边界条件不能混用。

| 问题 | 需要记录的量 | 当前状态 |
| --- | --- | --- |
| 稳态极化与电压损失 | 电流、整堆电压、单片数、面积、温度、气体分压 | 首个可执行模型 |
| 风量对温度和性能的影响 | 风机 PWM、转速、实测风速或流量、环境温湿度、堆温、负载 | 已加入实验设计与测量历史驱动候选推荐；尚未实现空冷热水物理模型 |
| 净输出功率最优 | 整堆电功率、风机和其他辅助设备的实测耗电 | 需实验数据和系统边界；模型功率不能直接当净功率 |
| 膜干燥与积水 | 环境温湿度、运行历史、阻抗/高频电阻、压差、性能恢复证据 | 需独立水管理实现与验证；仅凭电压下降不能确定机制 |
| 吹扫与瞬态负载 | 吹扫周期、持续时间、氢流量、时间序列、负载变化 | 尚未实现 |
| 局部温度与电流分布 | 测点位置、热像标定、局部电流、几何与边界条件 | 尚未实现空间模型 |

首批文献线索见 [literature.csv](literature.csv)。其中空冷论文目前用于确定研究问题和输入契约，尚未转化为经过验证的可执行工具。

## 数据格式

`research/measurement-template.csv` 只提供字段表头，没有伪造的实验记录。

- `time_s`、`current_A`、`stack_voltage_V`：实测时间、电堆电流和整堆电压。
- `cell_count`、`active_area_cm2`：用于后续区分单片/整堆和电流/电流密度。
- `stack_temperature_C`、`ambient_temperature_C`：温度测点和采样方式应在实验记录中说明。
- `ambient_rh_fraction`：范围 0 到 1，不能填百分数。
- `fan_pwm_fraction`：0 到 1 的控制占空比；它不是空气流量。
- `fan_speed_rpm`、`air_velocity_m_s`、`fan_power_W`：未测量的量留空，不用 PWM 代替。
- `hydrogen_pressure_kPa_abs`：绝对压力；应另行记录干气/湿气和分压换算条件。
- `purge_active`：吹扫状态；`notes` 保存异常、稳态选择和传感器说明。

## 第一项自己的研究任务

1. 选一组稳态极化数据并记录气体、温度、单片数与面积。
2. 使用 `scripts/run_polarization.py` 先复现官方参数案例，确认安装与输出可用。
3. 复制模型输入 JSON，填写自己的参数；对文献取值、实测取值和待辨识参数分别作注。
4. 在同一边界条件下比较模型和实验。v0.2 可校准原生 R/lambda，并保留训练/留出误差和可辨识性诊断；如果参数未知，不把示例曲线当作预测。
5. 再选择一篇有代码或可公开获取验证数据的空冷热水管理论文，使用 `research/prompts/convert-paper.zh-CN.md` 启动下一次转换。

## 文献依据与阅读范围

- [OPEM，JOSS 2018](https://joss.theoj.org/papers/10.21105/joss.00676)：已核对软件论文元信息、仓库与实际 Amphlett 源码；这是当前可执行来源。
- [Overall and local effects of operating parameters…，Applied Energy 2022](https://doi.org/10.1016/j.apenergy.2022.118978)：公开摘要及亮点说明温度和气速与水管理/性能相关；本次未阅读全文或复现其局部分布实验。
- [Experimental investigation…，IJHE 2024](https://www.sciencedirect.com/science/article/pii/S0360319924006992)：公开检索摘要涉及氢压、吹扫和堆温；本次未阅读全文或复现实验。
- [Development and experimental validation…，Journal of Power Sources](https://www.iri.upc.edu/files/scidoc/1184-Development-and-experimental-validation-of-a-dynamic-thermal-and-water-distribution-model-of-an-open-cathode-proton-exchange-membrane-fuel-cell.pdf)：机构提供论文链接，检索摘要描述开放阴极 H-100 的热水动态和风机/吹扫机制；本次没有成功获取全文，因此仅列为后续阅读来源。

上述文献提供选题入口，不构成对用户电堆参数、工况窗口或控制策略的验证。

## 公开工程仓库的补充初筛

还检查了两个主题匹配仓库的 README：[空冷燃料电池风场与性能分析](https://github.com/Pika-Zhihao/7.Wind-field-and-performance-analysis-of-air-cooled-fuel-cell-system) 说明它是使用 Fluent 的本科毕业设计与原始模型；[ALÉR-ION 开放阴极电堆](https://github.com/Alerion-SuperMileage-UL/ALER-ION-open-source-fuel-cell) 主要提供硬件设计、CAD 与工程记录，作者说明整堆尚未完成测试。两者目前仅列为工程资料线索，未检查全部文件、许可与复现条件，也未作为本次自动计算工具来源。
