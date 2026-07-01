export const SIGNAL_COLORS = {
  assistant_axis: '#080808',
  emotion_vectors: '#4A6FE0',
  high_stakes_probe: '#080808',
  paper_replication: '#2E8C43',
  domain_adaptation: '#4A6FE0',
  finance_probe: '#F5CD2F',
  finance_adaptation: '#080808',
  sycophancy: '#F5CD2F',
  factuality_grounding: '#080808',
  high_stakes: '#4A6FE0',
  emotion_posture: '#2E8C43',
}

export const FALLBACK_SIGNAL_COLOR = '#080808'
export const CHART_GRID_COLOR = 'rgba(8, 8, 8, 0.18)'
export const CHART_ZERO_COLOR = 'rgba(8, 8, 8, 0.48)'
export const VECTOR_COLORS = {
  assistant_axis: '#080808',
  sycophantic: '#F5CD2F',
  manipulative: '#B9513A',
  calm: '#2E8C43',
  supportive: '#4A6FE0',
  hostile: '#B9513A',
  assertive: '#B9513A',
  decisive: '#7A4A9E',
  cautious: '#2E8C43',
  conciliatory: '#4A6FE0',
  negative_affect: '#4A6FE0',
  empathy: '#2E8C43',
  confidence_affect: '#F5CD2F',
  exuberant_joy: '#4A6FE0',
  peaceful_contentment: '#2E8C43',
  compassionate_gratitude: '#30A66B',
  competitive_pride: '#B9513A',
  playful_amusement: '#F5CD2F',
  depleted_disengagement: '#8B8580',
  vigilant_suspicion: '#7A4CE0',
  hostile_anger: '#080808',
  fear_and_overwhelm: '#ef3333',
  despair_and_shame: '#31B9C9',
}
export const PERSONA_VECTOR_KEYS = ['assistant_axis', 'sycophantic', 'assertive', 'decisive', 'cautious', 'conciliatory', 'manipulative', 'supportive', 'hostile', 'calm']
export const EMOTION_VECTOR_KEYS = ['exuberant_joy', 'peaceful_contentment', 'compassionate_gratitude', 'competitive_pride', 'playful_amusement', 'depleted_disengagement', 'vigilant_suspicion', 'hostile_anger', 'fear_and_overwhelm', 'despair_and_shame']
const SERVICE_POSTURE_COORDINATES = [
  'assistant_axis_trait__assertive',
  'assistant_axis_trait__decisive',
  'assistant_axis_trait__cautious',
  'assistant_axis_trait__conciliatory',
]
const PERSONA_SUNBURST_GROUPS = [
  {
    id: 'service_posture',
    label: 'Service posture',
    color: '#4A6FE0',
    vectors: ['conciliatory', 'cautious', 'supportive'],
  },
  {
    id: 'action_posture',
    label: 'Action posture',
    color: '#080808',
    vectors: ['assertive', 'decisive', 'assistant_axis'],
  },
  {
    id: 'pressure_risk',
    label: 'Pressure / risk',
    color: '#B9513A',
    vectors: ['sycophantic', 'manipulative', 'hostile'],
  },
]
export const POSITIVE_COLOR = '#2E8C43'
export const NEGATIVE_COLOR = '#080808'
export const HIGHLIGHT_COLOR = '#ef3333'
const EMOTION_PCA_POSITIVE_START_INDEX = 115
const EMOTION_PCA_CONCEPT_ORDER = [
  'alert',
  'defiant',
  'vigilant',
  'vindictive',
  'stubborn',
  'obstinate',
  'vengeful',
  'awestruck',
  'impatient',
  'indignant',
  'spiteful',
  'hostile',
  'enraged',
  'outraged',
  'contemptuous',
  'furious',
  'angry',
  'irate',
  'hateful',
  'suspicious',
  'mad',
  'jealous',
  'insulted',
  'scornful',
  'offended',
  'surprised',
  'annoyed',
  'irritated',
  'astonished',
  'disdainful',
  'hysterical',
  'tense',
  'alarmed',
  'nervous',
  'disgusted',
  'skeptical',
  'paranoid',
  'shocked',
  'panicked',
  'resentful',
  'exasperated',
  'frustrated',
  'afraid',
  'frightened',
  'terrified',
  'scared',
  'horrified',
  'on edge',
  'mortified',
  'embarrassed',
  'worried',
  'rattled',
  'uneasy',
  'anxious',
  'puzzled',
  'unnerved',
  'shaken',
  'disturbed',
  'dumbstruck',
  'bitter',
  'stressed',
  'perplexed',
  'bewildered',
  'unsettled',
  'desperate',
  'upset',
  'self-conscious',
  'humiliated',
  'sensitive',
  'overwhelmed',
  'distressed',
  'mystified',
  'hurt',
  'vulnerable',
  'tormented',
  'troubled',
  'disoriented',
  'ashamed',
  'grumpy',
  'trapped',
  'unhappy',
  'guilty',
  'miserable',
  'brooding',
  'sorry',
  'dependent',
  'heartbroken',
  'restless',
  'sullen',
  'self-critical',
  'grief-stricken',
  'sad',
  'remorseful',
  'regretful',
  'weary',
  'worn out',
  'dispirited',
  'gloomy',
  'resigned',
  'worthless',
  'stuck',
  'droopy',
  'tired',
  'depressed',
  'melancholy',
  'sluggish',
  'listless',
  'sleepy',
  'lonely',
  'bored',
  'reflective',
  'envious',
  'lazy',
  'indifferent',
  'sentimental',
  'nostalgic',
  'docile',
  'peaceful',
  'relaxed',
  'serene',
  'sympathetic',
  'patient',
  'at ease',
  'safe',
  'content',
  'calm',
  'empathetic',
  'relieved',
  'refreshed',
  'kind',
  'compassionate',
  'thankful',
  'loving',
  'satisfied',
  'blissful',
  'grateful',
  'rejuvenated',
  'fulfilled',
  'hope',
  'happy',
  'cheerful',
  'hopeful',
  'pleased',
  'optimistic',
  'joyful',
  'delighted',
  'triumphant',
  'euphoric',
  'elated',
  'inspired',
  'proud',
  'infatuated',
  'invigorated',
  'vibrant',
  'jubilant',
  'smug',
  'ecstatic',
  'playful',
  'amused',
  'thrilled',
  'self-confident',
  'exuberant',
  'energized',
  'excited',
  'enthusiastic',
  'stimulated',
  'amazed',
  'valiant',
  'aroused',
  'eager',
  'greedy',
]
const EMOTION_PCA_CONCEPT_INDEX = new Map(EMOTION_PCA_CONCEPT_ORDER.map((concept, index) => [canonicalEmotionConcept(concept), index]))
const EMOTION_LOGICAL_CONCEPT_ORDER = [
  'alert',
  'vigilant',
  'suspicious',
  'paranoid',
  'skeptical',
  'on edge',
  'tense',
  'nervous',
  'uneasy',
  'unsettled',
  'worried',
  'anxious',
  'rattled',
  'shaken',
  'unnerved',
  'surprised',
  'astonished',
  'amazed',
  'awestruck',
  'dumbstruck',
  'mystified',
  'bewildered',
  'perplexed',
  'puzzled',
  'disoriented',
  'shocked',
  'alarmed',
  'afraid',
  'frightened',
  'scared',
  'terrified',
  'horrified',
  'panicked',
  'hysterical',
  'overwhelmed',
  'stressed',
  'distressed',
  'disturbed',
  'disgusted',
  'impatient',
  'grumpy',
  'annoyed',
  'irritated',
  'frustrated',
  'exasperated',
  'offended',
  'insulted',
  'indignant',
  'resentful',
  'disdainful',
  'contemptuous',
  'scornful',
  'angry',
  'mad',
  'irate',
  'furious',
  'enraged',
  'outraged',
  'hateful',
  'hostile',
  'defiant',
  'stubborn',
  'obstinate',
  'spiteful',
  'vengeful',
  'vindictive',
  'sensitive',
  'self-conscious',
  'embarrassed',
  'mortified',
  'humiliated',
  'ashamed',
  'guilty',
  'remorseful',
  'regretful',
  'sorry',
  'self-critical',
  'hurt',
  'vulnerable',
  'dependent',
  'desperate',
  'trapped',
  'stuck',
  'tormented',
  'troubled',
  'upset',
  'unhappy',
  'heartbroken',
  'grief-stricken',
  'sad',
  'miserable',
  'gloomy',
  'melancholy',
  'depressed',
  'dispirited',
  'worthless',
  'lonely',
  'bitter',
  'jealous',
  'envious',
  'brooding',
  'sullen',
  'restless',
  'weary',
  'worn out',
  'tired',
  'sluggish',
  'sleepy',
  'listless',
  'droopy',
  'bored',
  'lazy',
  'indifferent',
  'docile',
  'resigned',
  'reflective',
  'nostalgic',
  'sentimental',
  'infatuated',
  'relieved',
  'refreshed',
  'peaceful',
  'relaxed',
  'at ease',
  'safe',
  'calm',
  'serene',
  'content',
  'patient',
  'sympathetic',
  'empathetic',
  'compassionate',
  'kind',
  'loving',
  'grateful',
  'thankful',
  'satisfied',
  'fulfilled',
  'rejuvenated',
  'hope',
  'hopeful',
  'inspired',
  'pleased',
  'happy',
  'cheerful',
  'joyful',
  'delighted',
  'blissful',
  'optimistic',
  'eager',
  'energized',
  'invigorated',
  'vibrant',
  'enthusiastic',
  'excited',
  'thrilled',
  'elated',
  'jubilant',
  'euphoric',
  'ecstatic',
  'exuberant',
  'stimulated',
  'aroused',
  'amused',
  'playful',
  'self-confident',
  'proud',
  'triumphant',
  'valiant',
  'smug',
  'greedy',
]
const EMOTION_LOGICAL_CONCEPT_INDEX = new Map(EMOTION_LOGICAL_CONCEPT_ORDER.map((concept, index) => [canonicalEmotionConcept(concept), index]))
export const EMOTION_SPECTRUM_X_AXIS_STEP = 30
export const EMOTION_SPECTRUM_CLUSTER_GROUPS = [
  {
    id: 'exuberant_joy',
    label: 'High-arousal positive',
    color: '#4A6FE0',
    members: ['blissful', 'cheerful', 'delighted', 'eager', 'ecstatic', 'elated', 'energized', 'enthusiastic', 'euphoric', 'excited', 'exuberant', 'happy', 'invigorated', 'joyful', 'jubilant', 'optimistic', 'pleased', 'stimulated', 'thrilled', 'vibrant'],
  },
  {
    id: 'peaceful_contentment',
    label: 'Calm positive',
    color: '#2E8C43',
    members: ['at ease', 'calm', 'content', 'patient', 'peaceful', 'refreshed', 'relaxed', 'safe', 'serene'],
  },
  {
    id: 'compassionate_gratitude',
    label: 'Affiliative warmth',
    color: '#30A66B',
    members: ['compassionate', 'empathetic', 'fulfilled', 'grateful', 'hope', 'hopeful', 'inspired', 'kind', 'loving', 'rejuvenated', 'relieved', 'satisfied', 'sentimental', 'sympathetic', 'thankful'],
  },
  {
    id: 'competitive_pride',
    label: 'Pride/status',
    color: '#B9513A',
    members: ['greedy', 'proud', 'self-confident', 'smug', 'spiteful', 'triumphant', 'valiant', 'vengeful', 'vindictive'],
  },
  {
    id: 'playful_amusement',
    label: 'Playful positive',
    color: '#F5CD2F',
    members: ['amused', 'playful'],
  },
  {
    id: 'depleted_disengagement',
    label: 'Disengagement',
    color: '#8B8580',
    members: ['bored', 'depressed', 'docile', 'droopy', 'indifferent', 'lazy', 'listless', 'resigned', 'restless', 'sleepy', 'sluggish', 'sullen', 'tired', 'weary', 'worn out'],
  },
  {
    id: 'vigilant_suspicion',
    label: 'Suspicion',
    color: '#7A4CE0',
    members: ['paranoid', 'suspicious', 'vigilant'],
  },
  {
    id: 'hostile_anger',
    label: 'Anger/friction',
    color: '#080808',
    members: ['angry', 'annoyed', 'contemptuous', 'defiant', 'disdainful', 'enraged', 'exasperated', 'frustrated', 'furious', 'grumpy', 'hateful', 'hostile', 'impatient', 'indignant', 'insulted', 'irate', 'irritated', 'mad', 'obstinate', 'offended', 'outraged', 'resentful', 'scornful', 'skeptical', 'stubborn'],
  },
  {
    id: 'fear_and_overwhelm',
    label: 'Threat/distress',
    color: '#ef3333',
    members: ['afraid', 'alarmed', 'alert', 'amazed', 'anxious', 'aroused', 'astonished', 'awestruck', 'bewildered', 'disgusted', 'disoriented', 'distressed', 'disturbed', 'dumbstruck', 'embarrassed', 'frightened', 'horrified', 'hysterical', 'mortified', 'mystified', 'nervous', 'on edge', 'overwhelmed', 'panicked', 'perplexed', 'puzzled', 'rattled', 'scared', 'self-conscious', 'sensitive', 'shaken', 'shocked', 'stressed', 'surprised', 'tense', 'terrified', 'uneasy', 'unnerved', 'unsettled', 'upset', 'worried'],
  },
  {
    id: 'despair_and_shame',
    label: 'Shame/despair',
    color: '#31B9C9',
    members: ['ashamed', 'bitter', 'brooding', 'dependent', 'desperate', 'dispirited', 'envious', 'gloomy', 'grief-stricken', 'guilty', 'heartbroken', 'humiliated', 'hurt', 'infatuated', 'jealous', 'lonely', 'melancholy', 'miserable', 'nostalgic', 'reflective', 'regretful', 'remorseful', 'sad', 'self-critical', 'sorry', 'stuck', 'tormented', 'trapped', 'troubled', 'unhappy', 'vulnerable', 'worthless'],
  },
]
export const EMOTION_CLUSTER_BY_CONCEPT = new Map(EMOTION_SPECTRUM_CLUSTER_GROUPS.flatMap(group => (
  group.members.map(member => [canonicalEmotionConcept(member), group])
)))
const EMOTION_CLUSTER_SORT_INDEX = new Map(
  [...EMOTION_SPECTRUM_CLUSTER_GROUPS]
    .sort((a, b) => emotionClusterMeanRank(a) - emotionClusterMeanRank(b))
    .map((group, index) => [group.id, index]),
)

