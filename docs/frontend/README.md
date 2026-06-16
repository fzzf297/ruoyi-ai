# RuoYi 智能操作助手 — 前端技术文档

> 配套主方案见仓库根目录 `README.md`（v4.0）。本文聚焦**前端实现层**，用于梳理前端开发任务。  
> 技术栈：Vue 3 + `<script setup>` + TypeScript + Element Plus + Pinia + Vue Router + Vite（与 RuoYi-Vue-Plus 默认前端一致）。

## 目录

1. [范围与目标](#1-范围与目标)
2. [技术栈与依赖](#2-技术栈与依赖)
3. [整体架构](#3-整体架构)
4. [目录结构](#4-目录结构)
5. [状态管理（Pinia）](#5-状态管理pinia)
6. [SSE 传输层](#6-sse-传输层)
7. [事件分发与协议类型](#7-事件分发与协议类型)
8. [组件清单与职责](#8-组件清单与职责)
9. [page_context 采集](#9-page_context-采集)
10. [断线与刷新恢复](#10-断线与刷新恢复)
11. [错误处理与降级](#11-错误处理与降级)
12. [与 RuoYi 框架的集成点](#12-与-ruoyi-框架的集成点)
13. [安全约束（前端侧）](#13-安全约束前端侧)
14. [开发任务拆解清单](#14-开发任务拆解清单)

---

## 1. 范围与目标

前端负责：

- 提供常驻 AI 助手面板（输入、消息流、连接状态）
- 建立并维护 SSE 连接，消费 Agent 推送的事件
- 把事件渲染为：流式文本、表格、消歧选项、确认卡片、执行结果、进度
- 接收 `route` 事件执行页面跳转
- 采集当前页面 `page_context` 随消息上送
- 断线/刷新后恢复 UI 状态

前端**不负责**：鉴权裁决、业务规则、最终执行（均由 Agent + RuoYi 后端完成）。前端传入的 ID 只作候选，执行前由后端复查。

## 2. 技术栈与依赖

| 类别 | 选型 | 说明 |
|------|------|------|
| 框架 | Vue 3 + `<script setup>` + TS | 与 RuoYi-Vue-Plus 一致 |
| UI | Element Plus | `el-table`、`el-card`、`el-button`、`el-link`、`el-checkbox`、`el-input` 等 |
| 状态 | Pinia | 会话状态、消息列表、当前确认 |
| 路由 | Vue Router | route 事件跳转、page_context 读取 |
| 构建 | Vite | RuoYi 默认 |
| SSE 传输 | `@microsoft/fetch-event-source` | **必须**：原生 EventSource 不支持自定义请求头 |
| Markdown | `markdown-it` + 代码高亮（可选） | 流式文本渲染 |
| HTTP | RuoYi 既有 axios 封装（`@/utils/request`） | 复用拦截器与 token 注入 |
| 鉴权工具 | RuoYi 既有 `@/utils/auth` | 取/刷新 token |

新增依赖仅 `@microsoft/fetch-event-source`（及可选 `markdown-it`）。

## 3. 整体架构

```mermaid
flowchart TD
    subgraph host [RuoYi 前端宿主]
        Layout[src/layout]
        Biz[业务页面 / 系统管理]
    end
    subgraph panel [AI 助手面板 plugin]
        Panel[AiAssistantPanel.vue]
        Store[Pinia: aiAssistant]
        Stream[useAgentStream]
        Ctx[usePageContext]
        Comps[渲染组件集合]
    end
    Layout --> Panel
    Biz -. registerSelection .-> Store
    Panel --> Store
    Store --> Comps
    Panel --> Stream
    Stream -->|SSE 事件| Store
    Panel -->|POST /messages /confirm| Agent[(Agent 服务)]
    Stream -->|GET /stream| Agent
    Comps -->|router.push| Router[Vue Router]
```

要点：

- 面板挂在 `src/layout` 层，**跳转业务页时面板不卸载**（持久连接、持久会话）。
- 业务页面通过轻量「选区注册」把选中行上报给 store，面板无需侵入每个业务页。
- 数据流单向：SSE 事件 → store → 组件渲染；用户动作 → POST → 结果仍从 SSE 回推。

## 4. 目录结构

```text
src/plugins/ai-assistant/
├─ AiAssistantPanel.vue          # 容器组件
├─ components/
│  ├─ MessageList.vue            # 消息流容器，按 message.kind 分发子组件
│  ├─ MessageText.vue            # text / text_done 流式 Markdown
│  ├─ DataTable.vue              # data 事件表格
│  ├─ ClarifyCard.vue            # clarify 消歧/补参选项
│  ├─ ConfirmCard.vue            # confirm 确认卡片（含二次确认）
│  ├─ ActionResult.vue           # action_result 执行结果
│  ├─ ToolStatus.vue             # tool_status 进度
│  └─ ConnectionBadge.vue        # 连接状态指示
├─ composables/
│  ├─ useAgentStream.ts          # SSE 连接、重连、事件分发入口
│  ├─ usePageContext.ts          # 采集 page_context
│  └─ useAgentSession.ts         # 创建会话、发送消息、确认/取消、history 恢复
├─ store/
│  └─ aiAssistant.ts             # Pinia store
├─ api/
│  └─ agent.ts                   # /ai/sessions/* 接口封装（复用 request）
├─ types/
│  └─ events.ts                  # AgentEvent / 各 payload 类型定义
└─ utils/
   ├─ dispatch.ts                # dispatchEvent：type → handler
   └─ errorMap.ts                # 错误码 → 友好文案
```

## 5. 状态管理（Pinia）

```ts
// store/aiAssistant.ts
interface AgentMessage {
  id: string;
  kind: 'text' | 'data' | 'clarify' | 'confirm' | 'action_result' | 'tool_status';
  payload: unknown;
  done?: boolean;          // text 流式是否结束
}

interface AiAssistantState {
  sessionId: string | null;
  phase: 'idle' | 'clarifying' | 'awaiting_confirm' | 'executing';
  messages: AgentMessage[];
  lastEventId: string | null;       // 断线续传
  seenEventIds: Set<string>;        // 去重
  pendingConfirm: ConfirmPayload | null;
  pendingClarify: ClarifyPayload | null;
  connection: 'connecting' | 'open' | 'closed' | 'error';
  selection: SelectedRow[];         // 业务页注册的当前选区
}
```

关键 action：

- `ensureSession()`：无 session 时 `POST /ai/sessions`
- `appendText(eventId, delta)` / `finishText(eventId)`：流式文本
- `pushMessage(msg)`：追加 data / action_result 等
- `setConfirm(payload)` / `clearConfirm()`：确认卡片生命周期
- `registerSelection(rows)`：业务页上报选区
- `reset()`：退出登录/切换用户时清空（含 `seenEventIds`）

> store 中**不存 token**；token 始终从 `@/utils/auth` 实时取。

## 6. SSE 传输层

**核心约束**：原生 `EventSource` 无法设置 `Authorization` 头，禁止使用。改用 `@microsoft/fetch-event-source`，token 放请求头不放 URL。

```ts
// composables/useAgentStream.ts
import { fetchEventSource } from '@microsoft/fetch-event-source';
import { getToken } from '@/utils/auth';
import { useAiAssistantStore } from '../store/aiAssistant';
import { dispatchEvent } from '../utils/dispatch';

export function useAgentStream() {
  const store = useAiAssistantStore();
  let ctrl: AbortController | null = null;

  function connect(sessionId: string) {
    ctrl?.abort();
    ctrl = new AbortController();
    store.connection = 'connecting';
    fetchEventSource(`/ai/sessions/${sessionId}/stream`, {
      headers: {
        Authorization: `Bearer ${getToken()}`,
        'Last-Event-ID': store.lastEventId ?? '',
      },
      signal: ctrl.signal,
      openWhenHidden: true,
      onopen: async () => { store.connection = 'open'; await store.recoverFromHistory(); },
      onmessage(ev) {
        const event = JSON.parse(ev.data);
        if (store.seenEventIds.has(event.event_id)) return;
        store.seenEventIds.add(event.event_id);
        store.lastEventId = event.event_id;
        dispatchEvent(event, store);
      },
      onerror(err) { store.connection = 'error'; throw err; }, // 抛出→库指数退避重连
    });
  }
  function disconnect() { ctrl?.abort(); store.connection = 'closed'; }
  return { connect, disconnect };
}
```

要点：

- `openWhenHidden: true`：切到业务页签也保持连接。
- 重连后 `onopen` 调用 `recoverFromHistory()` 对齐状态（§10）。
- `Last-Event-ID` + `seenEventIds` 双重去重，避免重复卡片/重复 text。
- 退出登录或切换用户时 `disconnect()` 并 `store.reset()`。

## 7. 事件分发与协议类型

事件基础结构（与主方案 §15.2 一致）：

```ts
// types/events.ts
interface AgentEventBase {
  seq: number; event_id: string; session_id: string;
  correlation_id: string; created_at: string;
}
type AgentEvent = AgentEventBase & (
  | { type: 'text'; payload: { delta: string } }
  | { type: 'text_done'; payload: {} }
  | { type: 'route'; payload: RoutePayload }
  | { type: 'data'; payload: DataPayload }
  | { type: 'clarify'; payload: ClarifyPayload }
  | { type: 'confirm'; payload: ConfirmPayload }
  | { type: 'action_result'; payload: ActionResultPayload }
  | { type: 'tool_status'; payload: { tool: string; state: string } }
  | { type: 'error'; payload: { code: string; message: string; retryable: boolean } }
);
```

分发表：

| type | handler | 作用 |
|------|---------|------|
| text | `appendText` | 追加增量 |
| text_done | `finishText` | 定稿 Markdown |
| route | `handleRoute` | 校验后 `router.push` |
| data | `pushMessage` | 追加表格 |
| clarify | `setClarify` + `pushMessage` | 渲染选项，`phase=clarifying` |
| confirm | `setConfirm` | 渲染确认卡片，`phase=awaiting_confirm` |
| action_result | `pushMessage` + `notifyBizRefresh` | 结果 + 刷新业务页 |
| tool_status | `updateToolStatus` | 进度 |
| error | `mapError` | 友好文案 / Toast / token 刷新 |

## 8. 组件清单与职责

| 组件 | 输入（props） | 职责 | 关键 Element Plus |
|------|---------------|------|-------------------|
| `AiAssistantPanel` | — | 布局容器、输入框、发送、连接状态 | `el-drawer`/自定义浮层、`el-input` |
| `MessageList` | `messages` | 按 `kind` 分发子组件、滚动到底 | `el-scrollbar` |
| `MessageText` | `text, done` | 流式 Markdown 渲染 | — (markdown-it) |
| `DataTable` | `payload: DataPayload` | 动态列表格、truncated 引导、查看全部 | `el-table`、`el-table-column`、`el-link` |
| `ClarifyCard` | `payload: ClarifyPayload` | 最多 5 选项、点选回传 | `el-card`、`el-radio`/`el-button` |
| `ConfirmCard` | `payload: ConfirmPayload` | 影响范围、倒计时、二次确认、确认/拒绝/修改 | `el-card`、`el-button`、`el-checkbox`、`el-input`、`el-countdown` |
| `ActionResult` | `payload: ActionResultPayload` | 成功/失败明细 | `el-result`、`el-alert` |
| `ToolStatus` | `tool, state` | 工具执行进度 | `el-progress`/loading |
| `ConnectionBadge` | `connection` | 连接状态点 | `el-tag` |

### 8.1 ConfirmCard 行为细则（重点组件）

- 展示 `title`、`summary`、`affected_resources`、`expires_at` 倒计时。
- `risk_level=medium`：单按钮「确认执行」。
- `risk_level=high`：必须二次确认——勾选「我已知晓影响」或输入关键字（如 `确认删除`）后按钮才可用；批量操作展示数量 + 前若干条资源名称。
- 确认 → `POST /confirm`（**重新携带 token**，由 axios 拦截器注入），带 `confirm_id`；拒绝/修改 → `action: reject/modify`。
- 倒计时归零或收到 `CONFIRM_EXPIRED` → 卡片置灰，提示重新发起。
- 结果不在此处理，统一通过 SSE `action_result` 回推。

### 8.2 DataTable 展示规则

- `<=20` 条：表格 + 简短摘要。
- `truncated=true`（`>20`）：展示前 20 条 + `total` + 「在业务页查看全部」（携带相同查询条件 `router.push`）。
- 空结果：提示未找到并给出可修改条件。
- 不在面板做完整分页，大数据量引导回业务页。

## 9. page_context 采集

```ts
// composables/usePageContext.ts
export function usePageContext(): PageContext {
  const route = useRoute();
  const store = useAiAssistantStore();
  return {
    route: route.path,
    page_title: route.meta?.title as string,
    query_params: pickWhitelist(route.query),                 // 仅白名单
    selected_rows_summary: store.selection.slice(0, 20),       // 最多 20 条
  };
}
```

选区注册机制（业务页改动最小化）：业务页面在 `el-table` 的 `@selection-change` 时调用一次注册即可：

```ts
// 业务页面（如 system/user/index.vue）
const store = useAiAssistantStore();
function onSelectionChange(rows) {
  store.registerSelection(rows.map(r => ({ id: r.userId, userName: r.userName, nickName: r.nickName })));
}
```

字段约束：仅白名单（`route`、`page_title`、`query_params`、`selected_rows_summary`）；选中行 ≤20；不传密码/手机号等敏感字段；**ID 只作候选**。

## 10. 断线与刷新恢复

```ts
// store action: recoverFromHistory()
async recoverFromHistory() {
  if (!this.sessionId) return;
  const h = await getHistory(this.sessionId);  // GET /history
  this.phase = h.phase;
  this.rebuildMessages(h.messages);
  if (h.phase === 'awaiting_confirm') this.pendingConfirm = toConfirmPayload(h);
  else if (h.phase === 'executing' && h.execution_id) { /* 继续监听 SSE；已完成则展示 action_result */ }
}
```

规则：

- 面板挂载、SSE 重连成功（`onopen`）、浏览器刷新后都先 `GET /history` 对齐再重建 UI。
- `awaiting_confirm` 一律由 `/history` 重建卡片，**不靠 SSE 重推 confirm**，避免重复卡片/重复确认。
- 恢复信息仅用于 UI；真正执行以服务端确认快照为准。
- 重连后的 `/confirm` 必须重新携带 token。

## 11. 错误处理与降级

```ts
// utils/errorMap.ts
const ERROR_TEXT: Record<string, string> = {
  AUTH_EXPIRED: '登录状态已过期，请刷新后重试。',
  PERMISSION_DENIED: '你没有执行该操作的权限。',
  ENTITY_AMBIGUOUS: '匹配到多个对象，请先选择。',
  CONFIRM_EXPIRED: '确认已超时，请重新发起。',
  // ...
};
```

- 按 `code` 映射友好文案，**不展示堆栈、内网地址、SQL**。
- `AUTH_EXPIRED`：触发 RuoYi 既有 token 刷新；刷新成功后若处于 `awaiting_confirm`，凭原 `confirm_id` 直接重放 `/confirm`，无需用户重述。
- `retryable=true`：展示「重试」按钮。
- `MODEL_ERROR`：不影响已确认操作；仅提示文本生成失败。

## 12. 与 RuoYi 框架的集成点

| 集成点 | 做法 |
|--------|------|
| 布局挂载 | 在 `src/layout` 注入 `AiAssistantPanel`，全局常驻 |
| 路由跳转 | 复用全局 `router`；`router.resolve` 校验权限/存在性后 `router.push` |
| 鉴权 token | 复用 `@/utils/auth` 的 `getToken()` 与刷新逻辑 |
| HTTP 请求 | 复用 `@/utils/request`（axios 拦截器自动注入 Authorization） |
| 国际化 | confirm_template/错误文案走 RuoYi i18n（如需多语言） |
| 权限指令 | 入口按钮可用 `v-hasPermi` 控制面板可见性（可选） |

## 13. 安全约束（前端侧）

- token 不写入 Pinia/localStorage 之外的任何自定义存储，统一走 `@/utils/auth`；SSE 用 header 携带。
- page_context 严格白名单，敏感字段不传。
- 前端 ID 只作候选，不作为执行依据。
- 工具结果中的 URL 不自动请求、不可点击外链（防 SSRF/钓鱼）。
- Markdown 渲染需防 XSS（markdown-it 关闭 raw html 或做 sanitize）。
- 业务数据按服务端脱敏结果展示，前端不反脱敏。

## 14. 开发任务拆解清单

可直接据此建卡（建议顺序对应主方案 P0–P5）：

- [ ] **脚手架**：`plugins/ai-assistant` 目录、Pinia store、类型定义、api 封装
- [ ] **面板容器**：`AiAssistantPanel` 布局、输入发送、`ConnectionBadge`
- [ ] **SSE 传输**：`useAgentStream`（fetch-event-source、重连、去重、openWhenHidden）
- [ ] **会话**：`useAgentSession`（创建会话、发送消息、cancel）
- [ ] **文本渲染**：`MessageText` 流式 Markdown + XSS 防护
- [ ] **导航**：`handleRoute` + 权限/存在性校验
- [ ] **表格**：`DataTable` 动态列 + truncated 引导
- [ ] **消歧**：`ClarifyCard` 选项回传
- [ ] **确认**：`ConfirmCard`（medium/high 二次确认 + 倒计时 + 重携 token）
- [ ] **结果**：`ActionResult` + 通知业务页刷新
- [ ] **进度**：`ToolStatus`
- [ ] **上下文**：`usePageContext` + 业务页选区注册（先接用户管理页）
- [ ] **恢复**：`recoverFromHistory`（挂载/重连/刷新）
- [ ] **错误**：`errorMap` + AUTH_EXPIRED 刷新重放
- [ ] **集成**：layout 挂载、退出登录清理、权限入口控制
- [ ] **联调**：与 Agent 服务对齐事件结构、错误码、history 字段
