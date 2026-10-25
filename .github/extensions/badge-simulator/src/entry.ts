// Browser entry for the Badge Simulator canvas. build.mjs bundles this file
// together with the simulator modules from badger/badger.github.io (imported
// through the @site alias) into web/simulator.js.
import { BadgeInput, initBadgeKeyboard } from '@site/lib/badge-editor-input'
import { createBadgeModelController } from '@site/lib/badge-editor-model-controller'
import { initBadgeModel } from '@site/lib/badge-editor-model'
import { initBadgeMotion } from '@site/lib/badge-motion'
import { fileBytes, projectFile, simulationSource } from '@site/lib/badge-editor-project'
import { firmwareCompat } from '@site/lib/badge-firmware-compat'

type AppFile = { path: string; data: string }
type AppPayload = { app: string; revision: number; files: AppFile[] }
type ServerEvent =
  | { type: 'reload'; app: string | null; revision: number }
  | { type: 'apps'; apps: string[] }
  | { type: 'screenshot'; id: string }
  | { type: 'press'; bit: number; ms: number }
  | { type: 'restart' }

const appRoot = '/system/apps'
const $ = <T extends Element = HTMLElement>(selector: string) => document.querySelector<T>(selector)!

const root = $('#sim')
const host = $('[data-model]')
const screen = $<HTMLCanvasElement>('[data-screen]')
const status = $('[data-status]')
const appSelect = $<HTMLSelectElement>('[data-app]')
const output = $('[data-output]')
const rotateButton = $<HTMLButtonElement>('[data-model-rotate]')
const deployButton = $<HTMLButtonElement>('[data-deploy]')
const reloadButton = $<HTMLButtonElement>('[data-reload]')
const keys = [...document.querySelectorAll<HTMLButtonElement>('[data-button]')]

// Mirrors badge/main.py for a single app: run it, and when HOME is pressed run
// its on_exit hook and start it again (there is no menu in this canvas).
function launcher(target: string) {
  return `
import builtins, machine, sys, time, badgeware

class _ReturnHome(BaseException):
    pass

_armed = False
_target = ${JSON.stringify(target)}
_native_poll = badge.poll

def _exit_app():
    app = sys.modules.get(_target)
    on_exit = getattr(app, "on_exit", None)
    if callable(on_exit):
        try:
            on_exit()
        except Exception as e:
            sys.print_exception(e)

def _poll():
    global _armed
    _native_poll()
    if _armed and badge.pressed(BUTTON_HOME):
        _armed = False
        _exit_app()
        raise _ReturnHome()

def _reset():
    raise _ReturnHome()

badge.poll = _poll
machine.reset = _reset
builtins.reset = _reset
badgeware.reset = _reset

def _release():
    badge.poll()
    while badge.held():
        time.sleep(0.02)
        badge.poll()

while True:
    badge.mode(LORES | VSYNC)
    badge.autorotate(True)
    badgeware.set_backlight(1.0)
    _release()
    _armed = True
    saved_path = list(sys.path)
    try:
        launch(_target)
        print("[simulator] App returned. Press HOME to start it again.")
        _armed = False
        while not badge.pressed(BUTTON_HOME):
            time.sleep(0.05)
            badge.poll()
    except _ReturnHome:
        pass
    finally:
        sys.path[:] = saved_path
    print("[simulator] Restarting app")
`
}

function decode(data: string) {
  const binary = atob(data)
  const bytes = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i)
  return bytes
}

function request(payload: AppPayload) {
  const target = `${appRoot}/${payload.app}`
  const files = payload.files.map(({ path, data }) => {
    const file = projectFile(path, decode(data))
    const text = path.endsWith('.py') && file.text !== null ? simulationSource(file.text) : file.text
    return { name: `${target}/${path}`, content: fileBytes({ ...file, text }) }
  })
  const program = `import editor_support\nimport sys\nsys.path[:0] = ["/system/lib", "/lib", "/system"]\n${firmwareCompat}\n${launcher(target)}`
  return { program, files }
}

