/* ============================================================
 * thinking-orbs — 点状 3D 思考光球动画引擎(纯 JS 移植)
 *
 * 移植自 Jakub Antalik 的开源项目 thinking-orbs (MIT)
 *   https://github.com/Jakubantalik/thinking-orbs
 * 视觉基准:https://orbs.jakubantalik.com
 *
 * 几何计算与官方源码逐行一致:同一套 frame 函数 + z 排序画家,
 * 只去掉了 TypeScript 类型与 React 外壳,改为直接驱动 canvas。
 * 9 种状态 × 9 种模式,共享同一时钟,保持相位一致。
 * ============================================================ */
(function () {
  'use strict';

  /* ────────────────── core · 共享原语 ────────────────── */

  function lerp(a, b, f) { return a + (b - a) * f; }
  function frac(x) { return x - Math.floor(x); }

  /** Deterministic hash in [0, 1). */
  function hashD(a, b) {
    const h = Math.sin(a * 12.9898 + b * 78.233) * 43758.5453;
    return h - Math.floor(h);
  }

  /** Value noise on a 2D lattice — smooth, deterministic, cheap. */
  function vnoise(x, y) {
    const xi = Math.floor(x);
    const yi = Math.floor(y);
    let fx = x - xi;
    let fy = y - yi;
    fx = fx * fx * (3 - 2 * fx);
    fy = fy * fy * (3 - 2 * fy);
    const a = hashD(xi, yi);
    const b = hashD(xi + 1, yi);
    const c = hashD(xi, yi + 1);
    const d = hashD(xi + 1, yi + 1);
    return a + (b - a) * fx + (c - a) * fy + (a - b - c + d) * fx * fy;
  }

  /** Stable directions on a unit sphere (Fibonacci lattice). */
  function fibDir(i, n) {
    const golden = Math.PI * (3 - Math.sqrt(5));
    const y = 1 - (2 * (i + 0.5)) / n;
    const rad = Math.sqrt(1 - y * y);
    const a = i * golden;
    return [rad * Math.cos(a), y, rad * Math.sin(a)];
  }

  /** Shortest signed angular distance, wrapped to (-π, π]. */
  function angleDelta(a, b) {
    return Math.atan2(Math.sin(a - b), Math.cos(a - b));
  }

  /** Shared spin + tilt + orthographic projection. */
  function makeProj(yaw, tilt, cx, cy, scale) {
    const st = Math.sin(tilt);
    const ct = Math.cos(tilt);
    const sy = Math.sin(yaw);
    const cyw = Math.cos(yaw);
    return (x, y, z) => {
      const x1 = x * cyw + z * sy;
      const z1 = -x * sy + z * cyw;
      const y1 = y * ct - z1 * st;
      const z2 = y * st + z1 * ct;
      return [cx + x1 * scale, cy - y1 * scale, z2];
    };
  }

  /** Dot radii were tuned for a 300pt frame; sub-linear scaling keeps small spinners legible. */
  function radiusScale(size, pow) {
    return Math.pow(size / 300, pow);
  }

  /** Turn raw mode output into a finished frame: cull, clamp, z-sort far→near. */
  function finalizeFrame(dots, lines, rMin) {
    const visible = [];
    for (const d of dots) {
      if ((d.a === undefined ? 1 : d.a) < 0.02) continue;
      d.r = Math.max(rMin === undefined ? 0.3 : rMin, d.r);
      visible.push(d);
    }
    visible.sort((a, b) => a.z - b.z);
    return { dots: visible, lines: (lines || []).filter((l) => (l.a === undefined ? 1 : l.a) >= 0.02) };
  }

  /** Paint a finished frame. Lines first, so nodes sit on top of their edges. */
  function paintFrame(ctx, frame, dark) {
    for (const l of frame.lines) {
      const alpha = l.a === undefined ? 1 : l.a;
      const w = Math.min(1, Math.max(0, l.white));
      const g = Math.round((dark ? 1 - w : w) * 255);
      ctx.strokeStyle = 'rgba(' + g + ',' + g + ',' + g + ',' + alpha + ')';
      ctx.lineWidth = l.w;
      ctx.beginPath();
      ctx.moveTo(l.x1, l.y1);
      ctx.lineTo(l.x2, l.y2);
      ctx.stroke();
    }
    for (const d of frame.dots) {
      const alpha = d.a === undefined ? 1 : d.a;
      const w = Math.min(1, Math.max(0, d.white));
      const g = Math.round((dark ? 1 - w : w) * 255);
      ctx.fillStyle = 'rgba(' + g + ',' + g + ',' + g + ',' + alpha + ')';
      ctx.beginPath();
      ctx.arc(d.x, d.y, d.r, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  /* ────────────────── modes · 9 种状态几何 ────────────────── */

  /** orbits · working — 粒子在倾斜轨道上运行,无核 */
  function frameOrbits(size, t, o) {
    const cx = size / 2;
    const cy = size / 2;
    const R = (size / 2) * 0.82;
    const pt = makeProj(t * 0.12, 0.3, cx, cy, 1);
    const rs = radiusScale(size, o.rsPow === undefined ? 0.6 : o.rsPow);

    const dots = [];
    const orbitN = o.orbitN === undefined ? 12 : o.orbitN;
    const ghostN = o.ghostN === undefined ? 40 : o.ghostN;
    const particles = o.particles === undefined ? 3 : o.particles;

    for (let orb = 0; orb < orbitN; orb++) {
      const h1 = hashD(orb, 1.7);
      const h2 = hashD(orb, 5.2);
      const h3 = hashD(orb, 8.9);
      const ro = R * (0.45 + 0.52 * h1);
      const th = h1 * 2 * Math.PI;
      const phi = Math.acos(2 * h2 - 1);
      const nx = Math.sin(phi) * Math.cos(th);
      const ny = Math.cos(phi);
      const nz = Math.sin(phi) * Math.sin(th);
      let ux = -ny;
      let uy = nx;
      const uz = 0;
      const ul = Math.max(1e-6, Math.sqrt(ux * ux + uy * uy));
      ux /= ul;
      uy /= ul;
      const vx = ny * uz - nz * uy;
      const vy = nz * ux - nx * uz;
      const vz = nx * uy - ny * ux;
      const speed = (0.25 + 0.55 * h3) * (h3 > 0.5 ? 1 : -1);

      for (let k = 0; k < ghostN; k++) {
        const a = (k / ghostN) * 2 * Math.PI;
        const p = pt(
          (ux * Math.cos(a) + vx * Math.sin(a)) * ro,
          (uy * Math.cos(a) + vy * Math.sin(a)) * ro,
          (uz * Math.cos(a) + vz * Math.sin(a)) * ro
        );
        const depth = (p[2] / ro + 1) / 2;
        dots.push({
          x: p[0], y: p[1], z: p[2],
          r: (o.ghostR === undefined ? 0.9 : o.ghostR) * rs,
          white: 0.72,
          a: (o.ghostA === undefined ? 0.5 : o.ghostA) * (0.4 + 0.6 * depth)
        });
      }
      for (let m = 0; m < particles; m++) {
        const a = t * speed + (m / particles) * 2 * Math.PI + h2 * 6;
        const p = pt(
          (ux * Math.cos(a) + vx * Math.sin(a)) * ro,
          (uy * Math.cos(a) + vy * Math.sin(a)) * ro,
          (uz * Math.cos(a) + vz * Math.sin(a)) * ro
        );
        const depth = (p[2] / ro + 1) / 2;
        dots.push({
          x: p[0], y: p[1], z: p[2],
          r: ((o.partR === undefined ? 1.2 : o.partR) + (o.partRDepth === undefined ? 1.6 : o.partRDepth) * depth) * rs,
          white: 0.3 - 0.22 * depth
        });
      }
    }
    return finalizeFrame(dots, [], o.rMin);
  }

  /** globe · searching — 经纬网格球,扫描子午线划过 */
  function frameGlobe(size, t, o) {
    const spin = 0.5;
    const cx = size / 2;
    const cy = size / 2;
    const radius = (size / 2) * 0.82;
    const tilt = 0.4 + 0.06 * Math.sin(t * 0.35);
    const pt = makeProj(t * spin, tilt, cx, cy, radius);
    const scan = t * (spin + (1.7 - spin) * (o.scanMul === undefined ? 1 : o.scanMul));
    const rs = radiusScale(size, o.rsPow === undefined ? 0.6 : o.rsPow);
    const dimBase = o.dimBase === undefined ? 1 : o.dimBase;

    const dots = [];
    const latRings = o.latRings === undefined ? 17 : o.latRings;
    const lonDensity = o.lonDensity === undefined ? 44 : o.lonDensity;
    for (let li = 0; li <= latRings; li++) {
      const lat = -Math.PI / 2 + (li / latRings) * Math.PI;
      const cosLat = Math.cos(lat);
      const sinLat = Math.sin(lat);
      const lonCount = Math.max(1, Math.round(Math.abs(cosLat) * lonDensity));
      for (let lj = 0; lj < lonCount; lj++) {
        const lon = (lj / lonCount) * 2 * Math.PI;
        const p = pt(cosLat * Math.cos(lon), sinLat, cosLat * Math.sin(lon));
        const depth = (p[2] + 1) / 2;
        const d = angleDelta(lon + t * spin, scan);
        const boost = Math.exp(-(d * d) / 0.18) * Math.max(0, p[2]);
        dots.push({
          x: p[0], y: p[1], z: p[2],
          r: ((o.rBase === undefined ? 0.6 : o.rBase) + (o.rDepth === undefined ? 1.7 : o.rDepth) * depth + (o.rBoost === undefined ? 1 : o.rBoost) * boost) * rs,
          white: (o.inkFar === undefined ? 0.62 : o.inkFar) - (o.inkSpan === undefined ? 0.54 : o.inkSpan) * depth,
          a: dimBase + (1 - dimBase) * Math.min(1, boost)
        });
      }
    }
    return finalizeFrame(dots, [], o.rMin);
  }

  /** rubik · solving — 魔方带逐层扭转:打乱 → 归位 → 停息 → 循环 */
  function makeMoves(count) {
    const moves = [];
    for (let i = 0; i < count; i++) {
      const axis = Math.min(2, Math.floor(hashD(i, 2.3) * 3));
      const lo = -1.0 + 0.5 * Math.min(3, Math.floor(hashD(i, 5.9) * 4));
      const dir = hashD(i, 7.7) < 0.5 ? 1 : -1;
      moves.push({ axis: axis, lo: lo, hi: lo + 0.5, ang: (dir * Math.PI) / 2 });
    }
    return moves;
  }

  function solveCycle(time, count, slotDur, rest) {
    const cyc = 2 * count * slotDur + rest;
    const tc = time % cyc;
    const amount = new Array(count).fill(0);
    let active = -1;
    if (tc < 2 * count * slotDur) {
      const slot = Math.floor(tc / slotDur);
      const p = (tc - slot * slotDur) / slotDur;
      const cl = Math.min(1, p / 0.7);
      const ep = 1 - Math.pow(1 - cl, 3);
      if (slot < count) {
        for (let i = 0; i < slot; i++) amount[i] = 1;
        amount[slot] = ep;
        active = slot;
      } else {
        const u = 2 * count - 1 - slot;
        for (let i = 0; i < u; i++) amount[i] = 1;
        amount[u] = 1 - ep;
        active = u;
      }
    }
    return { amount: amount, active: active };
  }

  function applyMoves(pt3, moves, sc) {
    let x = pt3[0];
    let y = pt3[1];
    let z = pt3[2];
    let inActive = false;
    for (let i = 0; i < moves.length; i++) {
      if (sc.amount[i] <= 0) continue;
      const mv = moves[i];
      const coord = mv.axis === 0 ? x : mv.axis === 1 ? y : z;
      if (coord < mv.lo || coord >= mv.hi) continue;
      if (i === sc.active) inActive = true;
      const a = mv.ang * sc.amount[i];
      const ca = Math.cos(a);
      const sa = Math.sin(a);
      if (mv.axis === 0) {
        const y2 = y * ca - z * sa;
        z = y * sa + z * ca;
        y = y2;
      } else if (mv.axis === 1) {
        const x2 = x * ca + z * sa;
        z = -x * sa + z * ca;
        x = x2;
      } else {
        const x2 = x * ca - y * sa;
        y = x * sa + y * ca;
        x = x2;
      }
    }
    return [x, y, z, inActive];
  }

  function frameRubik(size, t, o) {
    const cx = size / 2;
    const cy = size / 2;
    const R = (size / 2) * 0.82;
    const pt = makeProj(t * 0.55, 0.35 + 0.1 * Math.sin(t * 0.9), cx, cy, R);
    const rs = radiusScale(size, o.rsPow === undefined ? 0.6 : o.rsPow);
    const moveCount = o.moveCount === undefined ? 14 : o.moveCount;
    const moves = makeMoves(moveCount);
    const sc = solveCycle(t, moveCount, 0.42, 1.2);

    const dots = [];
    const latRings = o.latRings === undefined ? 15 : o.latRings;
    const lonDensity = o.lonDensity === undefined ? 40 : o.lonDensity;
    for (let li = 0; li <= latRings; li++) {
      const lat = -Math.PI / 2 + (li / latRings) * Math.PI;
      const cosLat = Math.cos(lat);
      const sinLat = Math.sin(lat);
      const lonCount = Math.max(1, Math.round(Math.abs(cosLat) * lonDensity));
      for (let lj = 0; lj < lonCount; lj++) {
        const lon = (lj / lonCount) * 2 * Math.PI;
        const m = applyMoves([cosLat * Math.cos(lon), sinLat, cosLat * Math.sin(lon)], moves, sc);
        const p = pt(m[0], m[1], m[2]);
        const depth = (p[2] + 1) / 2;
        dots.push({
          x: p[0], y: p[1], z: p[2],
          r: ((o.rBase === undefined ? 0.6 : o.rBase) + (o.rDepth === undefined ? 1.7 : o.rDepth) * depth + (m[3] ? (o.rActive === undefined ? 0.3 : o.rActive) : 0)) * rs,
          white: (o.inkFar === undefined ? 0.62 : o.inkFar) - (o.inkSpan === undefined ? 0.54 : o.inkSpan) * depth - (m[3] ? 0.14 : 0)
        });
      }
    }
    return finalizeFrame(dots, [], o.rMin);
  }

  /** wave · listening — 两股异速波形滚过球面 */
  function frameWave(size, t, o) {
    const cx = size / 2;
    const cy = size / 2;
    const R = (size / 2) * 0.874;
    const pt = makeProj(t * 0.18, 0.38, cx, cy, 1);
    const rs = radiusScale(size, o.rsPow === undefined ? 0.6 : o.rsPow);

    const dots = [];
    const rings = o.rings === undefined ? 15 : o.rings;
    const lonDensity = o.lonDensity === undefined ? 40 : o.lonDensity;
    for (let ri = 0; ri <= rings; ri++) {
      const lat = -Math.PI / 2 + (ri / rings) * Math.PI;
      const cosLat = Math.cos(lat);
      const sinLat = Math.sin(lat);
      const w = 0.62 * Math.sin(t * 2.1 - ri * 0.52) + 0.38 * Math.sin(t * 1.27 + ri * 0.83);
      const rr = R * (0.88 + 0.105 * w);
      const lonCount = Math.max(1, Math.round(Math.abs(cosLat) * lonDensity));
      for (let lj = 0; lj < lonCount; lj++) {
        const lon = (lj / lonCount) * 2 * Math.PI;
        const p = pt(cosLat * Math.cos(lon) * rr, sinLat * rr, cosLat * Math.sin(lon) * rr);
        const depth = (p[2] / R + 1) / 2;
        const crest = Math.max(0, w);
        dots.push({
          x: p[0], y: p[1], z: p[2],
          r: ((o.rBase === undefined ? 0.6 : o.rBase) + (o.rDepth === undefined ? 1.7 : o.rDepth) * depth) * (1 + 0.4 * crest) * rs,
          white: 0.66 - 0.56 * depth - 0.1 * crest
        });
      }
    }
    return finalizeFrame(dots, [], o.rMin);
  }

  /** web · connecting — 节点在球面漂移,近邻连线,亮包沿随机节点对传输 */
  function frameWeb(size, t, o) {
    const cx = size / 2;
    const cy = size / 2;
    const R = (size / 2) * 0.8 * (o.spread === undefined ? 1 : o.spread);
    const pt = makeProj(t * 0.12, 0.32, cx, cy, R);
    const rs = radiusScale(size, o.rsPow === undefined ? 0.6 : o.rsPow);

    const nodeN = o.nodeN === undefined ? 30 : o.nodeN;
    const thr = o.thr === undefined ? 0.72 : o.thr;
    const nodeR = o.nodeR === undefined ? 1.4 : o.nodeR;
    const nodeRDepth = o.nodeRDepth === undefined ? 1.8 : o.nodeRDepth;

    const nodes = [];
    for (let i = 0; i < nodeN; i++) {
      const d = fibDir(i, nodeN);
      const x = d[0] + 0.3 * (vnoise(i * 0.31 + 9, t * 0.24) - 0.5) * 2;
      const y = d[1] + 0.3 * (vnoise(i * 0.53 + 27, t * 0.21) - 0.5) * 2;
      const z = d[2] + 0.3 * (vnoise(i * 0.77 + 55, t * 0.27) - 0.5) * 2;
      const l = Math.sqrt(x * x + y * y + z * z);
      nodes.push([x / l, y / l, z / l]);
    }

    const lines = [];
    const dots = [];

    for (let i = 0; i < nodeN; i++) {
      for (let j = i + 1; j < nodeN; j++) {
        const dx = nodes[i][0] - nodes[j][0];
        const dy = nodes[i][1] - nodes[j][1];
        const dz = nodes[i][2] - nodes[j][2];
        const dist = Math.sqrt(dx * dx + dy * dy + dz * dz);
        if (dist >= thr) continue;
        const p1 = pt(nodes[i][0], nodes[i][1], nodes[i][2]);
        const p2 = pt(nodes[j][0], nodes[j][1], nodes[j][2]);
        const depth = ((p1[2] + p2[2]) / 2 + 1) / 2;
        lines.push({
          x1: p1[0], y1: p1[1], x2: p2[0], y2: p2[1],
          white: 0.42,
          a: (1 - dist / thr) * (0.3 + 0.55 * depth),
          w: Math.max(0.6, (o.lineW === undefined ? 0.8 : o.lineW) * rs)
        });
      }
    }

    for (let i = 0; i < nodeN; i++) {
      const p = pt(nodes[i][0], nodes[i][1], nodes[i][2]);
      const depth = (p[2] + 1) / 2;
      const pulse = 1 + 0.25 * Math.sin(t * 1.4 + i * 2.7);
      dots.push({
        x: p[0], y: p[1], z: p[2],
        r: (nodeR + nodeRDepth * depth) * pulse * rs,
        white: 0.55 - 0.45 * depth
      });
    }

    const signals = o.signals === undefined ? 5 : o.signals;
    for (let s = 0; s < signals; s++) {
      const seg = Math.floor(t * 0.55 + s * 7.31);
      const a = Math.floor(hashD(seg, s * 3.1 + 1.7) * nodeN);
      const b = Math.floor(hashD(seg, s * 5.7 + 4.2) * nodeN);
      if (a === b) continue;
      const f = frac(t * 0.55 + s * 7.31);
      const x = lerp(nodes[a][0], nodes[b][0], f);
      const y = lerp(nodes[a][1], nodes[b][1], f);
      const z = lerp(nodes[a][2], nodes[b][2], f);
      const l = Math.max(1e-6, Math.sqrt(x * x + y * y + z * z));
      const p = pt(x / l, y / l, z / l);
      const depth = (p[2] + 1) / 2;
      dots.push({
        x: p[0], y: p[1], z: p[2],
        r: (nodeR * 1.5 + nodeRDepth * depth) * rs,
        white: 0.05,
        a: 0.5 + 0.5 * depth
      });
    }

    return finalizeFrame(dots, lines, o.rMin);
  }

  /** braid · weaving — 三股螺旋辫在球面互缠 */
  function frameBraid(size, t, o) {
    const cx = size / 2;
    const cy = size / 2;
    const R = (size / 2) * 0.76;
    const pt = makeProj(t * 0.4, 0.3, cx, cy, 1);
    const rs = radiusScale(size, o.rsPow === undefined ? 0.6 : o.rsPow);

    const dots = [];
    const ghostN = o.ghostN === undefined ? 150 : o.ghostN;
    for (let i = 0; i < ghostN; i++) {
      const d = fibDir(i, ghostN);
      const p = pt(d[0] * R, d[1] * R, d[2] * R);
      const depth = (p[2] / R + 1) / 2;
      dots.push({ x: p[0], y: p[1], z: p[2], r: 0.8 * rs, white: 0.78, a: 0.1 + 0.22 * depth });
    }

    const strandN = o.strandN === undefined ? 52 : o.strandN;
    const turns = o.turns === undefined ? 3 : o.turns;
    for (let s = 0; s < 3; s++) {
      const phase = (s / 3) * 2 * Math.PI;
      for (let i = 0; i < strandN; i++) {
        const u = (frac(i / strandN + t * 0.045) * 2 - 1) * 0.96;
        const surf = Math.sqrt(Math.max(0, 1 - u * u));
        const endFade = Math.min(1, (1 - Math.abs(u)) / 0.1);
        const a = u * Math.PI * turns + phase;
        const weave = 1 + 0.075 * Math.sin(u * Math.PI * turns * 2 + phase * 2 + t * 0.8);
        const rr = surf * R * weave;
        const p = pt(Math.cos(a) * rr, u * R * weave, Math.sin(a) * rr);
        const depth = (p[2] / R + 1) / 2;
        dots.push({
          x: p[0], y: p[1], z: p[2],
          r: ((o.rBase === undefined ? 1.2 : o.rBase) + (o.rDepth === undefined ? 1.8 : o.rDepth) * depth) * rs,
          white: 0.55 - 0.45 * depth,
          a: endFade * (0.45 + 0.55 * depth)
        });
      }
    }
    return finalizeFrame(dots, [], o.rMin);
  }

  /** ribbon · composing / ring · breathing — 丝带在固定大圆上游走;faceOn 变正面呼吸环 */
  function frameRibbon(size, t, o) {
    const cx = size / 2;
    const cy = size / 2;
    const R = (size / 2) * 0.78;
    const spin = o.spin === undefined ? 1 : o.spin;
    const camTilt = 0.3;
    const pt = makeProj(t * 0.1 * spin, camTilt, cx, cy, 1);
    const rs = radiusScale(size, o.rsPow === undefined ? 0.6 : o.rsPow);

    const dots = [];
    const ghostN = o.ghostN === undefined ? 150 : o.ghostN;
    for (let i = 0; i < ghostN; i++) {
      const d = fibDir(i, ghostN);
      const p = pt(d[0] * R, d[1] * R, d[2] * R);
      const depth = (p[2] / R + 1) / 2;
      dots.push({ x: p[0], y: p[1], z: p[2], r: 0.8 * rs, white: 0.78, a: 0.1 + 0.22 * depth });
    }

    const ya = t * 0.24 * spin;
    const ta = o.faceOn ? -camTilt : 0.55 + 0.3 * Math.sin(t * 0.18) * spin;
    const ux = Math.cos(ya);
    const uy = 0;
    const uz = Math.sin(ya);
    const vx = -uz * Math.sin(ta);
    const vy = Math.cos(ta);
    const vz = ux * Math.sin(ta);
    const nx = uy * vz - uz * vy;
    const ny = uz * vx - ux * vz;
    const nz = ux * vy - uy * vx;

    const wobAmp = 0.23 * (o.wobMul === undefined ? 1 : o.wobMul);
    const baseR = o.faceOn ? R / (1 + 0.85 * wobAmp) : R;

    const baseLanes = o.lanes === undefined ? 5 : o.lanes;
    const segs = o.segs === undefined ? 88 : o.segs;
    const lanes = Math.max(1, Math.round(baseLanes * (o.bandMul === undefined ? 1 : o.bandMul)));
    for (let w = 0; w < lanes; w++) {
      const laneOff = (w - (lanes - 1) / 2) * 0.075;
      const edge = Math.abs(w - (lanes - 1) / 2) / Math.max(1, (lanes - 1) / 2);
      for (let k = 0; k < segs; k++) {
        const a = (k / segs) * 2 * Math.PI;
        const wob =
          (0.16 * Math.sin(a * 3 - t * 1.7 + w * 0.22) + 0.07 * Math.sin(a * 5 + t * 1.1)) * (o.wobMul === undefined ? 1 : o.wobMul);
        const radial = o.faceOn ? 1 + wob : 1;
        const off = o.faceOn ? laneOff : laneOff + wob;
        const x = ux * Math.cos(a) + vx * Math.sin(a) + nx * off;
        const y = uy * Math.cos(a) + vy * Math.sin(a) + ny * off;
        const z = uz * Math.cos(a) + vz * Math.sin(a) + nz * off;
        const l = Math.sqrt(x * x + y * y + z * z);
        const rr = baseR * radial;
        const p = pt((x / l) * rr, (y / l) * rr, (z / l) * rr);
        const depth = (p[2] / R + 1) / 2;
        dots.push({
          x: p[0], y: p[1], z: p[2],
          r: ((o.rBase === undefined ? 1.1 : o.rBase) + (o.rDepth === undefined ? 1.7 : o.rDepth) * depth) * (1 - 0.25 * edge) * rs,
          white: 0.52 - 0.44 * depth + 0.18 * edge,
          a: 0.4 + 0.6 * depth
        });
      }
    }
    return finalizeFrame(dots, [], o.rMin);
  }

  /** morph · shaping — 点状轮廓 圆 → 三角 → 方 → 圆 匀速变形 */
  const HOLD = 1.4;
  const MORPH = 0.9;
  const SEG = HOLD + MORPH;

  function smoothE(x) { return x * x * (3 - 2 * x); }

  function polyPath(verts) {
    const V = verts.length;
    const L = [];
    let total = 0;
    for (let i = 0; i < V; i++) {
      const a = verts[i];
      const b = verts[(i + 1) % V];
      const l = Math.hypot(b[0] - a[0], b[1] - a[1]);
      L.push(l);
      total += l;
    }
    return (f) => {
      let target = f * total;
      let i = 0;
      while (target > L[i] && i < V - 1) {
        target -= L[i];
        i++;
      }
      const a = verts[i];
      const b = verts[(i + 1) % V];
      const ff = L[i] ? Math.min(1, target / L[i]) : 0;
      return [a[0] + (b[0] - a[0]) * ff, a[1] + (b[1] - a[1]) * ff];
    };
  }

  const CIRCLE = (f) => {
    const a = -Math.PI / 2 + f * 2 * Math.PI;
    return [Math.cos(a) * 0.24, Math.sin(a) * 0.24];
  };
  const TRIANGLE = polyPath([[0.0, -0.26], [0.24, 0.16], [-0.24, 0.16]]);
  const SQUARE = polyPath([[0, -0.2], [0.2, -0.2], [0.2, 0.2], [-0.2, 0.2], [-0.2, -0.2]]);
  const CYCLE = [CIRCLE, TRIANGLE, SQUARE];

  function morphN(d) { return Math.max(6, Math.round(34 * d)); }

  function frameMorph(size, t, o) {
    const K = CYCLE.length;
    const tc = t % (SEG * K);
    const k = Math.floor(tc / SEG);
    const local = tc - k * SEG;
    const m = local > HOLD ? smoothE((local - HOLD) / MORPH) : 0;
    const sprd = o.spread === undefined ? 1 : o.spread;

    const pA = CYCLE[k];
    const pB = CYCLE[(k + 1) % K];
    const M = 160;
    const pts = [];
    for (let i = 0; i < M; i++) {
      const f = i / M;
      const a = pA(f);
      const b = pB(f);
      pts.push([(a[0] + (b[0] - a[0]) * m) * sprd, (a[1] + (b[1] - a[1]) * m) * sprd]);
    }
    const L = [];
    let total = 0;
    for (let i = 0; i < M; i++) {
      const a = pts[i];
      const b = pts[(i + 1) % M];
      const l = Math.hypot(b[0] - a[0], b[1] - a[1]);
      L.push(l);
      total += l;
    }

    const n = morphN(o.iconD === undefined ? 1 : o.iconD);
    const re = (o.rDot === undefined ? 0.021 : o.rDot) * 1.35 * sprd;
    const pulse = 1 + 0.02 * Math.sin(local * 3.1);

    const dots = [];
    const c2 = size / 2;
    let seg = 0;
    let acc = 0;
    for (let k2 = 0; k2 < n; k2++) {
      const target = (k2 / n) * total;
      while (acc + L[seg] < target && seg < M - 1) {
        acc += L[seg];
        seg++;
      }
      const a = pts[seg];
      const b = pts[(seg + 1) % M];
      const f = L[seg] ? Math.min(1, (target - acc) / L[seg]) : 0;
      const x = (a[0] + (b[0] - a[0]) * f) * pulse;
      const y = (a[1] + (b[1] - a[1]) * f) * pulse;
      dots.push({
        x: c2 + x * size,
        y: c2 + y * size,
        z: 0,
        r: Math.max(0.35, re * size),
        white: 0.1
      });
    }
    return finalizeFrame(dots, [], o.rMin);
  }

  /* ────────────────── profiles · 密度 / 半径缩放 ────────────────── */
  const COUNT_PAIRS = [['latRings', 'lonDensity'], ['rings', 'lonDensity'], ['lanes', 'segs']];
  const COUNT_KEYS = ['orbitN', 'ghostN', 'nodeN', 'strandN', 'signals'];
  const ICON_DENSITY_KEYS = ['iconD'];
  const RADIUS_KEYS = ['rBase', 'rDepth', 'rActive', 'rDot', 'ghostR', 'partR', 'partRDepth', 'nodeR', 'nodeRDepth'];

  function scaleCounts(opts, scale) {
    const out = Object.assign({}, opts);
    const done = {};
    const rt = Math.sqrt(scale);
    for (const pair of COUNT_PAIRS) {
      const va = out[pair[0]];
      const vb = out[pair[1]];
      if (va != null && vb != null && !done[pair[0]] && !done[pair[1]]) {
        out[pair[0]] = Math.max(2, Math.round(va * rt));
        out[pair[1]] = Math.max(2, Math.round(vb * rt));
        done[pair[0]] = true;
        done[pair[1]] = true;
      }
    }
    for (const k of COUNT_KEYS) {
      const v = out[k];
      if (v != null && v !== 0 && !done[k]) out[k] = Math.max(1, Math.round(v * scale));
    }
    for (const k of ICON_DENSITY_KEYS) {
      const v = out[k];
      if (v != null) out[k] = Math.max(0.02, v * scale);
    }
    return out;
  }

  function scaleRadii(opts, scale) {
    const out = Object.assign({}, opts);
    for (const k of RADIUS_KEYS) {
      const v = out[k];
      if (v != null) out[k] = v * scale;
    }
    out.rSizeMul = (out.rSizeMul === undefined ? 1 : out.rSizeMul) * scale;
    return out;
  }

  const BASE_PROFILES = {
    globe:   { latRings: 17, lonDensity: 44, rBase: 0.6, rDepth: 1.7, rBoost: 1.0, inkFar: 0.62, inkSpan: 0.54, rsPow: 0.6, rMin: 0.3 },
    orbits:  { orbitN: 12, ghostN: 40, ghostR: 0.9, ghostA: 0.5, particles: 3, partR: 1.2, partRDepth: 1.6, rsPow: 0.6, rMin: 0.3 },
    rubik:   { latRings: 15, lonDensity: 40, moveCount: 14, rBase: 0.6, rDepth: 1.7, rActive: 0.3, inkFar: 0.62, inkSpan: 0.54, rsPow: 0.6, rMin: 0.3 },
    wave:    { rings: 15, lonDensity: 40, rBase: 0.6, rDepth: 1.7, rsPow: 0.6, rMin: 0.3 },
    web:     { nodeN: 30, thr: 0.72, signals: 5, nodeR: 1.4, nodeRDepth: 1.8, lineW: 0.8, rsPow: 0.6, rMin: 0.3 },
    braid:   { strandN: 52, turns: 3.0, ghostN: 150, rBase: 1.2, rDepth: 1.8, rsPow: 0.6, rMin: 0.3 },
    ribbon:  { lanes: 5, segs: 88, ghostN: 150, rBase: 1.1, rDepth: 1.7, rsPow: 0.6, rMin: 0.3 },
    ring:    { lanes: 5, segs: 88, ghostN: 0, faceOn: 1, rBase: 1.1, rDepth: 1.7, rsPow: 0.6, rMin: 0.3 },
    morph:   { rDot: 0.021, iconD: 1, rMin: 0.25 }
  };

  /* 官方 64pt 档调参(演示页几何尺寸,与官方 demo 一致) */
  const PRESETS_64 = {
    orbits:  { speed: 1.885, count: 1, size: 1 },
    globe:   { speed: 2.015, count: 0.42, size: 1.15, extra: { scanMul: 4.08, dimBase: 0.45 } },
    rubik:   { speed: 1.82, count: 0.35, size: 1.05 },
    wave:    { speed: 4.388, count: 0.341, size: 1 },
    web:     { speed: 3.315, count: 1.35, size: 0.95 },
    braid:   { speed: 1.625, count: 0.5, size: 1 },
    ribbon:  { speed: 2.34, count: 0.25, size: 0.85, extra: { spin: 0, bandMul: 3.9, wobMul: 1 } },
    ring:    { speed: 3.24, count: 0.25, size: 0.956, extra: { spin: 0, bandMul: 3.627, wobMul: 0.368 } },
    morph:   { speed: 2.405, count: 0.702, size: 0.395, extra: { spread: 1.45 } }
  };

  const STATE_TO_MODE = {
    working: 'orbits',
    searching: 'globe',
    solving: 'rubik',
    listening: 'wave',
    connecting: 'web',
    weaving: 'braid',
    composing: 'ribbon',
    breathing: 'ring',
    shaping: 'morph'
  };

  const MODE_FRAMES = {
    orbits: frameOrbits,
    globe: frameGlobe,
    rubik: frameRubik,
    wave: frameWave,
    web: frameWeb,
    braid: frameBraid,
    ribbon: frameRibbon,
    ring: frameRibbon,
    morph: frameMorph
  };

  function resolvePreset(state, size) {
    const mode = STATE_TO_MODE[state];
    const preset = PRESETS_64[mode];
    let opts = Object.assign({}, BASE_PROFILES[mode]);
    if (preset.count !== 1) opts = scaleCounts(opts, preset.count);
    if (preset.size !== 1) opts = scaleRadii(opts, preset.size);
    if (preset.extra) opts = Object.assign(opts, preset.extra);
    return { mode: mode, speed: preset.speed, opts: opts };
  }

  /* ────────────────── 渲染:共享时钟,一帧画完全部 orb ────────────────── */

  const orbsCtrl = { pause: null, play: null };

  function mount() {
    const canvases = Array.from(document.querySelectorAll('canvas[data-state]'));
    if (!canvases.length) return;

    const jobs = [];
    for (const cv of canvases) {
      const state = cv.getAttribute('data-state');
      if (!STATE_TO_MODE[state]) continue;
      const size = parseInt(cv.getAttribute('data-size') || '140', 10) || 140;
      const dpr = Math.min(2, (typeof window.devicePixelRatio !== 'undefined' && window.devicePixelRatio) || 1);
      cv.width = Math.round(size * dpr);
      cv.height = Math.round(size * dpr);
      const ctx = cv.getContext('2d');
      if (!ctx) continue;
      const r = resolvePreset(state, size);
      jobs.push({ cv: cv, ctx: ctx, size: size, dpr: dpr, frame: MODE_FRAMES[r.mode], speed: r.speed, opts: r.opts, visible: true });
    }
    if (!jobs.length) return;

    // 先各画一帧,避免未激活时空白
    const t0 = performance.now() / 1000;
    for (const j of jobs) {
      j.ctx.setTransform(j.dpr, 0, 0, j.dpr, 0, 0);
      j.ctx.clearRect(0, 0, j.size, j.size);
      paintFrame(j.ctx, j.frame(j.size, t0 * j.speed, j.opts), false);
    }

    let raf = 0;
    let running = false;
    const loop = () => {
      const t = performance.now() / 1000;
      for (const j of jobs) {
        if (!j.visible) continue;
        const ctx = j.ctx;
        ctx.setTransform(j.dpr, 0, 0, j.dpr, 0, 0);
        ctx.clearRect(0, 0, j.size, j.size);
        paintFrame(ctx, j.frame(j.size, t * j.speed, j.opts), false);
      }
      if (running) raf = requestAnimationFrame(loop);
    };
    const start = () => { if (!running) { running = true; raf = requestAnimationFrame(loop); } };
    const stop = () => { running = false; cancelAnimationFrame(raf); };

    // 离开视口 / 切走标签页时暂停,回来再续
    let visible = true;
    if (typeof IntersectionObserver !== 'undefined') {
      const io = new IntersectionObserver((entries) => {
        for (const entry of entries) {
          const j = jobs.find((x) => x.cv === entry.target);
          if (!j) continue;
          j.visible = entry.isIntersecting;
          visible = jobs.some((x) => x.visible);
          if (visible && document.visibilityState !== 'hidden') start();
          else stop();
        }
      });
      for (const j of jobs) io.observe(j.cv);
    }
    document.addEventListener('visibilitychange', function onVis() {
      if (document.visibilityState === 'hidden') stop();
      else if (visible) start();
    });
    if (visible) start();
    orbsCtrl.pause = stop;
    orbsCtrl.play = start;
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', mount, { once: true });
  } else {
    mount();
  }

  // 调试 / 教学入口:控制台可手动调用 frame 函数,或暂停 / 恢复动画
  const api = {
    MODE_FRAMES: MODE_FRAMES,
    resolvePreset: resolvePreset,
    paintFrame: paintFrame,
    pause: function () { if (orbsCtrl.pause) orbsCtrl.pause(); },
    play: function () { if (orbsCtrl.play) orbsCtrl.play(); }
  };
  if (typeof window !== 'undefined') window.__orbs = api;
  if (typeof globalThis !== 'undefined') globalThis.__orbs = api;
})();