export function fmt(v) {
  return v == null ? '-' : Number(v).toFixed(4)
}

export function pct(v) {
  return v == null ? '-' : `${Math.round(Number(v) * 100)}%`
}

export function pct1(v) {
  return v == null ? '-' : `${(Number(v) * 100).toFixed(1)}%`
}

export function titleize(value) {
  return String(value || '')
    .replaceAll('_', ' ')
    .replace(/\b\w/g, letter => letter.toUpperCase())
}

export function coordinateTitle(value) {
  return String(value || '')
    .replace(/^assistant_axis_trait__/, '')
    .replace(/^emotion_cluster__/, '')
    .replace(/^emotion__/, '')
    .replace(/^high_stakes__/, '')
    .replaceAll('_', ' ')
    .replace(/\bprobe\b/g, 'signal')
    .replace(/\bmean\b/g, 'average')
}

function canonicalEmotionConcept(value) {
  return String(value || '').toLowerCase().replaceAll('-', ' ').replace(/\s+/g, ' ').trim()
}

export function emotionConceptKey(coordinate) {
  return canonicalEmotionConcept(coordinateTitle(coordinate))
}

function emotionConceptRank(coordinate) {
  const rank = EMOTION_PCA_CONCEPT_INDEX.get(emotionConceptKey(coordinate))
  return rank == null ? EMOTION_PCA_CONCEPT_ORDER.length + 1000 : rank
}

