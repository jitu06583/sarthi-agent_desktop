import { describe, expect, it } from 'vitest'

import { isInternalSessionSource, sessionSourceLabel } from './session-source'

describe('kanban worker session source', () => {
  it('filters normalized internal sources while preserving human sessions', () => {
    expect(isInternalSessionSource(' KANBAN ')).toBe(true)
    expect(isInternalSessionSource('subagent')).toBe(true)
    expect(isInternalSessionSource('tool')).toBe(true)
    expect(isInternalSessionSource('acp')).toBe(false)
    expect(isInternalSessionSource('desktop')).toBe(false)
    expect(sessionSourceLabel('kanban')).toBe('Kanban')
  })
})
