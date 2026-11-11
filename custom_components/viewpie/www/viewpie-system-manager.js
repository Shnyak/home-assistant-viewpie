class ViewpieSystemManager extends HTMLElement {
  setConfig(config) {
    this._config = config || {};
    this._entryId = this._config.entry_id || "";
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    const states = Object.values(hass?.states || {});
    // Config-entry IDs are not exposed in hass.states. The integration adds
    // its own stable attribute so cards can safely scope multiple Viewpie devices.
    const belongsToEntry = state => !this._entryId ||
      String(state.attributes?.viewpie_entry_id || "") === this._entryId;
    const normalize = value => String(value || "")
      .toLocaleLowerCase()
      .replace(/^viewpie\s*/, "")
      .replace(/[^a-zа-яё0-9]+/giu, " ")
      .trim();
    const wanted = [
      ["Active panel", ["active panel"]],
      ["Active streams", ["active streams"]],
      ["CPU temperature", ["cpu temperature", "cpu temp"]],
      ["CPU usage", ["cpu usage", "cpu load"]],
      ["Decoder status", ["decoder status"]],
      ["Hardware decoders", ["hardware decoders"]],
      ["Load average (1m)", ["load average 1m"]],
      ["Paused", ["paused"]],
      ["Screen off", ["screen off"]],
      ["Software build date", ["software build date"]],
      ["Software decoders", ["software decoders"]],
      ["Software version", ["software version"]],
      ["Unknown decoder status", ["unknown decoder status"]],
      ["Uptime", ["uptime"]],
    ];
    this._rows = wanted.map(([label, aliases]) => {
      const domain = ["Paused", "Screen off"].includes(label) ? "binary_sensor." : "sensor.";
      const state = states.find(item => {
        if (!item.entity_id.startsWith(domain) || !belongsToEntry(item)) return false;
        const candidates = [
          item.attributes?.friendly_name,
          item.entity_id.split(".").pop().replace(/^viewpie_?/, "").replaceAll("_", " "),
        ].map(normalize);
        return aliases.some(alias => candidates.some(name =>
          name === alias || name.endsWith(` ${alias}`)
        ));
      });
      return {label, state};
    });
    const buttons = states.filter(s => s.entity_id.startsWith("button.") && belongsToEntry(s));
    const restartName = normalize("Перезагрузить Raspberry Pi");
    this._button = buttons.find(s => {
      const name = normalize(s.attributes?.friendly_name);
      return name === restartName || name.endsWith(` ${restartName}`);
    }) || null;
    this._render();
  }

  _formatValue(row) {
    const state = row.state;
    if (!state || ["unknown", "unavailable"].includes(state.state)) return "Неизвестно";
    if (row.label === "Paused" || row.label === "Screen off") {
      return state.state === "on" ? "Да" : "Нет";
    }
    const unit = state.attributes?.unit_of_measurement;
    return unit ? `${state.state} ${unit}` : state.state;
  }

  _render() {
    if (!this._config) return;
    const root = this.shadowRoot || this.attachShadow({mode:"open"});
    root.replaceChildren();
    const style = document.createElement("style");
    style.textContent = `
      :host{display:block}
      ha-card{padding:16px}
      h2{font-size:1.2rem;margin:0 0 14px}
      .section{font-size:.9rem;font-weight:600;color:var(--secondary-text-color);margin:14px 0 6px}
      .rows{display:flex;flex-direction:column}
      .row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:0 16px;align-items:center;
        width:100%;margin:0;padding:0;border:0;border-radius:0;border-bottom:1px solid var(--divider-color);
        background:transparent;color:inherit;font:inherit;text-align:left}
      .row:not(:disabled){cursor:pointer}
      .row:not(:disabled):hover{background:var(--secondary-background-color)}
      .row:focus-visible{outline:2px solid var(--primary-color);outline-offset:2px}
      .row:disabled{opacity:1;cursor:default}
      .name,.value{padding:9px 0}
      .name{color:var(--primary-text-color)}
      .value{text-align:right;font-variant-numeric:tabular-nums;font-weight:500}
      .muted{color:var(--secondary-text-color);font-weight:400}
      .row:not(:disabled) .value::after{content:"›";padding-left:8px;color:var(--secondary-text-color)}
      button{font:inherit;border:0;border-radius:8px;padding:11px 16px;background:var(--primary-color);
        color:var(--text-primary-color,#fff);cursor:pointer;width:100%;margin-top:16px}
      button:disabled{opacity:.55;cursor:default}
      .hint{margin-top:10px;color:var(--secondary-text-color);font-size:.88rem}
    `;
    const card = document.createElement("ha-card");
    const title = document.createElement("h2");
    title.textContent = this._config.title || "Управление системой";
    const section = document.createElement("div");
    section.className = "section";
    section.textContent = "Состояние системы";
    const rows = document.createElement("div");
    rows.className = "rows";
    for (const rowData of (this._rows || [])) {
      const row = document.createElement("button");
      row.type = "button";
      row.className = "row";
      row.disabled = !rowData.state;
      row.setAttribute("aria-label", `${rowData.label}: ${this._formatValue(rowData)}. Открыть историю`);
      const name = document.createElement("span");
      name.className = "name";
      name.textContent = rowData.label;
      const value = document.createElement("span");
      value.className = "value" + (!rowData.state || ["unknown", "unavailable"].includes(rowData.state.state) ? " muted" : "");
      value.textContent = this._formatValue(rowData);
      row.append(name, value);
      if (rowData.state) {
        row.addEventListener("click", () => {
          this.dispatchEvent(new CustomEvent("hass-more-info", {
            detail: {entityId: rowData.state.entity_id},
            bubbles: true,
            composed: true,
          }));
        });
      }
      rows.append(row);
    }

    const button = document.createElement("button");
    button.textContent = this._button ? "Перезагрузить Raspberry Pi" : "Кнопка перезагрузки недоступна";
    button.disabled = !this._button || this._button.state === "unavailable";
    button.addEventListener("click", async () => {
      if (!this._hass || !this._button) return;
      if (!window.confirm("Перезагрузить Raspberry Pi? Видеостена временно станет недоступна.")) return;
      button.disabled = true;
      try {
        await this._hass.callService("button", "press", {entity_id:this._button.entity_id});
      } catch (err) {
        window.alert("Не удалось отправить команду перезагрузки: " + (err?.message || err));
      } finally {
        button.disabled = false;
      }
    });
    const hint = document.createElement("div");
    hint.className = "hint";
    hint.textContent = this._button ? "Команда выполняется на Raspberry Pi." :
      "Задайте токен перезагрузки в параметрах интеграции и VIEWPIE_RESTART_TOKEN на Raspberry Pi.";
    card.append(title, section, rows, button, hint);
    root.append(style, card);
  }

  getCardSize() { return 7; }
  static getStubConfig() { return {title:"Управление системой"}; }
}
if (!customElements.get("viewpie-system-manager")) {
  customElements.define("viewpie-system-manager", ViewpieSystemManager);
}
window.customCards = window.customCards || [];
if (!window.customCards.some(card => card.type === "viewpie-system-manager")) {
  window.customCards.push({type:"viewpie-system-manager",name:"Viewpie — управление системой",description:"Состояние системы, сенсоры и перезагрузка Raspberry Pi"});
}