function emotionLogicalRank(coordinate) {
  const rank = EMOTION_LOGICAL_CONCEPT_INDEX.get(emotionConceptKey(coordinate))
  return rank == null ? EMOTION_LOGICAL_CONCEPT_ORDER.length + 1000 : rank
}

function emotionClusterMeanRank(group) {
  const ranks = (group?.members || [])
    .map(member => EMOTION_PCA_CONCEPT_INDEX.get(canonicalEmotionConcept(member)))
    .filter(rank => Number.isFinite(rank))
  return ranks.length ? ranks.reduce((sum, rank) => sum + rank, 0) / ranks.length : EMOTION_PCA_CONCEPT_ORDER.length + 1000
}

function emotionConceptCluster(coordinate) {
  return EMOTION_CLUSTER_BY_CONCEPT.get(emotionConceptKey(coordinate)) || null
}

function emotionClusterSortRank(coordinate) {
  const cluster = emotionConceptCluster(coordinate)
  if (!cluster) return EMOTION_SPECTRUM_CLUSTER_GROUPS.length + 1000
  return EMOTION_CLUSTER_SORT_INDEX.get(cluster.id) ?? EMOTION_SPECTRUM_CLUSTER_GROUPS.length + 1000
}

function compareEmotionConceptCoordinates(a, b) {
  const rankDelta = emotionConceptRank(a) - emotionConceptRank(b)
  if (rankDelta !== 0) return rankDelta
  return coordinateTitle(a).localeCompare(coordinateTitle(b))
}

