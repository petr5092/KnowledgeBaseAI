/**
 * Генерирует уникальный ID на основе времени и случайного числа
 */
export function generateUid(): string {
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`
}

/**
 * Форматирует таймстемп в строку времени HH:MM
 */
export function formatTime(ts: number): string {
  const d = new Date(ts)
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

