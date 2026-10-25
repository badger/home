// Dependency-free encoders for Badge Simulator recordings: animated GIF, PNG
// and a labelled contact sheet built from raw RGBA frames.
import { deflateSync } from "node:zlib";

// ---- PNG -------------------------------------------------------------------------
const crcTable = Array.from({ length: 256 }, (_, n) => {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    return c >>> 0;
});
function crc32(buf) {
    let c = 0xffffffff;
    for (const byte of buf) c = crcTable[(c ^ byte) & 0xff] ^ (c >>> 8);
    return (c ^ 0xffffffff) >>> 0;
}
function chunk(type, data) {
    const out = Buffer.alloc(12 + data.length);
    out.writeUInt32BE(data.length, 0);
    out.write(type, 4, "ascii");
    data.copy(out, 8);
    out.writeUInt32BE(crc32(out.subarray(4, 8 + data.length)), 8 + data.length);
    return out;
}
export function encodePng(width, height, rgba) {
    const raw = Buffer.alloc((width * 4 + 1) * height);
    for (let y = 0; y < height; y++) {
        raw[y * (width * 4 + 1)] = 0;
        Buffer.from(rgba.buffer, rgba.byteOffset + y * width * 4, width * 4).copy(raw, y * (width * 4 + 1) + 1);
    }
    const header = Buffer.alloc(13);
    header.writeUInt32BE(width, 0);
    header.writeUInt32BE(height, 4);
    header[8] = 8; header[9] = 6;
    return Buffer.concat([
        Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
        chunk("IHDR", header), chunk("IDAT", deflateSync(raw)), chunk("IEND", Buffer.alloc(0)),
    ]);
}

// ---- palette -----------------------------------------------------------------------
// Exact palette when the recording uses <= 256 colours (typical for badge apps),
// otherwise a weighted median cut.
function buildPalette(frames) {
    const counts = new Map();
    for (const f of frames) {
        const px = f.data;
        for (let i = 0; i < px.length; i += 4) {
            const key = (px[i] << 16) | (px[i + 1] << 8) | px[i + 2];
            counts.set(key, (counts.get(key) ?? 0) + 1);
        }
    }
    const colors = [...counts.keys()];
    if (colors.length <= 256) return colors;
    let boxes = [colors];
    const channel = (c, ch) => (c >> (16 - ch * 8)) & 255;
    while (boxes.length < 256) {
        let best = -1, bestRange = 0, bestCh = 0;
        boxes.forEach((box, i) => {
            if (box.length < 2) return;
            for (let ch = 0; ch < 3; ch++) {
                let lo = 255, hi = 0;
                for (const c of box) { const v = channel(c, ch); if (v < lo) lo = v; if (v > hi) hi = v; }
                if (hi - lo > bestRange) { bestRange = hi - lo; best = i; bestCh = ch; }
            }
        });
        if (best < 0) break;
        const box = boxes[best].sort((a, b) => channel(a, bestCh) - channel(b, bestCh));
        const total = box.reduce((s, c) => s + counts.get(c), 0);
        let acc = 0, cut = 1;
        for (; cut < box.length - 1; cut++) { acc += counts.get(box[cut - 1]); if (acc >= total / 2) break; }
        boxes.splice(best, 1, box.slice(0, cut), box.slice(cut));
    }
    return boxes.map((box) => {
        let r = 0, g = 0, b = 0, n = 0;
        for (const c of box) { const w = counts.get(c); r += (c >> 16) * w; g += ((c >> 8) & 255) * w; b += (c & 255) * w; n += w; }
        return (Math.round(r / n) << 16) | (Math.round(g / n) << 8) | Math.round(b / n);
    });
}
function nearestIndex(palette) {
    const exact = new Map(palette.map((c, i) => [c, i]));
    return (key) => {
        let idx = exact.get(key);
        if (idx !== undefined) return idx;
        let best = 0, bestD = Infinity;
        const r = key >> 16, g = (key >> 8) & 255, b = key & 255;
        palette.forEach((c, i) => {
            const d = (r - (c >> 16)) ** 2 + (g - ((c >> 8) & 255)) ** 2 + (b - (c & 255)) ** 2;
            if (d < bestD) { bestD = d; best = i; }
        });
        exact.set(key, best);
        return best;
    };
}

// ---- GIF ---------------------------------------------------------------------------
function lzw(indices, minCodeSize) {
    const clear = 1 << minCodeSize, eoi = clear + 1;
    const out = [];
    let cur = 0, bits = 0, codeSize = minCodeSize + 1, next = eoi + 1;
    let table = new Map();
    const emit = (code) => {
        cur |= code << bits; bits += codeSize;
        while (bits >= 8) { out.push(cur & 255); cur >>>= 8; bits -= 8; }
    };
    emit(clear);
    let prefix = indices[0];
    for (let i = 1; i < indices.length; i++) {
        const k = indices[i];
        const key = (prefix << 8) | k;
        const found = table.get(key);
        if (found !== undefined) { prefix = found; continue; }
        emit(prefix);
        if (next === 4096) {
            emit(clear);
            table = new Map(); next = eoi + 1; codeSize = minCodeSize + 1;
        } else {
            if (next >= 1 << codeSize) codeSize++;
            table.set(key, next++);
        }
        prefix = k;
    }
    emit(prefix);
    emit(eoi);
    if (bits > 0) out.push(cur & 255);
    return out;
}