// ---- console + log forwarding ---------------------------------------------
const lines: string[] = []
let pendingLog: string[] = []
let logTimer = 0
function post(path: string, body: unknown) {
  return fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }).catch(() => undefined)
}
function flushLog() {
  logTimer = 0
  if (!pendingLog.length) return
  const batch = pendingLog
  pendingLog = []
  void post('/api/log', { lines: batch })
}
function log(text: string) {
  for (const line of text.split('\n')) {
    lines.push(line)
    pendingLog.push(line)
  }
  while (lines.length > 400) lines.shift()
  output.textContent = lines.join('\n')
  output.scrollTop = output.scrollHeight
  if (!logTimer) logTimer = window.setTimeout(flushLog, 150)
}
function setStatus(text: string, state = '') {
  status.textContent = text
  root.dataset.runState = state
  void post('/api/status', { status: text, state })
}

// ---- 3D model ---------------------------------------------------------------
const controls = {
  screen: $<HTMLButtonElement>('[data-model-screen]'),
  full: $<HTMLButtonElement>('[data-model-full]'),
  status: $('[data-model-status]'),
  zoomIn: $<HTMLButtonElement>('[data-model-zoom-in]'),
  zoomOut: $<HTMLButtonElement>('[data-model-zoom-out]'),
}
const model = createBadgeModelController(async (signal, fail) => {
  const view = initBadgeModel(host, screen, (bit, pressed) => input.set('model', bit, pressed), signal, fail, controls)
  void view.ready.then(() => { root.dataset.model = 'ready' }, () => {})
  return view
}, error => {
  // Keep running with the flat screen if WebGL or the model is unavailable.
  root.dataset.model = 'flat'
  log(`[simulator] 3D badge unavailable (${error instanceof Error ? error.message : String(error)}); showing the flat screen.`)
})

// ---- input ------------------------------------------------------------------
let worker: Worker | null = null
let rotated = false
let buttons = 0
const sendButtons = () => worker?.postMessage({ buttons: buttons | (rotated ? 32768 : 0) })
const input = new BadgeInput(mask => {
  buttons = mask
  sendButtons()
  for (const key of keys) key.dataset.pressed = String((mask & Number(key.dataset.button)) !== 0)
  model.setButtons(mask)
})
initBadgeKeyboard(root, input)
const motion = initBadgeMotion(root, value => worker?.postMessage({ motion: value }), new AbortController().signal)
rotateButton.addEventListener('click', () => {
  rotated = !rotated
  rotateButton.setAttribute('aria-pressed', String(rotated))
  model.setRotated(rotated)
  motion.setFlipped(rotated)
  sendButtons()
})
for (const key of keys) {
  const bit = Number(key.dataset.button)
  const release = () => input.set(`pointer:${bit}`, bit, false)
  key.addEventListener('pointerdown', event => {
    if (event.button !== 0) return
    key.setPointerCapture(event.pointerId)
    input.set(`pointer:${bit}`, bit, true)
  })
  key.addEventListener('pointerup', release)
  key.addEventListener('pointercancel', release)
  key.addEventListener('lostpointercapture', release)
  key.addEventListener('contextmenu', event => event.preventDefault())
}
document.addEventListener('visibilitychange', () => { input.clear(); worker?.postMessage({ pause: document.hidden }) })

// ---- worker lifecycle ---------------------------------------------------------
let current: AppPayload | null = null
let ready = false

function run(payload: AppPayload) {
  current = payload
  if (!worker || !ready) return
  try {
    const req = request(payload)
    lines.length = 0
    log(`[simulator] Running ${payload.app} (revision ${payload.revision})`)
    worker.postMessage({ ...req, debug: false })
    worker.postMessage({ pause: document.hidden })
    setStatus(`Running ${payload.app}`, 'running')
  } catch (error) {
    log(`[simulator] ${error instanceof Error ? error.message : String(error)}`)
    setStatus('Could not start app', 'error')
  }
}