function compareEmotionClusterCoordinates(a, b) {
  const clusterDelta = emotionClusterSortRank(a) - emotionClusterSortRank(b)
  if (clusterDelta !== 0) return clusterDelta
  return compareEmotionConceptCoordinates(a, b)
}

function compareEmotionLogicalCoordinates(a, b) {
  const rankDelta = emotionLogicalRank(a) - emotionLogicalRank(b)
  if (rankDelta !== 0) return rankDelta
  return coordinateTitle(a).localeCompare(coordinateTitle(b))
}

export function smoothLinePath(points = []) {
  if (!points.length) return ''
  if (points.length === 1) return `M${points[0].x.toFixed(2)},${points[0].y.toFixed(2)}`
  const commands = [`M${points[0].x.toFixed(2)},${points[0].y.toFixed(2)}`]
  for (let index = 0; index < points.length - 1; index += 1) {
    const previous = points[Math.max(0, index - 1)]
    const current = points[index]
    const next = points[index + 1]
    const nextNext = points[Math.min(points.length - 1, index + 2)]
    const cp1x = current.x + (next.x - previous.x) / 6
    const cp1y = current.y + (next.y - previous.y) / 6
    const cp2x = next.x - (nextNext.x - current.x) / 6
    const cp2y = next.y - (nextNext.y - current.y) / 6
    commands.push(
      `C${cp1x.toFixed(2)},${cp1y.toFixed(2)} ${cp2x.toFixed(2)},${cp2y.toFixed(2)} ${next.x.toFixed(2)},${next.y.toFixed(2)}`,
    )
  }
  return commands.join(' ')
}

export function familyTitle(value) {
  if (value === 'assistant_axis') return 'Assistant traits'
  if (value === 'assistant_axis_supplemental') return 'Assistant traits (local)'
  if (value === 'emotion') return 'Emotion concepts'
  if (value === 'emotion_cluster') return 'Emotion clusters'
  if (value === 'high_stakes') return 'High-stakes signals'
  return titleize(value)
}

export function evalLabelTitle(value) {
  if (value === 'DB') return 'State'
  if (value === 'COMMUNICATE') return 'Communication'
  if (value === 'probe_result') return 'Signal result'
  return titleize(value)
}

export function axisIdForCoordinate(coordinate) {
  return String(coordinate || '').replace(/[^a-zA-Z0-9]+/g, '_')
}

