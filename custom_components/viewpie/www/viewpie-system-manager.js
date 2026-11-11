class ViewpieSystemManager extends HTMLElement {
  setConfig(config) {
    this._config = config || {};
    this._entryId = this._config.entry_id || "";
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    const states = Object.values(hass?.states || {});
    const belongsToEntry = state => !this._entryId ||
      state.entity_id.includes(this._entryId) ||
      String(state.attributes?.config_entry_id || "") === this._entryId;
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
      const state = states.find(item => item.entity_id.startsWith(domain) &&
        belongsToEntry(item) &&
        aliases.includes(normalize(item.attributes?.friendly_name || item.entity_id.split(".").pop().replace(/^viewpie_?/, "").replaceAll("_", " "))));
      return {label, state};
    });
    const buttons = states.filter(s => s.entity_id.startsWith("button.") && belongsToEntry(s));
    this._button = buttons.find(s =>
      normalize(s.attributes?.friendly_name) === normalize("Перезагрузить Raspberry Pi")) || null;
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
      .rows{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:0 16px}
      .row{display:contents}
      .name,.value{padding:8px 0;border-bottom:1px solid var(--divider-color)}
      .name{color:var(--primary-text-color)}
      .value{text-align:right;font-variant-numeric:tabular-nums;font-weight:500}
      .muted{color:var(--secondary-text-color);font-weight:400}
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
    for (const row of (this._rows || [])) {
      const name = document.createElement("div");
      name.className = "name";
      name.textContent = row.label;
      const value = document.createElement("div");
      value.className = "value" + (!row.state || ["unknown", "unavailable"].includes(row.state.state) ? " muted" : "");
      value.textContent = this._formatValue(row);
      rows.append(name, value);
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
