// Browser entry for the Badge Simulator canvas. build.mjs bundles this file
// together with the simulator modules from badger/badger.github.io (imported
// through the @site alias) into web/simulator.js.
import { BadgeInput, initBadgeKeyboard } from '@site/lib/badge-editor-input'
import { createBadgeModelController } from '@site/lib/badge-editor-model-controller'
import { initBadgeModel } from '@site/lib/badge-editor-model'
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js'
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
  | { type: 'exec'; id: string; code: string }
  | { type: 'rotate'; value?: boolean }
  | { type: 'record-start'; id: string; fps: number; video: boolean; scale: number }
  | { type: 'record-stop'; id: string }

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

// Runs agent-supplied MicroPython (the canvas `exec` action) and brackets its
// output with markers so the extension can return it. Expressions print their
// repr like the REPL; statements run with exec().
const execHelper = `
def _sim_exec(tag, code, scope):
    print("[sim-exec:%s:begin]" % tag)
    ok = True
    try:
        try:
            result = eval(code, scope)
        except SyntaxError:
            exec(code, scope)
        else:
            if result is not None:
                print(repr(result))
    except Exception as e:
        ok = False
        sys.print_exception(e)
    finally:
        print("[sim-exec:%s:%s]" % (tag, "ok" if ok else "error"))
`
const execFile = '/tmp/_sim_exec.py'

