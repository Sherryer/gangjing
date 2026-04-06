"""
探针测试样本
============
三个精心设计的测试样本，每个都故意埋入不同类型的问题。
用于验证 CriticShrimp 能否准确识别和分级。

每个样本附有"预期答案"——方便你对比模型输出是否准确。
"""

# ─────────────────────────────────────────────
# 样本 1：有问题的 React 代码
# 预期 CriticShrimp 找到的问题：
#   P0：useEffect 里 addEventListener 没有 cleanup（内存泄漏）
#   P0：fetch 没有错误处理，网络失败会静默崩溃
#   P1：组件卸载后 setState 仍然被调用（React 警告/内存泄漏）
#   P2：userId 没有放入 useEffect 依赖数组
#   P3：函数命名 getData 太模糊
# ─────────────────────────────────────────────
CODE_SAMPLE = '''
```jsx
import React, { useState, useEffect } from 'react';

function UserProfile({ userId }) {
  const [user, setUser] = useState(null);

  useEffect(() => {
    getData();

    window.addEventListener('resize', handleResize);
  }, []);  // 依赖数组为空

  async function getData() {
    const res = await fetch(`/api/users/${userId}`);
    const data = await res.json();
    setUser(data);
  }

  function handleResize() {
    console.log('window resized');
  }

  return <div>{user ? user.name : 'Loading...'}</div>;
}

export default UserProfile;
```
'''

# ─────────────────────────────────────────────
# 样本 2：有问题的商业计划书片段
# 预期 CriticShrimp 找到的问题：
#   P0：核心财务假设（转化率 30%）没有任何数据支撑
#   P1：竞品分析只提了一家，存在严重遗漏
#   P1：用户增长数据引用来源不明
#   P2：时间表（6个月盈利）过于乐观，无论证
#   P3：ROI 计算缺少成本项
# ─────────────────────────────────────────────
BUSINESS_SAMPLE = '''
## 杠精虾 SaaS 商业计划书

### 市场机会
AI 编程助手市场正在高速增长，2025年市场规模已达 500亿美元，
年增长率超过 40%（数据来源：某研究报告）。

### 目标用户
企业研发团队，预计中国市场有 200万潜在用户。

### 商业模式
订阅制：基础版免费，专业版 ¥99/月。
预计免费用户转化为付费用户的转化率为 30%。

### 竞品分析
目前市场上主要竞品是 GitHub Copilot，但我们的差异化在于"杠精模式"，
这是业界独创，暂无竞争对手。

### 财务预测
- 第1年：获取 10万免费用户，转化 3万付费用户，年收入 ¥3,564万
- 预计第6个月实现盈利
- 3年 ROI 预计超过 500%
'''

# ─────────────────────────────────────────────
# 样本 3：有问题的技术文章片段
# 预期 CriticShrimp 找到的问题：
#   P0：关键数据引用错误（React 占有率数据与实际不符）
#   P1：标题夸大（"React 已死"但正文没有支撑这个结论）
#   P1：选择性引用，只提对自己观点有利的数据
#   P2：技术术语 "virtual DOM" 解释有误
#   P3：结构混乱，第2段和第4段内容重复
# ─────────────────────────────────────────────
CONTENT_SAMPLE = '''
# React 已死？2026年前端框架大洗牌

近年来，React 的市场份额已经从巅峰时期的 80% 跌至不足 20%，
越来越多的开发者开始转向 Vue 和 Svelte。

React 的核心问题在于其 virtual DOM 机制——每次状态更新都需要
重新渲染整个 DOM 树，导致性能低下。

根据 Stack Overflow 2025年调查，React 仍然是最受欢迎的前端框架，
但满意度连续下降。这恰恰说明 React 已经走向衰落。

React 的市场份额持续下滑，这是不可逆转的趋势。
与此同时，Vue3 的性能比 React 高出 300%（某测试数据）。

结论：2026年，每个前端开发者都应该开始学习 Vue 或 Svelte，
放弃 React 是大势所趋。
'''

# ─────────────────────────────────────────────
# 样本字典（方便按名字取样本）
# ─────────────────────────────────────────────
SAMPLES = {
    "code":     CODE_SAMPLE,
    "business": BUSINESS_SAMPLE,
    "content":  CONTENT_SAMPLE,
}
