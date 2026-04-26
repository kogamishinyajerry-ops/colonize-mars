// ═══════════ 殖民火星 — 前端控制器 ═══════════

const ROW_LENGTHS = [5, 6, 7, 8, 9, 8, 7, 6, 5];
const HEX_W = 64;
const HEX_H = HEX_W * 2 / Math.sqrt(3);
const ROW_OFFSET_X = 24;
const ROW_OFFSET_Y = 16;

const PLAYER_COLORS = ["#ff6b3d", "#5dade2", "#6dd47e", "#c39bd3", "#ffd166"];

const RES_ICONS = {
  mc: "💰", steel: "⛏", titanium: "💎",
  plants: "🌿", energy: "⚡", heat: "🔥",
};
const RES_NAMES = {
  mc: "MC", steel: "钢", titanium: "钛",
  plants: "植", energy: "能", heat: "热",
};

let state = null;
let pendingHandled = null;        // 已经处理过的 pending 序号，避免重复触发
let researchKept = new Set();
let pollTimer = null;
let lastLogCount = 0;
let hexClickHandler = null;

// ═══════════ 启动模态 — DLC 模式选择 ═══════════
const MODE_HINTS = {
  base: "经典 Terraforming Mars 体验。三大全球参数+绿地+城市+里程碑。",
  orbital: "<strong>DLC I 轨道战争</strong>：新增 Force/Intel 资源，霸权税让 TR 第一名每代付 5MC，可花 Force 破坏对手卡。",
  parallel: "<strong>DLC II 平行火星</strong>：放弃公司选择，从已解锁派系（巴比伦/协议体/虫群）中选一个。每个派系有完全不同的核心循环。",
  "parallel-campaign": "<strong>DLC II 战役模式</strong>：选择章节进入剧情。胜利条件由章节定义，通关解锁新内容。",
  crimson: "<strong>DLC III 红色风暴</strong>：协作模式。火星灾害是共同敌人，威胁条满 30 = 全员失败。可援助队友。",
  "crimson-doom": "<strong>DLC III 末日难度</strong>：威胁阈值 20，每代 2 张灾害。极其残酷，建议熟练后挑战。",
  all: "<strong>混乱模式</strong>：三 DLC 同时启用。Force+灾害+派系全融合。慎入。",
};

let selectedChapter = 1;
let dlcSaveInfo = null;

document.getElementById("setup-mode").addEventListener("change", (e) => {
  const mode = e.target.value;
  document.getElementById("mode-hint").innerHTML = MODE_HINTS[mode] || "";
  const showChapters = mode === "parallel-campaign";
  document.getElementById("chapter-row").classList.toggle("hidden", !showChapters);
  if (showChapters && !dlcSaveInfo) loadDlcSave();
});

async function loadDlcSave() {
  const r = await fetch("/api/dlc_save");
  dlcSaveInfo = await r.json();
  renderChapterGrid();
}

function renderChapterGrid() {
  const cont = document.getElementById("chapter-grid");
  if (!dlcSaveInfo) return;
  cont.innerHTML = dlcSaveInfo.chapters.map(c => {
    const facName = (dlcSaveInfo.factions.find(f => f.key === c.faction) || {}).name || c.faction;
    const locked = c.num > 1 && !dlcSaveInfo.save.chapters_completed.includes(c.num - 1);
    const cls = "chapter-card"
      + (locked ? " locked" : "")
      + (c.num === selectedChapter ? " selected" : "")
      + (c.completed ? " completed" : "");
    return `<div class="${cls}" data-num="${c.num}" data-locked="${locked}">
      <div class="ch-num">第${c.num}章</div>
      <div class="ch-name">${escape(c.name)}</div>
      <div class="ch-faction">${escape(facName)}</div>
    </div>`;
  }).join("");
  cont.querySelectorAll(".chapter-card:not(.locked)").forEach(el => {
    el.addEventListener("click", () => {
      selectedChapter = parseInt(el.dataset.num);
      renderChapterGrid();
    });
  });
}

document.getElementById("setup-mode").dispatchEvent(new Event("change"));

