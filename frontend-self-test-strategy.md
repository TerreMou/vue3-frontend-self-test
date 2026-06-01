# Vue3 前端开发自测方案

## 1. 定位

面向前端开发人员的日常自测实践方案，不是建立专业测试体系。

技术栈：Vue 3 / `<script setup>` / Vite / TypeScript / TailwindCSS / AI Agent 辅助环境。

核心判断：

> 前端不是不适合测试，而是不适合把所有内容都当纯函数单测。纯逻辑用单测，组件测行为，关键业务流用 E2E。

## 2. 目标与边界

**目标：** 降低回归风险；核心逻辑可自动校验；复杂组件关键行为可验证；核心流程有冒烟保护；AI Agent 可参与测试生成与修复。

**非目标：** 不追求短期高覆盖率；不要求所有页面完整测试；不把开发变测试工程师；不以测试数量作为绩效。

## 3. 测试策略

```
纯逻辑 / composable / store 单测   70%  ← 优先建设，成本低、稳定性高
组件行为测试                        20%  ← 适度覆盖关键组件
关键业务流 E2E                      10%  ← 少量冒烟保护
```

比例表达优先级，非硬性要求。

## 4. 测试决策流程

拿到一段代码，按以下路径判断：

```
是纯函数/工具函数？  → 单测
是 composable？      → 单测（测状态变化与对外契约）
是 Pinia Store？     → 单测（getter 按纯函数，action 测状态变化）
是路由守卫？         → 单测（独立测试守卫函数）
是 Vue 组件？
  ├─ 有复杂交互/多状态？ → 组件行为测试
  └─ 纯展示/简单透传？  → 不测或极简测试
是核心业务流程？      → E2E（1-3 条）
```

**一律不测：** Tailwind class、DOM 层级、内部 ref/方法、无业务含义的浅层封装。

## 5. 分层详解

### 5.1 纯逻辑单测

适合对象：工具函数、数据格式化、金额/日期处理、权限判断、状态流转、表单校验规则、接口数据转换、排序/筛选/分页、复杂条件判断。

```ts
// price.ts
export function formatPrice(value: number): string {
  if (value < 0) return '-¥0.00'
  return '¥' + value.toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ',')
}

// price.test.ts
import { describe, it, expect } from 'vitest'
import { formatPrice } from './price'

describe('formatPrice', () => {
  it('负数显示 -¥0.00', () => expect(formatPrice(-1)).toBe('-¥0.00'))
  it('千分位分隔', () => expect(formatPrice(12345.6)).toBe('¥12,345.60'))
  it('零值', () => expect(formatPrice(0)).toBe('¥0.00'))
})
```

### 5.2 Composable 测试

适合对象：`usePagination`、`useTable`、`useSearchForm`、`usePermission`、`useUpload`、`useDialog` 等。

测试重点：初始化状态 → 方法调用后状态变化 → 异常时 error/loading → 参数变化后计算结果 → 对外契约。

```ts
// usePagination.test.ts
import { describe, it, expect } from 'vitest'
import { usePagination } from './usePagination'

describe('usePagination', () => {
  it('nextPage 后页码加 1', () => {
    const { pageNo, nextPage } = usePagination()
    nextPage()
    expect(pageNo.value).toBe(2)
  })

  it('resetPage 恢复到第 1 页', () => {
    const { pageNo, nextPage, resetPage } = usePagination()
    nextPage()
    resetPage()
    expect(pageNo.value).toBe(1)
  })
})
```

将接口请求、路由跳转等副作用与核心状态逻辑拆开，优先测业务状态变化。

### 5.3 Pinia Store 测试

**Getter** — 按纯函数方式断言：

```ts
import { createPinia, setActivePinia } from 'pinia'
import { useOrderStore } from './orderStore'

describe('useOrderStore', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('totalAmount 汇总订单金额', () => {
    const store = useOrderStore()
    store.orders = [{ id: '1', amount: 100 }, { id: '2', amount: 200 }]
    expect(store.totalAmount).toBe(300)
  })
})
```

**Action** — mock API 后断言状态变化：

```ts
it('fetchOrders 失败后记录错误', async () => {
  const store = useOrderStore()
  vi.spyOn(store, 'fetchOrders').mockImplementation(async () => {
    store.error = '网络异常'
    store.loading = false
  })
  await store.fetchOrders()
  expect(store.error).toBe('网络异常')
})
```

每个测试前 `setActivePinia(createPinia())` 确保状态隔离。

### 5.4 组件行为测试

适合组件：复杂表单、业务弹窗、列表筛选区、上传组件、状态操作按钮组、权限敏感组件、有 loading/empty/error 状态的展示组件。

断言用户行为与可感知结果，不断言实现细节：