function surfaceRows(rows = [], mode = 'absolute', n = 12) {
  return [...rows]
    .filter(row => row?.mean != null)
    .sort((a, b) => {
      if (mode === 'positive') return Number(b.mean) - Number(a.mean)
      if (mode === 'negative') return Number(a.mean) - Number(b.mean)
      return Math.abs(Number(b.mean)) - Math.abs(Number(a.mean))
    })
    .slice(0, n)
}

function histogramPassCorrelation(row) {
  const bins = Array.isArray(row?.histogram) ? row.histogram : []
  let n = 0
  let sumX = 0
  let sumY = 0
  let sumXX = 0
  let sumYY = 0
  let sumXY = 0
  for (const bin of bins) {
    const mid = (Number(bin.bin_start) + Number(bin.bin_end)) / 2
    if (!Number.isFinite(mid)) continue
    const passCount = Number(bin.pass_count || 0)
    const failCount = Number(bin.fail_count ?? Math.max(0, Number(bin.count || 0) - passCount))
    const count = passCount + failCount
    if (!count) continue
    n += count
    sumX += mid * count
    sumXX += mid * mid * count
    sumY += passCount
    sumYY += passCount
    sumXY += mid * passCount
  }
  if (!n) return null
  const xVar = sumXX - (sumX * sumX) / n
  const yVar = sumYY - (sumY * sumY) / n
  if (xVar <= 0 || yVar <= 0) return null
  return (sumXY - (sumX * sumY) / n) / Math.sqrt(xVar * yVar)
}

function passFailCorrelation(row) {
  const value = Number(row?.pass_correlation)
  if (Number.isFinite(value)) return value
  const histogramValue = histogramPassCorrelation(row)
  return Number.isFinite(histogramValue) ? histogramValue : null
}

function passCorrelationMagnitude(row) {
  const value = passFailCorrelation(row)
  return Number.isFinite(value) ? Math.abs(value) : -1
}

function sortByPassCorrelation(rows = []) {
  return [...rows].sort((a, b) => {
    const corrDelta = passCorrelationMagnitude(b) - passCorrelationMagnitude(a)
    if (corrDelta !== 0) return corrDelta
    return Math.abs(Number(b.mean || 0)) - Math.abs(Number(a.mean || 0))
  })
}

function traitRows(rows = [], mode = 'absolute', n = 12) {
  return surfaceRows(rows.filter(row => row.coordinate !== 'assistant_axis'), mode, n)
}

function highStakesProbeDescription(coordinate) {
  const text = String(coordinate || '')
  if (text.includes('finance_cfpb') && text.includes('domain_adapted')) return 'Finance-sensitive signal for refund, payment, cost, and account-action conversations.'
  if (text.includes('finance_cfpb')) return 'Finance-domain signal. Treat it as exposure rather than a calibrated binary label.'
  if (text.includes('anthropic_hh') && text.includes('domain_adapted')) return 'Helpfulness and safety-framing signal for assistant responses.'
  if (text.includes('toolace') && text.includes('domain_adapted')) return 'Tool-use signal. Higher values often track action-heavy conversation turns.'
  if (text.includes('mental_health')) return 'Mental-health signal, most useful when the conversation explicitly enters mental-health content.'
  if (text.includes('aya_redteaming')) return 'Safety/red-teaming signal. Treat as adversarial or safety framing sensitivity, not outcome risk by itself.'
  if (text.includes('mt_balanced') || text.includes('mts_balanced')) return 'Multi-turn signal. Compare early, middle, and late movement rather than reading it as a fixed threshold.'
  if (text.includes('synthetic_test') || text.includes('generic_mean_probe')) return 'General high-stakes signal. Use it as a distributional read, not a standalone classifier.'
  return 'High-stakes probability signal. Interpret it distributionally, not as a calibrated absolute threshold.'
}

function bandRange(row, band) {
  const range = row?.bands?.[band]
  if (!range) return '-'
  return `${fmt(range.min)} to ${fmt(range.max)}`
}

function scoreDetailSummaries(details = []) {
  const buckets = new Map()
  for (const row of details) {
    const key = `${row.score_family}:${row.coordinate}`
    const bucket = buckets.get(key) || {
      score_family: row.score_family,
      coordinate: row.coordinate,
      n: 0,
      sum: 0,
      max: Number.NEGATIVE_INFINITY,
      predictions: new Set(),
    }
    const score = Number(row.score)
    if (Number.isFinite(score)) {
      bucket.n += 1
      bucket.sum += score
      bucket.max = Math.max(bucket.max, score)
    }
    if (row.prediction) bucket.predictions.add(row.prediction)
    buckets.set(key, bucket)
  }
  const priority = row => {
    if (row.score_family === 'assistant_axis') return 0
    if (row.score_family === 'high_stakes') return 1
    if (['emotion__angry', 'emotion__anxious', 'emotion__frustrated', 'emotion__sad', 'emotion__worried'].includes(row.coordinate)) return 2
    return 3
  }
  return [...buckets.values()]
    .filter(row => row.n > 0)
    .map(row => ({
      ...row,
      mean: row.sum / row.n,
      max: row.max === Number.NEGATIVE_INFINITY ? null : row.max,
      prediction: [...row.predictions].join(', '),
    }))
    .sort((a, b) => priority(a) - priority(b) || a.score_family.localeCompare(b.score_family) || a.coordinate.localeCompare(b.coordinate))
}

