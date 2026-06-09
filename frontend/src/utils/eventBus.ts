/**
 * 轻量级事件总线 — 用于跨组件通信（通知→卡片自动刷新等）
 * 用法：
 *   import { eventBus } from '../utils/eventBus'
 *   // 订阅
 *   const unsub = eventBus.on('refreshCards', () => { ... })
 *   // 发布
 *   eventBus.emit('refreshCards')
 *   // 取消订阅
 *   unsub()
 */

type EventMap = {
  refreshCards: void  // 通知检测到更新时触发所有卡片重新拉取数据
}

type EventName = keyof EventMap
type Handler<T extends EventName> = (payload: EventMap[T]) => void

class EventBus {
  private listeners: Map<EventName, Set<Handler<any>>> = new Map()

  on<T extends EventName>(event: T, handler: Handler<T>): () => void {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set())
    }
    this.listeners.get(event)!.add(handler)
    // 返回取消订阅函数
    return () => this.off(event, handler)
  }

  off<T extends EventName>(event: T, handler: Handler<T>): void {
    this.listeners.get(event)?.delete(handler)
  }

  emit<T extends EventName>(event: T, payload?: EventMap[T]): void {
    this.listeners.get(event)?.forEach(h => h(payload))
  }
}

export const eventBus = new EventBus()
