#!/usr/bin/env node
// Persistent klattsch render bridge.
//
// Reads line-delimited JSON requests on stdin, writes line-delimited JSON
// responses on stdout. Avoids node-startup-per-eval cost.
//
// Request shapes:
//   {"id":N,"mode":"compile","text":"HH AH L OW","sampleRate":48000}
//   {"id":N,"mode":"raw","schedule":[{atMs,target,transitionMs}...],
//    "durMs":1234.0,"sampleRate":48000,"initialTarget":{...}}
//
// Response:
//   {"id":N,"ok":true,"sampleRate":48000,"nSamples":28320,
//    "samples_b64":"...","durMs":590.0,"warnings":[]}
//   {"id":N,"ok":false,"error":"..."}
//
// Samples are Float32 little-endian, base64-encoded. ~33% overhead but
// stdio pipe bandwidth is ample.

import { compileString, FormantSynth } from './klattsch/src/engine/index.js';
import readline from 'node:readline';

const rl = readline.createInterface({ input: process.stdin });

function render({ schedule, sampleRate, durMs, initialTarget }) {
  const synth = new FormantSynth({ sampleRate, schedule, initialTarget });
  const n = Math.ceil(durMs * sampleRate / 1000);
  const buf = new Float32Array(n);
  synth.process(buf);
  return buf;
}

function bufferToB64(f32) {
  // Float32Array shares its underlying ArrayBuffer; Buffer.from views it.
  return Buffer.from(f32.buffer, f32.byteOffset, f32.byteLength).toString('base64');
}

rl.on('line', (line) => {
  let req;
  try { req = JSON.parse(line); }
  catch (e) {
    process.stdout.write(JSON.stringify({ ok:false, error:'invalid json' }) + '\n');
    return;
  }
  const id = req.id;
  try {
    const sampleRate = req.sampleRate ?? 48000;
    let schedule, durMs, warnings = [];
    if (req.mode === 'compile') {
      const r = compileString(req.text);
      schedule = r.schedule;
      durMs = r.totalMs;
      warnings = r.warnings ?? [];
    } else if (req.mode === 'raw') {
      schedule = req.schedule;
      durMs = req.durMs;
    } else if (req.mode === 'schedule') {
      // Compile-only: return the schedule without rendering
      const r = compileString(req.text);
      process.stdout.write(JSON.stringify({
        id, ok:true, schedule: r.schedule, totalMs: r.totalMs,
        warnings: r.warnings ?? [],
      }) + '\n');
      return;
    } else {
      throw new Error(`unknown mode: ${req.mode}`);
    }
    const samples = render({ schedule, sampleRate, durMs, initialTarget: req.initialTarget });
    const out = {
      id, ok:true, sampleRate, nSamples: samples.length,
      durMs, warnings, samples_b64: bufferToB64(samples),
    };
    process.stdout.write(JSON.stringify(out) + '\n');
  } catch (e) {
    process.stdout.write(JSON.stringify({ id, ok:false, error: String(e?.message ?? e) }) + '\n');
  }
});

// Signal readiness (caller can wait for this line)
process.stdout.write(JSON.stringify({ ready: true }) + '\n');
