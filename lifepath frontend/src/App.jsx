import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Activity, AlertCircle, ArrowDownRight, ArrowRight, ArrowUpRight, Bell, BookOpenCheck,
  CalendarDays, Check, CheckCircle2, ChevronDown, ChevronRight, CircleHelp, CircleUserRound,
  ClipboardCheck, Clock3, CloudUpload, FileCheck2, FileText, GraduationCap, LayoutDashboard,
  ListChecks, LoaderCircle, Menu, MoreHorizontal, PanelLeftClose, Search, ShieldCheck,
  Sparkles, Upload, X, XCircle
} from 'lucide-react'

const API_BASE = (import.meta.env.VITE_API_BASE_URL ||
  (import.meta.env.PROD ? 'https://lifepath-firstcommit-26.onrender.com' : 'http://127.0.0.1:8000')).replace(/\/$/, '')

function workspaceToken() {
  let token = localStorage.getItem('lifepath-workspace-token')
  if (!/^[0-9a-f]{64}$/.test(token || '')) {
    token = Array.from(crypto.getRandomValues(new Uint8Array(32)), b => b.toString(16).padStart(2, '0')).join('')
    localStorage.setItem('lifepath-workspace-token', token)
  }
  return token
}

function workspaceFetch(url, options = {}) {
  return fetch(url, { ...options, headers: { ...options.headers, 'X-Workspace-Token': workspaceToken() } })
}

