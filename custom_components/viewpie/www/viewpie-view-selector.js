class ViewpieViewSelector extends HTMLElement {
  setConfig(config) {
    if (!config || typeof config !== "object") throw new Error("A card configuration object is required");
    this._config = config;
    this._entryId = config.entry_id || "";
    this._hass = this._hass || null;
    this._panels = [];
    this._cameras = [];
    this._panelEntity = null;
    this._fullscreenEntity = null;
    this._busy = false;
    this._status = "";
    this._refreshing = false;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    const states = Object.values(hass?.states || {});
    const matchesEntry = s => !this._entryId || s.entity_id.includes(this._entryId);
    const fullscreen = states.find(s => s.entity_id.startsWith("select.") &&
      s.entity_id.endsWith("_fullscreen_camera") && Array.isArray(s.attributes?.options) && matchesEntry(s));
    const panel = states.find(s => s.entity_id.startsWith("select.") &&
      s.entity_id.endsWith("_panel") && Array.isArray(s.attributes?.options) && matchesEntry(s));
    const signature = JSON.stringify([
      fullscreen?.entity_id, fullscreen?.attributes?.options, fullscreen?.state,
      panel?.entity_id, panel?.attributes?.options, panel?.state,
      panel?.attributes?.panel_details
    ]);
    if (signature !== this._signature) {
      this._signature = signature;
      this._fullscreenEntity = fullscreen || null;
      this._panelEntity = panel || null;
      this._cameras = fullscreen ? fullscreen.attributes.options.filter(x => x !== "Grid") : [];
      this._panels = panel ? panel.attributes.options : [];
      this._render();
    }
  }

  _el(tag, attrs = {}, value = "") {
    const node = document.createElement(tag);
    Object.entries(attrs).forEach(([key, val]) => {
      if (key === "class") node.className = val;
      else node.setAttribute(key, val);
    });
    if (value) node.textContent = value;
    return node;
  }

  _activeCamera() {
    const value = this._fullscreenEntity?.state;
    return value && value !== "Grid" ? value : null;
  }

  _activePanel() {
    return this._activeCamera() ? null : this._panelEntity?.state || null;
  }

  async _callSelect(entity, option) {
    if (!entity) throw new Error("Сущность управления не найдена");
    await this._hass.callService("select", "select_option", {
      entity_id: entity.entity_id,
      option
    });
  }

  async _choosePanel(panelId) {
    if (this._busy || !this._hass) return;
    this._busy = true;
    this._status = "Переключаю панель…";
    this._render();
    try {
      // The integration coordinator clears fullscreen mode before activating
      // the panel, so every caller (card, entity, or service) shares one rule.
      await this._callSelect(this._panelEntity, panelId);
      this._status = "Активна панель: " + panelId;
    } catch (err) {
      this._status = "Не удалось включить панель: " + (err?.message || err);
    } finally {
      this._busy = false;
      this._render();
    }
  }

  async _chooseCamera(camera) {
    if (this._busy || !this._hass) return;
    this._busy = true;
    const returningToPanel = this._activeCamera() === camera;
    this._status = returningToPanel ? "Возвращаюсь к активной панели…" : "Включаю камеру на весь экран…";
    this._render();
    try {
      await this._callSelect(this._fullscreenEntity, returningToPanel ? "Grid" : camera);
      this._status = returningToPanel ? "Полноэкранный режим выключен." : "Активна полноэкранная камера: " + camera;
    } catch (err) {
      this._status = "Не удалось включить камеру: " + (err?.message || err);
    } finally {
      this._busy = false;
      this._render();
    }
  }

  async _refresh() {
    if (this._refreshing || !this._hass) return;
    this._refreshing = true;
    this._status = "Обновляю списки камер и панелей…";
    this._render();
    try {
      const ids = [this._panelEntity?.entity_id, this._fullscreenEntity?.entity_id].filter(Boolean);
      if (!ids.length) throw new Error("Не найдены сущности Viewpie");
      await this._hass.callService("homeassistant", "update_entity", {entity_id: ids});
      this._status = "Списки обновлены.";
    } catch (err) {
      this._status = "Не удалось обновить списки: " + (err?.message || err);
    } finally {
      this._refreshing = false;
      this._render();
    }
  }

  _render() {
    if (!this._config) return;
    const root = this.shadowRoot || this.attachShadow({mode: "open"});
    root.replaceChildren();
    const style = this._el("style");
    style.textContent = `
      :host{display:block}ha-card{padding:16px}
      h2{font-size:1.2rem;margin:0 0 14px}
      h3{font-size:1rem;margin:18px 0 9px}
      .choice-list{display:flex;flex-direction:column;gap:7px}
      .choice-row{display:flex;align-items:center;justify-content:space-between;gap:12px;
        padding:8px 10px;border:1px solid var(--divider-color);border-radius:9px}
      .choice-label{min-width:0;overflow-wrap:anywhere}
      .choice-label.active{font-weight:600;color:var(--success-color,var(--primary-color))}
      button{flex:0 0 auto;font:inherit;border:1px solid var(--divider-color);border-radius:8px;padding:8px 13px;
        background:var(--secondary-background-color);color:var(--primary-text-color);cursor:pointer}
      button.active{background:var(--primary-color);border-color:var(--primary-color);color:var(--text-primary-color,#fff);font-weight:600}
      button:disabled{opacity:.65;cursor:default}
      .toolbar{display:flex;justify-content:flex-end;margin-top:16px}
      .refresh{background:var(--primary-color);color:var(--text-primary-color,#fff);border:0}
      .muted{color:var(--secondary-text-color);font-size:.88rem}
      .status{margin-top:12px;min-height:1.2em;font-size:.88rem;color:var(--secondary-text-color)}
      button:focus-visible{outline:2px solid var(--primary-color);outline-offset:2px}
    `;
    const card = this._el("ha-card");
    card.append(this._el("h2", {}, this._config.title || "Viewpie — выбор отображения"));
    card.append(this._el("h3", {}, "Панели"));
    const panels = this._el("div", {class: "choice-list"});
    const activePanel = this._activePanel();
    this._panels.forEach(id => {
      const active = id === activePanel;
      const row = this._el("div", {class: "choice-row"});
      row.append(this._el("span", {class: "choice-label" + (active ? " active" : "")}, id));
      const button = this._el("button", {class: active ? "active" : ""}, active ? "Активна" : "Переключить");
      button.setAttribute("aria-pressed", String(active));
      button.disabled = this._busy || active;
      button.addEventListener("click", () => this._choosePanel(id));
      row.append(button);
      panels.append(row);
    });
    if (!this._panels.length) panels.append(this._el("span", {class: "muted"}, "Панели не найдены."));
    card.append(panels);

    card.append(this._el("h3", {}, "Камеры"));
    const cameras = this._el("div", {class: "choice-list"});
    const activeCamera = this._activeCamera();
    this._cameras.forEach(name => {
      const active = name === activeCamera;
      const row = this._el("div", {class: "choice-row"});
      row.append(this._el("span", {class: "choice-label" + (active ? " active" : "")}, name));
      const button = this._el("button", {class: active ? "active" : ""}, active ? "Вернуться к панели" : "Переключить");
      button.setAttribute("aria-pressed", String(active));
      button.disabled = this._busy;
      button.addEventListener("click", () => this._chooseCamera(name));
      row.append(button);
      cameras.append(row);
    });
    if (!this._cameras.length) cameras.append(this._el("span", {class: "muted"}, "Камеры не найдены."));
    card.append(cameras);

    const toolbar = this._el("div", {class: "toolbar"});
    const refresh = this._el("button", {class: "refresh"}, this._refreshing ? "Обновление…" : "Обновить");
    refresh.disabled = this._busy || this._refreshing;
    refresh.addEventListener("click", () => this._refresh());
    toolbar.append(refresh);
    card.append(toolbar);
    card.append(this._el("div", {class: "status", role: "status"}, this._status));
    root.append(style, card);
  }

  getCardSize() { return 3; }
}

if (!customElements.get("viewpie-view-selector")) {
  customElements.define("viewpie-view-selector", ViewpieViewSelector);
}
window.customCards = window.customCards || [];
if (!window.customCards.some(card => card.type === "viewpie-view-selector")) {
  window.customCards.push({
    type: "viewpie-view-selector",
    name: "Viewpie — выбор отображения",
    description: "Отдельное переключение всех панелей и полноэкранных камер"
  });
}
