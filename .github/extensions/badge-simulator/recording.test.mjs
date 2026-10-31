import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { stripTypeScriptTypes } from "node:module";
import { join } from "node:path";
import { test } from "node:test";
import { runInNewContext } from "node:vm";
import { encodeGif } from "./media.mjs";

const extension = readFileSync(new URL("./extension.mjs", import.meta.url), "utf8");
const entry = readFileSync(new URL("./src/entry.ts", import.meta.url), "utf8");
const recordingCode = entry.slice(entry.indexOf("type Recording ="), entry.indexOf("// ---- server events"));
const actionCode = extension.slice(extension.indexOf("function recordingClient("), extension.indexOf("async function doExec("));

function actionHarness({ done = { duration_ms: 3000 }, finishImmediately = true, requireClient = async () => {} } = {}) {
    let now = 0, reloads = 0, gif;
    const events = [];
    const inst = { app: "test", recordings: new Map(), statsBy: new Map() };
    const client = {
        write(message) {
            const event = JSON.parse(message.slice(6));
            events.push(event);
            const rec = inst.recordings.get(event.id);
            if (event.type === "record-start") {
                rec.frames.push(
                    { t: 0, width: 1, height: 1, data: new Uint8Array(4) },
                    { t: 1000, width: 1, height: 1, data: new Uint8Array(4) },
                );
            } else if (event.type === "record-stop" && finishImmediately) {
                now += 2000; // Video export and upload time, not capture time.
                rec.finish(done);
            }
        },
    };
    inst.clients = new Set([client]);
    const doRecord = runInNewContext(`${actionCode}\ndoRecord`, {
        requireClient, doReload: () => reloads++, waitForRun: async () => {},
        cursorOf: () => 0, Date: { now: () => now }, setTimeout, clearTimeout,
        clampMs: (value, fallback) => value ?? fallback, sleep: async (ms) => { now += ms; },
        runScript: async () => { throw new Error("Script failed"); },
        snapshot: () => ({}), linesSince: () => [], join,
        session: { workspacePath: "artifacts" }, mkdirSync: () => {}, writeFileSync: () => {},
        contactSheet: () => Buffer.alloc(0),
        encodeGif: (width, height, frames, scale) => { gif = { width, height, frames, scale }; return Buffer.alloc(0); },
    });
    return { inst, events, record: (input) => doRecord(inst, input), get reloads() { return reloads; }, get gif() { return gif; } };
}