async function readApiJson(response, operation) {
  const text = await response.text()
  let payload = null
  if (text.trim()) {
    try {
      payload = JSON.parse(text)
    } catch {
      if (!response.ok) {
        throw new Error(`${operation} could not be completed (HTTP ${response.status}). Please try again.`)
      }
      throw new Error(`${operation} returned an unreadable response. Please try again.`)
    }
  }

  if (!response.ok) {
    const detail = payload?.detail
    const message = typeof detail === 'string' ? detail : detail?.message
    if (message) throw new Error(message)
    if ([502, 503, 504].includes(response.status)) {
      throw new Error(`The service did not finish this request (HTTP ${response.status}). Please try again.`)
    }
    throw new Error(`${operation} failed (HTTP ${response.status}). Please try again.`)
  }
  if (payload === null) throw new Error(`${operation} returned an empty response. Please try again.`)
  return payload
}
const todayLabel = new Intl.DateTimeFormat('en-IN', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric', timeZone: 'Asia/Kolkata' }).format(new Date()).toUpperCase()
const fallbackJourney = {
  university: 'Demo National University', programme: 'B.Sc. 2027–28',
  notice: 'Undergraduate Admission Bulletin · 2027–28',
  warning: 'This is fictional demonstration data. Always verify details with the official university notification.',
  eligibility: [
    { name: 'Academic qualification', detail: 'Class 12 or equivalent from a recognised board', status: 'Met' },
    { name: 'Minimum aggregate', detail: 'At least 50% aggregate marks in qualifying examination', status: 'Review' },
    { name: 'Subject requirement', detail: 'Mathematics or Biology as a subject in Class 12', status: 'Met' },
  ],
  documents: [
    { name: 'Class 10 marksheet', kind: 'Mandatory', status: 'Ready' },
    { name: 'Class 12 marksheet', kind: 'Mandatory', status: 'Needed' },
    { name: 'Category certificate', kind: 'Conditional', status: 'If applicable' },
    { name: 'Transfer certificate', kind: 'Mandatory', status: 'Needed' },
    { name: 'Passport-size photograph', kind: 'Mandatory', status: 'Ready' },
    { name: 'Sports achievement proof', kind: 'Optional', status: 'Optional' },
  ],
  steps: [
    { title: 'Review your eligibility', description: 'Check subject and aggregate requirements against your Class 12 results.', date: 'Before applying', status: 'complete', page: 3 },
    { title: 'Prepare your documents', description: 'Gather readable scans of your marksheets and supporting certificates.', date: 'Before applying', status: 'current', page: 5 },
    { title: 'Create your applicant account', description: 'Register on the university admissions portal with an active email and phone.', date: '10 Apr 2027', page: 2 },
    { title: 'Submit the application', description: 'Complete the online form and review every field before submission.', date: '24 Apr 2027', page: 2 },
    { title: 'Pay the application fee', description: 'Complete payment and save the transaction receipt for your records.', date: '24 Apr 2027', page: 2 },
    { title: 'Track application review', description: 'Check the portal for status updates or requests for additional information.', date: 'May 2027', page: 7 },
    { title: 'Check the merit list', description: 'Review the published list and follow the relevant outcome below.', date: '18 Jun 2027', page: 8 },
    { title: 'Complete admission formalities', description: 'Selected students verify documents and pay the admission fee.', date: 'By 25 Jun 2027', branch: 'selected', page: 9 },
    { title: 'Explore next options', description: 'If not selected, review waitlist movement and other available choices.', date: 'After result', branch: 'not_selected', page: 9 },
  ],
  outcomes: {
    selected: ['Accept your offer in the admission portal', 'Attend original document verification', 'Pay the admission fee before the deadline', 'Save your final admission confirmation'],
    not_selected: ['Check if you are on the waitlist', 'Track the next merit list release', 'Contact admissions support about next steps', 'Keep backup programme applications active'],
  },
  deadlines: [
    { label: 'Application opens', date: '10 Apr 2027', state: 'done' },
    { label: 'Application deadline', date: '24 Apr 2027', state: 'next' },
    { label: 'Merit list published', date: '18 Jun 2027', state: 'upcoming' },
    { label: 'Admission confirmation', date: '25 Jun 2027', state: 'upcoming' },
  ],
}

const iconMap = { Overview: LayoutDashboard, Journey: ListChecks, Documents: FileCheck2, Eligibility: ShieldCheck, Profile: CircleUserRound }
const navItems = ['Overview', 'Journey', 'Documents', 'Eligibility', 'Profile']

function firstValue(object, keys, fallback = '') {
  for (const key of keys) if (object?.[key] !== undefined && object?.[key] !== null) return object[key]
  return fallback
}
function asArray(value) { return Array.isArray(value) ? value : [] }
function normalizeJourney(payload) {
  const root = payload?.data || payload?.journey || payload || {}
  const rawSteps = asArray(firstValue(root, ['steps', 'journey_steps', 'admission_steps'], []))
  const rawDocs = asArray(firstValue(root, ['documents', 'document_checklist', 'required_documents'], []))
  const rawEligibility = asArray(firstValue(root, ['eligibility', 'eligibility_requirements', 'requirements'], []))
  const rawDeadlines = asArray(firstValue(root, ['deadlines', 'timeline'], []))
  const stepItems = rawSteps.length ? rawSteps.map((s, i) => ({
    title: firstValue(s, ['title', 'name', 'label'], `Admission step ${i + 1}`),
    description: firstValue(s, ['description', 'details', 'instruction'], 'Review this requirement and follow the instructions in the notice.'),
    date: firstValue(s, ['deadline', 'date', 'due_date'], 'See notice'),
    page: firstValue(s, ['page', 'page_number', 'source_page'], null),
    status: s.completed ? 'complete' : 'locked' in s && s.locked ? 'locked' : 'todo',
    branch: firstValue(s, ['branch', 'outcome'], ''),
  })) : fallbackJourney.steps
  const docs = rawDocs.length ? rawDocs.map(d => ({
    name: firstValue(d, ['name', 'title', 'document'], 'Document'),
    kind: firstValue(d, ['kind', 'type', 'requirement'], 'Mandatory'),
    status: firstValue(d, ['status'], 'Needed'),
  })) : fallbackJourney.documents
  const eligibility = rawEligibility.length ? rawEligibility.map(e => ({
    name: firstValue(e, ['name', 'title', 'requirement'], 'Eligibility requirement'),
    detail: firstValue(e, ['description', 'details', 'value'], 'Review the official admission notice.'),
    status: firstValue(e, ['status'], 'Review'),
  })) : fallbackJourney.eligibility
  return {
    ...fallbackJourney, ...root,
    university: firstValue(root, ['university', 'university_name', 'institution'], fallbackJourney.university),
    programme: firstValue(root, ['programme', 'program', 'course', 'programme_name'], fallbackJourney.programme),
    notice: firstValue(root, ['notice', 'notice_title', 'title'], fallbackJourney.notice),
    warning: firstValue(root, ['warning', 'disclaimer'], fallbackJourney.warning),
    steps: stepItems, documents: docs, eligibility,
    deadlines: rawDeadlines.length ? rawDeadlines.map(d => ({ label: firstValue(d, ['label', 'title', 'name'], 'Deadline'), date: firstValue(d, ['date', 'deadline', 'due_date'], 'See notice'), state: 'upcoming' })) : fallbackJourney.deadlines,
    outcomes: root.outcomes || root.branches || fallbackJourney.outcomes,
  }
}
function normalizeBackendJourney(data, analysisData) {
  const rawSteps = data.steps || []

  const steps = rawSteps.map((step, index) => ({
    key: step.key,
    kind: step.kind,
    lockedReason: step.locked_reason,
    backendStatus: step.status,
    title: step.title || `Admission step ${index + 1}`,
    description:
      step.guidance?.what_to_do ||
      step.sources?.[0]?.explanation ||
      step.notes?.join(' ') ||
      'Review this step carefully.',
    date: step.deadlines?.[0]?.date_iso ||
      'See notice',
    page: step.sources?.[0]?.page || null,
    status: step.status === 'completed' ? 'complete' :
      step.status === 'locked' ? 'locked' : 'todo',
    branch: step.branch || '',
  }))

  const documents = [
    ...new Map(
      rawSteps.flatMap(step => step.documents || [])
        .map(doc => [doc.name, {
          name: doc.name,
          kind: ({ mandatory: 'Mandatory', conditional: 'Conditional', optional: 'Optional', not_specified: 'Not specified', not_required: 'Not required' })[doc.level] || 'Not specified',
          status: 'Needed',
        }])
    ).values()
  ]

  const deadlines = rawSteps.flatMap(step =>
    (step.deadlines || []).map(d => ({
      label: d.label || 'Admission deadline',
      date: d.date_iso || 'See notice',
      state: d.date_status || 'upcoming',
    }))
  )

  return {
    university: analysisData.institution || 'Institution in admission notice',
    programme: analysisData.programme || 'Admission programme',
    notice: analysisData.title || 'Uploaded admission notice',
    academicYear: analysisData.academic_year || 'See notice',
    warning: 'AI can make mistakes. Check all requirements and dates against the official notice.',
    steps,
    documents,
    eligibility: (analysisData.items || []).filter(item => item.category === 'eligibility' && item.review_state !== 'rejected' && (item.quote_check === 'verified' || ['accepted', 'edited'].includes(item.review_state))).map(item => ({ name: item.name, detail: item.explanation, status: 'Review' })),
    deadlines,
    outcomes: { selected: [], not_selected: [] },
  }
}
function Badge({ children, tone = 'neutral', className = '' }) { return <span className={`badge badge-${tone} ${className}`}>{children}</span> }
function SectionTitle({ eyebrow, title, action }) { return <div className="section-title"><div><div className="eyebrow">{eyebrow}</div><h2>{title}</h2></div>{action}</div> }

function savedProgress(id = localStorage.getItem('lifepath-analysis-id')) {
  try {
    const saved = JSON.parse(localStorage.getItem(`lifepath-completed:${id}`) || '[]')
    return Array.isArray(saved) ? saved.filter(n => Number.isInteger(n) && n >= 0) : []
  } catch {
    return []
  }
}

function App() {
  const [page, setPage] = useState('Overview')
  const [journey, setJourney] = useState(null)
  const [source, setSource] = useState('loading')
  const [apiError, setApiError] = useState('')
  const [apiErrorTitle, setApiErrorTitle] = useState('Backend unavailable.')
  const [selected, setSelected] = useState(() => savedProgress())
  const [branch, setBranch] = useState('selected')
  const [mobileMenu, setMobileMenu] = useState(false)
  const [file, setFile] = useState(null)
  const [analysis, setAnalysis] = useState(null)
  const [savedAnalyses, setSavedAnalyses] = useState([])
  const [uploadBusy, setUploadBusy] = useState(false)
  const [toast, setToast] = useState('')
  const progressUpdate = useRef(false)

  async function loadJourney() {
    const id = localStorage.getItem('lifepath-analysis-id')
    if (!id) { setSource('empty'); await refreshAnalyses(); return }
    setSource('loading'); setApiError('')
    try {
      const response = await workspaceFetch(`${API_BASE}/api/analyses/${id}`)
      const payload = await readApiJson(response, 'Loading your notice')
      setAnalysis(payload)
      const preview = await workspaceFetch(`${API_BASE}/api/analyses/${id}/journey`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({})
      })
      let restored = normalizeBackendJourney(await readApiJson(preview, 'Loading your journey'), payload)
      const saved = savedProgress(id).filter(i => i < restored.steps.length)
      const completed = saved.map(i => restored.steps[i]).filter(s => s?.kind !== 'suggested').map(s => s.key)
      if (completed.length) {
        const checked = await workspaceFetch(`${API_BASE}/api/analyses/${id}/journey`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ completed })
        })
        restored = normalizeBackendJourney(await readApiJson(checked, 'Restoring your progress'), payload)
      }
      setJourney(restored)
      setSelected(saved.filter(i => restored.steps[i]?.kind === 'suggested' || restored.steps[i]?.status === 'complete'))
      setSource('analysis')
    } catch (error) {
      setSource('empty')
      setApiErrorTitle('Could not restore your journey.')
      setApiError(error.message || 'Please try again.')
    }
  }
  async function refreshAnalyses() {
    try {
      const response = await workspaceFetch(`${API_BASE}/api/analyses`)
      setSavedAnalyses(await readApiJson(response, 'Loading saved notices'))
    } catch (error) {
      setApiErrorTitle('Could not load saved notices.')
      setApiError(error.message || 'Please try again.')
    }
  }
  useEffect(() => { loadJourney() }, [])
  const steps = journey?.steps || []
  const countedSteps = steps.map((step, i) => ({ step, i })).filter(({ step }) => step.kind !== 'suggested' && (!step.branch || step.branch === branch))
  const done = countedSteps.filter(({ i }) => selected.includes(i)).length
  const documentItems = journey?.documents || []
  const eligibility = journey?.eligibility || []
  const progress = countedSteps.length ? Math.round(done / countedSteps.length * 100) : 0
  const upcoming = steps.find((s, i) => !selected.includes(i) && !s.branch) || steps.find(s => s.branch === branch) || steps[0]
  const filteredSteps = useMemo(() => steps.filter(s => !s.branch || s.branch === branch), [steps, branch, journey])

  async function toggleStep(index) {
    if (progressUpdate.current || !analysis) return
    const step = steps[index]
    if (!selected.includes(index) && ['locked', 'conditional', 'not_applicable'].includes(step.backendStatus)) {
      showToast(step.lockedReason || 'Complete the earlier steps first.')
      return
    }
    const next = selected.includes(index) ? selected.filter(i => i !== index) : [...selected, index]
    progressUpdate.current = true
    try {
      const completed = next.map(i => steps[i]).filter(s => s?.kind !== 'suggested').map(s => s.key)
      const response = await workspaceFetch(`${API_BASE}/api/analyses/${analysis.id}/journey`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ completed, outcome: step.branch ? branch : null })
      })
      const preview = await readApiJson(response, 'Updating the journey')
      const updated = normalizeBackendJourney(preview, analysis)
      const suggested = next.filter(i => steps[i]?.kind === 'suggested')
      const valid = updated.steps.map((s, i) => s.status === 'complete' ? i : -1).filter(i => i >= 0)
      const saved = [...new Set([...suggested, ...valid])]
      setJourney(updated); setSelected(saved)
      localStorage.setItem(`lifepath-completed:${analysis.id}`, JSON.stringify(saved))
    } catch (error) {
      setApiErrorTitle('Could not update the journey.')
      setApiError(error.message || 'Please try again.')
    } finally { progressUpdate.current = false }
  }
  function showToast(message) { setToast(message); window.setTimeout(() => setToast(''), 2800) }
  async function uploadNotice() {
    if (!file) {
      showToast('Please choose a PDF first.')
      return
    }

    setUploadBusy(true)
    setApiError('')
    setApiErrorTitle('Notice analysis failed.')

    try {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('title', file.name.replace(/\.pdf$/i, ''))

      const response = await workspaceFetch(`${API_BASE}/api/analyses`, {
        method: 'POST',
        body: formData
      })

      const payload = await readApiJson(response, 'Analysing the notice')

      setAnalysis(payload)
      localStorage.setItem('lifepath-analysis-id', payload.id)
      const journeyResponse = await workspaceFetch(`${API_BASE}/api/analyses/${payload.id}/journey`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
      })

      const journeyPayload = await readApiJson(journeyResponse, 'Building the admission journey')

      setJourney(normalizeBackendJourney(journeyPayload, payload))
      setSource('analysis')
      setSelected([])
      localStorage.removeItem(`lifepath-completed:${payload.id}`)
      showToast(`Notice processed. ${payload.counts?.items ?? 0} items extracted.`)
    } catch (error) {
      setApiErrorTitle('Notice analysis failed.')
      setApiError(error.message || 'Could not process this notice.')
    } finally {
      setUploadBusy(false)
    }
  }

  async function resolveConflict(conflict, side = null) {
    try {
      setApiError('')
      setApiErrorTitle('Could not update the journey.')
      const response = await workspaceFetch(
        `${API_BASE}/api/analyses/${analysis.id}/conflicts/resolve`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            conflict_key: conflict.key,
            chosen_item_id: side ? side.item_id : null,
            note: side
              ? 'Reviewed and selected by the applicant.'
              : 'Reviewed by the applicant. Both source requirements are retained.'
          })
        }
      )

      const updatedAnalysis = await readApiJson(response, 'Saving your conflict decision')

      setAnalysis(updatedAnalysis)

      if (updatedAnalysis.counts.unresolved_conflicts === 0) {
        const journeyResponse = await workspaceFetch(
          `${API_BASE}/api/analyses/${analysis.id}/journey`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({})
          }
        )

        const journeyPayload = await readApiJson(journeyResponse, 'Building the admission journey')

        setJourney(normalizeBackendJourney(journeyPayload, updatedAnalysis))
        setSource('analysis')
        setSelected([])
        localStorage.removeItem(`lifepath-completed:${analysis.id}`)
        showToast('All conflicts reviewed. Your journey is ready!')
      } else {
        showToast('Conflict decision saved.')
      }
    } catch (error) {
      setApiErrorTitle('Could not update the journey.')
      setApiError(error.message || 'Could not resolve conflict.')
    }
  }

  function navigate(item) { setPage(item); setMobileMenu(false); window.scrollTo({ top: 0, behavior: 'smooth' }) }

  if (!journey) return <main className="page-wrap">
    <div className="welcome-row"><div><div className="eyebrow">LIFEPATH</div><h1>Your admission journey</h1><p>Upload an admission notice to create your roadmap.</p></div></div>
    {apiError && <div className="connection-alert"><AlertCircle size={16} /><span><b>{apiErrorTitle}</b> {apiError}</span><button onClick={() => setApiError('')} aria-label="Dismiss"><X size={16} /></button></div>}
    {source === 'loading' ? <div className="loading-state">Loading your journey…</div> : <section className="panel" style={{padding: 24}}>
      <h2>Start with an admission notice</h2><p>Choose a text-based PDF. Notice text is sent to the AI service for analysis. Check results against the official notice.</p>
      <p>Saved notices are tied to this browser. Clearing browser data removes access; account recovery is not available yet.</p>
      <label className="upload-button"><Upload size={15} /> {file ? 'Replace notice' : 'Choose a PDF'}<input type="file" accept=".pdf,application/pdf" onChange={e => setFile(e.target.files?.[0] || null)} /></label>
      {file && <p>{file.name}</p>}<button className="primary-button" disabled={!file || uploadBusy} onClick={uploadNotice}>{uploadBusy ? 'Processing notice…' : 'Upload and analyse'}</button>
      {localStorage.getItem('lifepath-analysis-id') && <button className="outline-button" onClick={loadJourney}>Return to saved journey</button>}
      {savedAnalyses.length > 0 && <div><h3>Saved notices on this browser</h3>{savedAnalyses.map(item => <button className="outline-button" key={item.id} onClick={() => { localStorage.setItem('lifepath-analysis-id', item.id); loadJourney() }}>{item.title || 'Untitled notice'}</button>)}</div>}
      {analysis?.conflicts?.filter(c => !c.resolved).map(conflict => <div key={conflict.key}><h3>{conflict.title}</h3>{conflict.sides.map(side => <div key={side.item_id}><p>{side.document_name} · Page {side.page}: {side.value}</p><blockquote>{side.quote}</blockquote><button className="outline-button" onClick={() => resolveConflict(conflict, side)}>Choose this information</button></div>)}</div>)}
    </section>}
  </main>

  return <div className="app-shell">
    <aside className={`sidebar ${mobileMenu ? 'sidebar-open' : ''}`}>
      <a className="brand" href="#overview" onClick={e => { e.preventDefault(); navigate('Overview') }}><span className="brand-mark"><Activity size={19} strokeWidth={2.6} /></span><span>LIFE<span className="brand-light">PATH</span></span></a>
      <div className="team-pill"><span className="team-dot" /> UNSCRIPTED MINDS <span className="hack-tag">FC '26</span></div>
      <div className="side-label">WORKSPACE</div>
      <nav>{navItems.map(item => { const Icon = iconMap[item]; return <button key={item} onClick={() => navigate(item)} className={`nav-link ${page === item ? 'active' : ''}`}><Icon size={18} /><span>{item}</span>{item === 'Journey' && <span className="nav-count">{steps.length || '—'}</span>}</button> })}</nav>
      <div className="sidebar-bottom">
        <div className="help-card"><div className="help-icon"><CircleHelp size={17} /></div><b>Need a hand?</b><span>Know what to do, one step at a time.</span><button onClick={() => showToast('Your admission journey is ready to explore.')}>Explore your journey <ArrowRight size={14} /></button></div>
        <div className="user-mini"><div className="avatar">A</div><div><b>Applicant</b><span>Student workspace</span></div><MoreHorizontal size={18} className="muted-icon" /></div>
      </div>
    </aside>
    {mobileMenu && <button className="scrim" aria-label="Close menu" onClick={() => setMobileMenu(false)} />}
    <main className="main-area">
      <header className="topbar"><button className="icon-button menu-button" onClick={() => setMobileMenu(!mobileMenu)} aria-label="Open menu"><Menu size={20} /></button><div className="breadcrumb">Workspace <ChevronRight size={14} /> <strong>{page}</strong></div><div className="top-actions"><div className="search-box"><Search size={16} /><span>Search anything...</span><kbd>⌘ K</kbd></div><button className="icon-button notification" aria-label="Notifications" onClick={() => showToast('You’re all caught up.')}><Bell size={18} /><i /></button><div className="avatar top-avatar">A</div></div></header>
      <div className="page-wrap">
        <div className="demo-notice"><div className="demo-icon"><Sparkles size={15} /></div><div><b>UPLOADED NOTICE</b><span>Review the extracted information against the official notice before relying on it.</span></div><button onClick={() => { setAnalysis(null); setJourney(null); setFile(null); setSource('empty'); setApiError(''); refreshAnalyses() }}>New notice</button></div>
        {apiError && <div className="connection-alert"><AlertCircle size={16} /><span><b>{apiErrorTitle}</b> {apiError}</span><button onClick={() => setApiError('')} aria-label="Dismiss"><X size={16} /></button></div>}
        {analysis?.conflicts?.some(c => !c.resolved) && (
  <section className="panel" style={{ marginBottom: 24, padding: 24, color: '#222222', background: '#ffffff' }}>
    <h2>Review conflicting information</h2>
    <p>Compare the official sources and choose which information should guide your journey.</p>

    {analysis.conflicts.filter(c => !c.resolved).map(conflict => (
      <div key={conflict.key} style={{ borderTop: '1px solid #ddd', padding: '18px 0' }}>
        <h3>{conflict.title}</h3>

        {conflict.sides.map(side => (
          <div key={side.item_id} style={{ margin: '14px 0', padding: 14, background: '#f5f5f5', borderRadius: 10 }}>
            <b>{side.document_name} · Page {side.page}</b>
            <p>{side.value}</p>
            <blockquote>{side.quote}</blockquote>
            <button
              className="primary-button"
              onClick={() => resolveConflict(conflict, side)}
            >
              Choose this information
            </button>
          </div>
        ))}
        <button
  className="primary-button"
  style={{ marginTop: 12 }}
  onClick={() => resolveConflict(conflict, null)}
>
  Keep both requirements
</button>
      </div>
    ))}
  </section>
)}
        {source === 'loading' && !journey ? <div className="loading-state"><LoaderCircle className="spin" size={26} /><span>Loading your admission journey…</span></div> : <>
          {page === 'Overview' && <Overview journey={journey} steps={steps} selected={selected} done={done} total={countedSteps.length} progress={progress} upcoming={upcoming} branch={branch} setBranch={setBranch} navigate={navigate} toggleStep={toggleStep} file={file} setFile={setFile} showToast={showToast} uploadNotice={uploadNotice} uploadBusy={uploadBusy} />}
          {page === 'Journey' && <JourneyPage journey={journey} steps={filteredSteps} selected={selected} done={done} total={countedSteps.length} toggleStep={toggleStep} branch={branch} setBranch={setBranch} />}
          {page === 'Documents' && <DocumentsPage documents={documentItems} />}
          {page === 'Eligibility' && <EligibilityPage requirements={eligibility} warning={journey.warning} />}
          {page === 'Profile' && <ProfilePage showToast={showToast} />}
        </>}
      </div>
      <footer className="footer"><span>© 2026 LIFEPATH · Unscripted Minds</span><span><span className="live-dot" /> {source === 'analysis' || source === 'api' ? 'Backend connected' : 'Demo preview'} <span className="footer-sep">·</span> FirstCommit '26</span></footer>
    </main>
    {toast && <div className="toast"><CheckCircle2 size={17} />{toast}</div>}
  </div>
}