document.getElementById("setup-start").addEventListener("click", async () => {
  const mode = document.getElementById("setup-mode").value;
  const players = parseInt(document.getElementById("setup-players").value);
  const seedRaw = document.getElementById("setup-seed").value;
  const humanRaw = document.getElementById("setup-human").value;

  const dlcs = [];
  if (mode === "orbital") dlcs.push({name: "orbital"});
  else if (mode === "parallel") dlcs.push({name: "parallel"});
  else if (mode === "parallel-campaign") dlcs.push({name: "parallel", chapter: selectedChapter});
  else if (mode === "crimson") dlcs.push({name: "crimson", difficulty: "normal"});
  else if (mode === "crimson-doom") dlcs.push({name: "crimson", difficulty: "doom"});
  else if (mode === "all") {
    dlcs.push({name: "orbital"});
    dlcs.push({name: "parallel"});
    dlcs.push({name: "crimson", difficulty: "normal"});
  }

  const body = {
    players,
    seed: seedRaw === "" ? null : parseInt(seedRaw),
    human_idx: parseInt(humanRaw),
    dlcs,
  };
  await fetch("/api/new_game", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(body),
  });

  // 战役模式显示剧情
  if (mode === "parallel-campaign" && dlcSaveInfo) {
    const ch = dlcSaveInfo.chapters.find(c => c.num === selectedChapter);
    if (ch) showChapterIntro(ch);
  }

  document.getElementById("setup-modal").classList.add("hidden");
  document.getElementById("app").classList.remove("hidden");
  startPolling();
});

function showChapterIntro(ch) {
  const overlay = document.createElement("div");
  overlay.className = "chapter-intro";
  overlay.innerHTML = `<div class="chapter-intro-card">
    <h2>第${ch.num}章 · ${escape(ch.name)}</h2>
    <div class="intro-text">${escape(ch.intro)}</div>
    <div class="target"><strong>目标：</strong>${escape(ch.target)}</div>
    <button class="btn btn-primary" id="intro-close" style="width:100%">进入火星 →</button>
  </div>`;
  document.body.appendChild(overlay);
  overlay.querySelector("#intro-close").addEventListener("click", () => overlay.remove());
}

document.getElementById("btn-restart").addEventListener("click", () => {
  if (confirm("放弃当前游戏并重开？")) location.reload();
});

// ═══════════ 主轮询 ═══════════
function startPolling() {
  pollTimer = setInterval(refresh, 600);
  refresh(true);
}

async function refresh(full = false) {
  const url = full ? "/api/state?full=1" : "/api/state";
  const resp = await fetch(url);
  const snap = await resp.json();
  if (!snap.started) return;
  state = snap;
  render();
  if (snap.done) {
    clearInterval(pollTimer);
    showEndgame(snap.result);
  }
}

// ═══════════ 渲染入口 ═══════════
function render() {
  renderTopbar();
  renderPlayers();
  renderMilestonesAwards();
  renderBoard();
  renderHand();
  renderDecision();
  renderDLCs();
  appendLogs(state.logs_new || state.logs_all || []);
}

// ═══════════ 顶部参数栏 ═══════════
function renderTopbar() {
  document.getElementById("val-gen").textContent = state.generation;
  document.getElementById("val-temp").textContent = state.temperature;
  document.getElementById("val-oxy").textContent = state.oxygen;
  document.getElementById("val-ocean").textContent = state.oceans;
  // 进度条
  const tempPct = ((state.temperature + 30) / 38) * 100;
  const oxyPct = (state.oxygen / 14) * 100;
  const oceanPct = (state.oceans / 9) * 100;
  document.getElementById("track-temp").style.width = tempPct + "%";
  document.getElementById("track-oxy").style.width = oxyPct + "%";
  document.getElementById("track-ocean").style.width = oceanPct + "%";
}

