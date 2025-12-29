import type { NodeKind } from './appConfig'

export type ThemeNodeKind = NodeKind | 'Subject' | 'Section' | 'Topic' | 'Skill' | 'Resource' | 'Default'

export const GRAPH_THEME = {
  nodes: {
    colors: {
      concept: '#7c5cff',
      skill: '#e71d36',
      resource: '#ff9f1c',
      Subject: '#ff9f1c', // Orange/Gold
      Section: '#2ec4b6', // Teal/Blue
      Topic: '#7c5cff',   // Purple
      Skill: '#e71d36',   // Red/Pink
      Resource: '#808080',
      Default: '#7c5cff',
    } as Record<ThemeNodeKind, string>,
    sizes: {
      concept: 24,
      skill: 18,
      resource: 16,
      Subject: 40,
      Section: 32,
      Topic: 24,
      Skill: 18,
      Resource: 16,
      Default: 24,
    } as Record<ThemeNodeKind, number>,
    font: {
      size: 14,
      color: '#ffffff',
      strokeWidth: 3,
      strokeColor: '#000000',
      vadjustRatio: 0.8, // Multiplier for size
    },
    shape: 'hexagon',
    borderWidth: 2,
  },
  edges: {
    width: 1,
    dashes: [2, 4] as const,
    color: {
      color: 'rgba(255,255,255,0.4)',
      highlight: '#fff',
      opacity: 0.4,
    },
    arrows: {
      scaleFactor: 0.4,
    },
  },
  physics: {
    gravitationalConstant: -100,
    centralGravity: 0.005,
    springLength: 200,
    springConstant: 0.05,
    stabilizationIterations: 250,
  },
  tooltip: {
    background: 'rgba(20, 20, 30, 0.9)',
    borderColor: 'rgba(255, 255, 255, 0.1)',
    offset: 20,
  }
} as const