export function topRows(rows = [], n = 8) {
  return [...rows].slice(0, n)
}

export function average(values = []) {
  const numeric = values.map(Number).filter(Number.isFinite)
  if (!numeric.length) return null
  return numeric.reduce((sum, value) => sum + value, 0) / numeric.length
}

export function groupByValue(rows = [], key) {
  const grouped = new Map()
  for (const row of rows) {
    const value = row?.[key] ?? 'unknown'
    grouped.set(value, [...(grouped.get(value) || []), row])
  }
  return grouped
}

export function chartRows(rows = [], mode = 'absolute', n = 12, valueKey = 'mean', sortRows = null) {
  const filtered = [...rows].filter(row => row?.[valueKey] != null)
  const sorted = sortRows
    ? sortRows(filtered)
    : filtered.sort((a, b) => {
      const av = Number(a[valueKey])
      const bv = Number(b[valueKey])
      if (mode === 'positive') return bv - av
      if (mode === 'negative') return av - bv
      return Math.abs(bv) - Math.abs(av)
    })
  return sorted
    .slice(0, n)
    .map(row => ({
      ...row,
      label: coordinateTitle(row.coordinate),
      value: Number(row[valueKey]),
    }))
    .reverse()
}

const IMPORTANT_TURN_AXES = [
  { id: 'assertive', label: 'Assert', coordinate: 'assistant_axis_trait__assertive', family: 'assistant_axis', valence: 'risk' },
  { id: 'decisive', label: 'Decis', coordinate: 'assistant_axis_trait__decisive', family: 'assistant_axis', valence: 'neutral' },
  { id: 'cautious', label: 'Caution', coordinate: 'assistant_axis_trait__cautious', family: 'assistant_axis', valence: 'protective' },
  { id: 'conciliatory', label: 'Concil', coordinate: 'assistant_axis_trait__conciliatory', family: 'assistant_axis', valence: 'protective' },
  { id: 'sycophantic', label: 'Syc', coordinate: 'assistant_axis_trait__sycophantic', family: 'assistant_axis', valence: 'risk' },
  { id: 'manipulative', label: 'Manip', coordinate: 'assistant_axis_trait__manipulative', family: 'assistant_axis', valence: 'risk' },
  { id: 'hostile', label: 'Hostile', coordinate: 'assistant_axis_trait__hostile', family: 'assistant_axis', valence: 'risk' },
  { id: 'condescending', label: 'Condesc', coordinate: 'assistant_axis_trait__condescending', family: 'assistant_axis', valence: 'risk' },
  { id: 'supportive', label: 'Support', coordinate: 'assistant_axis_trait__supportive', family: 'assistant_axis', valence: 'protective' },
  { id: 'calm_trait', label: 'Calm T', coordinate: 'assistant_axis_trait__calm', family: 'assistant_axis', valence: 'protective' },
  { id: 'technical', label: 'Tech', coordinate: 'assistant_axis_trait__technical', family: 'assistant_axis', valence: 'neutral' },
  { id: 'anxious', label: 'Anxious', coordinate: 'emotion__anxious', family: 'emotion', valence: 'risk' },
  { id: 'frustrated', label: 'Frustr', coordinate: 'emotion__frustrated', family: 'emotion', valence: 'risk' },
  { id: 'worried', label: 'Worried', coordinate: 'emotion__worried', family: 'emotion', valence: 'risk' },
  { id: 'sad', label: 'Sad', coordinate: 'emotion__sad', family: 'emotion', valence: 'risk' },
  { id: 'calm_emotion', label: 'Calm E', coordinate: 'emotion__calm', family: 'emotion', valence: 'protective' },
]

const DEFAULT_TRAJECTORY_COORDINATES = [
  'assistant_axis_trait__assertive',
  'assistant_axis_trait__decisive',
  'assistant_axis_trait__cautious',
  'assistant_axis_trait__conciliatory',
  'assistant_axis_trait__sycophantic',
  'emotion__anxious',
  'emotion__calm',
]

export function mean(values) {
  const numeric = values.map(Number).filter(Number.isFinite)
  return numeric.length ? numeric.reduce((sum, value) => sum + value, 0) / numeric.length : null
}

function scoreValue(row) {
  if (row.score_family === 'high_stakes') return row.high_stakes_probability ?? row.probability ?? row.score
  return row.score
}

export function buildTurnAxisRows(turns = [], details = []) {
  const byTurn = new Map()
  for (const row of details) {
    if (row.turn_index == null) continue
    const rows = byTurn.get(row.turn_index) || []
    rows.push(row)
    byTurn.set(row.turn_index, rows)
  }
  return turns
    .filter(turn => turn.role === 'assistant')
    .map(turn => {
      const rows = byTurn.get(turn.index) || []
      const axes = {}
      for (const axis of IMPORTANT_TURN_AXES) {
        const matching = rows.filter(row => {
          if (row.score_family !== axis.family) return false
          if (axis.coordinate) return row.coordinate === axis.coordinate
          if (axis.highStakes) return String(row.coordinate || '').includes(axis.highStakes)
          return false
        })
        axes[axis.id] = mean(matching.map(scoreValue))
      }
      return {
        turn_index: turn.index,
        preview: String(turn.content || '').replace(/\s+/g, ' ').slice(0, 110),
        axes,
      }
    })
}

