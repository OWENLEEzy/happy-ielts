import createClient from 'openapi-fetch'
import type { paths } from '@/types/api'

// Empty string = same-origin relative URLs (e.g. /api/...)
export const client = createClient<paths>({ baseUrl: '' })
