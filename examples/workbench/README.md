# 合成软件验证样例

这些文件不是用户实验，也不是已验证的空冷电堆性能。极化数据来自固定 OPEM 原始函数的已知参数；条件比较与优化历史用于检查数据管线，历史的数值由明确的非物理玩具函数构造。

- measurements-synthetic.csv：6 对重复，每个工况每次重复含 3 行时间采样。
- polarization-synthetic.csv：25 个原模型生成点，真值 R=0.002 ohm、lambda=18；split 列在优化前固定。
- history-synthetic.csv：16 条分析测试记录，非物理玩具目标为 2.8I-0.012I²-4PWM²，玩具温度为 30+0.9I-12PWM；不是空冷热模型。
- experiment-bounds.json：示例输入范围，不是硬件允许工况。