function Overview({ journey, steps, selected, done, total, progress, upcoming, branch, setBranch, navigate, toggleStep, file, setFile, showToast, uploadNotice, uploadBusy }) {
  const nextIndex = Math.max(0, steps.findIndex((s, i) => !selected.includes(i) && !s.branch))
  return <>
    <div className="welcome-row"><div><div className="eyebrow">{todayLabel} <span className="tiny-line" /> YOUR ADMISSION HQ</div><h1>Good morning, <span>Applicant.</span></h1><p>Your path to admission, made clear. One step at a time.</p></div><button className="primary-button" onClick={() => navigate('Journey')}><ListChecks size={17} /> View my journey <ArrowRight size={16} /></button></div>
    <section className="hero-card"><div className="hero-glow" /><div className="hero-copy"><Badge tone="blue"><span className="badge-dot" /> YOUR ACTIVE JOURNEY</Badge><h2>{journey.programme}</h2><p className="university"><GraduationCap size={16} /> {journey.university}</p><div className="hero-meta"><span><CalendarDays size={15} /> Admission cycle {journey.academicYear}</span><span><FileText size={15} /> {journey.notice}</span></div><button className="hero-link" onClick={() => navigate('Journey')}>Open admission journey <ArrowRight size={16} /></button></div><div className="progress-ring-wrap"><div className="progress-ring" style={{ '--progress': `${progress}%` }}><div><strong>{progress}%</strong><span>COMPLETE</span></div></div><span className="progress-caption">{done} of {total} supported steps done</span></div><div className="hero-shape shape-one" /><div className="hero-shape shape-two" /></section>
    <section className="stats-grid"><StatCard label="Journey progress" value={`${progress}%`} detail={`${done} steps completed`} icon={<Activity size={17} />} trend={progress ? 'up' : null} /><StatCard label="Next deadline" value={upcoming?.date || 'See notice'} detail={upcoming?.title || 'Review your next step'} icon={<Clock3 size={17} />} accent="amber" /><StatCard label="Documents ready" value={`${journey.documents.filter(d => d.status === 'Ready').length}/${journey.documents.filter(d => d.kind === 'Mandatory').length}`} detail="Mandatory documents" icon={<FileCheck2 size={17} />} accent="green" /><StatCard label="Eligibility check" value="In progress" detail={`${journey.eligibility.length} requirements to review`} icon={<ShieldCheck size={17} />} accent="violet" /></section>
    <div className="content-grid overview-grid"><section className="panel journey-preview"><SectionTitle eyebrow="YOUR NEXT STEPS" title="Admission journey" action={<button className="text-button" onClick={() => navigate('Journey')}>View all <ArrowRight size={14} /></button>} /><div className="mini-steps">{steps.slice(0, 4).map((step, i) => <div className={`mini-step ${selected.includes(i) || step.status === 'complete' ? 'mini-done' : i === nextIndex ? 'mini-current' : ''}`} key={step.title}><button className="step-check" onClick={() => toggleStep(i)}>{selected.includes(i) || step.status === 'complete' ? <Check size={13} /> : <span>{String(i + 1).padStart(2, '0')}</span>}</button><div className="mini-step-body"><div className="mini-step-top"><b>{step.title}</b><span>{step.date}</span></div><p>{step.description}</p></div></div>)}</div><button className="outline-button full-button" onClick={() => navigate('Journey')}>Continue your journey <ArrowRight size={15} /></button></section>
      <div className="right-stack"><section className="panel deadline-panel"><SectionTitle eyebrow="DON'T MISS A DATE" title="Key deadlines" action={<button className="icon-plain" onClick={() => showToast('Verify all dates with the official notice.')}><MoreHorizontal size={18} /></button>} /><div className="deadline-list">{journey.deadlines.map((d, i) => <div className="deadline-item" key={d.label}><span className="deadline-marker"></span><div><b>{d.label}</b><span>{d.date}</span></div><Badge tone="neutral">Verify</Badge></div>)}</div></section>
      <section className="upload-card"><div className="upload-card-top"><div className="upload-icon"><CloudUpload size={18} /></div><Badge tone="neutral">NOTICE UPLOAD</Badge></div><h3>Have an admission notice?</h3><p>Upload an official admission notice to extract requirements and build your personalised journey.</p><label className="upload-button"><Upload size={15} /> {file ? 'Replace notice' : 'Choose a PDF'}<input type="file" accept=".pdf,application/pdf" onChange={e => setFile(e.target.files?.[0] || null)} /></label>

{file && <div className="file-selected"><FileText size={14} />{file.name}</div>}

<button
  className="upload-button"
  type="button"
  disabled={!file || uploadBusy}
  onClick={uploadNotice}
>
  <CloudUpload size={15} />
  {uploadBusy ? 'Processing notice...' : 'Upload and analyse'}
</button></section></div></div>
    <div className="content-grid lower-grid"><section className="panel docs-panel"><SectionTitle eyebrow="GET PREPARED" title="Document checklist" action={<button className="text-button" onClick={() => navigate('Documents')}>See all <ArrowRight size={14} /></button>} /><div className="doc-preview-list">{journey.documents.slice(0, 4).map((d, i) => <div className="doc-row" key={d.name}><span className={`doc-type-icon ${d.status === 'Ready' ? 'doc-ready' : ''}`}>{d.status === 'Ready' ? <Check size={15} /> : <FileText size={15} />}</span><div className="doc-row-name"><b>{d.name}</b><span>{d.kind}</span></div><span className={`doc-status ${d.status === 'Ready' ? 'status-ready' : ''}`}>{d.status}</span></div>)}</div></section><section className="panel outcome-panel"><div className="outcome-head"><div><div className="eyebrow">PLAN FOR EVERY OUTCOME</div><h2>Your next chapter</h2></div><div className="segmented"><button className={branch === 'selected' ? 'chosen' : ''} onClick={() => setBranch('selected')}>Selected</button><button className={branch === 'not_selected' ? 'chosen' : ''} onClick={() => setBranch('not_selected')}>Not selected</button></div></div><div className="outcome-content"><div className={`outcome-icon ${branch === 'selected' ? 'outcome-good' : 'outcome-alt'}`}>{branch === 'selected' ? <GraduationCap size={20} /> : <ArrowDownRight size={20} />}</div><div><b>{branch === 'selected' ? 'If you are selected' : 'There are still paths forward.'}</b><span>{(journey.outcomes?.[branch] || [])[0] || 'Check the official notice for your next action.'}</span></div><button className="icon-button small" onClick={() => navigate('Journey')} aria-label="Explore branch"><ArrowRight size={16} /></button></div><button className="subtle-link" onClick={() => navigate('Journey')}>Explore the {branch === 'selected' ? 'selected' : 'not selected'} journey <ArrowRight size={14} /></button></section></div>
  </>
}