// Mirrors badge/main.py for a single app: run it, and when HOME is pressed run
// its on_exit hook and start it again (there is no menu in this canvas).
function launcher(target: string) {
  return `
import builtins, machine, os, sys, time, badgeware
${execHelper}
_exec_scope = {}

def _service_exec():
    try:
        with open(${JSON.stringify(execFile)}) as f:
            src = f.read()
    except OSError:
        return
    try:
        os.remove(${JSON.stringify(execFile)})
    except OSError:
        pass
    tag, _, code = src.partition("\\n")
    app = sys.modules.get(_target)
    scope = _exec_scope
    if app is not None:
        try:
            scope = app.__dict__
        except AttributeError:
            _exec_scope["app"] = app
    _sim_exec(tag, code, scope)

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
    _service_exec()
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
  return { program: `${prelude}\n${launcher(target)}`, files }
}

const prelude = `import editor_support\nimport sys\nsys.path[:0] = ["/system/lib", "/lib", "/system"]\n${firmwareCompat}`

// Used when no app loop is polling (the app crashed or the runtime is idle):
// run the snippet as a standalone program instead.
const standaloneExec = (id: string, code: string) =>
  `${prelude}\n${execHelper}\n_sim_exec(${JSON.stringify(id)}, ${JSON.stringify(code)}, {"__name__": "__main__"})\n`

// ---- console + log forwarding ---------------------------------------------
const lines: string[] = []
let pendingLog: string[] = []
let logTimer = 0
// The custom header makes cross-origin pages fail CORS preflight, so only this page can POST.
const postHeaders = { 'Content-Type': 'application/json', 'X-Badge-Simulator': '1' }
function post(path: string, body: unknown) {
  return fetch(path, { method: 'POST', headers: postHeaders, body: JSON.stringify(body) }).catch(() => undefined)
}
function flushLog() {
  logTimer = 0
  if (!pendingLog.length) return
  const batch = pendingLog
  pendingLog = []
  void post('/api/log', { lines: batch })
}
let inExec = false
function log(text: string) {
  for (const line of text.split('\n')) {
    pendingLog.push(line)
    const marker = /^\[sim-exec:[\w-]+:(begin|ok|error)\]$/.exec(line)
    if (marker) { inExec = marker[1] === 'begin'; continue }
    if (!inExec) lines.push(line)
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
// The Universe 2026 badge has its USB-C socket on the left edge; the site model
// places it on the right, so mirror those parts across the board's centre.
const parseAsync = GLTFLoader.prototype.parseAsync
GLTFLoader.prototype.parseAsync = async function (...args: Parameters<typeof parseAsync>) {
  const gltf = await parseAsync.apply(this, args)
  gltf.scene.traverse(object => {
    if (!/^usb-?c/i.test(object.name)) return
    object.position.x = -object.position.x
    object.scale.x = -object.scale.x
  })
  return gltf
}
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
  // Keyboard (Space/Enter) and assistive-technology activation fire click without a pointer press.
  key.addEventListener('click', event => {
    if (event.detail !== 0) return
    input.set(`click:${bit}`, bit, true)
    window.setTimeout(() => input.set(`click:${bit}`, bit, false), 120)
  })
}
document.addEventListener('visibilitychange', () => { input.clear(); worker?.postMessage({ pause: document.hidden }) })

// ---- worker lifecycle ---------------------------------------------------------
let current: AppPayload | null = null
let ready = false
let running = false
let frames = 0
let hasAppFrame = false
const clientId = Math.random().toString(36).slice(2)
let framesAtLastStat = 0
let backlight = 1
// Paths written into the worker's filesystem since it started. The worker only
// overwrites files, so a deleted or renamed file needs a fresh runtime.
const written = new Set<string>()

function run(payload: AppPayload) {
  current = payload
  hasAppFrame = false
  if (!worker || !ready) return
  const paths = new Set(payload.files.map(file => `${payload.app}/${file.path}`))
  if ([...written].some(path => !paths.has(path))) { startWorker(); return }
  try {
    const req = request(payload)
    for (const path of paths) written.add(path)
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
  written.clear()
  ready = false
  running = false
  hasAppFrame = false
  const next = new Worker('/simulator/micropython.worker.js', { type: 'module' })
  worker = next
  next.onerror = event => { event.preventDefault(); log(`[simulator] Worker error: ${event.message}`); setStatus('Simulator error', 'error') }
  next.onmessage = ({ data }) => {
    if (next !== worker) return
    if (typeof data.stdout === 'string') log(data.stdout)
    if (data.running) running = true
    if (data.completed) running = false
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
      frames++
      hasAppFrame = true
      if (recording) recording.rendered++
      recordFrame()
      root.dataset.framed = 'true'
    }
    if (data.backlight !== undefined) backlight = data.backlight
    if (data.backlight !== undefined) model.setBacklight(Math.max(0.15, Math.min(1, data.backlight)))
  }
}

function setApps(apps: string[], selected: string | null) {
  appSelect.replaceChildren(new Option('Choose app…', ''), ...apps.map(name => new Option(name, name)))
  appSelect.value = selected ?? ''
  deployButton.disabled = !selected
}

function setAppIdentity(payload: AppPayload | null) {
  document.title = payload ? `Badge Simulator · ${payload.app}` : 'Badge Simulator'
  const icon = payload?.files.find(file => file.path === 'icon.png')
  const favicon = document.querySelector<HTMLLinkElement>('link[rel="icon"]')
  if (favicon) favicon.href = icon ? `data:image/png;base64,${icon.data}` : 'data:,'
}

async function loadApp() {
  const response = await fetch('/api/app')
  if (response.status === 204) {
    current = null
    setAppIdentity(null)
    deployButton.disabled = true
    startWorker()
    screen.getContext('2d')?.clearRect(0, 0, screen.width, screen.height)
    model.updateFrame()
    setStatus('Choose an app to run')
    return
  }
  if (!response.ok) { setStatus(await response.text(), 'error'); return }
  const payload = await response.json() as AppPayload
  setAppIdentity(payload)
  if (![...appSelect.options].some(option => option.value === payload.app)) appSelect.add(new Option(payload.app, payload.app))
  appSelect.value = payload.app
  deployButton.disabled = false
  run(payload)
}

function execCode(id: string, code: string) {
  if (!worker || !ready) {
    log(`[sim-exec:${id}:begin]`)
    log('Simulator runtime is not ready yet.')
    log(`[sim-exec:${id}:error]`)
    return
  }
  if (running) {
    worker.postMessage({ file: { name: execFile, code: `${id}\n${code}` } })
  } else {
    worker.postMessage({ program: standaloneExec(id, code), files: [] })
    setStatus('Ran code in the simulator (app stopped; reload to restart it)', 'stopped')
  }
}

window.setInterval(() => {
  void post('/api/stats', {
    client: clientId, fps: frames - framesAtLastStat, frames, width: screen.width, height: screen.height,
    running, paused: document.hidden, rotated, backlight,
  })
  framesAtLastStat = frames
}, 1000)

// ---- recording (the canvas `record` action) -------------------------------------
// Streams changed frames as raw RGBA to the extension, which encodes GIF/PNG. Video
// uses MediaRecorder on an upscaled copy of the screen.
type Recording = {
  id: string; interval: number; start: number; last: number; hash: number; rendered: number
  fps: number; scale: number; captureVideo: boolean; stopping: boolean
  uploads: Promise<unknown>[]; video?: { canvas: HTMLCanvasElement; recorder?: MediaRecorder; chunks: Blob[]; error?: string }
}
let recording: Recording | null = null
function frameHash(data: Uint8ClampedArray) {
  const words = new Uint32Array(data.buffer, data.byteOffset, data.byteLength >> 2)
  let h = 0x811c9dc5 ^ words.length
  for (let i = 0; i < words.length; i++) h = Math.imul(h ^ words[i], 0x01000193)
  return h >>> 0
}
function recordFrame(force = false) {
  const rec = recording
  if (!rec || !hasAppFrame || rec.stopping) return
  const now = performance.now()
  if (!force && now - rec.last < rec.interval - 2) return
  const { width, height } = screen
  if (!width || !height) return
  const image = screen.getContext('2d')!.getImageData(0, 0, width, height)
  const hash = frameHash(image.data) ^ (width << 16) ^ height
  if (rec.captureVideo && !rec.video) startRecordingVideo(rec)
  if (rec.video) {
    const ctx = rec.video.canvas.getContext('2d')!
    ctx.imageSmoothingEnabled = false
    ctx.drawImage(screen, 0, 0, rec.video.canvas.width, rec.video.canvas.height)
  }
  if (hash === rec.hash) return
  rec.last = now
  rec.hash = hash
  const query = `id=${rec.id}&t=${(now - rec.start).toFixed(1)}&w=${width}&h=${height}`
  rec.uploads.push(fetch(`/api/record-frame?${query}`, {
    method: 'POST', headers: { 'Content-Type': 'application/octet-stream', 'X-Badge-Simulator': '1' }, body: image.data,
  }).catch(() => undefined))
}
function startRecording(id: string, fps: number, video: boolean, scale: number) {
  if (recording) { void post('/api/record-done', { id, error: 'A recording is already in progress in this canvas' }); return }
  const now = performance.now()
  recording = { id, interval: 1000 / fps, start: now, last: -Infinity, hash: -1, rendered: 0, uploads: [], fps, scale, captureVideo: video, stopping: false }
  recordFrame(true)
}
function startRecordingVideo(rec: Recording) {
  const canvas = document.createElement('canvas')
  const factor = rec.scale || (screen.width >= 320 ? 2 : 4)
  canvas.width = screen.width * factor
  canvas.height = screen.height * factor
  try {
    const types = ['video/mp4;codecs=avc1', 'video/mp4', 'video/webm;codecs=vp9', 'video/webm']
    const mimeType = types.find((t) => MediaRecorder.isTypeSupported(t))
    const recorder = new MediaRecorder(canvas.captureStream(rec.fps), mimeType ? { mimeType, videoBitsPerSecond: 4_000_000 } : undefined)
    const chunks: Blob[] = []
    recorder.ondataavailable = (event) => { if (event.data.size) chunks.push(event.data) }
    recorder.start(250)
    rec.video = { canvas, recorder, chunks }
  } catch (error) {
    rec.video = { canvas, chunks: [], error: String(error) }
  }
}
async function stopRecording(id: string) {
  const rec = recording
  if (!rec || rec.id !== id || rec.stopping) { void post('/api/record-done', { id, error: 'No active recording in this canvas' }); return }
  recordFrame(true)
  rec.stopping = true
  const duration = performance.now() - rec.start
  let video: { mime: string; data: string } | undefined
  let videoError = rec.video?.error
  if (rec.video?.recorder) {
    const { recorder, chunks } = rec.video
    await new Promise<void>((resolve) => { recorder.onstop = () => resolve(); recorder.stop() })
    const blob = new Blob(chunks, { type: recorder.mimeType })
    if (blob.size) {
      const bytes = new Uint8Array(await blob.arrayBuffer())
      let binary = ''
      for (let i = 0; i < bytes.length; i += 0x8000) binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000))
      video = { mime: recorder.mimeType, data: btoa(binary) }
    } else videoError = 'MediaRecorder produced no data'
  }
  await Promise.all(rec.uploads)
  void post('/api/record-done', { id, duration_ms: duration, rendered_frames: rec.rendered, video, video_error: videoError })
  recording = null
}

// ---- server events ------------------------------------------------------------
function capture(id: string) {
  const body: Record<string, string> = { id, screen: screen.toDataURL('image/png') }
  void post('/api/screenshot', body)
}

function connect() {
  const events = new EventSource(`/events?client=${clientId}`)
  events.onmessage = ({ data }) => {
    const event = JSON.parse(data) as ServerEvent
    if (event.type === 'apps') setApps(event.apps, appSelect.value || null)
    else if (event.type === 'reload') void loadApp()
    else if (event.type === 'restart') { current = null; startWorker(); void loadApp() }
    else if (event.type === 'screenshot') capture(event.id)
    else if (event.type === 'exec') execCode(event.id, event.code)
    else if (event.type === 'record-start') startRecording(event.id, event.fps, event.video, event.scale)
    else if (event.type === 'record-stop') void stopRecording(event.id)
    else if (event.type === 'rotate') { if (event.value === undefined || event.value !== rotated) rotateButton.click() }
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
  const response = await fetch('/api/deploy', { method: 'POST', headers: postHeaders, body: JSON.stringify({ app: appSelect.value }) }).catch(() => null)
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
