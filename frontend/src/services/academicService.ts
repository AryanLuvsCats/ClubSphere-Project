import { api } from './apiClient'
import type { Branch, Paginated } from '../domain/types'
import { FALLBACK_BRANCHES } from '../data/fallbackBranches'

export const academicService = {
  async getBranches(): Promise<Branch[]> {
    try {
      const res = await api.get<Paginated<Branch>>('/branches')
      return res.items?.length ? res.items : FALLBACK_BRANCHES
    } catch {
      return FALLBACK_BRANCHES
    }
  },
}
