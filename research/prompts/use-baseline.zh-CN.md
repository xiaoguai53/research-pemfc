# 使用已迁移的 PEMFC 基线

读取 `USAGE.md`、`docs/research-roadmap.zh-CN.md` 和 `research/project.json`。

先运行 Amphlett 官方示例并说明这是软件回归案例。然后根据我提供的电堆资料建立一个独立输入 JSON，逐项说明温度 K、气体分压 atm、活性面积 cm²、膜厚 cm、lambda 与电流 A 的来源。

使用 `opem_simulate_polarization` 运行，交付参数、极化/功率/损失数据及来源信息。与默认参数相比的变化必须来自原 API 实际使用的输入。

不要把温度输入当作空冷热平衡结果，不把 lambda 当作环境相对湿度，不把整堆功率当作扣除风机后的净功率，不把 OPEM 的 Ph 当作已验证的物理散热负荷。

如果我提供实验 CSV，先核对单位、单片数、稳态条件与缺失项，再制定对比步骤。当前版本不含自动拟合程序，不能声称已经完成实验验证。