function StatCard({ label, value, detail, icon, trend, accent = 'blue' }) { return <div className="stat-card"><div className={`stat-icon icon-${accent}`}>{icon}</div><span className="stat-label">{label}</span><div className="stat-value">{value}{trend && <ArrowUpRight size={16} className="trend" />}</div><span className="stat-detail">{detail}</span></div> }

function JourneyPage({ journey, steps, selected, done, total, toggleStep, branch, setBranch }) {
  const outcomes = journey.outcomes?.[branch] || []
  return <><PageHeading eyebrow="YOUR PERSONAL ROADMAP" title="Admission journey" description="Every step, deadline, and decision in one clear path." /><section className="panel journey-page-panel"><div className="journey-toolbar"><div className="journey-summary"><span className="journey-progress-mark"><Activity size={17} /></span><div><b>{journey.programme}</b><span>{done} of {total} supported steps complete</span></div></div><div className="segmented branch-switch"><button className={branch === 'selected' ? 'chosen' : ''} onClick={() => setBranch('selected')}><CheckCircle2 size={14} /> Selected</button><button className={branch === 'not_selected' ? 'chosen' : ''} onClick={() => setBranch('not_selected')}><XCircle size={14} /> Not selected</button></div></div><div className="journey-list">{steps.map((step) => { const originalIndex = journey.steps.indexOf(step); const completed = selected.includes(originalIndex) || step.status === 'complete'; return <article className={`journey-step ${completed ? 'journey-step-complete' : ''}`} key={`${step.title}-${originalIndex}`}><div className="journey-rail"><button className={`journey-node ${completed ? 'node-done' : ''}`} onClick={() => toggleStep(originalIndex)}>{completed ? <Check size={14} /> : <span>{String(originalIndex + 1).padStart(2, '0')}</span>}</button></div><div className="journey-step-card"><div className="journey-step-heading"><div><div className="journey-step-meta"><Badge tone={step.branch ? (branch === 'selected' ? 'green' : 'violet') : completed ? 'green' : 'blue'}>{step.branch ? (step.branch === 'selected' ? 'IF SELECTED' : 'IF NOT SELECTED') : completed ? 'COMPLETED' : 'STEP'}</Badge><span><CalendarDays size={13} /> {step.date}</span></div><h3>{step.title}</h3></div><button className="icon-plain" onClick={() => toggleStep(originalIndex)} title={completed ? 'Mark incomplete' : 'Mark complete'}>{completed ? <CheckCircle2 size={19} className="green-text" /> : <CircleUserRound size={18} />}</button></div><p>{step.description}</p>{step.page && <div className="source-ref"><BookOpenCheck size={14} /><span>Source reference</span><b>Page {step.page}</b><span className="source-sep">·</span><span>{journey.notice}</span></div>}</div></article> })}</div><div className="branch-plan"><div className="branch-plan-icon">{branch === 'selected' ? <GraduationCap size={18} /> : <ArrowDownRight size={18} />}</div><div><Badge tone={branch === 'selected' ? 'green' : 'violet'}>OUTCOME PLAN</Badge><h3>{branch === 'selected' ? 'If you are selected' : 'If you are not selected'}</h3><p>Conditional next steps are included so you always know what to do after results.</p><ol>{outcomes.map((step, i) => <li key={step}><span>{i + 1}</span>{step}</li>)}</ol></div></div></section><div className="inline-warning"><AlertCircle size={16} /><span>{journey.warning || 'Confirm all requirements and dates with the official notice.'}</span></div></>
}

