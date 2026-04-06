# 🦐🦐🦐 三虾互杠工作流报告

**内容类型**: code
**杠精等级**: Level 2
**总轮次**: 2 轮
**最终状态**: ✅ 终审通过，无 P0 问题
**时间**: 2026-04-01 10:22:10

---

## 📋 各轮审查摘要

| 轮次 | P0 | P1 | 状态 |
|-----|----|----|------|
| Round 2 | 0 | 2 | ✅ 通过 |

---

## 🏆 最终版本（ProposalShrimp 产出）

# useLocalStorage Hook 初稿

```typescript
import { useState, useEffect, useCallback, useRef } from 'react';

type SetValue<T> = (value: T | ((val: T) => T)) => void;

function useLocalStorage<T>(
  key: string,
  initialValue: T | (() => T)
): [T, SetValue<T>] {
  // 读取 localStorage 值
  const readValue = useCallback((): T => {
    // SSR 兼容
    if (typeof window === 'undefined') {
      return initialValue instanceof Function ? initialValue() : initialValue;
    }

    try {
      const item = window.localStorage.getItem(key);
      return item !== null
        ? JSON.parse(item)
        : (initialValue instanceof Function ? initialValue() : initialValue);
    } catch (error) {
      console.warn(`Error reading localStorage key "${key}":`, error);
      return initialValue instanceof Function ? initialValue() : initialValue;
    }
  }, [initialValue, key]);

  const [storedValue, setStoredValue] = useState<T>(readValue);

  // 用 ref 存储最新值，避免 setValue 闭包陷阱
  const storedValueRef = useRef(storedValue);
  storedValueRef.current = storedValue;

  // 写入值到 state 和 localStorage
  const setValue: SetValue<T> = useCallback((value) => {
    if (typeof window === 'undefined') {
      console.warn(
        `useLocalStorage: cannot set value for key "${key}" on server side`
      );
      return;
    }

    try {
      const valueToStore =
        value instanceof Function ? value(storedValueRef.current) : value;

      setStoredValue(valueToStore);
      window.localStorage.setItem(key, JSON.stringify(valueToStore));
    } catch (error) {
      console.warn(`Error setting localStorage key "${key}":`, error);
    }
  }, [key]);

  // 监听 storage 事件，实现跨标签页同步
  useEffect(() => {
    const handleStorageChange = (e: StorageEvent) => {
      if (e.key !== key) return;

      // 值被其他标签页删除
      if (e.newValue === null) {
        const fallback =
          initialValue instanceof Function ? initialValue() : initialValue;
        setStoredValue(fallback);
        return;
      }

      try {
        setStoredValue(JSON.parse(e.newValue));
      } catch (error) {
        console.warn(`Error parsing storage event for key "${key}":`, error);
      }
    };

    window.addEventListener('storage', handleStorageChange);
    return () => window.removeEventListener('storage', handleStorageChange);
  }, [key, initialValue]);

  return [storedValue, setValue];
}

export default useLocalStorage;
```

## 使用示例

```typescript
// 基础用法
const [name, setName] = useLocalStorage('user-name', 'Guest');

// 惰性初始化（避免每次渲染都执行）
const [data, setData] = useLocalStorage('large-data', () => fetchInitialData());

// 函数式更新
setName(prev => prev.toUpperCase());
```

---

**自我审查备注**：
- `initialValue` 放在 `readValue` 和 `useEffect` 的依赖数组中，如果用户传入内联函数/对象，可能导致不必要的重渲染或重新订阅。可以考虑用 `useRef` 固化 initialValue，但会牺牲灵活性
- 没有处理 `key` 变化的情况——如果 key 在运行时改变，state 不会自动重新从 localStorage 读取，这可能是一个边缘场景

<!-- ProposalShrimp v1 -->

---

## 🔍 终审 Review Report（CriticShrimp）

## 🦐 杠精虾 Review Report

**输入类型**: 代码
**杠精等级**: Level 2

---

### 📊 问题总览

| 级别 | 数量 |
|-----|------|
| P0 🔴 | 0 条 |
| P1 🟠 | 2 条 |
| P2 🟡 | 2 条 |
| P3 🔵 | 0 条 |

---

### 🔍 问题详情

#### P1 🟠 [性能] `useEffect` 依赖 `initialValue` 导致频繁重新订阅

- **位置**: 第 68 行
- **问题**: `useEffect` 依赖数组包含 `initialValue`，用户传入内联对象/函数时，每次渲染都会触发 cleanup + 重新订阅 storage 事件
- **影响**: 高频渲染场景下会产生大量无意义的事件监听器增删操作，性能下降
- **修复建议**: 用 `useState` 固化 `initialValue`，使其只在首次渲染时确定

```typescript
// 在 readValue 定义之前添加
const [stableInitialValue] = useState(() => initialValue);

// 然后将所有 initialValue 替换为 stableInitialValue
// useEffect 依赖数组移除 initialValue
}, [key]); // 只依赖 key
```

---

#### P1 🟠 [正确性] `key` 变化时 state 不会自动同步

- **位置**: 整体逻辑缺失
- **问题**: 当 `key` prop 在运行时改变，`storedValue` 仍保持旧值，不会从 localStorage 重新读取
- **影响**: 数据不一致，用户切换 key 后看到错误的值
- **修复建议**: 添加 `useEffect` 监听 key 变化

```typescript
// 在 storage 事件监听的 useEffect 之后添加
useEffect(() => {
  setStoredValue(readValue());
}, [key, readValue]);
```

注意：这需要配合 P1 第一条的修复，否则 `readValue` 依赖 `initialValue` 会频繁重建。

---

#### P2 🟡 [可维护性] `initialValue instanceof Function` 判断重复 4 次

- **位置**: 第 14、16、26、55 行
- **问题**: 相同的类型判断逻辑散落在多处，违反 DRY 原则
- **影响**: 修改时容易遗漏，增加维护成本
- **修复建议**: 抽取为工具函数

```typescript
function getInitialValue<T>(value: T | (() => T)): T {
  return value instanceof Function ? value() : value;
}

// 使用时
return getInitialValue(initialValue);
```

---

#### P2 🟡 [正确性] `JSON.parse` 返回值缺少运行时校验

- **位置**: 第 18 行、第 60 行
- **问题**: `JSON.parse(item)` 直接返回赋值给类型 `T`，但 localStorage 数据可能被篡改或格式过期
- **影响**: 类型不匹配时后续代码可能崩溃（如期望 `{ name: string }` 实际得到 `null` 或旧版本数据结构）
- **修复建议**: 可选地支持校验函数参数

```typescript
function useLocalStorage<T>(
  key: string,
  initialValue: T | (() => T),
  options?: { validator?: (data: unknown) => data is T }
): [T, SetValue<T>] {
  // ...
  const parsed = JSON.parse(item);
  if (options?.validator && !options.validator(parsed)) {
    return getInitialValue(initialValue);
  }
  return parsed;
}
```

---

### ✅ 亮点

- SSR 兼容处理完善，`typeof window` 检查覆盖了 `readValue` 和 `setValue`
- 使用 `useRef` 存储最新值，正确规避了 `setValue` 的闭包陷阱
- 跨标签页同步功能完整，包括 `newValue === null` 的删除场景处理
- 支持函数式更新，API 与 `useState` 保持一致，学习成本低

---

### 📝 总结

代码质量良好，核心功能完备，SSR 和跨标签页同步都有考虑。主要问题集中在依赖数组设计上——`initialValue` 的不稳定性会引发连锁反应。建议优先修复 P1 问题，固化 `initialValue` 并补充 `key` 变化的响应逻辑。

---