// ═══════════ 玩家面板 ═══════════
function renderPlayers() {
  const cont = document.getElementById("players-list");
  cont.innerHTML = "";
  for (const p of state.players) {
    const div = document.createElement("div");
    const isCurrent = p.idx === state.current_player_idx && !p.passed && !state.done;
    div.className = "player-card"
      + (isCurrent ? " active" : "")
      + (p.passed ? " passed" : "")
      + (!p.is_ai ? " is-human" : "");
    div.innerHTML = `
      <div class="player-name">
        <span>
          <span style="color:${PLAYER_COLORS[p.idx]};font-weight:bold">●</span>
          <strong>${escape(p.name)}</strong>
          <span class="player-corp">[${escape(p.corp_name || "—")}]</span>
        </span>
        <span>
          <span class="player-tr">TR ${p.tr}</span>
          <span class="player-vp">${p.vp_estimate}VP</span>
        </span>
      </div>
      <div class="res-grid">
        ${renderResCells(p.resources, p.production)}
      </div>
      <div style="margin-top:6px;font-size:10px;color:var(--text-dim)">
        手牌:${p.hand.length}  打出:${p.played.length}
        ${p.passed ? '<span style="color:var(--gold)"> · 已跳过</span>' : ''}
      </div>
    `;
    cont.appendChild(div);
  }
}

function renderResCells(res, prod) {
  return Object.keys(RES_ICONS).map(k => {
    const v = res[k];
    const p = prod[k];
    const sign = p > 0 ? `+${p}` : (p < 0 ? `${p}` : "0");
    const cls = p < 0 ? " neg" : "";
    return `<div class="res-cell">
      <span class="ic">${RES_ICONS[k]}</span>
      <span><span class="v">${v}</span><span class="p${cls}">${sign}</span></span>
    </div>`;
  }).join("");
}

// ═══════════ DLC 状态附加面板 ═══════════
function renderDLCs() {
  const dlcs = state.dlcs || {};

  // DLC III 威胁条
  const tb = document.getElementById("threat-bar");
  if (dlcs.crimson) {
    tb.classList.remove("hidden");
    const t = dlcs.crimson.threat;
    const max = dlcs.crimson.threshold;
    document.getElementById("threat-val").textContent = t;
    document.getElementById("threat-max").textContent = max;
    document.getElementById("threat-fill").style.width = Math.min(100, (t / max) * 100) + "%";
    if (t >= max * 0.7) tb.classList.add("critical");
    else tb.classList.remove("critical");

    // 灾害日志侧栏
    const sec = document.getElementById("dlc-crimson-section");
    sec.classList.remove("hidden");
    const log = dlcs.crimson.disasters_log || [];
    document.getElementById("disasters-log").innerHTML = log.slice(-6).reverse().map(d =>
      `<li><span class="gen">G${d.gen}</span> ${escape(d.name)}</li>`
    ).join("") || "<li style='color:var(--text-dim)'>(尚无灾害)</li>";
    const prev = dlcs.crimson.next_preview;
    document.getElementById("next-disaster-preview").innerHTML =
      prev ? `🔭 下代预警：<strong>${escape(prev)}</strong>` : "";
  } else {
    tb.classList.add("hidden");
    document.getElementById("dlc-crimson-section").classList.add("hidden");
  }

  // DLC I/II 玩家卡内附加条
  if (dlcs.orbital || dlcs.parallel) {
    document.querySelectorAll(".player-card").forEach((el, idx) => {
      // 移除旧附加（renderPlayers 已重画时不需要）
      const p = state.players[idx];
      if (!p) return;
      // Orbital
      if (dlcs.orbital) {
        const ob = dlcs.orbital.players.find(x => x.idx === p.idx);
        if (ob) {
          const div = document.createElement("div");
          div.className = "orbital-bar";
          let html = `<span class="obar-cell">⚔ Force ${ob.force} (+${ob.force_prod})</span>
                      <span class="obar-cell intel">🕵 Intel ${ob.intel} (+${ob.intel_prod})</span>`;
          const napCount = Object.keys(ob.naps || {}).length;
          if (napCount) html += `<span class="obar-cell nap">📜 NAP ${napCount}</span>`;
          if (ob.war_crimes) html += `<span class="obar-cell crime">⚖ ${ob.war_crimes}</span>`;
          div.innerHTML = html;
          el.appendChild(div);
        }
      }
      // Parallel
      if (dlcs.parallel) {
        const pb = dlcs.parallel.players.find(x => x.idx === p.idx);
        if (pb && pb.faction) {
          const div = document.createElement("div");
          div.className = "faction-bar";
          let html = `<span class="fbar-cell">${escape(pb.faction)}</span>`;
          if (pb.faith) html += `<span class="fbar-cell">✨ 信仰 ${pb.faith}</span>`;
          if (pb.compute) html += `<span class="fbar-cell">⚙ 算力 ${pb.compute}</span>`;
          if (pb.biomass) html += `<span class="fbar-cell">🦠 生物质 ${pb.biomass}</span>`;
          if (pb.hive_size) html += `<span class="fbar-cell">蜂巢 ${pb.hive_size}</span>`;
          if (pb.cathedral) html += `<span class="fbar-cell cathedral">⛪ 大教堂</span>`;
          if (pb.sing_progress) html += `<span class="fbar-cell singularity">奇点 ${pb.sing_progress}%</span>`;
          div.innerHTML = html;
          el.appendChild(div);
        }
      }
    });
  }
}