function DocumentsPage({ documents }) {
  const groups = ['Mandatory', 'Conditional', 'Optional', 'Not specified', 'Not required']
  return <><PageHeading eyebrow="BE READY BEFORE YOU APPLY" title="Document checklist" description="Know what to collect, what applies to you, and what’s already ready." /><div className="doc-count-row"><div className="doc-count-card"><b>{documents.filter(d => d.kind === 'Mandatory').length}</b><span>Mandatory</span></div><div className="doc-count-card"><b>{documents.filter(d => d.kind === 'Conditional').length}</b><span>Conditional</span></div><div className="doc-count-card"><b>{documents.filter(d => d.kind === 'Optional').length}</b><span>Optional</span></div></div><div className="document-groups">{groups.map(group => <section className="panel document-group" key={group}><div className="document-group-title"><div><span className={`group-dot group-${group.toLowerCase()}`} /><h2>{group} documents</h2></div><span>{documents.filter(d => d.kind.toLowerCase() === group.toLowerCase()).length} items</span></div>{documents.filter(d => d.kind.toLowerCase() === group.toLowerCase()).map(d => <div className="document-item" key={d.name}><div className="document-file-icon"><FileText size={17} /></div><div className="document-detail"><b>{d.name}</b><span>{group === 'Conditional' ? 'Required only if this applies to your profile' : group === 'Optional' ? 'May support your application' : group === 'Mandatory' ? 'Required according to the notice' : 'Check this item in the notice'}</span></div><Badge tone={d.status === 'Ready' ? 'green' : group === 'Conditional' ? 'amber' : 'neutral'}>{d.status}</Badge></div>)}</section>)}</div><div className="inline-warning"><AlertCircle size={16} /><span>Check the official admission notice for the complete list and any conditions.</span></div></>
}