function startWorker() {
  worker?.terminate()
  ready = false
  const next = new Worker('/simulator/micropython.worker.js', { type: 'module' })
  worker = next
  next.onerror = event => { event.preventDefault(); log(`[simulator] Worker error: ${event.message}`); setStatus('Simulator error', 'error') }
  next.onmessage = ({ data }) => {
    if (next !== worker) return
    if (typeof data.stdout === 'string') log(data.stdout)
    if (data.bootError) { log(`[simulator] ${data.bootError}`); setStatus('Simulator failed to boot', 'error') }
    if (data.failed) setStatus(`${current?.app ?? 'App'} crashed — see output`, 'error')
    if (data.stuck) { log('[simulator] App did not stop; restarting the runtime.'); startWorker() }
    if (data.ready) {
      ready = true
      sendButtons()
      if (current) run(current)
      else setStatus('Choose an app to run')
    }
    if (data.frame) {
      const { width, height, buffer } = data.frame
      if (screen.width !== width || screen.height !== height) { screen.width = width; screen.height = height }
      screen.getContext('2d')?.putImageData(new ImageData(new Uint8ClampedArray(buffer), width, height), 0, 0)
      model.updateFrame()
      root.dataset.framed = 'true'
    }
    if (data.backlight !== undefined) model.setBacklight(Math.max(0.15, Math.min(1, data.backlight)))
  }
}

function setApps(apps: string[], selected: string | null) {
  appSelect.replaceChildren(new Option('Choose app…', ''), ...apps.map(name => new Option(name, name)))
  appSelect.value = selected ?? ''
  deployButton.disabled = !selected
}

async function loadApp() {
  const response = await fetch('/api/app')
  if (response.status === 204) { current = null; deployButton.disabled = true; setStatus('Choose an app to run'); return }
  if (!response.ok) { setStatus(await response.text(), 'error'); return }
  const payload = await response.json() as AppPayload
  if (![...appSelect.options].some(option => option.value === payload.app)) appSelect.add(new Option(payload.app, payload.app))
  appSelect.value = payload.app
  deployButton.disabled = false
  run(payload)
}

// ---- server events ------------------------------------------------------------
function capture(id: string) {
  const body: Record<string, string> = { id, screen: screen.toDataURL('image/png') }
  void post('/api/screenshot', body)
}

function connect() {
  const events = new EventSource('/events')
  events.onmessage = ({ data }) => {
    const event = JSON.parse(data) as ServerEvent
    if (event.type === 'apps') setApps(event.apps, appSelect.value || null)
    else if (event.type === 'reload') void loadApp()
    else if (event.type === 'restart') startWorker()
    else if (event.type === 'screenshot') capture(event.id)
    else if (event.type === 'press') {
      input.set(`agent:${event.bit}`, event.bit, true)
      window.setTimeout(() => input.set(`agent:${event.bit}`, event.bit, false), event.ms)
    }
  }
}

appSelect.addEventListener('change', () => { void post('/api/select', { app: appSelect.value || null }) })
reloadButton.addEventListener('click', () => { void loadApp() })
deployButton.addEventListener('click', async () => {
  if (!appSelect.value) return
  deployButton.disabled = true
  const response = await fetch('/api/deploy', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ app: appSelect.value }) }).catch(() => null)
  const message = response?.ok ? `Asked Copilot to deploy ${appSelect.value} to your badge` : 'Could not ask Copilot to deploy'
  setStatus(message, response?.ok ? 'deploying' : 'error')
  log(`[simulator] ${message}`)
  window.setTimeout(() => { deployButton.disabled = false }, 4000)
})
$('[data-clear-output]').addEventListener('click', () => { lines.length = 0; output.textContent = '' })

async function init() {
  const state = await fetch('/api/state').then(r => r.json()) as { apps: string[]; app: string | null }
  setApps(state.apps, state.app)
  model.start()
  startWorker()
  if (state.app) await loadApp()
  connect()
}
void init()