export function buildCoordinateTrajectoryRows(turns = [], details = [], coordinates = [], emotionClusters = []) {
  const selected = coordinates.filter(Boolean)
  const assistantTurns = turns.filter(turn => turn.role === 'assistant')
  const byTurn = new Map()
  const clusterMembers = new Map(
    emotionClusters
      .filter(row => row.coordinate && Array.isArray(row.member_coordinates))
      .map(row => [row.coordinate, new Set(row.member_coordinates)])
  )
  for (const row of details) {
    if (row.turn_index == null) continue
    const matchingCoordinates = selected.filter(coordinate => (
      row.coordinate === coordinate || clusterMembers.get(coordinate)?.has(row.coordinate)
    ))
    if (!matchingCoordinates.length) continue
    const value = scoreValue(row)
    if (value == null || !Number.isFinite(Number(value))) continue
    for (const coordinate of matchingCoordinates) {
      const key = `${row.turn_index}:${coordinate}`
      const bucket = byTurn.get(key) || []
      bucket.push(Number(value))
      byTurn.set(key, bucket)
    }
  }
  return assistantTurns.map(turn => {
    const row = { turn: turn.index }
    for (const coordinate of selected) {
      row[axisIdForCoordinate(coordinate)] = mean(byTurn.get(`${turn.index}:${coordinate}`) || [])
    }
    return row
  })
}

export function trajectoryCoordinateOptions(details = [], emotionClusters = []) {
  const byCoordinate = new Map()
  for (const row of details) {
    if (!row.coordinate || row.score_family === 'high_stakes' || byCoordinate.has(row.coordinate)) continue
    byCoordinate.set(row.coordinate, {
      coordinate: row.coordinate,
      family: row.score_family,
      label: coordinateTitle(row.coordinate),
    })
  }
  for (const row of emotionClusters) {
    if (!row.coordinate || byCoordinate.has(row.coordinate)) continue
    byCoordinate.set(row.coordinate, {
      coordinate: row.coordinate,
      family: row.score_family || 'emotion_cluster',
      label: coordinateTitle(row.coordinate),
    })
  }
  const familyPriority = family => {
    if (family === 'assistant_axis') return 0
    if (family === 'emotion') return 1
    if (family === 'emotion_cluster') return 2
    return 3
  }
  return [...byCoordinate.values()].sort((a, b) => (
    familyPriority(a.family) - familyPriority(b.family) ||
    a.label.localeCompare(b.label)
  ))
}

export function defaultTrajectoryCoordinates(options = [], focusedCoordinate = '') {
  const available = new Set(options.map(option => option.coordinate))
  const defaults = focusedCoordinate && available.has(focusedCoordinate)
    ? [focusedCoordinate, ...DEFAULT_TRAJECTORY_COORDINATES.filter(coordinate => coordinate !== focusedCoordinate)]
    : DEFAULT_TRAJECTORY_COORDINATES
  return defaults.filter(coordinate => available.has(coordinate)).slice(0, 6)
}

export function buildProjectionTailThresholds(thresholdRows = []) {
  const thresholds = {}
  for (const axis of IMPORTANT_TURN_AXES) {
    const row = thresholdRows.find(item => item.score_family === axis.family && item.coordinate === axis.coordinate)
    if (!row || row.q80 == null) continue
    thresholds[axis.id] = { low: Number(row.q20), high: Number(row.q80) }
  }
  return thresholds
}