function EligibilityPage({ requirements, warning }) { return <><PageHeading eyebrow="CHECK BEFORE YOU APPLY" title="Eligibility requirements" description="A clear view of the criteria in your admission journey." /><div className="eligibility-layout"><section className="panel eligibility-panel"><SectionTitle eyebrow="PROGRAMME CRITERIA" title="What you need to qualify" /><div className="eligibility-list">{requirements.map((r, i) => <div className="eligibility-item" key={r.name}><span className={`eligibility-number ${r.status === 'Met' ? 'eligibility-met' : ''}`}>{r.status === 'Met' ? <Check size={14} /> : String(i + 1).padStart(2, '0')}</span><div><b>{r.name}</b><p>{r.detail}</p></div><Badge tone={r.status === 'Met' ? 'green' : 'amber'}>{r.status}</Badge></div>)}</div><div className="inline-warning"><AlertCircle size={16} /><span>{warning || 'Confirm eligibility against the official notice.'}</span></div></section><aside className="panel eligibility-side"><div className="eligibility-side-icon"><ShieldCheck size={24} /></div><div className="eyebrow">A QUICK REMINDER</div><h3>Your details matter</h3><p>Some requirements vary by category, board, or programme. Keep your profile updated and check conditional items carefully.</p><div className="side-check-row"><CheckCircle2 size={16} /><span>Review every criterion</span></div><div className="side-check-row"><CheckCircle2 size={16} /><span>Verify with official notice</span></div></aside></div></> }