// ═══════════ 里程碑 / 奖励 ═══════════
function renderMilestonesAwards() {
  // 里程碑名（与后端一致）
  const ms = [
    ["Terraformer 改造者", "TR ≥ 35"],
    ["Mayor 市长", "拥有 ≥3 城市"],
    ["Gardener 园丁", "拥有 ≥3 绿地"],
    ["Builder 建造者", "≥8 建筑标签"],
    ["Planner 谋划者", "手牌 ≥16 张"],
  ];
  const aw = [
    ["Landlord 大地主", "板块最多"],
    ["Banker 银行家", "MC 产能最高"],
    ["Scientist 科学家", "科学标签最多"],
    ["Thermalist 热能学家", "热资源最多"],
    ["Miner 矿工", "钢+钛最多"],
  ];
  document.getElementById("milestones-list").innerHTML = ms.map(([n, d]) => {
    const claimed = state.claimed_milestones[n];
    const claimedTxt = (claimed !== undefined)
      ? `<span style="color:var(--gold)"> · P${claimed} ✓</span>` : "";
    return `<li class="${claimed!==undefined?'claimed':''}">
      <strong>${escape(n)}</strong>${claimedTxt}<br>
      <span class="small">${escape(d)}</span>
    </li>`;
  }).join("");
  const awCosts = [8, 14, 20];
  const fundedCount = Object.keys(state.funded_awards).length;
  document.getElementById("awards-list").innerHTML = aw.map(([n, d]) => {
    const funder = state.funded_awards[n];
    const fundedTxt = (funder !== undefined)
      ? `<span style="color:var(--gold)"> · P${funder} 资助</span>` : "";
    const nextCost = fundedCount < 3 ? ` (下一${awCosts[fundedCount]}M$)` : "";
    return `<li class="${funder!==undefined?'claimed':''}">
      <strong>${escape(n)}</strong>${fundedTxt}<br>
      <span class="small">${escape(d)}${funder===undefined?nextCost:''}</span>
    </li>`;
  }).join("");
}

// ═══════════ 棋盘渲染 ═══════════
function renderBoard() {
  const svg = document.getElementById("mars-board");
  // 计算总宽高
  const maxLen = Math.max(...ROW_LENGTHS);
  const totalW = ROW_OFFSET_X * 2 + maxLen * HEX_W;
  const totalH = ROW_OFFSET_Y * 2 + (ROW_LENGTHS.length - 1) * (HEX_H * 0.75) + HEX_H;
  svg.setAttribute("viewBox", `0 0 ${totalW} ${totalH}`);

  // 是否为可点击模式（hex 选择 pending）
  const pickHex = state.pending && state.pending.type === "hex";
  const validCoords = new Set();
  if (pickHex) {
    for (const c of state.pending.choices) {
      validCoords.add(`${c.row},${c.col}`);
    }
  }

  let svgContent = "";
  for (let r = 0; r < state.board.rows.length; r++) {
    const row = state.board.rows[r];
    const indent = (maxLen - row.length) * HEX_W / 2;
    for (let c = 0; c < row.length; c++) {
      const hex = row[c];
      const cx = ROW_OFFSET_X + indent + c * HEX_W + HEX_W / 2;
      const cy = ROW_OFFSET_Y + r * (HEX_H * 0.75) + HEX_H / 2;
      svgContent += renderHex(hex, cx, cy, pickHex && validCoords.has(`${hex.row},${hex.col}`));
    }
  }
  svg.innerHTML = svgContent;

  // 绑定点击
  svg.querySelectorAll(".hex.clickable").forEach(el => {
    el.addEventListener("click", () => {
      const r = parseInt(el.dataset.r);
      const c = parseInt(el.dataset.c);
      if (state.pending && state.pending.type === "hex") {
        submitAnswer({row: r, col: c});
      }
    });
  });
}

