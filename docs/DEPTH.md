# 物业修缮增项复核验证目录

AI/ML · 传统ML · 中型

修改业务链路时先检查受影响模块的测试，再运行整套 `pytest`。回归记录须能够定位到具体单据或计算值。

## 功能模块

| 编号 | 功能 | 核对内容 | 核心文件 | 独立测试 |
|---|---|---|---|---|
| M1 | 增项表 | 单据版次与隔离 | `src/scopebill/variation_forms/service.py` | `tests/test_variation_forms.py` |
| M2 | 审批时间 | 截止日和成熟标签 | `src/scopebill/approval_dates/service.py` | `tests/test_approval_dates.py` |
| M3 | 造价因素 | 原始数据到特征 | `src/scopebill/scope_load/service.py` | `tests/test_scope_load.py` |
| M4 | 增项评分 | 训练及可重复推断 | `src/scopebill/change_scorecard/service.py` | `tests/test_change_scorecard.py` |
| M5 | 签证回放 | 回放误差及可信区间 | `src/scopebill/addendum_replay/service.py` | `tests/test_addendum_replay.py` |
| M6 | 项目分组 | 差异定位和外推审查 | `src/scopebill/building_portfolio/service.py` | `tests/test_building_portfolio.py` |
| M7 | 复量预算 | 硬规则与额度分配 | `src/scopebill/survey_budget/service.py` | `tests/test_survey_budget.py` |
| M8 | 价证登记 | 单据及额度证据 | `src/scopebill/price_evidence/service.py` | `tests/test_price_evidence.py` |

## 深度登记

| 编号 | 边界 | 判断 | 处理位置 | 测试定位 |
|---|---|---|---|---|
| TRAP-14 | 同版不同读数 | 两条都隔离，换序结论一致 | `src/scopebill/variation_forms/service.py` | `tests/test_variation_forms.py::test_conflicting_same_version_is_order_independent` |
| TRAP-19 | 多个规则或外推标记重叠 | 硬约束优先，保留全部命中码 | `src/scopebill/survey_budget/service.py` | `tests/test_survey_budget.py::test_hard_rule_precedes_outside_reference` |
| TRAP-23 | 标签落在窗口的终点 | 终点进入隔离段，窗口为半开区间 | `src/scopebill/approval_dates/service.py` | `tests/test_approval_dates.py::test_half_open_days` |
| TRAP-32 | 大偏移细方差与常数列 | 中心化后累加，常数列尺度为一 | `src/scopebill/scope_load/service.py` | `tests/test_scope_load.py::test_cancellation_safe_scaling` |
| TRAP-42 | 拟合窗口后才回传结果 | 依标签成熟时间屏蔽，未来数据不参与拟合 | `src/scopebill/approval_dates/service.py` | `tests/test_approval_dates.py::test_mature_label_cannot_cross_partition` |
| TRAP-43 | 回放没有成熟记录 | 记录未定义状态，避免以零误差替代 | `src/scopebill/addendum_replay/service.py` | `tests/test_addendum_replay.py::test_no_outcome_gets_undefined_metrics` |
| TRAP-44 | 校准样本不足 | 分派前转人工判读并保留原因 | `src/scopebill/addendum_replay/service.py` | `tests/test_addendum_replay.py::test_empty_calibration_requires_review` |
| TRAP-53 | 单条推断与混批 | 复用冻结参数，各条估计完全一致 | `src/scopebill/change_scorecard/service.py` | `tests/test_change_scorecard.py::test_input_batch_invariance` |
| TRAP-54 | 特征版本与模型不配对 | 拒绝继续推断并要求重拟合 | `src/scopebill/change_scorecard/service.py` | `tests/test_change_scorecard.py::test_mismatched_model_input_version_fails` |
