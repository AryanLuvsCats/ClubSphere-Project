import { api } from './apiClient'
import type { UploadResult } from '../domain/types'

export type UploadEntityType = 'Clubs' | 'Events' | 'ClubProposals'
export type UploadMediaKind = 'logo' | 'charter' | 'poster' | 'attachment'

export const uploadService = {
  async uploadFile(
    file: File,
    entityType: UploadEntityType,
    entityId: number,
    mediaKind?: UploadMediaKind,
  ): Promise<UploadResult> {
    const formData = new FormData()
    formData.append('file', file)
    if (entityType === 'Clubs') {
      if (mediaKind) {
        formData.append('media_kind', mediaKind)
      }
      return api.upload<UploadResult>(`/clubs/${entityId}/media`, formData)
    }
    if (entityType === 'Events') {
      return api.upload<UploadResult>(`/events/${entityId}/banner`, formData)
    }
    formData.append('entity_type', entityType)
    formData.append('entity_id', String(entityId))
    if (mediaKind) {
      formData.append('media_kind', mediaKind)
    }
    return api.upload<UploadResult>('/uploads', formData)
  },
}