function ProfilePage({ showToast }) { const [name, setName] = useState(localStorage.getItem('lifepath-name') || 'Applicant'); const [category, setCategory] = useState(localStorage.getItem('lifepath-category') || 'Prefer not to say'); const [board, setBoard] = useState(localStorage.getItem('lifepath-board') || ''); function save(e) { e.preventDefault(); localStorage.setItem('lifepath-name', name); localStorage.setItem('lifepath-category', category); localStorage.setItem('lifepath-board', board); showToast('Profile saved on this device.') } return <><PageHeading eyebrow="YOUR DETAILS, YOUR JOURNEY" title="Student profile" description="Your profile helps make conditional admission steps easier to understand." /><div className="profile-layout"><form className="panel profile-form" onSubmit={save}><SectionTitle eyebrow="ABOUT YOU" title="Applicant details" /><div className="form-grid"><label>Display name<input value={name} onChange={e => setName(e.target.value)} placeholder="Your name" /></label><label>Category<select value={category} onChange={e => setCategory(e.target.value)}><option>Prefer not to say</option><option>General</option><option>OBC</option><option>SC</option><option>ST</option><option>EWS</option></select></label><label className="span-two">Class 12 board<input value={board} onChange={e => setBoard(e.target.value)} placeholder="e.g. CBSE, ISC, State Board" /></label></div><div className="profile-note"><ShieldCheck size={16} /><span>Your profile is saved only in this browser.</span></div><button className="primary-button" type="submit"><Check size={16} /> Save profile</button></form><aside className="panel profile-tip"><div className="upload-icon"><Sparkles size={18} /></div><div className="eyebrow">PERSONALISED GUIDANCE</div><h3>Small details make a clearer path.</h3><p>Category and academic details can affect eligibility, certificates, and next steps. Keep them accurate before using the journey as a guide.</p><Badge tone="blue">LOCAL PROFILE</Badge></aside></div></> }

function PageHeading({ eyebrow, title, description }) { return <div className="page-heading"><div className="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{description}</p></div> }

export default App