test("explicit recording scale is an integer 1-4, validated before any side effects", async () => {
    const h = actionHarness();
    for (const scale of [0, 5, 1.5, -1, NaN, Infinity, null, "2"]) {
        await assert.rejects(h.record({ scale, restart: true }), /integer from 1 to 4/);
    }
    assert.equal(h.reloads, 0);
    assert.equal(h.events.length, 0);
    for (const scale of [1, 2, 3, 4]) {
        await h.record({ scale });
        assert.equal(h.gif.scale, scale);
        assert.equal(h.events.at(-2).scale, scale);
    }
    await h.record({});
    assert.equal(h.gif.scale, 2);
    assert.match(extension, /scale: \{ type: "integer", minimum: 1, maximum: 4/);
});

test("GIF timing and static diagnostics exclude export time; missing duration falls back to wall time", async () => {
    const h = actionHarness();
    const result = await h.record({});
    assert.equal(result.duration_ms, 3000);
    assert.equal(result.longest_static_ms, 2000);
    assert.deepEqual(Array.from(h.gif.frames, (f) => f.delayMs), [1000, 2000]);
    for (const duration_ms of [undefined, null, -1, NaN]) {
        const fallback = await actionHarness({ done: { duration_ms } }).record({});
        assert.equal(fallback.duration_ms, 5000);
        assert.equal(fallback.longest_static_ms, 4000);
    }
    assert.equal((await actionHarness({ done: { duration_ms: 0 } }).record({ duration_ms: 0 })).duration_ms, 0);
});

test("overlapping actions are rejected before restart, through capture and export, and the lock is released", async () => {
    let connect;
    const h = actionHarness({
        requireClient: () => new Promise((resolve) => { connect = resolve; }),
        finishImmediately: false,
    });
    const first = h.record({ restart: true });
    await assert.rejects(h.record({ restart: true }), /already in progress/);
    assert.equal(h.reloads, 0);
    connect();
    // Drain the action's resolved awaits until it is waiting for record-done.
    for (let i = 0; i < 10 && !h.events.some((e) => e.type === "record-stop"); i++) await Promise.resolve();
    assert.equal(h.events.at(-1).type, "record-stop");
    await assert.rejects(h.record({ restart: true }), /already in progress/);
    assert.equal(h.reloads, 1);
    const id = h.events[0].id;
    h.inst.recordings.get(id).finish({ duration_ms: 3000 });
    await first;
    assert.equal(h.inst.recordings.size, 0);
    assert.equal(h.inst.recordingActive, false);
});

test("recording lock is released when a script fails", async () => {
    const h = actionHarness();
    await assert.rejects(h.record({ steps: [{}] }), /Script failed/);
    assert.equal(h.events.at(-1).type, "record-stop");
    assert.equal(h.inst.recordings.size, 0);
    assert.equal(h.inst.recordingActive, false);
    await h.record({});
});

function browserHarness() {
    let now = 0, pixel = 0, finishVideo;
    const uploads = [], posts = [], recorders = [];
    const context = {
        getImageData: () => ({ data: new Uint8ClampedArray(screen.width * screen.height * 4).fill(pixel) }),
        drawImage: () => {},
    };
    const screen = { width: 320, height: 240, getContext: () => context };
    class MediaRecorder {
        static isTypeSupported() { return true; }
        constructor(stream) { recorders.push(this); this.stream = stream; this.mimeType = "video/webm"; }
        start() { this.started = true; }
        stop() { this.stopped = true; finishVideo = () => this.onstop(); }
    }
    const api = runInNewContext(stripTypeScriptTypes(`
        let hasAppFrame = false;
        ${recordingCode}
        ({
            startRecording, stopRecording, recordFrame,
            realFrame() { hasAppFrame = true; if (recording) recording.rendered++; recordFrame(); }
        })
    `), {
        screen, performance: { now: () => now }, MediaRecorder, Blob, btoa,
        document: { createElement: () => ({
            width: 0, height: 0, getContext: () => context,
            captureStream() { return { width: this.width, height: this.height }; },
        }) },
        fetch: (url) => { uploads.push(url); return Promise.resolve({ ok: true }); },
        post: (url, body) => { posts.push({ url, body }); return Promise.resolve(); },
    });
    return {
        ...api, screen, uploads, posts, recorders,
        setFrame(time, value) { now = time; pixel = value; },
        finishVideo() { finishVideo(); },
    };
}

test("recording waits for a real LORES frame before capturing or choosing video dimensions", async () => {
    const h = browserHarness();
    h.startRecording("first", 15, true, 2);
    assert.equal(h.uploads.length, 0);
    assert.equal(h.recorders.length, 0);
    h.screen.width = 160; h.screen.height = 120;
    h.setFrame(100, 1); h.realFrame();
    h.setFrame(200, 2); h.realFrame();
    assert.equal(h.uploads.length, 2);
    for (const url of h.uploads) assert.match(url, /w=160&h=120/);
    assert.equal(h.recorders.length, 1);
    assert.equal(h.recorders[0].stream.width, 320);
    assert.equal(h.recorders[0].stream.height, 240);
    const stopping = h.stopRecording("first");
    h.finishVideo();
    await stopping;
    assert.equal(h.recorders[0].stopped, true);
    assert.equal(h.posts.at(-1).body.rendered_frames, 2);
});

test("stopping captures the latest screen within a sampling interval and still deduplicates unchanged frames", async () => {
    const h = browserHarness();
    h.setFrame(0, 1); h.realFrame();
    h.startRecording("first", 1, false, 1);
    h.setFrame(20, 2); h.realFrame();
    assert.equal(h.uploads.length, 1);
    await h.stopRecording("first");
    assert.equal(h.uploads.length, 2);
    assert.match(h.uploads.at(-1), /t=20.0/);
    h.startRecording("second", 1, false, 1);
    await h.stopRecording("second");
    assert.equal(h.uploads.length, 3);
});

test("browser overlap guard retains and stops the original MediaRecorder, including during export", async () => {
    const h = browserHarness();
    h.realFrame();
    h.startRecording("first", 15, true, 1);
    h.startRecording("second", 15, true, 1);
    assert.match(h.posts.at(-1).body.error, /already in progress/);
    assert.equal(h.posts.at(-1).body.id, "second");
    assert.equal(h.recorders.length, 1);
    const stopping = h.stopRecording("first");
    assert.equal(h.recorders[0].stopped, true);
    h.startRecording("third", 15, true, 1);
    assert.match(h.posts.at(-1).body.error, /already in progress/);
    h.finishVideo();
    await stopping;
    assert.equal(h.posts.at(-1).body.id, "first");
    assert.equal(h.posts.at(-1).body.error, undefined);
    h.startRecording("fourth", 15, true, 1);
    assert.equal(h.recorders.length, 2);
    const last = h.stopRecording("fourth");
    h.finishVideo();
    await last;
});

// Independent GIF decoder: require a complete EOI code, not just all pixels.
function decodeGif(gif) {
    const paletteSize = 1 << ((gif[10] & 7) + 1);
    const palette = Array.from({ length: paletteSize }, (_, i) => gif[13 + i * 3]);
    let pos = 13 + paletteSize * 3;
    const blocks = () => {
        const bytes = [];
        while (gif[pos]) {
            const size = gif[pos++];
            bytes.push(...gif.subarray(pos, pos + size));
            pos += size;
        }
        pos++;
        return bytes;
    };
    while (gif[pos] === 0x21) { pos += 2; blocks(); }
    assert.equal(gif[pos], 0x2c);
    pos += 10;
    const min = gif[pos++], clear = 1 << min, eoi = clear + 1;
    const bytes = blocks();
    let bit = 0, width = min + 1, next = eoi + 1, previous, clears = 0;
    let table = Array.from({ length: clear }, (_, i) => [i]);
    const pixels = [], widths = [];
    for (;;) {
        assert.ok(bit + width <= bytes.length * 8, "Incomplete GIF code before EOI");
        let code = 0;
        for (let i = 0; i < width; i++, bit++) code |= ((bytes[bit >> 3] >> (bit & 7)) & 1) << i;
        if (code === clear) {
            clears++;
            table = Array.from({ length: clear }, (_, i) => [i]);
            width = min + 1; next = eoi + 1; previous = undefined;
            continue;
        }
        if (code === eoi) return { pixels: pixels.map((i) => palette[i]), widths, eoiWidth: width, clears };
        const value = code < next ? table[code] : code === next && previous ? [...previous, previous[0]] : undefined;
        assert.ok(value, `Invalid GIF dictionary code ${code}`);
        pixels.push(...value);
        if (previous && next < 4096) {
            table[next++] = [...previous, value[0]];
            if (next === 1 << width && width < 12) { width++; widths.push(width); }
        }
        previous = value;
    }
}

test("GIF LZW round trips width boundaries, final-prefix EOI growth and dictionary resets", () => {
    let seed = 0x12345678;
    const random = () => { seed ^= seed << 13; seed ^= seed >>> 17; seed ^= seed << 5; return seed >>> 0; };
    let finalBoundary = false, fullDictionary = false;
    for (const colors of [4, 16, 256]) {
        for (const length of [11, 12, 32, 255, 256, 1024, 50000]) {
            for (let attempt = 0; attempt < (length === 11 ? 100 : 1); attempt++) {
                const pixels = Array.from({ length }, () => random() % colors);
                const data = Uint8Array.from(pixels.flatMap((p) => [p, 0, 0, 255]));
                const decoded = decodeGif(encodeGif(length, 1, [{ data, delayMs: 100 }]));
                assert.deepEqual(decoded.pixels, pixels);
                if (colors === 4 && length === 11 && decoded.eoiWidth === 5) finalBoundary = true;
                if (decoded.widths.includes(12) && decoded.clears > 1) fullDictionary = true;
            }
        }
    }
    assert.ok(finalBoundary, "Exercise the four-colour 11-pixel final prefix boundary");
    assert.ok(fullDictionary, "Exercise 12-bit codes and dictionary reset");
});

test("GIF integer scales replicate pixels without gaps", () => {
    for (const scale of [1, 2, 3, 4]) {
        const data = Uint8Array.from([11, 0, 0, 255, 22, 0, 0, 255]);
        const gif = encodeGif(2, 1, [{ data, delayMs: 100 }], scale);
        assert.equal(gif.readUInt16LE(6), 2 * scale);
        assert.equal(gif.readUInt16LE(8), scale);
        const expected = Array.from({ length: scale }, () => [
            ...Array(scale).fill(11), ...Array(scale).fill(22),
        ]).flat();
        assert.deepEqual(decodeGif(gif).pixels, expected);
    }
});