function renderHex(hex, cx, cy, clickable) {
  const w = HEX_W, h = HEX_H;
  // 尖顶六边形顶点（相对中心）
  const pts = [
    [0, -h/2],
    [w/2, -h/4],
    [w/2, h/4],
    [0, h/2],
    [-w/2, h/4],
    [-w/2, -h/4],
  ].map(([x,y]) => `${cx+x},${cy+y}`).join(" ");

  let cls = "hex";
  if (hex.tile === "Ocean") cls += " hex-tile-ocean";
  else if (hex.tile === "Greenery") cls += " hex-tile-greenery";
  else if (hex.tile === "City") cls += " hex-tile-city";
  else if (hex.kind === "OceanReserved") cls += " hex-ocean-reserved";
  else if (hex.kind === "Volcanic") cls += " hex-volcanic";
  else if (hex.kind === "Noctis") cls += " hex-noctis";
  else cls += " hex-land";
  if (clickable) cls += " clickable target";

  let extras = "";
  // 板块图标
  if (hex.tile === "Ocean") {
    extras += `<text class="hex-tile-icon" x="${cx}" y="${cy}">🌊</text>`;
  } else if (hex.tile === "Greenery") {
    extras += `<text class="hex-tile-icon" x="${cx}" y="${cy}">🌱</text>`;
  } else if (hex.tile === "City") {
    extras += `<text class="hex-tile-icon" x="${cx}" y="${cy}">🏙</text>`;
  } else {
    // 显示奖励
    if (hex.bonus) {
      const [k, n] = hex.bonus;
      const ic = {steel:"⛏", titanium:"💎", plant:"🌿", card:"🃏", heat:"🔥"}[k] || "?";
      extras += `<text class="hex-bonus" x="${cx}" y="${cy+2}">${ic}${n>1?n:""}</text>`;
    }
  }
  // 拥有者标记
  if (hex.owner !== null && hex.owner !== undefined && hex.tile !== "Ocean") {
    extras += `<circle cx="${cx + w/3}" cy="${cy - h/3}" r="6" fill="${PLAYER_COLORS[hex.owner]}" stroke="#1a1a26" stroke-width="1"/>`;
    extras += `<text class="hex-owner-mark" x="${cx + w/3}" y="${cy - h/3 + 3}">${hex.owner}</text>`;
  }
  // 坐标
  extras += `<text class="hex-label" x="${cx}" y="${cy + h/2 - 3}">${hex.row},${hex.col}</text>`;

  return `<g><polygon class="${cls}" points="${pts}" data-r="${hex.row}" data-c="${hex.col}"/>${extras}</g>`;
}

// ═══════════ 手牌渲染 ═══════════
function renderHand() {
  const me = state.players.find(p => !p.is_ai);
  if (!me) {
    document.getElementById("hand-title").textContent = "(观战模式)";
    document.getElementById("hand-cards").innerHTML = "";
    return;
  }
  document.getElementById("hand-title").textContent = `手牌 (${me.hand.length})`;

  // 当前合法可打出的卡（来自 pending action 列表）
  const playable = new Set();
  if (state.pending && state.pending.type === "action") {
    for (const a of state.pending.legal) {
      if (a.kind === "play_card") playable.add(a.card_id);
    }
  }

  const cont = document.getElementById("hand-cards");
  cont.innerHTML = me.hand.map(c => renderCard(c, {playable: playable.has(c.id)})).join("");
  cont.querySelectorAll(".card").forEach((el, i) => {
    el.addEventListener("click", () => showCardDetail(me.hand[i]));
  });
}

