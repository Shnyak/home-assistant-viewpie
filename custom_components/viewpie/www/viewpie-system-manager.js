class ViewpieSystemManager extends HTMLElement {
  setConfig(config) {
    this._config = config || {};
    this._entryId = this._config.entry_id || "";
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    const states = Object.values(hass?.states || {});
    const candidates = states.filter(s => s.entity_id.startsWith("button.") &&
      String(s.attributes?.friendly_name || "").trim() === "Перезагрузить Raspberry Pi" &&
      (!this._entryId || s.entity_id.includes(this._entryId)));
    this._button = candidates[0] || null;
    this._render();
  }

  _render() {
    if (!this._config) return;
    const root = this.shadowRoot || this.attachShadow({mode:"open"});
    root.replaceChildren();
    const style = document.createElement("style");
    style.textContent = `:host{display:block}ha-card{padding:16px}h2{font-size:1.2rem;margin:0 0 14px}
      button{font:inherit;border:0;border-radius:8px;padding:11px 16px;background:var(--primary-color);
      color:var(--text-primary-color,#fff);cursor:pointer;width:100%}
      button:disabled{opacity:.55;cursor:default}.hint{margin-top:10px;color:var(--secondary-text-color);font-size:.88rem}`;
    const card = document.createElement("ha-card");
    const title = document.createElement("h2");
    title.textContent = this._config.title || "Управление";
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
      "Настройте ключ API в параметрах интеграции и секрет VIEWPIE_RESTART_TOKEN на Raspberry Pi.";
    card.append(title, button, hint);
    root.append(style, card);
  }

  getCardSize() { return 2; }
  static getStubConfig() { return {title:"Управление"}; }
}
if (!customElements.get("viewpie-system-manager")) {
  customElements.define("viewpie-system-manager", ViewpieSystemManager);
}
window.customCards = window.customCards || [];
if (!window.customCards.some(card => card.type === "viewpie-system-manager")) {
  window.customCards.push({type:"viewpie-system-manager",name:"Viewpie — управление",description:"Управление системой и перезагрузка Raspberry Pi"});
}
