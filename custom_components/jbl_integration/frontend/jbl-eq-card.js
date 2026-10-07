class JBLEqualizerCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
    this._hass = null;
    this._entityId = null;
    this._draft = null;
    this._dragIndex = null;
  }

  setConfig(config) {
    this._config = config || {};
  }

  set hass(hass) {
    this._hass = hass;
    const entityId = this._config.entity || this._findEntity(hass);
    const state = entityId ? hass.states[entityId] : null;
    if (!state) {
      this._entityId = entityId;
      this._renderMissing();
      return;
    }

    const incoming = Array.isArray(state.attributes.gains)
      ? state.attributes.gains.map(Number)
      : [];

    if (this._entityId !== entityId || !this._draft || !this._dirty) {
      this._draft = incoming;
      this._dirty = false;
    }
    this._entityId = entityId;
    this._render(state);
  }

  _findEntity(hass) {
    return Object.keys(hass.states).find(
      (entityId) =>
        entityId.startsWith("sensor.") &&
        hass.states[entityId]?.attributes?.jbl_eq_editor === true
    );
  }

  _renderMissing() {
    const markup = `
      <ha-card class="${modal ? "modal-card" : ""}">
        <div class="missing">
          JBL Equalizer entity not found. Set <code>entity:</code> in the card config.
        </div>
      </ha-card>
      <style>
        .missing { padding: 20px; color: var(--secondary-text-color); }
      </style>`;
  }

  _render(state) {
    if (this._config.mode === "button") {
      this._renderButton(state);
      return;
    }

    this._renderEditor(state, false);
  }

  _renderButton(state) {
    const title = this._escape(this._config.name || "Equalizer");
    const preset = this._escape(
      state.attributes.active_preset || state.state || "Custom"
    );

    this.shadowRoot.innerHTML = `
      <ha-card class="button-card" tabindex="0" role="button" aria-label="Open JBL Equalizer">
        <div class="button-content">
          <ha-icon icon="mdi:equalizer"></ha-icon>
          <div class="button-text">
            <div class="button-title">${title}</div>
            <div class="button-subtitle">${preset}</div>
          </div>
          <ha-icon icon="mdi:chevron-right"></ha-icon>
        </div>
      </ha-card>
      <div id="modal-root"></div>
      <style>
        .button-card { cursor:pointer; padding:14px 16px; }
        .button-content { display:flex; align-items:center; gap:12px; }
        .button-content > ha-icon:first-child { color:var(--primary-color); }
        .button-text { flex:1; min-width:0; }
        .button-title { font-size:16px; font-weight:600; color:var(--primary-text-color); }
        .button-subtitle { font-size:12px; color:var(--secondary-text-color); margin-top:2px; }
      </style>`;

    const open = () => this._openModal(state);
    const card = this.shadowRoot.querySelector(".button-card");
    card?.addEventListener("click", open);
    card?.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter" || ev.key === " ") {
        ev.preventDefault();
        open();
      }
    });
  }

  _openModal(state) {
    const root = this.shadowRoot.getElementById("modal-root");
    if (!root) return;

    root.innerHTML = `
      <div class="modal-backdrop">
        <div class="modal-shell" role="dialog" aria-modal="true">
          <button id="modal-close" class="modal-close" aria-label="Close">
            <ha-icon icon="mdi:close"></ha-icon>
          </button>
          <div id="modal-editor"></div>
        </div>
      </div>
      <style>
        .modal-backdrop {
          position:fixed; inset:0; z-index:9999;
          display:flex; align-items:center; justify-content:center;
          padding:18px; background:rgba(0,0,0,.48);
          backdrop-filter:blur(6px);
        }
        .modal-shell {
          position:relative; width:min(720px, 96vw); max-height:90vh;
          overflow:auto; border-radius:22px;
          background:var(--card-background-color);
          box-shadow:0 18px 60px rgba(0,0,0,.35);
        }
        .modal-close {
          position:absolute; z-index:2; top:10px; right:10px;
          width:38px; height:38px; display:grid; place-items:center;
          border:0; border-radius:50%; cursor:pointer;
          background:var(--secondary-background-color);
          color:var(--primary-text-color);
        }
      </style>`;

    const modalEditor = root.querySelector("#modal-editor");
    if (modalEditor) {
      this._renderEditor(state, true, modalEditor);
    }

    const close = () => { root.innerHTML = ""; };
    root.querySelector("#modal-close")?.addEventListener("click", close);
    root.querySelector(".modal-backdrop")?.addEventListener("click", (ev) => {
      if (ev.target.classList.contains("modal-backdrop")) close();
    });
  }

  _renderEditor(state, modal = false, target = this.shadowRoot) {
    const a = state.attributes;
    const bands = a.bands || [];
    const minimums = a.minimums || bands.map(() => -6);
    const maximums = a.maximums || bands.map(() => 6);
    const step = Number(a.step || 0.5);
    const gains = this._draft || (a.gains || []).map(Number);
    const globalMin = Math.min(...minimums, -6);
    const globalMax = Math.max(...maximums, 6);
    const width = 620;
    const height = 280;
    const left = 46;
    const right = 20;
    const top = 36;
    const bottom = 46;
    const plotW = width - left - right;
    const plotH = height - top - bottom;
    const x = (i) => left + (bands.length === 1 ? plotW / 2 : (i * plotW) / (bands.length - 1));
    const y = (value) => top + ((globalMax - value) / (globalMax - globalMin)) * plotH;
    const zeroY = y(0);

    const points = gains.map((v, i) => `${x(i)},${y(v)}`).join(" ");
    const area = bands.length
      ? `${left},${zeroY} ${points} ${x(bands.length - 1)},${zeroY}`
      : "";

    const gridValues = [globalMax, 0, globalMin];
    const grid = gridValues.map((v) => `
      <g>
        <line x1="${left}" x2="${width - right}" y1="${y(v)}" y2="${y(v)}"
          class="grid ${v === 0 ? "zero" : ""}" />
        <text x="${left - 10}" y="${y(v) + 4}" text-anchor="end" class="axis">${v > 0 ? "+" : ""}${v}</text>
      </g>`).join("");

    const bandEls = bands.map((label, i) => `
      <g class="band" data-index="${i}">
        <line x1="${x(i)}" x2="${x(i)}" y1="${top}" y2="${top + plotH}" class="vgrid"/>
        <line x1="${x(i)}" x2="${x(i)}" y1="${zeroY}" y2="${y(gains[i])}" class="stem"/>
        <text x="${x(i)}" y="20" text-anchor="middle" class="value">${Number(gains[i]).toFixed(step < 1 ? 1 : 0)}</text>
        <circle cx="${x(i)}" cy="${y(gains[i])}" r="10" class="handle" data-index="${i}"/>
        <text x="${x(i)}" y="${height - 14}" text-anchor="middle" class="band-label">${label}</text>
      </g>`).join("");

    const presetMap = a.preset_map || {};
    const presetOptions = Object.entries(presetMap)
      .map(([id, name]) => `<option value="${this._escape(id)}" ${name === a.active_preset ? "selected" : ""}>${this._escape(name)}</option>`)
      .join("");

    this.shadowRoot.innerHTML = `
      <ha-card>
        <div class="header">
          <div>
            <div class="title">${this._escape(this._config.name || "Equalizer")}</div>
            <div class="subtitle">${this._dirty ? "Edited" : this._escape(a.active_preset || state.state || "Custom")}</div>
          </div>
          ${presetOptions ? `<select id="preset" aria-label="EQ preset">${presetOptions}</select>` : ""}
        </div>

        <div class="chart-wrap">
          <svg id="chart" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none">
            <defs>
              <linearGradient id="fill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stop-color="var(--primary-color)" stop-opacity=".32"/>
                <stop offset="100%" stop-color="var(--primary-color)" stop-opacity=".03"/>
              </linearGradient>
            </defs>
            ${grid}
            ${area ? `<polygon points="${area}" class="area"/>` : ""}
            ${bands.length > 1 ? `<polyline points="${points}" class="curve"/>` : ""}
            ${bandEls}
          </svg>
        </div>

        <div class="footer">
          <button id="flat" class="secondary">Flat</button>
          <div class="range">${globalMin} dB <span>→</span> ${globalMax > 0 ? "+" : ""}${globalMax} dB</div>
          <button id="apply" class="primary" ${this._dirty ? "" : "disabled"}>Apply</button>
        </div>
      </ha-card>

      <style>
        :host { display:block; }
        ha-card {
          overflow:hidden;
          padding:18px 18px 14px;
          border-radius:var(--ha-card-border-radius, 18px);
          background:var(--ha-card-background, var(--card-background-color));
        }
        .header { display:flex; align-items:center; justify-content:space-between; gap:16px; margin-bottom:4px; }
        .title { font-size:20px; font-weight:650; color:var(--primary-text-color); }
        .subtitle { font-size:12px; color:var(--secondary-text-color); margin-top:3px; }
        select {
          color:var(--primary-text-color); background:var(--secondary-background-color);
          border:1px solid var(--divider-color); border-radius:12px; padding:8px 30px 8px 10px;
        }
        .chart-wrap { width:100%; overflow:hidden; touch-action:none; }
        svg { width:100%; height:auto; min-height:245px; overflow:visible; touch-action:none; }
        .grid { stroke:var(--divider-color); stroke-width:1; vector-effect:non-scaling-stroke; }
        .grid.zero { stroke:var(--secondary-text-color); stroke-opacity:.6; }
        .vgrid { stroke:var(--divider-color); stroke-opacity:.55; vector-effect:non-scaling-stroke; }
        .curve { fill:none; stroke:var(--primary-color); stroke-width:4; stroke-linecap:round; stroke-linejoin:round; vector-effect:non-scaling-stroke; }
        .area { fill:url(#fill); }
        .stem { stroke:var(--primary-color); stroke-width:3; stroke-opacity:.8; vector-effect:non-scaling-stroke; }
        .handle { fill:var(--primary-color); stroke:var(--card-background-color); stroke-width:3; cursor:grab; vector-effect:non-scaling-stroke; }
        .handle:active { cursor:grabbing; }
        text { user-select:none; pointer-events:none; }
        .axis,.band-label { fill:var(--secondary-text-color); font-size:12px; }
        .value { fill:var(--primary-text-color); font-size:12px; font-weight:600; }
        .footer { display:flex; align-items:center; gap:12px; justify-content:space-between; margin-top:4px; }
        .range { color:var(--secondary-text-color); font-size:12px; }
        button { border:0; border-radius:12px; padding:10px 16px; font-weight:600; cursor:pointer; }
        button.primary { background:var(--primary-color); color:var(--text-primary-color, white); }
        button.secondary { background:var(--secondary-background-color); color:var(--primary-text-color); }
        button:disabled { opacity:.45; cursor:default; }
        ${modal ? ".modal-card { box-shadow:none; border-radius:22px; padding-top:54px; }" : ""}
      </style>`;

    target.innerHTML = markup;
    this._bind(state, { top, plotH, globalMin, globalMax, minimums, maximums, step }, target);
  }

  _bind(state, graph, root = this.shadowRoot) {
    const chart = root.getElementById("chart");
    chart?.querySelectorAll(".handle").forEach((handle) => {
      handle.addEventListener("pointerdown", (ev) => {
        this._dragIndex = Number(handle.dataset.index);
        handle.setPointerCapture?.(ev.pointerId);
        ev.preventDefault();
      });
    });

    chart?.addEventListener("pointermove", (ev) => {
      if (this._dragIndex === null) return;
      const rect = chart.getBoundingClientRect();
      const svgY = ((ev.clientY - rect.top) / rect.height) * 280;
      const raw = graph.globalMax -
        ((svgY - graph.top) / graph.plotH) * (graph.globalMax - graph.globalMin);
      const i = this._dragIndex;
      const min = Number(graph.minimums[i]);
      const max = Number(graph.maximums[i]);
      const quantized = Math.round(raw / graph.step) * graph.step;
      this._draft[i] = Math.max(min, Math.min(max, quantized));
      this._dirty = true;
      this._render(state);
    });

    const stop = () => { this._dragIndex = null; };
    chart?.addEventListener("pointerup", stop);
    chart?.addEventListener("pointercancel", stop);
    chart?.addEventListener("pointerleave", (ev) => {
      if (ev.buttons === 0) stop();
    });

    root.getElementById("flat")?.addEventListener("click", () => {
      this._draft = this._draft.map(() => 0);
      this._dirty = true;
      this._render(state);
    });

    root.getElementById("apply")?.addEventListener("click", async () => {
      if (!this._dirty) return;
      await this._hass.callService("jbl_integration", "set_eq_curve", {
        entry_id: state.attributes.entry_id,
        gains: this._draft,
      });
      this._dirty = false;
    });

    root.getElementById("preset")?.addEventListener("change", async (ev) => {
      await this._hass.callService("jbl_integration", "set_eq_preset", {
        entry_id: state.attributes.entry_id,
        eq_id: ev.target.value,
      });
      this._dirty = false;
    });
  }

  _escape(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  getCardSize() {
    return 4;
  }
}

if (!customElements.get("jbl-equalizer-card")) {
  customElements.define("jbl-equalizer-card", JBLEqualizerCard);
}

window.customCards = window.customCards || [];
if (!window.customCards.some((card) => card.type === "jbl-equalizer-card")) {
  window.customCards.push({
    type: "jbl-equalizer-card",
    name: "JBL Equalizer Card",
    description: "Interactive JBL equalizer. Use mode: button for a compact launcher.",
    preview: true,
  });
}
