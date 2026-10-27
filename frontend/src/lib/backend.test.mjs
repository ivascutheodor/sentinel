import test from 'node:test'
import assert from 'node:assert/strict'
import { api, apiUrl, resolveApiOrigin, ApiError } from './api.ts'
import { parseUser, parseEvent, recordingUrl, getCurrentUser, getEvents, getEvent, deleteEvent, signOut } from './backend.ts'
import { signIn, signInErrorMessage } from './auth.ts'

const userId = '00000000-0000-4000-8000-000000000001'
const cameraId = '00000000-0000-4000-8000-000000000002'
const eventId = '00000000-0000-4000-8000-000000000003'
const clipId = '00000000-0000-4000-8000-000000000004'
const rawUser = { id: userId, username: 'front.desk', display_name: 'Front Desk', role: 'admin' }
const flatEvent = { id: eventId, camera_id: cameraId, video_path: '/srv/recordings/entrance 01.mp4', created_at: '2026-10-20T10:00:00Z' }
const now = Date.parse('2026-10-26T10:00:00Z') / 1000
const clip = { id: clipId, part_number: 1, status: 'ready', filepath: '/srv/recordings/entrance 01.mp4', expires_at: '2026-10-27T10:00:00Z' }
const richEvent = { id: eventId, camera_id: cameraId, event_type: 'person_presence', status: 'completed', started_at: '2026-10-20T09:00:00Z', last_person_seen_at: '2026-10-20T09:00:20Z', closed_at: '2026-10-20T09:00:30Z', end_reason: 'person_absent', created_at: '2026-10-20T10:00:00Z', clips: [clip] }
const serverEvent = { ...flatEvent, status: 'completed', started_at: richEvent.started_at, last_person_seen_at: richEvent.last_person_seen_at, closed_at: richEvent.closed_at, duration_seconds: 30, clip_status: 'ready' }

function mockFetch(t, respond) {
  const previous = globalThis.fetch
  globalThis.fetch = respond
  t.after(() => { globalThis.fetch = previous })
}

test('user mapping uses username and server-assigned roles', () => {
  assert.deepEqual(parseUser(rawUser), { id: userId, username: 'front.desk', name: 'Front Desk', role: 'administrator', initials: 'FD' })
  assert.equal(parseUser({ ...rawUser, role: 'user' }).role, 'operator')
  assert.throws(() => parseUser({ ...rawUser, role: 'owner' }), ApiError)
  assert.throws(() => parseUser({ ...rawUser, username: undefined, email: 'admin@test.invalid' }), ApiError)
})

test('login sends the exact API contract and preserves password whitespace', async t => {
  mockFetch(t, async (url, options) => {
    assert.equal(url, 'http://localhost:8000/api/v1/auth/login')
    assert.equal(options.method, 'POST')
    assert.equal(options.credentials, 'include')
    assert.equal(options.cache, 'no-store')
    assert.equal(options.headers.has('X-API-Key'), false)
    assert.deepEqual(JSON.parse(options.body), { username: 'front.desk', password: '  password with spaces  ' })
    return Response.json(rawUser)
  })
  await signIn({ username: '  FRONT.DESK  ', password: '  password with spaces  ' }, new AbortController().signal)
})

test('login rejects a malformed success response', async t => {
  mockFetch(t, async () => Response.json({ ok: true }))
  await assert.rejects(signIn({ username: 'front.desk', password: 'password' }, new AbortController().signal), error => error.status === 502)
})

test('auth and event operations use supported paths/methods, including 204 responses', async t => {
  const calls = []
  mockFetch(t, async (url, options) => {
    calls.push([url, options.method ?? 'GET'])
    if (url.endsWith('/auth/me')) return Response.json(rawUser)
    if (url.endsWith('/events')) return Response.json([flatEvent])
    if (options.method === 'DELETE' || url.endsWith('/auth/logout')) return new Response(null, { status: 204 })
    return Response.json(flatEvent)
  })
  const signal = new AbortController().signal
  assert.equal((await getCurrentUser(signal)).username, 'front.desk')
  assert.equal((await getEvents(signal)).length, 1)
  assert.equal((await getEvent(eventId, signal)).cameraId, cameraId)
  await deleteEvent(eventId, signal)
  await signOut()
  assert.deepEqual(calls, [
    ['http://localhost:8000/api/v1/auth/me', 'GET'], ['http://localhost:8000/api/v1/events', 'GET'],
    [`http://localhost:8000/api/v1/events/${eventId}`, 'GET'], [`http://localhost:8000/api/v1/events/${eventId}`, 'DELETE'],
    ['http://localhost:8000/api/v1/auth/logout', 'POST'],
  ])
})