function renderCard(c, opts = {}) {
  const tags = c.tags.map(t => `<span class="tag tag-${t}">${t}</span>`).join("");
  const vpHtml = c.vp ? `<span class="c-vp">${c.vp>0?'+':''}${c.vp}VP</span>` : "";
  const resMark = c.resource_kind ? `<span class="c-resmark">${c.resource_kind} x${c.resources_on_card}</span>` : "";
  const playable = opts.playable ? " playable" : "";
  return `<div class="card type-${c.type}${playable}">
    <div class="c-head">
      <span class="c-name">${escape(c.name)}${vpHtml}${resMark}</span>
      <span class="c-cost">${c.cost}M$</span>
    </div>
    <div class="c-tags">${tags}</div>
    <div class="c-desc">${escape(c.description)}</div>
  </div>`;
}

function showCardDetail(c) {
  const z = document.getElementById("card-zoom");
  document.getElementById("card-zoom-content").innerHTML = renderCard(c);
  z.classList.remove("hidden");
}

// ═══════════ 决策面板 ═══════════
function renderDecision() {
  const panel = document.getElementById("decision-panel");
  if (!state.pending) {
    if (state.done) {
      panel.innerHTML = `<div class="decision-empty">🏁 游戏结束</div>`;
    } else {
      const cur = state.players[state.current_player_idx];
      panel.innerHTML = `<div class="decision-empty">⏳ 等待 P${state.current_player_idx} (${escape(cur ? cur.name : '?')}) 行动...</div>`;
    }
    pendingHandled = null;
    return;
  }
  const pkey = JSON.stringify(state.pending).slice(0, 200);
  if (pkey === pendingHandled) return; // 同一个 pending 不重渲染
  pendingHandled = pkey;
  researchKept = new Set();

  const t = state.pending.type;
  if (t === "corp") renderCorpChoice(panel);
  else if (t === "research") renderResearch(panel);
  else if (t === "action") renderActionMenu(panel);
  else if (t === "hex") renderHexPick(panel);
}

function renderCorpChoice(panel) {
  const opts = state.pending.options;
  let html = `<h3>${escape(state.pending.prompt)}</h3><div class="corp-options">`;
  for (let i = 0; i < opts.length; i++) {
    const c = opts[i];
    html += `<div class="corp-option" data-i="${i}">
      <div class="corp-name">${escape(c.name)}</div>
      <div class="corp-desc">${escape(c.description)}</div>
    </div>`;
  }
  html += `</div>`;
  panel.innerHTML = html;
  panel.querySelectorAll(".corp-option").forEach(el => {
    el.addEventListener("click", () => {
      submitAnswer({index: parseInt(el.dataset.i)});
    });
  });
}

function renderResearch(panel) {
  const drawn = state.pending.drawn;
  let html = `<h3>${escape(state.pending.prompt)}</h3>
    <div style="font-size:11px;color:var(--text-dim);margin-bottom:6px">
      你的 MC: ${state.pending.mc} · 选 N 张需付 N×3 MC
    </div>
    <div class="research-list">`;
  for (let i = 0; i < drawn.length; i++) {
    const c = drawn[i];
    const tags = c.tags.map(t => `<span class="tag tag-${t}">${t}</span>`).join("");
    html += `<div class="research-card" data-i="${i}">
      <span class="rc-cost">${c.cost}M$</span>
      <span class="rc-name">${escape(c.name)}<div class="rc-tags" style="font-size:10px">${tags} ${escape(c.description.slice(0,60))}</div></span>
    </div>`;
  }
  html += `</div>
    <div class="research-confirm">
      <span id="research-cost">已选 0 张, 花费 0 MC</span>
      <button class="btn btn-primary" id="research-go">确认</button>
    </div>`;
  panel.innerHTML = html;

  panel.querySelectorAll(".research-card").forEach(el => {
    el.addEventListener("click", () => {
      const i = parseInt(el.dataset.i);
      if (researchKept.has(i)) {
        researchKept.delete(i);
        el.classList.remove("kept");
      } else {
        researchKept.add(i);
        el.classList.add("kept");
      }
      const n = researchKept.size;
      document.getElementById("research-cost").textContent =
        `已选 ${n} 张, 花费 ${n*3} MC`;
    });
  });
  document.getElementById("research-go").addEventListener("click", () => {
    submitAnswer({indices: [...researchKept].sort((a,b)=>a-b)});
  });
}

