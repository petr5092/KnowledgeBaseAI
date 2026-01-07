export const ASSISTANT_CONFIG = {
  actionOptions: [
    { value: '', label: 'Ответ' },
    { value: 'explain_relation', label: 'Связь' },
    { value: 'viewport', label: 'Граф' },
    { value: 'roadmap', label: 'План' },
  ],
  defaults: {
    depth: 1,
    limit: 30,
    count: 10,
    difficultyMin: 1,
    difficultyMax: 5
  }
} as const;

