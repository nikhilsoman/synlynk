(function () {
  'use strict';

  function initMotherboard() {
    const canvas = document.getElementById('motherboard-canvas');
    if (!canvas) return;

    const DPR = window.devicePixelRatio || 1;
    const CW = parseInt(canvas.getAttribute('width'), 10) || 520;
    const CH = parseInt(canvas.getAttribute('height'), 10) || 460;

    canvas.width = CW * DPR;
    canvas.height = CH * DPR;
    canvas.style.width = CW + 'px';
    canvas.style.height = CH + 'px';

    const ctx = canvas.getContext('2d', { alpha: true });
    ctx.scale(DPR, DPR);

    // Isometric projection tuned for 520x460 viewport
    const TW = 11.6;
    const TH = 5.8;
    const ZS = 9.6;
    const OX = 148;
    const OY = 54;

    function iso(gx, gy, gz = 0) {
      return {
        x: OX + (gx - gy) * TW,
        y: OY + (gx + gy) * TH - gz * ZS
      };
    }

    // Colors (brand-matched per spec)
    const COL = {
      board: '#060C0A',
      surface: '#07120E',
      gridL: 'rgba(46,196,160,0.04)',
      gridD: 'rgba(46,196,160,0.07)',
      via: 'rgba(46,196,160,0.12)',
      claude: { line: '#D97757', top: '#E88B6A', left: '#B55E3A', right: '#8A4020', dark: '#5A2A10' },
      gemini: { line: '#4285F4', top: '#6AA3FF', left: '#2870E0', right: '#1858C0', dark: '#0C3888' },
      grok:   { line: '#A259F7', top: '#C890FF', left: '#9060D8', right: '#6E44B8', dark: '#4A2888' },
      codex:  { line: '#888888', top: '#9A9A9A', left: '#5A5A5A', right: '#3A3A3A', dark: '#1A1A1A' },
      npu:    { top: '#1a0a38', side1: '#0e0522', side2: '#0a0318', glow: '#A259F7' },
      trunk:  '#2EC4A0',
      text:   'rgba(233,233,238,0.75)',
      textDim:'rgba(233,233,238,0.3)',
    };

    const BH = 0.6;
    const TZ = BH + 0.15;

    function poly(pts, fill, stroke, sw = 0.5, alpha = 1) {
      ctx.save();
      ctx.globalAlpha = alpha;
      ctx.beginPath();
      ctx.moveTo(pts[0].x, pts[0].y);
      for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i].x, pts[i].y);
      ctx.closePath();
      if (fill) { ctx.fillStyle = fill; ctx.fill(); }
      if (stroke) { ctx.strokeStyle = stroke; ctx.lineWidth = sw; ctx.stroke(); }
      ctx.restore();
    }

    function isoBox(gx, gy, gw, gd, z0, zh, pal, glowColor) {
      const p = (x, y, z) => iso(x, y, z);
      const rf = [p(gx, gy + gd, z0), p(gx + gw, gy + gd, z0), p(gx + gw, gy + gd, zh), p(gx, gy + gd, zh)];
      poly(rf, pal.left, '#000', 0.4, 0.95);

      const lf = [p(gx + gw, gy, z0), p(gx + gw, gy + gd, z0), p(gx + gw, gy + gd, zh), p(gx + gw, gy, zh)];
      poly(lf, pal.right, '#000', 0.4, 0.95);

      const tf = [p(gx, gy, zh), p(gx + gw, gy, zh), p(gx + gw, gy + gd, zh), p(gx, gy + gd, zh)];
      poly(tf, pal.top, glowColor || pal.line, glowColor ? 1 : 0.4, 0.95);

      if (glowColor) {
        ctx.save();
        ctx.shadowBlur = 16;
        ctx.shadowColor = glowColor;
        ctx.beginPath();
        ctx.moveTo(tf[0].x, tf[0].y);
        for (let i = 1; i < tf.length; i++) ctx.lineTo(tf[i].x, tf[i].y);
        ctx.closePath();
        ctx.strokeStyle = glowColor;
        ctx.lineWidth = 1.4;
        ctx.stroke();
        ctx.restore();
      }
    }

    function drawBoard() {
      const GW = 22, GH = 14;
      const tl = iso(0, 0, BH), tr = iso(GW, 0, BH), br = iso(GW, GH, BH), bl = iso(0, GH, BH);

      const grad = ctx.createLinearGradient(tl.x, tl.y, br.x, br.y);
      grad.addColorStop(0, '#07120E');
      grad.addColorStop(1, '#050E0B');

      poly([tl, tr, br, bl], null, 'rgba(46,196,160,0.06)', 0.5);

      const fl = [iso(0, GH, 0), iso(GW, GH, 0), iso(GW, GH, BH), iso(0, GH, BH)];
      poly(fl, '#04090A', 'rgba(46,196,160,0.05)', 0.5);

      const fr = [iso(GW, 0, 0), iso(GW, GH, 0), iso(GW, GH, BH), iso(GW, 0, BH)];
      poly(fr, '#030807', 'rgba(46,196,160,0.05)', 0.5);

      ctx.save();
      ctx.beginPath();
      ctx.moveTo(tl.x, tl.y); ctx.lineTo(tr.x, tr.y); ctx.lineTo(br.x, br.y); ctx.lineTo(bl.x, bl.y);
      ctx.closePath();
      ctx.fillStyle = '#060F0C';
      ctx.fill();
      ctx.restore();

      ctx.save();
      ctx.strokeStyle = 'rgba(46,196,160,0.045)';
      ctx.lineWidth = 0.5;
      for (let x = 2; x < GW; x += 2) {
        const a = iso(x, 0, BH), b = iso(x, GH, BH);
        ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
      }
      for (let y = 2; y < GH; y += 2) {
        const a = iso(0, y, BH), b = iso(GW, y, BH);
        ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
      }
      ctx.restore();

      const vias = [
        [3,3],[5,1],[7,3],[3,11],[5,13],[7,11],
        [15,3],[17,1],[19,3],[15,11],[17,13],[19,11],
        [1,7],[21,7],[11,1],[11,13],
        [4,6],[4,8],[18,6],[18,8],
      ];
      ctx.save();
      vias.forEach(([vx, vy]) => {
        const p = iso(vx, vy, BH);
        ctx.beginPath(); ctx.arc(p.x, p.y, 2.4, 0, Math.PI * 2);
        ctx.strokeStyle = 'rgba(46,196,160,0.18)'; ctx.lineWidth = 1; ctx.stroke();
        ctx.beginPath(); ctx.arc(p.x, p.y, 1.0, 0, Math.PI * 2);
        ctx.fillStyle = '#030907'; ctx.fill();
      });
      ctx.restore();
    }

    function tubeLine(x1, y1, x2, y2, color, width = 3.0, alpha = 0.9) {
      const p1 = iso(x1, y1, TZ), p2 = iso(x2, y2, TZ);
      ctx.save();
      ctx.globalAlpha = alpha;
      ctx.shadowBlur = 6; ctx.shadowColor = color;
      ctx.strokeStyle = color; ctx.lineWidth = width;
      ctx.lineCap = 'round';
      ctx.beginPath(); ctx.moveTo(p1.x, p1.y); ctx.lineTo(p2.x, p2.y); ctx.stroke();
      ctx.shadowBlur = 0; ctx.globalAlpha = alpha * 0.18;
      ctx.strokeStyle = '#fff'; ctx.lineWidth = 0.7;
      ctx.beginPath(); ctx.moveTo(p1.x, p1.y); ctx.lineTo(p2.x, p2.y); ctx.stroke();
      ctx.restore();
    }

    function station(gx, gy, colors, isHub = false, label = '', labelOff = { x: 0, y: 0 }) {
      const p = iso(gx, gy, TZ + 0.05);
      const r = isHub ? 5.5 : 3.8;

      ctx.save();
      if (colors.length > 1) {
        ctx.shadowBlur = 8; ctx.shadowColor = colors[0];
        ctx.beginPath(); ctx.arc(p.x, p.y, r + 1.5, 0, Math.PI * 2);
        ctx.strokeStyle = 'rgba(255,255,255,0.12)'; ctx.lineWidth = 1; ctx.stroke();
      }
      ctx.shadowBlur = 10; ctx.shadowColor = colors[0];
      ctx.beginPath(); ctx.arc(p.x, p.y, r, 0, Math.PI * 2);
      ctx.fillStyle = '#070E0C'; ctx.fill();
      ctx.strokeStyle = colors[0]; ctx.lineWidth = isHub ? 2.0 : 1.5;
      ctx.stroke();
      if (colors.length > 1) {
        ctx.strokeStyle = colors[1]; ctx.lineWidth = 1.2;
        ctx.beginPath(); ctx.arc(p.x, p.y, r - 1.6, 0, Math.PI * 2); ctx.stroke();
      }
      if (isHub) {
        ctx.beginPath(); ctx.arc(p.x, p.y, 2.2, 0, Math.PI * 2);
        ctx.fillStyle = colors[0]; ctx.fill();
      }
      ctx.restore();

      if (label) {
        ctx.save();
        ctx.font = isHub ? `600 8px 'JetBrains Mono',monospace` : `500 7px 'JetBrains Mono',monospace`;
        ctx.fillStyle = isHub ? colors[0] : 'rgba(233,233,238,0.45)';
        ctx.textAlign = 'center';
        ctx.fillText(label, p.x + labelOff.x, p.y + labelOff.y);
        ctx.restore();
      }
    }

    function cpuStack(gx, gy, models, pal, labelName) {
      models.forEach(m => {
        isoBox(gx, gy, 2.2, 2.2, m.z0, m.zh, pal);
      });

      const topZ = models[models.length - 1].zh;
      const center = iso(gx + 1.1, gy + 1.1, topZ);
      ctx.save();
      ctx.font = `600 7px 'JetBrains Mono',monospace`;
      ctx.fillStyle = pal.line;
      ctx.textAlign = 'center';
      ctx.fillText(models[models.length - 1].name, center.x, center.y + 2.5);
      ctx.restore();

      const top0 = iso(gx + 1.1, gy + 1.1, topZ + 0.7);
      ctx.save();
      ctx.font = `700 9px 'JetBrains Mono',monospace`;
      ctx.fillStyle = pal.line;
      ctx.textAlign = 'center';
      ctx.shadowBlur = 6; ctx.shadowColor = pal.line;
      ctx.fillText(labelName.toUpperCase(), top0.x, top0.y);
      ctx.restore();

      models.forEach((m, i) => {
        if (i < models.length - 1) {
          const mp = iso(gx + 1.1, gy + 1.1, m.zh);
          ctx.save();
          ctx.font = `500 6.5px 'JetBrains Mono',monospace`;
          ctx.fillStyle = 'rgba(233,233,238,0.28)';
          ctx.textAlign = 'center';
          ctx.fillText(m.name, mp.x, mp.y + 1.5);
          ctx.restore();
        }
      });

      const harnessPt = iso(gx + 1.1, gy + 1.1, topZ + 1.35);
      ctx.save();
      ctx.font = `400 6px 'JetBrains Mono',monospace`;
      ctx.fillStyle = 'rgba(255,255,255,0.13)';
      ctx.textAlign = 'center';
      ctx.fillText('HARNESS', harnessPt.x, harnessPt.y);
      ctx.restore();
    }

    function drawSGlyph(screenPt, scale) {
      ctx.save();
      ctx.translate(screenPt.x, screenPt.y);
      ctx.scale(scale, scale);
      ctx.lineCap = 'round';
      const s = 7;
      ctx.beginPath();
      ctx.moveTo(0, -s); ctx.bezierCurveTo(-s * 0.9, -s, -s * 0.9, -s * 0.1, 0, 0);
      ctx.bezierCurveTo(s * 0.9, s * 0.1, s * 0.9, s, 0, s);
      ctx.strokeStyle = '#A259F7'; ctx.lineWidth = 2.2; ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(0, -s); ctx.bezierCurveTo(-s * 0.9, -s, -s * 0.9, -s * 0.1, 0, 0);
      ctx.strokeStyle = '#5B8DEF'; ctx.lineWidth = 1.3; ctx.stroke();
      ctx.beginPath(); ctx.moveTo(0, s); ctx.lineTo(0, s * 1.55);
      ctx.strokeStyle = '#2EC4A0'; ctx.lineWidth = 2.2; ctx.stroke();
      ctx.beginPath(); ctx.arc(0, -s, 1.8, 0, Math.PI * 2); ctx.fillStyle = '#5B8DEF'; ctx.fill();
      ctx.beginPath(); ctx.arc(0, s * 1.55, 1.8, 0, Math.PI * 2); ctx.fillStyle = '#2EC4A0'; ctx.fill();
      ctx.restore();
    }

    function drawNPU(gx, gy, gw, gd, zh) {
      isoBox(gx - 0.4, gy - 0.4, gw + 0.8, gd + 0.8, 0.6, 0.85,
        { top: '#0a0a12', left: '#07070e', right: '#050509' }, null);

      ctx.save();
      ctx.strokeStyle = 'rgba(162,89,247,0.28)'; ctx.lineWidth = 0.6;
      for (let i = 0; i <= gw; i += 0.5) {
        const a = iso(gx + i, gy, 0.85), b = iso(gx + i, gy, 1.25);
        ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
      }
      for (let j = 0; j <= gd; j += 0.5) {
        const a = iso(gx + gw, gy + j, 0.85), b = iso(gx + gw, gy + j, 1.25);
        ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
      }
      ctx.restore();

      const rf = [iso(gx, gy + gd, 1.25), iso(gx + gw, gy + gd, 1.25), iso(gx + gw, gy + gd, zh), iso(gx, gy + gd, zh)];
      const rfGrad = ctx.createLinearGradient(rf[0].x, rf[0].y, rf[2].x, rf[2].y);
      rfGrad.addColorStop(0, '#0e0525'); rfGrad.addColorStop(1, '#1a0840');
      poly(rf, rfGrad, '#A259F7', 0.5);

      const lf = [iso(gx + gw, gy, 1.25), iso(gx + gw, gy + gd, 1.25), iso(gx + gw, gy + gd, zh), iso(gx + gw, gy, zh)];
      const lfGrad = ctx.createLinearGradient(lf[0].x, lf[0].y, lf[2].x, lf[2].y);
      lfGrad.addColorStop(0, '#08031a'); lfGrad.addColorStop(1, '#100528');
      poly(lf, lfGrad, '#A259F7', 0.4);

      const tf = [iso(gx, gy, zh), iso(gx + gw, gy, zh), iso(gx + gw, gy + gd, zh), iso(gx, gy + gd, zh)];
      const npuGrad = ctx.createLinearGradient(tf[0].x, tf[0].y, tf[2].x, tf[2].y);
      npuGrad.addColorStop(0, '#18063c'); npuGrad.addColorStop(0.5, '#220850'); npuGrad.addColorStop(1, '#14043a');
      poly(tf, npuGrad, 'rgba(162,89,247,0.55)', 1);

      ctx.save();
      ctx.strokeStyle = 'rgba(162,89,247,0.11)'; ctx.lineWidth = 0.35;
      for (let i = 1; i < gw; i++) {
        const a = iso(gx + i, gy, zh), b = iso(gx + i, gy + gd, zh);
        ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
      }
      for (let j = 1; j < gd; j++) {
        const a = iso(gx, gy + j, zh), b = iso(gx + gw, gy + j, zh);
        ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
      }
      ctx.restore();

      const pad = 0.45;
      const die = [iso(gx + pad, gy + pad, zh + 0.08), iso(gx + gw - pad, gy + pad, zh + 0.08),
                   iso(gx + gw - pad, gy + gd - pad, zh + 0.08), iso(gx + pad, gy + gd - pad, zh + 0.08)];
      const dieGrad = ctx.createLinearGradient(die[0].x, die[0].y, die[2].x, die[2].y);
      dieGrad.addColorStop(0, 'rgba(162,89,247,0.07)'); dieGrad.addColorStop(1, 'rgba(91,141,239,0.04)');
      poly(die, dieGrad, 'rgba(162,89,247,0.22)', 0.5);

      ctx.save();
      const center = iso(gx + gw / 2, gy + gd / 2, zh);
      const glowGrad = ctx.createRadialGradient(center.x, center.y, 0, center.x, center.y, 58);
      glowGrad.addColorStop(0, 'rgba(162,89,247,0.10)'); glowGrad.addColorStop(1, 'transparent');
      ctx.fillStyle = glowGrad;
      ctx.beginPath(); ctx.arc(center.x, center.y, 58, 0, Math.PI * 2); ctx.fill();
      ctx.restore();

      drawSGlyph(iso(gx + gw / 2, gy + gd / 2, zh + 0.12), 0.78);

      const lbl = iso(gx + gw / 2, gy + gd / 2, zh + 1.4);
      ctx.save();
      ctx.font = `800 10px 'JetBrains Mono',monospace`;
      ctx.fillStyle = '#A259F7'; ctx.textAlign = 'center';
      ctx.shadowBlur = 10; ctx.shadowColor = '#A259F7';
      ctx.fillText('synlynk', lbl.x, lbl.y);
      ctx.font = `500 7px 'JetBrains Mono',monospace`;
      ctx.fillStyle = 'rgba(255,255,255,0.18)'; ctx.shadowBlur = 0;
      ctx.fillText('COORD · NPU', lbl.x, lbl.y + 10);
      ctx.restore();
    }

    // Routes for particles (L-shaped metro)
    const ROUTES_DEF = [
      [3.5, 3.5, 7.6, 3.5, COL.claude.line],
      [7.6, 3.5, 7.6, 4.9, COL.claude.line],
      [18.2, 3.5, 14.0, 3.5, COL.gemini.line],
      [14.0, 3.5, 14.0, 4.9, COL.gemini.line],
      [3.5, 10.2, 7.6, 10.2, COL.grok.line],
      [7.6, 10.2, 7.6, 9.0, COL.grok.line],
      [18.2, 10.2, 14.0, 10.2, COL.codex.line],
      [14.0, 10.2, 14.0, 9.0, COL.codex.line],
      [7.6, 4.9, 14.0, 4.9, COL.trunk],
      [7.6, 9.0, 14.0, 9.0, COL.trunk],
      [7.6, 4.9, 7.6, 9.0, COL.trunk],
      [14.0, 4.9, 14.0, 9.0, COL.trunk],
    ];

    class Particle {
      constructor() { this.reset(); }
      reset() {
        const r = ROUTES_DEF[Math.floor(Math.random() * ROUTES_DEF.length)];
        this.x1 = r[0]; this.y1 = r[1]; this.x2 = r[2]; this.y2 = r[3]; this.color = r[4];
        this.t = 0; this.speed = 0.014 + Math.random() * 0.009;
        this.rev = Math.random() > 0.5;
        if (this.rev) { const tmp = [this.x1, this.y1]; this.x1 = this.x2; this.y1 = this.y2; this.x2 = tmp[0]; this.y2 = tmp[1]; }
        this.size = 1.4 + Math.random() * 0.9;
      }
      update() { this.t += this.speed; if (this.t > 1.0) this.reset(); }
      draw() {
        const x = this.x1 + (this.x2 - this.x1) * this.t;
        const y = this.y1 + (this.y2 - this.y1) * this.t;
        const p = iso(x, y, TZ + 0.28);
        const alpha = Math.sin(this.t * Math.PI) * 0.85;
        ctx.save();
        ctx.globalAlpha = alpha;
        ctx.shadowBlur = 8; ctx.shadowColor = this.color;
        ctx.beginPath(); ctx.arc(p.x, p.y, this.size, 0, Math.PI * 2);
        ctx.fillStyle = this.color; ctx.fill();
        ctx.restore();
      }
    }

    const particles = Array.from({ length: 42 }, () => new Particle());

    function drawCapacitor(gx, gy, color) {
      isoBox(gx, gy, 0.42, 0.42, BH, BH + 1.55,
        { top: color + '33', left: color + '1a', right: color + '11' });
    }

    function drawBusGroup(gx, gy, dir, color, count = 3) {
      const spacing = 0.36;
      for (let i = 0; i < count; i++) {
        const off = (i - (count - 1) / 2) * spacing;
        if (dir === 'x') tubeLine(gx, gy + off, gx + 2.1, gy + off, color, 1.0, 0.22);
        else tubeLine(gx + off, gy, gx + off, gy + 2.1, color, 1.0, 0.22);
      }
    }

    let frame = 0;
    let rafId = null;
    let running = false;

    function draw() {
      ctx.clearRect(0, 0, CW, CH);

      ctx.fillStyle = '#060C0A';
      ctx.fillRect(0, 0, CW, CH);

      drawBoard();

      drawBusGroup(5.6, 3.5, 'x', COL.claude.line);
      drawBusGroup(14.4, 3.5, 'x', COL.gemini.line);
      drawBusGroup(5.6, 10.2, 'x', COL.grok.line);
      drawBusGroup(14.4, 10.2, 'x', COL.codex.line);

      // Claude
      tubeLine(3.5, 3.5, 7.6, 3.5, COL.claude.line, 2.8);
      tubeLine(7.6, 3.5, 7.6, 4.9, COL.claude.line, 2.8);
      // Gemini
      tubeLine(18.2, 3.5, 14.0, 3.5, COL.gemini.line, 2.8);
      tubeLine(14.0, 3.5, 14.0, 4.9, COL.gemini.line, 2.8);
      // Grok
      tubeLine(3.5, 10.2, 7.6, 10.2, COL.grok.line, 2.8);
      tubeLine(7.6, 10.2, 7.6, 9.0, COL.grok.line, 2.8);
      // Codex
      tubeLine(18.2, 10.2, 14.0, 10.2, COL.codex.line, 2.8);
      tubeLine(14.0, 10.2, 14.0, 9.0, COL.codex.line, 2.8);
      // Trunk ring
      tubeLine(7.6, 4.9, 14.0, 4.9, COL.trunk, 2.2);
      tubeLine(7.6, 9.0, 14.0, 9.0, COL.trunk, 2.2);
      tubeLine(7.6, 4.9, 7.6, 9.0, COL.trunk, 2.2);
      tubeLine(14.0, 4.9, 14.0, 9.0, COL.trunk, 2.2);
      // Stubs
      tubeLine(2.85, 3.5, 3.5, 3.5, COL.claude.line, 1.6);
      tubeLine(21.1, 3.5, 18.2, 3.5, COL.gemini.line, 1.6);
      tubeLine(2.85, 10.2, 3.5, 10.2, COL.grok.line, 1.6);
      tubeLine(21.1, 10.2, 18.2, 10.2, COL.codex.line, 1.6);

      // Stations (interchanges)
      station(7.6, 4.9, [COL.trunk, COL.claude.line], true, 'dispatch', { x: 0, y: -11 });
      station(14.0, 4.9, [COL.trunk, COL.gemini.line], true, 'relay', { x: 0, y: -11 });
      station(7.6, 9.0, [COL.trunk, COL.grok.line], true, 'profiles', { x: 0, y: 11 });
      station(14.0, 9.0, [COL.trunk, COL.codex.line], true, 'state', { x: 0, y: 11 });

      station(7.6, 3.5, [COL.claude.line], false, 'ctx·L', { x: 0, y: -9 });
      station(14.0, 3.5, [COL.gemini.line], false, 'ctx·G', { x: 0, y: -9 });
      station(7.6, 10.2, [COL.grok.line], false, 'ctx·X', { x: 0, y: 9 });
      station(14.0, 10.2, [COL.codex.line], false, 'ctx·C', { x: 0, y: 9 });

      // Decor caps
      drawCapacitor(5.6, 0.9, COL.claude.line);
      drawCapacitor(6.5, 0.9, COL.claude.line);
      drawCapacitor(15.3, 0.9, COL.gemini.line);
      drawCapacitor(16.2, 0.9, COL.gemini.line);
      drawCapacitor(5.6, 12.4, COL.grok.line);
      drawCapacitor(6.5, 12.4, COL.grok.line);
      drawCapacitor(15.3, 12.4, COL.codex.line);
      drawCapacitor(16.2, 12.4, COL.codex.line);

      // CPU stacks (back-to-front painter order)
      cpuStack(1.6, 1.6, [
        { name: 'HAIKU·4', z0: BH, zh: 2.0 },
        { name: 'SONNET·4', z0: 2.0, zh: 3.5 },
        { name: 'OPUS·4', z0: 3.5, zh: 4.6 },
      ], COL.claude, 'Claude');

      cpuStack(1.6, 9.0, [
        { name: 'GROK·3m', z0: BH, zh: 2.1 },
        { name: 'GROK·3', z0: 2.1, zh: 4.0 },
      ], COL.grok, 'Grok');

      cpuStack(17.8, 1.6, [
        { name: 'FLASH', z0: BH, zh: 2.0 },
        { name: 'PRO·2.5', z0: 2.0, zh: 4.4 },
      ], COL.gemini, 'Gemini');

      // NPU center (after back stacks, before front)
      drawNPU(9.1, 5.0, 3.8, 3.8, 5.3);

      cpuStack(17.8, 9.0, [
        { name: '4.1', z0: BH, zh: 1.7 },
        { name: 'O4m', z0: 1.7, zh: 3.1 },
        { name: 'O3', z0: 3.1, zh: 4.7 },
      ], COL.codex, 'Codex');

      // Corner hub dots
      station(2.85, 3.5, [COL.claude.line], true, '', {});
      station(21.1, 3.5, [COL.gemini.line], true, '', {});
      station(2.85, 10.2, [COL.grok.line], true, '', {});
      station(21.1, 10.2, [COL.codex.line], true, '', {});

      // Packets
      particles.forEach(p => { p.update(); p.draw(); });

      // Subtle scanline
      ctx.save();
      const sx = ((frame * 0.7) % (CW + 70)) - 35;
      const sg = ctx.createLinearGradient(sx, 0, sx + 50, 0);
      sg.addColorStop(0, 'transparent');
      sg.addColorStop(0.5, 'rgba(46,196,160,0.018)');
      sg.addColorStop(1, 'transparent');
      ctx.fillStyle = sg;
      ctx.fillRect(0, 0, CW, CH);
      ctx.restore();

      // HUD overlay (top-left)
      ctx.save();
      ctx.font = `600 9px 'JetBrains Mono',monospace`;
      ctx.fillStyle = 'rgba(46,196,160,0.55)';
      ctx.fillText('COORD-OS', 14, 18);
      ctx.font = `500 7px 'JetBrains Mono',monospace`;
      ctx.fillStyle = 'rgba(255,255,255,0.18)';
      ctx.fillText('4 AGENTS · 0 DEPS · MIT', 14, 30);
      ctx.restore();

      // Legend (bottom-right inside canvas)
      ctx.save();
      const lx = CW - 128, ly = CH - 78;
      ctx.fillStyle = 'rgba(0,0,0,0.55)';
      ctx.fillRect(lx - 6, ly - 6, 122, 70);
      ctx.strokeStyle = 'rgba(255,255,255,0.06)';
      ctx.lineWidth = 1;
      ctx.strokeRect(lx - 6, ly - 6, 122, 70);

      ctx.font = `500 7px 'JetBrains Mono',monospace`;
      ctx.fillStyle = 'rgba(255,255,255,0.22)';
      ctx.fillText('METRO LINES', lx, ly + 7);

      const lines = [
        { c: COL.claude.line, n: 'Claude' },
        { c: COL.gemini.line, n: 'Gemini' },
        { c: COL.grok.line, n: 'Grok' },
        { c: COL.codex.line, n: 'Codex' },
        { c: COL.trunk, n: 'Dispatch' },
      ];
      lines.forEach((l, i) => {
        const yy = ly + 17 + i * 11;
        ctx.fillStyle = l.c;
        ctx.fillRect(lx, yy - 2, 14, 2);
        ctx.fillStyle = 'rgba(233,233,238,0.45)';
        ctx.fillText(l.n, lx + 19, yy);
      });
      ctx.restore();

      frame++;
    }

    function loop() {
      if (!running) return;
      draw();
      rafId = requestAnimationFrame(loop);
    }

    function start() {
      if (running) return;
      running = true;
      if (!rafId) rafId = requestAnimationFrame(loop);
    }

    function stop() {
      running = false;
      if (rafId) {
        cancelAnimationFrame(rafId);
        rafId = null;
      }
    }

    // Reduced motion
    const rm = window.matchMedia ? window.matchMedia('(prefers-reduced-motion: reduce)') : { matches: false };
    if (rm.matches) {
      // draw static once
      draw();
      // still allow manual debug start
    } else {
      // visibility + intersection driven
      document.addEventListener('visibilitychange', () => {
        if (document.hidden) stop();
        else if (!rm.matches) start();
      }, { passive: true });

      if ('IntersectionObserver' in window) {
        const io = new IntersectionObserver((ents) => {
          ents.forEach((ent) => {
            if (ent.isIntersecting) start();
            else stop();
          });
        }, { threshold: 0.08 });
        io.observe(canvas);
      } else {
        // fallback start
        setTimeout(start, 120);
      }
    }

    // Self start on load
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', () => {
        setTimeout(() => { if (!rm.matches) start(); else draw(); }, 60);
      });
    } else {
      setTimeout(() => { if (!rm.matches) start(); else draw(); }, 60);
    }

    // Debug handle only
    window.__synlynkMotherboard = {
      start: () => start(),
      stop: () => stop(),
      redraw: () => draw(),
      canvas
    };
  }

  // Auto-invoke
  initMotherboard();
})();