test('compact events preserve registration time without inventing severity, review, or clip readiness', () => {
  const event = parseEvent(flatEvent, now)
  assert.equal(event.ts, Date.parse(flatEvent.created_at) / 1000)
  assert.equal(event.timestampLabel, 'Registered')
  assert.equal(event.clips[0].url, 'http://localhost:8000/api/v1/videos/entrance%2001.mp4')
  assert.equal(event.clips[0].status, 'unknown')
  assert.equal(event.severity, undefined)
  assert.equal(event.reviewed, undefined)
  assert.deepEqual(parseEvent({ ...flatEvent, video_path: null }, now).clips, [])
})

test('current authenticated server events preserve capture times and single-recording readiness', () => {
  const event = parseEvent(serverEvent, now)
  assert.equal(event.ts, Date.parse(serverEvent.started_at) / 1000)
  assert.equal(event.timestampLabel, 'Started')
  assert.equal(event.captureStatus, 'completed')
  assert.equal(event.closedAt, Date.parse(serverEvent.closed_at) / 1000)
  assert.equal(event.clips[0].status, 'ready')
  assert.equal(event.clips[0].url, 'http://localhost:8000/api/v1/videos/entrance%2001.mp4')
  for (const status of ['pending', 'failed', 'deleting', 'deleted']) {
    for (const path of [null, serverEvent.video_path]) {
      const clip = parseEvent({ ...serverEvent, clip_status: status, video_path: path }, now).clips[0]
      assert.equal(clip.status, status)
      assert.equal(clip.url, null)
    }
  }
  assert.equal(parseEvent({ ...serverEvent, video_path: null }, now).clips[0].status, 'unavailable')
  assert.deepEqual(parseEvent({ ...serverEvent, clip_status: null, video_path: null }, now).clips, [])
  const active = parseEvent({ ...serverEvent, status: 'capturing', closed_at: null }, now)
  assert.equal(active.captureStatus, 'capturing')
  assert.equal(active.closedAt, undefined)
  assert.equal(parseEvent({ ...serverEvent, status: 'interrupted' }, now).captureStatus, 'interrupted')
})

test('rich events preserve capture state, recording lifecycle, expiry, and clip ordering', () => {
  const event = parseEvent({ ...richEvent, clips: [
    { ...clip, id: '00000000-0000-4000-8000-000000000005', part_number: 2, status: 'pending', filepath: null }, clip,
  ] }, now)
  assert.equal(event.timestampLabel, 'Started')
  assert.equal(event.ts, Date.parse(richEvent.started_at) / 1000)
  assert.equal(event.captureStatus, 'completed')
  assert.equal(event.closedAt, Date.parse(richEvent.closed_at) / 1000)
  assert.deepEqual(event.clips.map(clip => clip.partNumber), [1, 2])
  assert.equal(event.clips[1].url, null)
  for (const status of ['pending', 'failed', 'deleting', 'deleted']) {
    assert.equal(parseEvent({ ...richEvent, clips: [{ ...clip, status }] }, now).clips[0].url, null)
  }
  const expired = parseEvent(richEvent, Date.parse('2026-10-28T10:00:00Z') / 1000).clips[0]
  assert.equal(expired.status, 'expired')
  assert.equal(expired.url, null)
})