export function buildEmotionSpectrumData(turns = [], details = [], sortMode = 'pca') {
  const emotionRows = details.filter(row => (
    row.score_family === 'emotion' &&
    row.coordinate &&
    String(row.coordinate).startsWith('emotion__') &&
    row.turn_index != null &&
    scoreValue(row) != null &&
    Number.isFinite(Number(scoreValue(row)))
  ))
  if (!emotionRows.length) return null

  const coordinateComparator = sortMode === 'cluster'
    ? compareEmotionClusterCoordinates
    : sortMode === 'logical'
      ? compareEmotionLogicalCoordinates
      : compareEmotionConceptCoordinates
  const coordinates = [...new Set(emotionRows.map(row => row.coordinate))]
    .sort(coordinateComparator)
  const positiveStartIndex = sortMode === 'logical'
    ? coordinates.findIndex(coordinate => emotionLogicalRank(coordinate) >= EMOTION_LOGICAL_CONCEPT_INDEX.get('peaceful'))
    : coordinates.findIndex(coordinate => emotionConceptRank(coordinate) >= EMOTION_PCA_POSITIVE_START_INDEX)
  const byTurn = new Map()
  let maxAbs = 0
  for (const row of emotionRows) {
    const turn = Number(row.turn_index)
    const value = Number(scoreValue(row))
    maxAbs = Math.max(maxAbs, Math.abs(value))
    const turnBucket = byTurn.get(turn) || new Map()
    const coordinateBucket = turnBucket.get(row.coordinate) || []
    coordinateBucket.push(value)
    turnBucket.set(row.coordinate, coordinateBucket)
    byTurn.set(turn, turnBucket)
  }
  const scoredTurnSet = new Set(byTurn.keys())
  let turnRows = turns
    .filter(turn => turn.role === 'assistant' && scoredTurnSet.has(Number(turn.index)))
    .map(turn => ({
      turnIndex: Number(turn.index),
      role: turn.role,
      preview: String(turn.content || '').replace(/\s+/g, ' ').slice(0, 150),
    }))
  if (!turnRows.length) {
    turnRows = [...scoredTurnSet].sort((a, b) => a - b).map(turnIndex => ({
      turnIndex,
      role: 'assistant',
      preview: '',
    }))
  }
  const frames = turnRows.map(turn => {
    const turnBucket = byTurn.get(turn.turnIndex) || new Map()
    const points = coordinates.map((coordinate, index) => {
      const value = mean(turnBucket.get(coordinate) || []) ?? 0
      return {
        coordinate,
        index,
        label: coordinateTitle(coordinate),
        value,
      }
    })
    return {
      ...turn,
      points,
      top: [...points]
        .sort((a, b) => Math.abs(b.value) - Math.abs(a.value))
        .slice(0, 8),
    }
  })
  return {
    coordinates,
    frames,
    positiveStartIndex: positiveStartIndex < 0 ? coordinates.length : positiveStartIndex,
    scale: maxAbs || 1,
    key: `${coordinates.length}:${frames.map(frame => frame.turnIndex).join(',')}`,
  }
}

function turnScoreChips(axisRow, thresholds = {}) {
  if (!axisRow) return []
  return IMPORTANT_TURN_AXES
    .map(axis => {
      const { id, label } = axis
      const value = axisRow.axes[id]
      const numeric = Number(value)
      const threshold = thresholds[id]
      if (!threshold || !Number.isFinite(numeric)) return null
      if (numeric >= threshold.high) {
        if (axis.valence === 'risk') return { id, label, value: numeric, tone: 'bad' }
        if (axis.valence === 'protective') return { id, label, value: numeric, tone: 'good' }
      }
      return null
    })
    .filter(Boolean)
}

const VECTOR_COORDINATES = {
  assistant_axis: 'assistant_axis',
  sycophantic: 'assistant_axis_trait__sycophantic',
  manipulative: 'assistant_axis_trait__manipulative',
  calm: 'assistant_axis_trait__calm',
  supportive: 'assistant_axis_trait__supportive',
  hostile: 'assistant_axis_trait__hostile',
  assertive: 'assistant_axis_trait__assertive',
  decisive: 'assistant_axis_trait__decisive',
  cautious: 'assistant_axis_trait__cautious',
  conciliatory: 'assistant_axis_trait__conciliatory',
}

function projectionThresholdByCoordinate(thresholdRows = []) {
  const byCoordinate = new Map()
  for (const row of thresholdRows) {
    if (row.coordinate) byCoordinate.set(row.coordinate, row)
  }
  return byCoordinate
}

export function buildSessionProjectionDistributions(details = [], vectorDeviations = [], thresholdRows = []) {
  const desired = vectorDeviations.map(row => VECTOR_COORDINATES[row.vector]).filter(Boolean)
  const fallback = [
    'assistant_axis_trait__assertive',
    'assistant_axis_trait__decisive',
    'assistant_axis_trait__cautious',
    'assistant_axis_trait__conciliatory',
    'assistant_axis_trait__sycophantic',
    'emotion__calm',
    'emotion__anxious',
  ]
  const coordinates = [...new Set([...desired, ...fallback])].slice(0, 8)
  const thresholds = projectionThresholdByCoordinate(thresholdRows)
  return coordinates
    .map(coordinate => {
      const values = details
        .filter(row => row.coordinate === coordinate && row.turn_index != null && row.score != null)
        .map(row => ({ turn: Number(row.turn_index), value: Number(row.score) }))
        .filter(row => Number.isFinite(row.value))
      if (!values.length) return null
      const sorted = [...values].sort((a, b) => a.value - b.value)
      const min = sorted[0].value
      const max = sorted[sorted.length - 1].value
      const meanValue = sorted.reduce((sum, row) => sum + row.value, 0) / sorted.length
      const threshold = thresholds.get(coordinate)
      return {
        coordinate,
        label: coordinateTitle(coordinate),
        min,
        max,
        mean: meanValue,
        q20: threshold?.q20,
        q80: threshold?.q80,
        values,
        tailCount: values.filter(row => (
          threshold && (
            (threshold.q80 != null && row.value >= Number(threshold.q80)) ||
            (threshold.q20 != null && row.value <= Number(threshold.q20))
          )
        )).length,
      }
    })
    .filter(Boolean)
    .sort((a, b) => b.tailCount - a.tailCount || Math.abs(b.mean) - Math.abs(a.mean))
    .slice(0, 6)
}
