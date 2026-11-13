class ViewpieViewSelector extends HTMLElement {
  setConfig(config) {
    if (!config || typeof config !== "object") throw new Error("A card configuration object is required");
    this._config = config;
    this._entryId = config.entry_id || "";
    this._hass = this._hass || null;
    this._panels = [];
    this._cameras = [];
    this._panelEntity = null;
    this._startupPanelEntity = null;
    this._fullscreenEntity = null;
    this._screenEntity = null;
    this._busy = false;
    this._status = "";
    this._refreshing = false;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    const states = Object.values(hass?.states || {});
    const fullscreen = states.find(s => s.entity_id.startsWith("select.") &&
      s.attributes?.icon === "mdi:fullscreen" && Array.isArray(s.attributes?.options));
    const panel = states.find(s => s.entity_id.startsWith("select.") &&
      s.attributes?.icon === "mdi:view-dashboard" && Array.isArray(s.attributes?.options));
    const startupPanel = states.find(s => s.entity_id.startsWith("select.") &&
      s.attributes?.icon === "mdi:home-map-marker" && Array.isArray(s.attributes?.options));
    // With has_entity_name enabled, HA composes friendly_name from the
    // device name and entity name (for example "Viewpie (host) Экран").
    // Match the dedicated screen switch by its stable icon/name instead of
    // requiring friendly_name to equal the bare word "Экран".
    const screenCandidates = states.filter(s => s.entity_id.startsWith("switch.") && (
        s.attributes?.icon === "mdi:pause-circle" ||
        String(s.attributes?.friendly_name || "").trim().toLowerCase().includes("экран") ||
        s.entity_id.endsWith("_pause")
      ));
    const screen = screenCandidates.sort((a, b) => {
      const score = s => (s.attributes?.icon === "mdi:pause-circle" ? 4 : 0) +
        (String(s.attributes?.friendly_name || "").trim().toLowerCase().includes("экран") ? 2 : 0) +
        (s.entity_id.endsWith("_pause") ? 1 : 0);
      return score(b) - score(a);
    })[0] || null;
    const signature = JSON.stringify([
      fullscreen?.entity_id, fullscreen?.attributes?.options, fullscreen?.state,
      panel?.entity_id, panel?.attributes?.options, panel?.state,
      panel?.attributes?.panel_details, startupPanel?.entity_id,
      startupPanel?.attributes?.options, startupPanel?.state, screen?.entity_id, screen?.state
    ]);
    if (signature !== this._signature) {
      this._signature = signature;
      this._fullscreenEntity = fullscreen || null;
      this._panelEntity = panel || null;
      this._startupPanelEntity = startupPanel || null;
      this._screenEntity = screen || null;
      this._entryId = this._config.entry_id ||
        panel?.attributes?.viewpie_entry_id ||
        startupPanel?.attributes?.viewpie_entry_id || "";
      this._panelDetails = panel?.attributes?.panel_details || {};
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

  _panelLabel(panelId) {
    const response = this._panelDetails?.[panelId];
    const panel = response?.panel || response;
    const name = typeof panel?.name === "string" ? panel.name.trim() : "";
    return name || panelId;
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

  async _toggleScreen() {
    if (this._busy || !this._hass || !this._screenEntity) return;
    this._busy = true;
    const turnOn = this._screenEntity.state !== "on";
    this._status = turnOn ? "Включаю экран…" : "Выключаю экран…";
    this._render();
    try {
      await this._hass.callService("switch", turnOn ? "turn_on" : "turn_off", {
        entity_id: this._screenEntity.entity_id
      });
      this._status = turnOn ? "Экран включён." : "Экран выключен.";
    } catch (err) {
      this._status = "Не удалось переключить экран: " + (err?.message || err);
    } finally {
      this._busy = false;
      this._render();
    }
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
      this._status = "Активна панель: " + this._panelLabel(panelId);
    } catch (err) {
      this._status = "Не удалось включить панель: " + (err?.message || err);
    } finally {
      this._busy = false;
      this._render();
    }
  }

  async _setStartupPanel(panelId) {
    if (this._busy || !this._hass || !this._startupPanelEntity) return;
    this._busy = true;
    this._status = "Сохраняю стартовую панель…";
    this._render();
    try {
      await this._callSelect(this._startupPanelEntity, panelId);
      this._status = "Стартовая панель: " + this._panelLabel(panelId);
    } catch (err) {
      this._status = "Не удалось сохранить стартовую панель: " + (err?.message || err);
    } finally {
      this._busy = false;
      this._render();
    }
  }

  async _movePanel(panelId, delta) {
    if (this._busy || !this._hass) return;
    const order = [...this._panels];
    const from = order.indexOf(panelId);
    const to = from + delta;
    if (from < 0 || to < 0 || to >= order.length) return;
    [order[from], order[to]] = [order[to], order[from]];
    this._busy = true;
    this._status = "Сохраняю порядок панелей…";
    this._render();
    try {
      const payload = {order};
      if (this._entryId) payload.entry_id = this._entryId;
      await this._hass.callService("viewpie", "reorder_panels", payload);
      const ids = [this._panelEntity?.entity_id, this._startupPanelEntity?.entity_id].filter(Boolean);
      if (ids.length) {
        await this._hass.callService("homeassistant", "update_entity", {entity_id: ids});
      }
      this._status = "Порядок панелей сохранён.";
    } catch (err) {
      this._status = "Не удалось изменить порядок панелей: " + (err?.message || err);
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
      .screen-control{margin:0 0 16px}
      .choice-list{display:grid;grid-template-rows:repeat(2,minmax(48px,auto));grid-auto-flow:column;grid-auto-columns:minmax(110px,1fr);gap:8px;overflow-x:auto;padding-bottom:3px}
      .choice-row{box-sizing:border-box;display:flex;align-items:center;justify-content:center;min-width:0;min-height:48px;width:100%;padding:7px;border:1px solid var(--divider-color);border-radius:9px;background:var(--secondary-background-color);color:var(--primary-text-color);font:600 clamp(11px,4cqi,16px)/1.15 inherit;text-align:center;overflow-wrap:anywhere;container-type:inline-size;cursor:pointer}
      .choice-row.active{background:var(--primary-color);border-color:var(--primary-color);color:var(--text-primary-color,#fff)}
      .choice-label{min-width:0;overflow-wrap:anywhere;text-align:center}
      .choice-label.active{font-weight:700;color:inherit}
      .panel-actions{display:none}
      .startup-select{width:100%;min-height:42px;padding:8px 10px;border:1px solid var(--divider-color);
        border-radius:8px;background:var(--card-background-color);color:var(--primary-text-color);font:inherit}
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
    const screenRow = this._el("div", {class: "choice-row screen-control"});
    screenRow.append(this._el("span", {class: "choice-label"}, "Экран"));
    const screenOn = this._screenEntity?.state === "on";
    const screenButton = this._el("button", {class: screenOn ? "active" : ""},
      this._screenEntity ? (screenOn ? "Включён" : "Выключен") : "Сущность не найдена");
    screenButton.disabled = this._busy || !this._screenEntity || this._screenEntity.state === "unavailable";
    screenButton.setAttribute("aria-pressed", String(screenOn));
    screenButton.addEventListener("click", () => this._toggleScreen());
    screenRow.append(screenButton);
    card.append(screenRow);
    card.append(this._el("h3", {}, "Панели"));
    const panels = this._el("div", {class: "choice-list"});
    const activePanel = this._activePanel();
    this._panels.forEach(id => {
      const active = id === activePanel;
      const button = this._el("button", {class: "choice-row" + (active ? " active" : "")}, this._panelLabel(id));
      button.type = "button";
      button.setAttribute("aria-pressed", String(active));
      button.disabled = this._busy || active;
      button.addEventListener("click", () => this._choosePanel(id));
      panels.append(button);
    });
    if (!this._panels.length) panels.append(this._el("span", {class: "muted"}, "Панели не найдены."));
    card.append(panels);

    card.append(this._el("h3", {}, "Панель при запуске"));
    if (this._startupPanelEntity && this._startupPanelEntity.state !== "unavailable") {
      const startupSelect = this._el("select", {class: "startup-select"});
      const startupOptions = this._startupPanelEntity.attributes?.options || this._panels;
      startupOptions.forEach(id => {
        const option = this._el("option", {value: id}, this._panelLabel(id));
        option.selected = id === this._startupPanelEntity.state;
        startupSelect.append(option);
      });
      startupSelect.value = this._startupPanelEntity.state || "";
      startupSelect.disabled = this._busy || !startupOptions.length;
      startupSelect.addEventListener("change", () => this._setStartupPanel(startupSelect.value));
      card.append(startupSelect);
    } else {
      card.append(this._el("div", {class: "muted"},
        "Настройка стартовой панели доступна после обновления Viewpie на Raspberry Pi."));
    }

    card.append(this._el("h3", {}, "Камеры"));
    const cameras = this._el("div", {class: "choice-list"});
    const activeCamera = this._activeCamera();
    this._cameras.forEach(name => {
      const active = name === activeCamera;
      const button = this._el("button", {class: "choice-row" + (active ? " active" : "")}, name);
      button.type = "button";
      button.setAttribute("aria-pressed", String(active));
      button.disabled = this._busy;
      button.addEventListener("click", () => this._chooseCamera(name));
      cameras.append(button);
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

  static getConfigElement() { return document.createElement("viewpie-card-config-editor"); }
  static getStubConfig() { return { title: "Выбор отображения" }; }
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
