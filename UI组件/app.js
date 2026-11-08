/* ============ UI 组件演示 · 手动交互 ============ */
(function () {

  /* ── 02/03 弹层控件 ── */
  // tooltip 由 CSS :hover 触发,无需 JS

  function bindToggle(btnId, layerSel) {
    const btn = document.getElementById(btnId);
    const layer = document.querySelector(layerSel);
    if (!btn || !layer) return;
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      layer.classList.toggle('show');
    });
  }
  bindToggle('btnDd', '#dd01');

  const pop = document.getElementById('pop01');
  const btnPop = document.getElementById('btnPop');
  if (pop && btnPop) {
    btnPop.addEventListener('click', (e) => { e.stopPropagation(); pop.classList.toggle('show'); });
    ['popClose', 'popMore'].forEach(id => {
      const b = document.getElementById(id);
      if (b) b.addEventListener('click', () => pop.classList.remove('show'));
    });
  }

  function bindMask(btnId, maskId, closeIds) {
    const btn = document.getElementById(btnId);
    const mask = document.getElementById(maskId);
    if (!btn || !mask) return;
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      // 模态弹层互斥:打开一个,关闭其他
      document.querySelectorAll('.mask.show').forEach(m => { if (m !== mask) m.classList.remove('show'); });
      mask.classList.add('show');
    });
    mask.addEventListener('click', (e) => { if (e.target === mask) mask.classList.remove('show'); });
    closeIds.forEach(id => {
      const b = document.getElementById(id);
      if (b) b.addEventListener('click', () => mask.classList.remove('show'));
    });
  }
  bindMask('btnModal', 'modalMask', ['modalCancel', 'modalOk']);
  bindMask('btnDrawer', 'drawerMask', ['drawerClose']);
  bindMask('btnSheet', 'sheetMask', []);

  // ESC 关闭所有弹层
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      document.querySelectorAll('.mask.show').forEach(m => m.classList.remove('show'));
      document.querySelectorAll('.dd.show, .pop.show').forEach(l => l.classList.remove('show'));
    }
  });

  /* ── 03 导航组件 ── */
  // tabs
  const tabbar = document.getElementById('tabbar01');
  const tabpanel = document.getElementById('tabpanel01');
  if (tabbar && tabpanel) {
    const labels = ['内容 · 首页', '内容 · 发现', '内容 · 我的'];
    tabbar.querySelectorAll('.tab').forEach(tab => tab.addEventListener('click', () => {
      tabbar.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      tabpanel.textContent = labels[parseInt(tab.dataset.i)];
    }));
  }

  // segmented control
  const seg = document.getElementById('seg01');
  if (seg) {
    const thumb = seg.querySelector('.seg-thumb');
    const items = seg.querySelectorAll('.seg-item');
    function segGo(i) {
      items.forEach((it, idx) => it.classList.toggle('active', idx === i));
      thumb.style.left = items[i].offsetLeft + 'px';
      thumb.style.width = items[i].offsetWidth + 'px';
    }
    items.forEach((it, i) => it.addEventListener('click', () => segGo(i)));
    requestAnimationFrame(() => segGo(0));
  }

  // breadcrumb
  const crumb = document.getElementById('crumb01');
  if (crumb) {
    crumb.querySelectorAll('.step').forEach((st, i) => st.addEventListener('click', () => {
      crumb.querySelectorAll('.step').forEach((s, j) => {
        s.classList.toggle('done', j < i);
        s.classList.toggle('here', j === i);
      });
    }));
  }

  // pagination
  const pager = document.getElementById('pager01');
  if (pager) {
    const pages = pager.querySelectorAll('.pg[data-n]');
    let cur = 0;
    function pageGo(i) {
      cur = (i + pages.length) % pages.length;
      pages.forEach((p, idx) => p.classList.toggle('active', idx === cur));
    }
    pager.querySelectorAll('.pg').forEach(p => p.addEventListener('click', () => {
      if (p.dataset.act === 'prev') pageGo(cur - 1);
      else if (p.dataset.act === 'next') pageGo(cur + 1);
      else pageGo(parseInt(p.dataset.n) - 1);
    }));
    pageGo(0);
  }

  // stepper
  const stepper = document.getElementById('stepper01');
  if (stepper) {
    const steps = stepper.querySelectorAll('.st');
    const links = stepper.querySelectorAll('.link');
    function stepGo(i) {
      steps.forEach((st, idx) => {
        st.classList.toggle('done', idx < i);
        st.classList.toggle('active', idx === i);
      });
      links.forEach((lk, idx) => lk.classList.toggle('done', idx < i));
    }
    steps.forEach((st, i) => st.addEventListener('click', () => stepGo(i)));
    stepGo(0);
  }

  // sidebar
  const sb = document.getElementById('sbwrap01');
  const sbBtn = document.getElementById('sbToggle01');
  if (sb && sbBtn) {
    sbBtn.addEventListener('click', () => {
      sb.classList.toggle('closed');
      sbBtn.textContent = sb.classList.contains('closed') ? '展开' : '收起';
    });
    sb.querySelectorAll('.sbitem').forEach(it => it.addEventListener('click', () => {
      sb.querySelectorAll('.sbitem').forEach(x => x.classList.remove('active'));
      it.classList.add('active');
    }));
  }

  // bottom navigation
  const bn = document.getElementById('bnwrap01');
  const bncontent = document.getElementById('bncontent01');
  if (bn && bncontent) {
    bn.querySelectorAll('.bnitem').forEach(it => it.addEventListener('click', () => {
      bn.querySelectorAll('.bnitem').forEach(t => t.classList.remove('active'));
      it.classList.add('active');
      bncontent.textContent = it.dataset.l;
    }));
  }

  /* ── 04 加载动画 ── */
  // button loading:点击进入 1.8s 加载态
  const bl = document.getElementById('btnLoad01');
  if (bl) {
    bl.addEventListener('click', () => {
      if (bl.classList.contains('loading')) return;
      bl.classList.add('loading');
      bl.disabled = true;
      setTimeout(() => {
        bl.classList.remove('loading');
        bl.disabled = false;
      }, 1800);
    });
  }

  // page loader:循环演示"加载 → 内容浮现",点击可重播
  const pl = document.getElementById('pload01');
  if (pl) {
    let plTimer = null;
    function plCycle() {
      pl.classList.remove('playing');
      plTimer = setTimeout(() => pl.classList.add('playing'), 3000);
    }
    plTimer = setTimeout(() => pl.classList.add('playing'), 3000);
    setInterval(plCycle, 5200);
    pl.addEventListener('click', () => {
      clearTimeout(plTimer);
      plCycle();
    });
  }

  // skeleton / shimmer:循环演示「加载 → 完成」
  const skel = document.getElementById('skelDemo01');
  if (skel) {
    setInterval(() => {
      skel.classList.remove('done');
      setTimeout(() => skel.classList.add('done'), 2600);
    }, 4400);
  }
  const shim = document.getElementById('shimDemo01');
  if (shim) {
    setInterval(() => {
      shim.classList.remove('idle');
      setTimeout(() => shim.classList.add('idle'), 2400);
    }, 4100);
  }

  /* ── 05 特殊控件 ── */
  // carousel
  const caro = document.getElementById('caro01');
  if (caro) {
    const track = caro.querySelector('.track');
    const slideW = () => (track.querySelector('.slide').offsetWidth || 420);
    const dots = caro.querySelectorAll('#caroDots01 i');
    let ci = 0;
    function caroGo(i) {
      ci = (i + 3) % 3;
      track.style.transform = 'translateX(-' + ci * slideW() + 'px)';
      dots.forEach((d, idx) => d.classList.toggle('on', idx === ci));
    }
    caro.querySelector('.navbtn.prev').addEventListener('click', () => caroGo(ci - 1));
    caro.querySelector('.navbtn.next').addEventListener('click', () => caroGo(ci + 1));
    dots.forEach(d => d.addEventListener('click', () => caroGo(parseInt(d.dataset.i))));
  }

  // number input
  const ni = document.getElementById('numinput01');
  const nval = document.getElementById('nval01');
  if (ni && nval) {
    let nv = 2;
    ni.querySelectorAll('.nbtn').forEach(b => b.addEventListener('click', () => {
      nv = Math.min(10, Math.max(0, nv + parseInt(b.dataset.d)));
      nval.textContent = nv;
    }));
  }

  // timeline:点击节点,该节点及之前全部点亮;完成态再点最后一项重置
  const tl = document.getElementById('tline01');
  if (tl) {
    const rows = tl.querySelectorAll('.trow');
    rows.forEach((r, i) => r.addEventListener('click', () => {
      const allOn = Array.from(rows).every(x => x.classList.contains('on'));
      if (allOn && i === rows.length - 1) {
        rows.forEach(x => x.classList.remove('on'));
        return;
      }
      rows.forEach((x, j) => x.classList.toggle('on', j <= i));
    }));
  }

  // switch
  const sw = document.getElementById('sw01');
  const swLabel = document.getElementById('swlabel01');
  if (sw && swLabel) {
    sw.addEventListener('click', () => {
      const on = sw.classList.toggle('on');
      swLabel.textContent = on ? '自动更新 · 已开启' : '自动更新';
    });
  }

})();