```ts
import { render, screen } from '@testing-library/vue'
import userEvent from '@testing-library/user-event'
import UserForm from './UserForm.vue'

describe('UserForm', () => {
  it('必填项为空时禁用提交按钮', () => {
    render(UserForm)
    expect(screen.getByRole('button', { name: '提交' })).toBeDisabled()
  })

  it('填写必填项后可提交', async () => {
    const user = userEvent.setup()
    render(UserForm)
    await user.type(screen.getByLabelText('用户名'), 'test')
    expect(screen.getByRole('button', { name: '提交' })).toBeEnabled()
  })
})
```

查找元素：按钮文本、label、role、提示文案。触发：用户输入、点击、选择。

### 5.5 路由守卫测试

守卫逻辑抽成纯函数独立测试：

```ts
import { beforeEachGuard } from './guards'

it('未登录时重定向到登录页', () => {
  const next = vi.fn()
  beforeEachGuard({ path: '/order', matched: [{ meta: { requiresAuth: true } }] }, undefined, next)
  expect(next).toHaveBeenCalledWith({ path: '/login' })
})
```

路由参数驱动的组件测试用 `createMemoryHistory` 构造可控环境。

### 5.6 关键业务流 E2E

定位：开发侧冒烟保护，每个核心模块 1-3 条（成功路径 / 关键失败路径 / 高风险边界路径）。不依赖真实线上数据，不覆盖所有分支。

### 5.7 可访问性（a11y）基础测试

Testing Library 天然鼓励可访问性友好的查询方式，零额外成本。如需系统检查可集成 `jest-axe`：

```ts
it('无 a11y 违规', async () => {
  const { container } = render(UserForm)
  expect(await axe(container)).toHaveNoViolations()
})
```

a11y 测试作为组件测试附加项，不单独设层，在关键组件上逐步补充。

## 6. 工具选型

| 层级 | 工具 | 用途 |
|------|------|------|
| 单测/组件 | Vitest | 测试运行器，适配 Vite |
| | @vue/test-utils | 验证 props/emit/slot |
| | @testing-library/vue + user-event | 用户视角组件行为测试 |
| | @testing-library/jest-dom | DOM 断言扩展 |
| | jsdom / happy-dom | 模拟浏览器环境 |
| | @vitest/coverage-v8 | 覆盖率统计 |
| | jest-axe | a11y 检查（可选） |
| 接口 Mock | MSW | 网络层 mock，可复用于开发/测试/Storybook |
| E2E | Playwright | 自动等待、截图/trace、CI 友好 |

组件测试优先用 Testing Library，需验证 props/emit/slot 时用 Vue Test Utils。

### 6.1 MSW 配置

**tests/mocks/handlers.ts：**

```ts
import { http, HttpResponse } from 'msw'

export const handlers = [
  http.get('/api/orders', () => {
    return HttpResponse.json({ data: [{ id: '1', status: 'draft', amount: 100 }] })
  }),
  http.post('/api/orders', async ({ request }) => {
    const body = await request.json()
    if (!body.name) return HttpResponse.json({ message: '名称不能为空' }, { status: 400 })
    return HttpResponse.json({ data: { id: '2', ...body } }, { status: 201 })
  }),
]
```

**tests/mocks/server.ts：**

```ts
import { setupServer } from 'msw/node'
import { handlers } from './handlers'
export const server = setupServer(...handlers)
```

**tests/setup.ts：**

```ts
import '@testing-library/jest-dom/vitest'
import { server } from './mocks/server'

beforeAll(() => server.listen({ onUnhandledRequest: 'warn' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())
```

测试中临时覆盖 handler：`server.use(http.get('/api/orders', () => HttpResponse.json({}, { status: 500 })))`

### 6.2 异步测试模式

核心原则：**不用 setTimeout hack，用 waitFor 或 findBy 等待异步结果。**

| 场景 | 推荐方式 |
|------|----------|
| 等待元素出现/消失 | `findBy*`（自带 waitFor） |
| 等待非 DOM 的异步断言 | `waitFor` |
| 控制定时器、倒计时、防抖 | `vi.useFakeTimers` |
| 等待路由跳转完成 | `await router.isReady()` + `findBy*` |

避免：`setTimeout(() => ..., 0)`、手动 `await new Promise(r => setTimeout(r, 100))`、依赖真实延迟。

## 7. 目录结构

```
src/
  utils/price.ts                → utils/price.test.ts
  composables/usePagination.ts  → composables/usePagination.test.ts
  stores/orderStore.ts          → stores/orderStore.test.ts
  router/guards.ts              → router/guards.test.ts
  components/UserForm.vue       → components/UserForm.test.ts
  pages/order/OrderList.vue     → pages/order/OrderList.test.ts

tests/
  setup.ts                # 全局初始化（jest-dom、MSW server 启停）
  mocks/
    handlers.ts           # MSW 默认请求处理器
    server.ts             # MSW server 实例
  fixtures/
    order.ts              # createOrder 工厂函数
    user.ts               # createUser 工厂函数
    permission.ts         # createPermission 工厂函数

e2e/
  login.spec.ts
  order-flow.spec.ts
```

测试文件就近放置，E2E 独立目录。

