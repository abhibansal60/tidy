// node cues.mjs > cues.json : 120 BPM bed (beat 0.5 s) plus hits synced to docs/shotlist.md
const cues = [], at = (t, type, o = {}) => cues.push({ t: +t.toFixed(3), type, ...o });
const ROOTS = [55, 43.65, 65.41, 49];                      // A, F, C, G: one bar (2 s) each
for (let t = 0; t < 34; t += 0.5) {
  if (t >= 21.5 && t < 22.5) continue;                     // drop out at the twist
  at(t, 'kick', { gain: 0.55 });
  at(t + 0.25, 'hat', { gain: 0.8 });
  at(t, 'bass', { f: ROOTS[Math.floor(t / 2) % 4], gain: t >= 22.5 && t < 28 ? 0.5 : 0.8 });
}
for (const t of [0, 3, 6, 10, 13.5, 18, 24.5, 28, 31]) at(t, 'whoosh', { gain: 0.8 });
for (let t = 0.05; t < 1.0; t += 0.09) at(t, 'click', { gain: 0.35 });   // ring counting
at(2.0, 'thump');                                                          // "Is it right?"
for (let t = 3.1; t < 4.4; t += 0.25) at(t, 'pop', { gain: 0.35 });       // dots wave
at(4.3, 'click'); at(4.45, 'click');
for (let i = 0; i < 30; i++) at(6.2 + i / 30, 'click', { gain: 0.25 });   // typing
at(7.7, 'pop'); at(8.7, 'pop'); at(8.8, 'thump', { gain: 0.5 });
at(10.7, 'click'); at(10.85, 'click'); at(12.0, 'pop');
at(13.84, 'pop'); at(15.52, 'thump', { gain: 0.7 }); at(16.0, 'pop'); at(16.4, 'click');
for (let t = 18.15; t < 19.0; t += 0.1) at(t, 'pop', { gain: 0.25 }); at(19.6, 'pop');
at(21.5, 'thump'); at(23.2, 'thump'); at(23.22, 'click');                 // twist and stamp
for (let t = 24.65; t < 25.5; t += 0.1) at(t, 'pop', { gain: 0.25 }); at(26.1, 'pop'); at(26.6, 'thump', { gain: 0.6 });
at(28.4, 'click'); at(28.6, 'click'); at(28.85, 'click'); at(29.5, 'pop');
at(31.6, 'pop'); at(32.2, 'pop'); at(32.9, 'pop'); at(33.0, 'thump', { gain: 0.6 });
console.log(JSON.stringify(cues.sort((a, b) => a.t - b.t)));
