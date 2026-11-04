class ViewpieCardConfigEditor extends HTMLElement {
  setConfig(config) {
    this._config = { ...config };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
  }

  _emit(key, value) {
    this._config = { ...this._config, [key]: value };
    this.dispatchEvent(new CustomEvent("config-changed", {
      detail: { config: this._config },
      bubbles: true,
      composed: true
    }));
  }

  _render() {
    if (!this._config) return;
    const root = this.shadowRoot || this.attachShadow({ mode: "open" });
    root.replaceChildren();
    const style = document.createElement("style");
    style.textContent = `
      .field{display:block;margin:12px 0}
      label{display:block;font-weight:500;margin-bottom:6px}
      input{box-sizing:border-box;width:100%;padding:9px;border:1px solid var(--divider-color);
        border-radius:6px;background:var(--card-background-color);color:var(--primary-text-color);font:inherit}
      .hint{color:var(--secondary-text-color);font-size:.85em;margin-top:5px}
    `;
    root.append(style);
    this._addTextField(root, "Заголовок карточки", "title", "Название, отображаемое над карточкой");
    this._addTextField(root, "ID устройства (необязательно)", "entry_id",
      "Нужно только если в Home Assistant настроено несколько устройств Viewpie");
    if (this._config.rows !== undefined) this._addNumberField(root, "Строки сетки по умолчанию", "rows", 1, 8);
    if (this._config.columns !== undefined) this._addNumberField(root, "Столбцы сетки по умолчанию", "columns", 1, 8);
  }

  _addTextField(root, labelText, key, hintText) {
    const wrap = document.createElement("div");
    wrap.className = "field";
    const label = document.createElement("label");
    label.textContent = labelText;
    const input = document.createElement("input");
    input.type = "text";
    input.value = this._config[key] || "";
    input.addEventListener("input", () => this._emit(key, input.value));
    const hint = document.createElement("div");
    hint.className = "hint";
    hint.textContent = hintText;
    wrap.append(label, input, hint);
    root.append(wrap);
  }

  _addNumberField(root, labelText, key, min, max) {
    const wrap = document.createElement("div");
    wrap.className = "field";
    const label = document.createElement("label");
    label.textContent = labelText;
    const input = document.createElement("input");
    input.type = "number";
    input.min = String(min);
    input.max = String(max);
    input.step = "1";
    input.value = String(this._config[key]);
    input.addEventListener("change", () => {
      const value = Math.max(min, Math.min(max, Number(input.value) || min));
      input.value = String(value);
      this._emit(key, value);
    });
    wrap.append(label, input);
    root.append(wrap);
  }
}

if (!customElements.get("viewpie-card-config-editor")) {
  customElements.define("viewpie-card-config-editor", ViewpieCardConfigEditor);
}