## 8. 测试数据策略

使用工厂函数，测试只关注差异字段：

```ts
export function createOrder(overrides: Partial<Order> = {}): Order {
  return { id: 'order-001', status: 'draft', amount: 100, creator: 'tester', ...overrides }
}
```

测试数据要求：稳定、可读、贴近业务、不含真实用户隐私、不依赖线上接口。

## 9. 开发自测流程

| 场景 | 做法 |
|------|------|
| 新增纯逻辑 | 同步补单测 |
| 新增 composable | 覆盖初始化状态和核心状态变化 |
| 新增复杂组件 | 覆盖关键用户行为 |
| 新增核心流程 | 视情况补 E2E |
| 修 bug | 先写测试复现 → 确认失败 → 修复 → 确认通过 → 保留回归用例 |
| 重构 | 先补核心行为保护测试 → 跑通 → 重构 → 确认仍通过 |
| 提交前 | 跑相关单测 + 组件测试 + 手工自测；核心流程跑 E2E |

bug 难以自动化时记录原因（依赖第三方状态/纯样式兼容/依赖特殊硬件）。

## 10. 覆盖率策略

1. **跑起来** — 接入 Vitest，跑通第一个测试
2. **写起来** — 核心逻辑逐步有测试
3. **守起来** — 新增/修改核心逻辑必须带测试，覆盖率不下降
4. **看趋势** — 关注覆盖率趋势，不追求绝对数字

覆盖率是温度计，不是绩效指标。高风险模块可单独设目标。

## 11. CI 集成

| 阶段 | 运行内容 |
|------|----------|
| 第一阶段 | 类型检查 + Lint + 单测 |
| 第二阶段 | + 组件测试 + 覆盖率报告 |
| 第三阶段 | + Playwright 冒烟测试（初期不阻塞，稳定后纳入） |

测试失败时保留截图、trace 或日志。

## 12. 老项目渐进式接入

典型困境：组件中混杂大量逻辑，缺少 composable 抽离，直接写测试成本极高。解决思路：**先抽逻辑再补测试，小步推进。**

改造步骤：

```
1. 识别组件中的纯逻辑片段（格式化、校验、状态判断）
2. 抽成独立函数或 composable，组件改为调用
3. 为抽出的函数补单测（成本低、稳定性高）
4. 组件本身补少量行为测试（只测关键交互）
```

接入优先级：

| 优先级 | 操作 | 产出 |
|--------|------|------|
| P0 | 找出 utils/helpers 中已有的纯函数，补单测 | 立即可测，零改造 |
| P1 | 从高频修改的组件中抽逻辑，补单测 | 降低回归风险最高的模块 |
| P2 | 为核心 composable 补测试 | 保护共享状态逻辑 |
| P3 | 为关键组件补行为测试 | 保护用户交互 |
| P4 | 补 E2E 冒烟 | 保护核心流程 |

不要求一次性改造完成，每次修 bug 或加需求时顺手抽一小块即可。

## 13. 落地计划

| 阶段 | 目标 | 验收标准 |
|------|------|----------|
| 第 1 周 | 接入 Vitest，跑通第一个测试 | 本地/CI 可运行，有 1-2 个参考样例 |
| 第 2-3 周 | 2-3 个高频模块补测试，建立规范 | 新增逻辑带测试，bug 修复补回归，成员可独立写测试 |
| 第 4-7 周 | 引入 MSW，复杂组件补行为测试 | 接口 mock 统一，关键组件有状态测试，失败易定位 |
| 持续 | 接入 Playwright，核心流程 E2E | 核心模块 1-3 条 E2E，发版前自动检查，失败有截图/trace |

## 14. 风险规避

| 风险 | 表现 | 规避 |
|------|------|------|
| 测试过度 | 改样式导致大量失败，开发抵触 | 不测 class/内部实现，不以覆盖率为唯一目标 |
| Mock 失真 | 测试通过但线上失败 | MSW mock 与接口文档对齐，关键路径用 E2E 兜底 |
| E2E 不稳定 | 频繁超时/误报 | 只覆盖核心路径，用 Playwright 自动等待，失败保留 trace |
| 维护负担 | 测试比业务代码还多 | 只测高价值场景，低价值测试及时删除 |

## 15. 最小配置参考

**package.json scripts：**

```json
{
  "test": "vitest",
  "test:run": "vitest run",
  "test:coverage": "vitest run --coverage",
  "e2e": "playwright test"
}
```

**vitest.config.ts：**

```ts
export default defineConfig({
  test: {
    environment: 'jsdom',
    setupFiles: ['tests/setup.ts'],
    coverage: { provider: 'v8' },
  },
  resolve: { alias: { /* 与 Vite 保持一致 */ } },
})
```

**tests/setup.ts：**

```ts
import '@testing-library/jest-dom/vitest'
import { server } from './mocks/server'

beforeAll(() => server.listen({ onUnhandledRequest: 'warn' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())
```
