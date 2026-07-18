import { useQuery } from '@tanstack/react-query'

import { getSarthiConfigRecord } from '@/sarthi'
import { queryClient, writeCache } from '@/lib/query-client'
import type { SarthiConfigRecord } from '@/types/sarthi'

// One shared cache for the whole profile config record (`GET /api/config`).
// Every settings surface (MCP, model, config) reads and writes through this key
// so a save in one shows in the others, and revisiting a tab paints the cache
// instead of blanking on a fresh fetch.
//
// Distinct from session/hooks/use-sarthi-config.ts, which is side-effecting —
// it pushes personality/cwd/voice/… into the session stores for live chat.
export const SARTHI_CONFIG_KEY = ['sarthi-config-record'] as const

// staleTime 0 → serve cache instantly, background-revalidate on every mount.
export const useSarthiConfigRecord = () =>
  useQuery({ queryKey: SARTHI_CONFIG_KEY, queryFn: getSarthiConfigRecord, staleTime: 0 })

export const setSarthiConfigCache = writeCache<SarthiConfigRecord>(SARTHI_CONFIG_KEY)

export const invalidateSarthiConfig = () => queryClient.invalidateQueries({ queryKey: SARTHI_CONFIG_KEY })
