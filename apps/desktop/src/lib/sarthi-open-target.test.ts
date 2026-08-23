import { describe, expect, it } from 'vitest'

import {
  normalizeSarthiOpenString,
  pathFromSarthiDeepLink,
  pathFromOpenDeepLink,
  resolveSarthiOpenPath
} from './sarthi-open-target'

describe('normalizeSarthiOpenString', () => {
  it('accepts hash-router paths and strips a leading hash', () => {
    expect(normalizeSarthiOpenString('/index-network/intent/1')).toBe('/index-network/intent/1')
    expect(normalizeSarthiOpenString('#/index-network/intent/1')).toBe('/index-network/intent/1')
  })

  it('maps plugin-scoped sarthi:// deep links to the same path', () => {
    expect(normalizeSarthiOpenString('sarthi://index-network/intent/1')).toBe('/index-network/intent/1')
    expect(normalizeSarthiOpenString('sarthi://index-network/intent/1?focus=true')).toBe(
      '/index-network/intent/1?focus=true'
    )
  })

  it('maps sarthi://open/… deep links by stripping the open host', () => {
    expect(normalizeSarthiOpenString('sarthi://open/index-network/intent/1')).toBe('/index-network/intent/1')
    expect(normalizeSarthiOpenString('sarthi://open/settings/plugins')).toBe('/settings/plugins')
  })

  it('rejects reserved sarthi kinds and unsafe paths', () => {
    expect(normalizeSarthiOpenString('sarthi://blueprint/morning-brief')).toBeNull()
    expect(normalizeSarthiOpenString('sarthi://plugin/install')).toBeNull()
    expect(normalizeSarthiOpenString('https://example.com/x')).toBeNull()
    expect(normalizeSarthiOpenString('/../etc/passwd')).toBeNull()
    expect(normalizeSarthiOpenString('index-network')).toBeNull()
  })
})

describe('resolveSarthiOpenPath', () => {
  it('merges structured path + params', () => {
    expect(resolveSarthiOpenPath({ path: '/index-network/intent/1', params: { focus: 'true' } })).toBe(
      '/index-network/intent/1?focus=true'
    )
  })

  it('resolves href the same as a bare string', () => {
    expect(resolveSarthiOpenPath({ href: 'sarthi://index-network/intent/1' })).toBe('/index-network/intent/1')
  })
})

describe('pathFromSarthiDeepLink', () => {
  it('builds the navigate path from a plugin-scoped deep-link payload', () => {
    expect(pathFromSarthiDeepLink('index-network', 'intent/1')).toBe('/index-network/intent/1')
  })

  it('builds the navigate path from sarthi://open/… payloads', () => {
    expect(pathFromOpenDeepLink('index-network/intent/1')).toBe('/index-network/intent/1')
    expect(pathFromSarthiDeepLink('open', 'agent/42')).toBe('/agent/42')
  })

  it('ignores reserved kinds', () => {
    expect(pathFromSarthiDeepLink('blueprint', 'morning-brief')).toBeNull()
    expect(pathFromSarthiDeepLink('plugin', 'install')).toBeNull()
  })
})
