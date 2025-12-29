export type NodeKind = 'concept' | 'skill' | 'resource'

export const APP_CONFIG = {
  defaultStartNode: 'TOP-DEMO',
  testNodes: ['TOP-DEMO', 'SUB-MATH', 'sub-cs'],
  systemFields: ['uid', 'title', 'kind', 'labels', 'incoming', 'outgoing'],
  
  // Маппинг типов из БД к фронтенд-стандарту 4.2
  kindMap: {
    skill: 'skill',
    resource: 'resource',
    example: 'resource',
    subject: 'concept',
    section: 'concept',
    topic: 'concept',
  } as Record<string, NodeKind>,
  
  defaultKind: 'concept' as NodeKind
} as const
