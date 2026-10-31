class ViewpieLayoutEditor extends HTMLElement {
  setConfig(config) {
    if (!config || typeof config !== "object") throw new Error("A card configuration object is required");
    this._config = config;
    this._entryId = config.entry_id || "";
    this._rows = this._clamp(config.rows ?? 2, 1, 8);
    this._cols = this._clamp(config.columns ?? 2, 1, 8);
    this._cells = this._cells || {};
    this._panelId = "";
    this._panelName = "";
    this._selectedPanel = "";
    this._status = "";
    this._error = false;
    this._render();
  }

  _clamp(value, min, max) {
    const n = Number(value);
    return Number.isFinite(n) ? Math.max(min, Math.min(max, Math.round(n))) : min;
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._loaded) {
      this._loaded = true;
      this._loadData();
    }
    this._render();
  }

  async _loadData() {
    if (!this._hass) return;
    try {
      const states = Object.values(this._hass.states || {});
      const suffix = this._entryId ? `_${this._entryId}` : "";
      const panelSelect = states.find(s => s.entity_id.startsWith("select.") && s.entity_id.endsWith("_panel") && s.attributes.options && (!this._entryId || s.entity_id.includes(this._entryId)));
      const cameraSelect = states.find(s => s.entity_id.startsWith("select.") && s.entity_id.endsWith("_fullscreen") && s.attributes.options && (!this._entryId || s.entity_id.includes(this._entryId)));
      this._panelSelectEntity = panelSelect?.entity_id || "";
      this._panelDetails = panelSelect?.attributes?.panel_details || {};
      this._panelOptions = panelSelect ? panelSelect.attributes.options.filter(x => x !== "Grid") : [];
      this._cameraOptions = cameraSelect ? cameraSelect.attributes.options.filter(x => x !== "Grid") : [];
      this._render();
    } catch (err) {
      this._status = "Не удалось получить список камер и панелей из Home Assistant.";
      this._error = true;
      this._render();
    }
  }

  _el(tag, attrs = {}, text = "") {
    const node = document.createElement(tag);
    Object.entries(attrs).forEach(([key, value]) => {
      if (key === "class") node.className = value;
      else if (key === "value") node.value = value;
      else node.setAttribute(key, value);
    });
    if (text !== "") node.textContent = text;
    return node;
  }

  _field(label, input) {
    const wrap = this._el("label", { class: "field" });
    wrap.append(this._el("span", {}, label), input);
    return wrap;
  }

  _render() {
    if (!this._config) return;
    const root = this.shadowRoot || this.attachShadow({ mode: "open" });
    root.replaceChildren();
    const style = this._el("style");
    style.textContent = `
      :host { display:block; }
      ha-card { padding:16px; }
      h2 { font-size:1.25rem; margin:0 0 12px; }
      .fields { display:grid; grid-template-columns:repeat(auto-fit,minmax(145px,1fr)); gap:12px; }
      .field { display:flex; flex-direction:column; gap:5px; font-size:.9rem; }
      input, select { box-sizing:border-box; width:100%; min-width:0; padding:9px; color:var(--primary-text-color); background:var(--card-background-color); border:1px solid var(--divider-color); border-radius:6px; }
      .grid { display:grid; gap:8px; margin:16px 0; }
      .cell { min-width:0; padding:8px; border:1px solid var(--divider-color); border-radius:8px; background:var(--secondary-background-color); }
      .cell small { display:block; margin-bottom:5px; color:var(--secondary-text-color); }
      button { border:0; border-radius:6px; padding:10px 14px; cursor:pointer; background:var(--primary-color); color:var(--text-primary-color,#fff); font-weight:600; }
      button[disabled] { opacity:.5; cursor:wait; }
      .muted { color:var(--secondary-text-color); font-size:.85rem; }
      .status { margin-top:12px; white-space:pre-wrap; }
      .error { color:var(--error-color); }
      .actions { display:flex; flex-wrap:wrap; gap:8px; }
    `;
    const card = this._el("ha-card");
    card.append(this._el("h2", {}, this._config.title || "Редактор раскладки Viewpie"));
    const fields = this._el("div", { class: "fields" });

    const existing = this._el("select");
    existing.append(this._el("option", { value: "" }, "Создать новую…"));
    (this._panelOptions || []).forEach(panelId => {
      const option = this._el("option", { value: panelId }, panelId);
      if (panelId === this._selectedPanel) option.selected = true;
      existing.append(option);
    });
    existing.value = this._selectedPanel || "";
    existing.addEventListener("change", () => this._loadPanelIntoEditor(existing.value));
    fields.append(this._field("Существующая панель", existing));

    const id = this._el("input", { value: this._panelId, placeholder: "например, yard_day" });
    id.value = this._panelId;
    id.disabled = Boolean(this._selectedPanel);
    id.addEventListener("input", () => { this._panelId = id.value; });
    fields.append(this._field("ID новой панели", id));

    const name = this._el("input", { value: this._panelName, placeholder: "Например, Двор" });
    name.value = this._panelName;
    name.addEventListener("input", () => { this._panelName = name.value; });
    fields.append(this._field("Название панели", name));

    const rows = this._numberInput(this._rows, 1, 8, value => { this._rows = value; this._render(); });
    fields.append(this._field("Строки", rows));
    const cols = this._numberInput(this._cols, 1, 8, value => { this._cols = value; this._render(); });
    fields.append(this._field("Столбцы", cols));
    card.append(fields);

    const grid = this._el("div", { class: "grid" });
    grid.style.gridTemplateColumns = `repeat(${this._cols}, minmax(0, 1fr))`;
    for (let r = 0; r < this._rows; r++) {
      for (let c = 0; c < this._cols; c++) {
        const key = `${r},${c}`;
        const cell = this._el("div", { class: "cell" });
        cell.append(this._el("small", {}, `Ячейка ${r + 1} × ${c + 1}`));
        const select = this._el("select");
        select.append(this._el("option", { value: "" }, "— пусто —"));
        (this._cameraOptions || []).forEach(camera => {
          const option = this._el("option", { value: camera }, camera);
          if ((this._cells[key] || "") === camera) option.selected = true;
          select.append(option);
        });
        select.value = this._cells[key] || "";
        select.addEventListener("change", () => { this._cells[key] = select.value; });
        cell.append(select);
        grid.append(cell);
      }
    }
    card.append(grid);
    const help = this._el("p", { class: "muted" },
      "Пустые ячейки разрешены. Создание добавляет новую панель через API Viewpie; существующие панели этот первый этап не изменяет.");
    card.append(help);
    const actions = this._el("div", { class: "actions" });
    const save = this._el("button", {}, this._selectedPanel ? "Сохранить изменения" : "Создать панель");
    save.addEventListener("click", () => this._savePanel(save));
    actions.append(save);
    const clear = this._el("button", {}, "Очистить сетку");
    clear.style.background = "var(--secondary-text-color)";
    clear.addEventListener("click", () => { this._cells = {}; this._render(); });
    actions.append(clear);
    card.append(actions);
    const status = this._el("div", { class: `status${this._error ? " error" : ""}` }, this._status);
    card.append(status);
    root.append(style, card);
  }

  _numberInput(value, min, max, callback) {
    const input = this._el("input", { type: "number", min: String(min), max: String(max), value: String(value) });
    input.value = String(value);
    input.addEventListener("change", () => callback(this._clamp(input.value, min, max)));
    return input;
  }

  _loadPanelIntoEditor(panelId) {
    this._selectedPanel = panelId || "";
    if (!panelId) {
      this._panelId = "";
      this._panelName = "";
      this._cells = {};
      this._rows = this._clamp(this._config.rows ?? 2, 1, 8);
      this._cols = this._clamp(this._config.columns ?? 2, 1, 8);
      this._status = "Режим создания новой панели.";
      this._error = false;
      this._render();
      return;
    }
    const panel = this._panelDetails?.[panelId];
    if (!panel) {
      this._status = "Детали панели пока недоступны. Обновите страницу или проверьте API Viewpie.";
      this._error = true;
      this._render();
      return;
    }
    const layout = String(panel.layout || "").split(/\\r?\\n/).map(row => row.trim()).filter(Boolean).map(row => row.split(/\\s+/));
    if (!layout.length || !layout[0].length) {
      this._status = "У панели неизвестный формат layout; редактирование не загружено, чтобы не испортить конфигурацию.";
      this._error = true;
      this._render();
      return;
    }
    const cols = Math.max(...layout.map(row => row.length));
    this._rows = this._clamp(layout.length, 1, 8);
    this._cols = this._clamp(cols, 1, 8);
    this._cells = {};
    const viewportMap = new Map();
    const sourceViewports = Array.isArray(panel.viewports) ? panel.viewports : [];
    if (sourceViewports.some(vp => Array.isArray(vp?.feeds) && vp.feeds.length > 1)) {
      this._status = "У панели есть ячейки с несколькими потоками. Этот редактор пока не поддерживает такой формат и не загрузил раскладку, чтобы не потерять данные.";
      this._error = true;
      this._render();
      return;
    }
    sourceViewports.forEach(vp => {
      if (vp && vp.slot) viewportMap.set(String(vp.slot), Array.isArray(vp.feeds) ? vp.feeds[0] || "" : "");
    });
    layout.slice(0, 8).forEach((row, r) => row.slice(0, 8).forEach((slot, c) => {
      const camera = viewportMap.get(String(slot));
      if (camera) this._cells[`${r},${c}`] = String(camera);
    }));
    this._panelId = panelId;
    this._panelName = String(panel.name || panelId);
    this._status = `Загружена панель «${this._panelName}». Проверьте ячейки перед сохранением.`;
    this._error = false;
    this._render();
  }

  async _savePanel(button) {
    const panelId = this._selectedPanel || (this._panelId || "").trim();
    const panelName = (this._panelName || "").trim();
    if (!panelId || !panelName) {
      this._status = "Укажите ID и название панели.";
      this._error = true;
      this._render();
      return;
    }
    if (!this._hass) return;
    button.disabled = true;
    this._status = this._selectedPanel ? "Сохраняю изменения панели…" : "Создаю панель…";
    this._error = false;
    this._render();
    try {
      const layoutRows = [];
      const viewports = [];
      for (let r = 0; r < this._rows; r++) {
        const slots = [];
        for (let c = 0; c < this._cols; c++) {
          const slot = `s${r}${c}`;
          slots.push(slot);
          const camera = this._cells[`${r},${c}`];
          if (camera) viewports.push({ slot, feeds: [camera] });
        }
        layoutRows.push(slots.join(" "));
      }
      const data = {
        operation: this._selectedPanel ? "update" : "create",
        panel_id: panelId,
        name: panelName,
        layout: layoutRows.join("\\n"),
        viewports
      };
      if (this._entryId) data.entry_id = this._entryId;
      await this._hass.callService("viewpie", "manage_panel", data);
      this._status = `Панель «${panelName}» сохранена в Viewpie.`;
      this._error = false;
      this._panelId = panelId;
      this._selectedPanel = panelId;
      this._panelDetails = this._panelDetails || {};
      this._panelDetails[panelId] = { id: panelId, name: panelName, layout: data.layout, viewports };
      this._panelOptions = [...new Set([...(this._panelOptions || []), panelId])];
    } catch (err) {
      this._status = `Не удалось сохранить панель: ${err?.message || err}`;
      this._error = true;
    } finally {
      this._render();
    }
  }

  getCardSize() { return Math.max(4, this._rows * 2 + 3); }

  static getConfigElement() { return document.createElement("viewpie-layout-editor-editor"); }
  static getStubConfig() { return { title: "Редактор раскладки Viewpie", rows: 2, columns: 2 }; }
}

if (!customElements.get("viewpie-layout-editor")) {
  customElements.define("viewpie-layout-editor", ViewpieLayoutEditor);
}

window.customCards = window.customCards || [];
if (!window.customCards.some(card => card.type === "viewpie-layout-editor")) {
  window.customCards.push({
    type: "viewpie-layout-editor",
    name: "Viewpie Layout Editor",
    description: "Создание новой раскладки камеры Viewpie из сетки"
  });
}
