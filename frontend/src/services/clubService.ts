import { api } from './apiClient'
import type { Club, ClubPublicProfile, MembershipJoinResponse, MembershipMember, MembershipUpdateRequest, MyMembershipStatus, Paginated } from '../domain/types'

export interface GetClubsParams {
  search?: string
  branch_id?: string
  program_id?: string
  status?: string
  page?: number
  page_size?: number
}

export const clubService = {
  async getMyMembershipStatuses(): Promise<MyMembershipStatus[]> {
    return api.get<MyMembershipStatus[]>('/clubs/my-memberships')
  },

  async getPendingRequestCount(): Promise<{ count: number }> {
    return api.get<{ count: number }>('/clubs/pending-request-count')
  },

  async getClubs(params: GetClubsParams = {}): Promise<Paginated<Club>> {
    const query = new URLSearchParams()
    query.set('page', String(params.page ?? 1))
    query.set('page_size', String(params.page_size ?? 50))
    if (params.search?.trim()) query.set('search', params.search.trim())
    if (params.status) query.set('status', params.status)
    if (params.program_id) query.set('program_id', params.program_id)
    else if (params.branch_id) query.set('branch_id', params.branch_id)

    return api.get<Paginated<Club>>(`/clubs?${query.toString()}`)
  },

  async getClub(clubId: number): Promise<Club> {
    return api.get<Club>(`/clubs/${clubId}`)
  },

  async getClubPublicProfile(clubId: number): Promise<ClubPublicProfile> {
    return api.get<ClubPublicProfile>(`/clubs/${clubId}/public-profile`)
  },

  async requestJoinClub(clubId: number): Promise<MembershipJoinResponse> {
    return api.post<MembershipJoinResponse>(`/clubs/${clubId}/join`)
  },

  async getClubMembers(
    clubId: number,
    status?: string,
    page: number = 1,
    pageSize: number = 50,
  ): Promise<Paginated<MembershipMember>> {
    const query = new URLSearchParams()
    query.set('page', String(page))
    query.set('page_size', String(pageSize))
    if (status) query.set('status', status)
    return api.get<Paginated<MembershipMember>>(`/clubs/${clubId}/members?${query.toString()}`)
  },

  async updateMembershipStatus(
    clubId: number,
    membershipId: number,
    payload: MembershipUpdateRequest,
  ): Promise<MembershipMember> {
    return api.put<MembershipMember>(`/clubs/${clubId}/members/${membershipId}`, payload)
  },
}