// frames: [{ data: Uint8Array RGBA, delayMs }], all width x height. Scaled up by
// pixel replication so small badge screens stay crisp.
export function encodeGif(width, height, frames, scale = 1) {
    const palette = buildPalette(frames);
    let tableBits = 1;
    while (1 << tableBits < Math.max(palette.length, 2)) tableBits++;
    const minCodeSize = Math.max(2, tableBits);
    const lookup = nearestIndex(palette);
    const W = width * scale, H = height * scale;
    const bytes = [];
    const u16 = (v) => bytes.push(v & 255, (v >> 8) & 255);
    bytes.push(..."GIF89a".split("").map((c) => c.charCodeAt(0)));
    u16(W); u16(H);
    bytes.push(0xf0 | (tableBits - 1), 0, 0);
    for (let i = 0; i < 1 << tableBits; i++) {
        const c = palette[i] ?? 0;
        bytes.push(c >> 16, (c >> 8) & 255, c & 255);
    }
    bytes.push(0x21, 0xff, 0x0b, ..."NETSCAPE2.0".split("").map((c) => c.charCodeAt(0)), 3, 1, 0, 0, 0);
    let carry = 0;
    for (const frame of frames) {
        // GIF delays are centiseconds; carry rounding so total duration stays accurate.
        const exact = frame.delayMs / 10 + carry;
        const delay = Math.max(2, Math.round(exact));
        carry = exact - delay;
        bytes.push(0x21, 0xf9, 4, 0); u16(delay); bytes.push(0, 0);
        bytes.push(0x2c); u16(0); u16(0); u16(W); u16(H); bytes.push(0);
        const indices = new Uint8Array(W * H);
        const px = frame.data;
        for (let y = 0; y < height; y++) {
            for (let x = 0; x < width; x++) {
                const o = (y * width + x) * 4;
                const idx = lookup((px[o] << 16) | (px[o + 1] << 8) | px[o + 2]);
                for (let dy = 0; dy < scale; dy++) indices.fill(idx, (y * scale + dy) * W + x * scale, (y * scale + dy) * W + x * scale + scale);
            }
        }
        bytes.push(minCodeSize);
        const data = lzw(indices, minCodeSize);
        for (let i = 0; i < data.length; i += 255) {
            const block = data.slice(i, i + 255);
            bytes.push(block.length, ...block);
        }
        bytes.push(0);
    }
    bytes.push(0x3b);
    return Buffer.from(bytes);
}

// ---- contact sheet ---------------------------------------------------------------
const glyphs = {
    0: "111101101101111", 1: "010110010010111", 2: "111001111100111", 3: "111001111001111",
    4: "101101111001001", 5: "111100111001111", 6: "111100111101111", 7: "111001001001001",
    8: "111101111101111", 9: "111101111001111", ".": "000000000000010", s: "000011110011110",
    "#": "101111101111101", " ": "000000000000000",
};
// frames: [{ data, t }] at width x height. Returns a PNG grid with "#n t.ts" labels.
export function contactSheet(width, height, frames, { columns = 4, scale = 1 } = {}) {
    const cols = Math.min(columns, frames.length);
    const rows = Math.ceil(frames.length / cols);
    const gap = 4, label = 14, cw = width * scale, ch = height * scale;
    const W = gap + cols * (cw + gap), H = gap + rows * (ch + label + gap);
    const out = new Uint8Array(W * H * 4);
    for (let i = 0; i < out.length; i += 4) { out[i] = 36; out[i + 1] = 41; out[i + 2] = 47; out[i + 3] = 255; }
    frames.forEach((frame, n) => {
        const ox = gap + (n % cols) * (cw + gap), oy = gap + Math.floor(n / cols) * (ch + label + gap);
        for (let y = 0; y < ch; y++) {
            for (let x = 0; x < cw; x++) {
                const s = (Math.floor(y / scale) * width + Math.floor(x / scale)) * 4, d = ((oy + y) * W + ox + x) * 4;
                out[d] = frame.data[s]; out[d + 1] = frame.data[s + 1]; out[d + 2] = frame.data[s + 2]; out[d + 3] = 255;
            }
        }
        const text = `#${n + 1} ${(frame.t / 1000).toFixed(2)}s`;
        [...text].forEach((c, i) => {
            const g = glyphs[c] ?? glyphs[" "];
            for (let gy = 0; gy < 5; gy++) for (let gx = 0; gx < 3; gx++) {
                if (g[gy * 3 + gx] !== "1") continue;
                for (let py = 0; py < 2; py++) for (let px = 0; px < 2; px++) {
                    const x = ox + i * 8 + gx * 2 + px, y = oy + ch + 2 + gy * 2 + py;
                    if (x < W && y < H) { const d = (y * W + x) * 4; out[d] = out[d + 1] = out[d + 2] = 230; }
                }
            }
        });
    });
    return encodePng(W, H, out);
}