test('media URLs use the configured API origin, escaped single filenames and reject unsafe paths', () => {
  assert.equal(recordingUrl('C:\\recordings\\entrée #1.mp4'), 'http://localhost:8000/api/v1/videos/entr%C3%A9e%20%231.mp4')
  assert.equal(recordingUrl('recordings/a&b.mp4'), 'http://localhost:8000/api/v1/videos/a%26b.mp4')
  for (const path of [null, '', '../private.mp4', '/recordings/../private.mp4', 'https://evil.test/video.mp4', 'file:///private.mp4', 'clip\u0000.mp4', '/recordings/']) {
    assert.equal(recordingUrl(path), null, String(path))
  }
})

test('malformed IDs, missing fields, naive timestamps, and unsupported states fail explicitly', () => {
  for (const event of [
    { ...flatEvent, id: 1 }, { ...flatEvent, camera_id: 'unknown' },
    { ...flatEvent, created_at: '2026-10-20T10:00:00' },
    { ...flatEvent, video_path: undefined }, { ...richEvent, status: 'done' },
    { ...serverEvent, clip_status: 'streaming' }, { ...serverEvent, status: 'done' },
    { ...serverEvent, closed_at: undefined }, { ...serverEvent, started_at: '2026-10-20T09:00:00' },
    { ...richEvent, clips: [{ ...clip, status: 'streaming' }] },
  ]) assert.throws(() => parseEvent(event, now), ApiError)
})

test('history and detail accept the current authenticated server response', async t => {
  mockFetch(t, async () => Response.json(serverEvent))
  assert.equal((await getEvent(eventId, new AbortController().signal)).timestampLabel, 'Started')
  globalThis.fetch = async () => Response.json([serverEvent])
  assert.equal((await getEvents(new AbortController().signal))[0].clips[0].status, 'ready')
})

test('events sort newest first and never require a camera-list response', async t => {
  mockFetch(t, async () => Response.json([flatEvent, { ...flatEvent, id: clipId, camera_id: clipId, created_at: '2026-10-21T10:00:00+00:00' }]))
  const events = await getEvents(new AbortController().signal)
  assert.deepEqual(events.map(event => event.id), [clipId, eventId])
})

test('HTTP errors keep status, cancellation propagates, and failed reads do not look successful', async t => {
  mockFetch(t, async () => Response.json({ detail: 'Not authenticated' }, { status: 401 }))
  await assert.rejects(getCurrentUser(new AbortController().signal), error => error instanceof ApiError && error.status === 401)
  globalThis.fetch = async () => new Response('<html>wrong server</html>', { status: 200 })
  await assert.rejects(api('/auth/me'), error => error.status === 502)
  globalThis.fetch = async () => { throw new TypeError('Network unavailable') }
  await assert.rejects(api('/auth/me'), error => error.status === 0)
  const controller = new AbortController()
  controller.abort()
  globalThis.fetch = async () => { throw controller.signal.reason }
  await assert.rejects(api('/auth/me', { signal: controller.signal }), error => error.name === 'AbortError')
  assert.match(signInErrorMessage(new ApiError('technical', 401)), /username or password/)
})


test('API origins support Tailscale, private hosts, IPv6, and explicit deployment settings', () => {
  assert.equal(resolveApiOrigin('', 'http://homie:5173/events'), 'http://homie:8000')
  assert.equal(resolveApiOrigin(undefined, 'http://100.80.90.10:5173/login'), 'http://100.80.90.10:8000')
  assert.equal(resolveApiOrigin('', 'http://[fd7a:115c:a1e0::1]:5173'), 'http://[fd7a:115c:a1e0::1]:8000')
  assert.equal(resolveApiOrigin('https://sentinel.internal:8443/', 'https://sentinel.internal:5173'), 'https://sentinel.internal:8443')
  assert.equal(resolveApiOrigin('  http://homie:8001  ', 'http://homie:5173'), 'http://homie:8001')
  for (const origin of ['file:///private', 'http://user:password@homie:8000', 'http://homie:8000/api/v1', 'http://homie:8000/?token=secret']) {
    assert.throws(() => resolveApiOrigin(origin, 'http://homie:5173'))
  }
  assert.equal(apiUrl('/auth/me'), 'http://localhost:8000/api/v1/auth/me')
})