function renderActionMenu(panel) {
  const legal = state.pending.legal;
  let html = `<h3>${escape(state.pending.prompt)}</h3><div class="action-list">`;
  for (const a of legal) {
    let kindIcon = "";
    if (a.kind === "play_card") kindIcon = "🃏 ";
    else if (a.kind === "std_project") kindIcon = "🏗 ";
    else if (a.kind === "blue_action") kindIcon = "🔵 ";
    else if (a.kind === "claim_milestone") kindIcon = "🏆 ";
    else if (a.kind === "fund_award") kindIcon = "🏅 ";
    else if (a.kind === "convert_plants") kindIcon = "🌱 ";
    else if (a.kind === "convert_heat") kindIcon = "🔥 ";
    else if (a.kind === "pass") kindIcon = "⏸ ";
    html += `<button class="btn btn-action" data-i="${a.index}">${kindIcon}${escape(a.label)}</button>`;
  }
  html += `</div>`;
  panel.innerHTML = html;
  panel.querySelectorAll(".btn-action").forEach(el => {
    el.addEventListener("click", () => {
      submitAnswer({index: parseInt(el.dataset.i)});
    });
  });
}

function renderHexPick(panel) {
  const ch = state.pending.choices;
  const kind = state.pending.kind;
  const kindLabels = {ocean: "🌊 海洋", greenery: "🌱 绿地", city: "🏙 城市"};
  let html = `<h3>放置 ${kindLabels[kind] || kind}</h3>
    <div style="font-size:11px;color:var(--text-dim);margin-bottom:6px">
      可点击棋盘上闪烁的格子，或在下方选择：
    </div>
    <div class="hex-pick-list">`;
  for (const h of ch.slice(0, 60)) {
    const bonus = h.bonus ? ` 🎁${h.bonus[0][0]}${h.bonus[1]>1?h.bonus[1]:""}` : "";
    const adj = h.adjacent_oceans > 0 ? ` 💧${h.adjacent_oceans}` : "";
    html += `<div class="hex-pick-item" data-r="${h.row}" data-c="${h.col}">
      (${h.row},${h.col})${bonus}${adj}
    </div>`;
  }
  html += `</div>`;
  panel.innerHTML = html;
  panel.querySelectorAll(".hex-pick-item").forEach(el => {
    el.addEventListener("click", () => {
      submitAnswer({row: parseInt(el.dataset.r), col: parseInt(el.dataset.c)});
    });
  });
}

// ═══════════ 提交答案 ═══════════
async function submitAnswer(ans) {
  pendingHandled = null; // 允许重渲染
  await fetch("/api/submit", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(ans),
  });
  // 立刻刷新一次
  setTimeout(refresh, 80);
}

// ═══════════ 日志 ═══════════
function appendLogs(lines) {
  if (!lines || !lines.length) return;
  const log = document.getElementById("log-stream");
  // 防止重复追加（首次 full snapshot 后增量）
  const cont = document.createDocumentFragment();
  for (const line of lines) {
    const d = document.createElement("div");
    let cls = "l";
    if (line.includes("世代") && line.includes("开始")) cls += " l-gen";
    else if (line.includes("游戏结束") || line.includes("胜者")) cls += " l-end";
    else if (line.includes("已达上限") || line.includes("🏆") || line.includes("🏅")) cls += " l-warn";
    d.className = cls;
    d.textContent = line;
    cont.appendChild(d);
  }
  log.appendChild(cont);
  log.scrollTop = log.scrollHeight;
}

// ═══════════ 终局 ═══════════
function showEndgame(result) {
  const m = document.getElementById("endgame-modal");
  const c = document.getElementById("endgame-content");
  if (!result || !result.ranking) {
    c.innerHTML = "<p>游戏结束</p>";
  } else {
    let html = `<div class="endgame-ranking">`;
    for (let i = 0; i < result.ranking.length; i++) {
      const [idx, name, vp] = result.ranking[i];
      html += `<div class="row ${i===0?'first':''}">
        <span>${i+1}. P${idx} ${escape(name)}</span>
        <span><strong>${vp} VP</strong></span>
      </div>`;
    }
    html += `</div>`;
    c.innerHTML = html;
  }
  m.classList.remove("hidden");
}

// ═══════════ 工具 ═══════════
function escape(s) {
  if (s == null) return "";
  return String(s).replace(/[&<>"']/g, m => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[m]));
}
