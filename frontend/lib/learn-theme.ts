export const GL = {
  bg:          'linear-gradient(160deg, #0f0d1a 0%, #1a1428 60%, #0d1118 100%)',
  fg:          '#f0ebe0',
  fgMuted:     'rgba(240,235,224,0.5)',
  fgFaint:     'rgba(240,235,224,0.25)',
  amber:       '#c9a84c',
  amberMuted:  'rgba(201,168,76,0.6)',
  amberFaint:  'rgba(201,168,76,0.08)',
  card:        'rgba(240,235,224,0.04)',
  cardBorder:  'rgba(201,168,76,0.15)',
  inputBg:     'rgba(240,235,224,0.05)',
  inputBorder: 'rgba(240,235,224,0.12)',
  navBg:       'rgba(15,13,26,0.90)',
  navBorder:   'rgba(201,168,76,0.12)',
  headerBg:    'rgba(15,13,26,0.80)',
  headerBorder:'rgba(201,168,76,0.12)',
} as const

// Reusable inline style helpers
export const glBtn = {
  background: 'linear-gradient(135deg, #c9a84c 0%, #e8c96a 50%, #c9a84c 100%)',
  color: '#0f0d1a',
  boxShadow: '0 0 24px rgba(201,168,76,0.2), 0 4px 12px rgba(0,0,0,0.3)',
  fontFamily: 'Manrope, sans-serif',
  fontWeight: 600,
} as const

export const glBtnDisabled = {
  background: 'rgba(201,168,76,0.15)',
  color: '#0f0d1a',
} as const
