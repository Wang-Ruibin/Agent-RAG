import request from './request'

export type BotPlatform = 'WEIXIN_OC' | 'DINGTALK' | 'QQ_ONEBOT'

export interface BotInstance {
  id: number
  platform: BotPlatform
  name: string
  status: string
  status_detail?: string | null
  mention_required: boolean
  command_prefix?: string | null
  created_at: string
  updated_at: string
}

export interface BotInput {
  platform: BotPlatform
  name: string
  credentials: Record<string, string>
  mention_required: boolean
  command_prefix?: string
}

export const listBots = () => request.get('/api/admin/bots')
export const createBot = (data: BotInput) => request.post('/api/admin/bots', data)
export const updateBot = (id: number, data: Partial<BotInput>) => request.patch(`/api/admin/bots/${id}`, data)
export const removeBot = (id: number) => request.delete(`/api/admin/bots/${id}`)
export const startBot = (id: number) => request.post(`/api/admin/bots/${id}/start`)
export const stopBot = (id: number) => request.post(`/api/admin/bots/${id}/stop`)
export const getBotHealth = (id: number) => request.get(`/api/admin/bots/${id}/health`)
export const getBotLoginQr = (id: number) => request.post(`/api/admin/bots/${id}/login/qr`)
