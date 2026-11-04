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
    const signature = this._getDataSignature(hass);
    if (!this._loaded || signature !== this._dataSignature) {
      this._loaded = true;
      this._dataSignature = signature;
      this._loadData();
    }
  }

  _getDataSignature(hass) {
    const states = Object.values(hass?.states || {});
    const panel = states.find(s =>
      s.entity_id.startsWith("select.") &&
      s.entity_id.endsWith("_panel") &&
      s.attributes?.options &&
      (!this._entryId || s.entity_id.includes(this._entryId))
    );
    const camera = states.find(s =>
      s.entity_id.startsWith("select.") &&
      s.entity_id.endsWith("_fullscreen_camera") &&
      s.attributes?.options &&
      (!this._entryId || s.entity_id.includes(this._entryId))
    );
    return JSON.stringify([
      panel?.entity_id, panel?.state, panel?.attributes?.options,
      panel?.attributes?.panel_details,
      camera?.entity_id, camera?.state, camera?.attributes?.options
    ]);
  }

  _loadData() {
    if (!this._hass) return;
    try {
      const states = Object.values(this._hass.states || {});
      const panelSelect = states.find(s =>
        s.entity_id.startsWith("select.") &&
        s.entity_id.endsWith("_panel") &&
        s.attributes?.options &&
        (!this._entryId || s.entity_id.includes(this._entryId))
      );
      const cameraSelect = states.find(s =>
        s.entity_id.startsWith("select.") &&
        s.entity_id.endsWith("_fullscreen_camera") &&
        s.attributes?.options &&
        (!this._entryId || s.entity_id.includes(this._entryId))
      );
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
      const option = this._el("option", { value: panelId }, this._panelLabel(panelId));
      if (panelId === this._selectedPanel) option.selected = true;
      existing.append(option);
    });
    existing.value = this._selectedPanel || "";
    existing.addEventListener("change", () => this._loadPanelIntoEditor(existing.value));
    fields.append(this._field("Существующая панель", existing));

    const name = this._el("input", { value: this._panelName, placeholder: "Например, Двор" });
    name.value = this._panelName;
    const idPreview = this._el("div", { class: "muted" },
      this._selectedPanel
        ? "Технический ID: " + this._panelId
        : "ID будет создан автоматически: " + this._generatePanelId(this._panelName || "panel"));
    name.addEventListener("input", () => {
      this._panelName = name.value;
      if (!this._selectedPanel) {
        idPreview.textContent = "ID будет создан автоматически: " + this._generatePanelId(this._panelName || "panel");
      }
    });
    fields.append(this._field("Название панели", name));
    fields.append(this._field("Технический ID", idPreview));

    const size = this._numberInput(this._rows, 1, 8, value => {
      this._rows = value;
      this._cols = value;
      this._render();
    });
    fields.append(this._field("Размер квадратной сетки", size));
    card.append(fields);

    const grid = this._el("div", { class: "grid" });
    grid.style.gridTemplateColumns = `repeat(${this._cols}, minmax(0, 1fr))`;
    for (let r = 0; r < this._rows; r++) {
      for (let c = 0; c < this._cols; c++) {
        const key = `${r},${c}`;
        const cell = this._el("div", { class: "cell" });
        cell.append(this._el("small", {}, `Ячейка ${r + 1} × ${c + 1}`));
        const select = this._el("select");
        select.title = "Выберите одну камеру для этой ячейки. Одну и ту же камеру можно использовать в разных ячейках.";
        select.append(this._el("option", { value: "" }, "— не выбрана —"));
        const selectedCamera = Array.isArray(this._cells[key]) ? this._cells[key][0] : this._cells[key];
        (this._cameraOptions || []).forEach(camera => {
          const option = this._el("option", { value: camera }, this._cameraPlacementLabel(camera));
          select.append(option);
        });
        select.value = selectedCamera || "";
        select.addEventListener("change", () => {
          this._cells[key] = select.value;
        });
        cell.append(select);
        cell.append(this._el("small", {}, "Одна камера на ячейку; одну камеру разрешено повторять в других ячейках."));
        grid.append(cell);
      }
    }
    card.append(grid);

    const previewTitle = this._el("h3", {}, "Предпросмотр раскладки до сохранения");
    previewTitle.style.margin = "20px 0 8px";
    card.append(previewTitle);
    const preview = this._el("div", { class: "preview-grid" });
    preview.style.display = "grid";
    preview.style.gridTemplateColumns = `repeat(${this._cols}, minmax(0, 1fr))`;
    preview.style.gap = "4px";
    preview.style.padding = "4px";
    preview.style.border = "1px solid var(--divider-color)";
    preview.style.borderRadius = "8px";
    preview.style.background = "var(--primary-background-color)";
    let regions = [];
    this._previewError = "";
    try { regions = this._getCameraRegions(); }
    catch (err) { this._previewError = err.message || String(err); }
    const covered = new Set();
    for (const region of regions) {
      const previewCell = this._makePreviewCell(region.camera);
      previewCell.style.gridRow = `${region.top + 1} / ${region.bottom + 2}`;
      previewCell.style.gridColumn = `${region.left + 1} / ${region.right + 2}`;
      preview.append(previewCell);
      region.cells.forEach(cell => covered.add(cell));
    }
    for (let r = 0; r < this._rows; r++) {
      for (let c = 0; c < this._cols; c++) {
        if (covered.has(`${r},${c}`)) continue;
        const raw = this._cells[`${r},${c}`];
        const camera = Array.isArray(raw) ? (raw[0] || "") : (raw || "");
        const empty = this._makePreviewCell(camera);
        empty.style.gridRow = String(r + 1);
        empty.style.gridColumn = String(c + 1);
        preview.append(empty);
      }
    }
    card.append(preview);
    if (this._previewError) {
      const warning = this._el("p", { class: "muted error" }, this._previewError);
      card.append(warning);
    }
    const help = this._el("p", { class: "muted" },
      "Сетка всегда квадратная (от 1×1 до 8×8). Соседние ячейки одной камеры объединяются только в квадратный viewport (2×2, 3×3 и т. д.). Пустые ячейки допустимы.");
    card.append(help);
    const actions = this._el("div", { class: "actions" });
    const save = this._el("button", {}, this._selectedPanel ? "Сохранить изменения" : "Создать панель");
    save.addEventListener("click", () => this._savePanel(save));
    actions.append(save);
    const clear = this._el("button", {}, "Очистить сетку");
    clear.style.background = "var(--secondary-text-color)";
    clear.addEventListener("click", () => { this._cells = {}; this._render(); });
    actions.append(clear);
    if (this._selectedPanel) {
      const remove = this._el("button", {}, "Удалить панель");
      remove.style.background = "var(--error-color)";
      remove.addEventListener("click", () => this._deletePanel(remove));
      actions.append(remove);
    }
    card.append(actions);
    const status = this._el("div", { class: `status${this._error ? " error" : ""}` }, this._status);
    card.append(status);
    root.append(style, card);
  }

  _makePreviewCell(camera) {
    const cell = this._el("div", { class: "preview-cell" });
    Object.assign(cell.style, {
      minHeight: "72px", minWidth: "0", padding: "8px", boxSizing: "border-box",
      border: "1px solid var(--divider-color)", borderRadius: "5px",
      background: "var(--card-background-color)", display: "flex",
      flexDirection: "column", justifyContent: "center", textAlign: "center",
      overflowWrap: "anywhere"
    });
    const label = this._el(camera ? "strong" : "span", {}, camera || "Пусто");
    label.style.fontSize = ".85rem";
    if (!camera) label.style.color = "var(--secondary-text-color)";
    cell.append(label);
    return cell;
  }

  _getCameraRegions() {
    const values = Array.from({ length: this._rows }, (_, r) =>
      Array.from({ length: this._cols }, (_, c) => {
        const value = this._cells[`${r},${c}`];
        return Array.isArray(value) ? (value[0] || "") : (value || "");
      })
    );
    const visited = new Set();
    const regions = [];
    for (let r = 0; r < this._rows; r++) for (let c = 0; c < this._cols; c++) {
      const camera = values[r][c], key = `${r},${c}`;
      if (!camera || visited.has(key)) continue;
      const queue = [[r, c]], cells = [];
      visited.add(key);
      while (queue.length) {
        const [y, x] = queue.shift();
        cells.push(`${y},${x}`);
        for (const [ny, nx] of [[y-1,x],[y+1,x],[y,x-1],[y,x+1]]) {
          const next = `${ny},${nx}`;
          if (ny >= 0 && ny < this._rows && nx >= 0 && nx < this._cols &&
              values[ny][nx] === camera && !visited.has(next)) {
            visited.add(next); queue.push([ny, nx]);
          }
        }
      }
      const coords = cells.map(value => value.split(",").map(Number));
      const top = Math.min(...coords.map(v => v[0]));
      const bottom = Math.max(...coords.map(v => v[0]));
      const left = Math.min(...coords.map(v => v[1]));
      const right = Math.max(...coords.map(v => v[1]));
      const height = bottom - top + 1;
      const width = right - left + 1;
      const area = height * width;
      if (area !== cells.length) {
        throw new Error(`Ячейки камеры «${camera}» должны образовывать один сплошной прямоугольник. Исправьте Г-образную или разорванную область.`);
      }
      if (cells.length > 1 && height !== width) {
        throw new Error('Область камеры «' + camera + '» должна быть квадратной (2×2, 3×3 и т. д.). Прямоугольные объединения запрещены.');
      }
      regions.push({ camera, cells, top, bottom, left, right });
    }
    return regions;
  }

  _cameraPlacementLabel(camera) {
    const placements = [];
    const details = this._panelDetails || {};
    for (const [panelId, response] of Object.entries(details)) {
      // GET /api/panels/{id} returns { id, panel: { layout, viewports, name } }.
      const panel = response?.panel || response;
      const rows = String(panel?.layout || "").trim().split(/\r?\n/).filter(Boolean)
        .map(row => row.trim().split(/\s+/));
      const viewports = Array.isArray(panel?.viewports) ? panel.viewports : [];
      for (const viewport of viewports) {
        if (!(viewport?.feeds || []).includes(camera)) continue;
        for (let r = 0; r < rows.length; r++) {
          for (let col = 0; col < rows[r].length; col++) {
            if (rows[r][col] === viewport.slot) placements.push(`${this._panelLabel(panelId)} · ${r + 1}×${col + 1}`);
          }
        }
      }
    }
    return placements.length ? `${camera} — ${placements.join(", ")}` : `${camera} — не назначена`;
  }

  _panelLabel(panelId) {
    const response = this._panelDetails?.[panelId];
    const panel = response?.panel || response;
    const name = typeof panel?.name === "string" ? panel.name.trim() : "";
    return name || panelId;
  }

  _slugifyPanelName(value) {
    const transliteration = {
      а:"a", б:"b", в:"v", г:"g", д:"d", е:"e", ё:"yo", ж:"zh", з:"z",
      и:"i", й:"y", к:"k", л:"l", м:"m", н:"n", о:"o", п:"p", р:"r",
      с:"s", т:"t", у:"u", ф:"f", х:"kh", ц:"ts", ч:"ch", ш:"sh",
      щ:"shch", ъ:"", ы:"y", ь:"", э:"e", ю:"yu", я:"ya"
    };
    const transliterated = Array.from(String(value || "").toLowerCase())
      .map(char => transliteration[char] ?? char)
      .join("")
      .normalize("NFKD")
      .replace(/[\u0300-\u036f]/g, "");
    return transliterated.replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || "panel";
  }

  _generatePanelId(name) {
    const base = this._slugifyPanelName(name);
    const used = new Set(this._panelOptions || []);
    if (!used.has(base)) return base;
    let suffix = 2;
    while (used.has(base + "-" + suffix)) suffix++;
    return base + "-" + suffix;
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
    const response = this._panelDetails?.[panelId];
    const panel = response?.panel || response;
    if (!panel) {
      this._status = "Детали панели пока недоступны. Обновите страницу или проверьте API Viewpie.";
      this._error = true;
      this._render();
      return;
    }
    const layout = String(panel.layout || "").split(/\r?\n/).map(row => row.trim()).filter(Boolean).map(row => row.split(/\s+/));
    if (!layout.length || !layout[0].length) {
      this._status = "У панели неизвестный формат layout; редактирование не загружено, чтобы не испортить конфигурацию.";
      this._error = true;
      this._render();
      return;
    }
    const cols = Math.max(...layout.map(row => row.length));
    if (layout.length !== cols || layout.some(row => row.length !== cols)) {
      this._status = "Эта панель имеет прямоугольную или неполную сетку. Редактор поддерживает только квадратные сетки; исходная панель не изменена.";
      this._error = true;
      this._render();
      return;
    }
    this._rows = this._clamp(layout.length, 1, 8);
    this._cols = this._clamp(cols, 1, 8);
    this._cells = {};
    const viewportMap = new Map();
    const sourceViewports = Array.isArray(panel.viewports) ? panel.viewports : [];
    sourceViewports.forEach(vp => {
      if (vp && vp.slot) {
        const feeds = Array.isArray(vp.feeds) ? vp.feeds : [];
        viewportMap.set(String(vp.slot), feeds.map(feed =>
          typeof feed === "string" ? feed : (feed && typeof feed === "object" ? String(feed.name || feed.id || "") : "")
        ).filter(Boolean));
      }
    });
    layout.slice(0, 8).forEach((row, r) => row.slice(0, 8).forEach((slot, c) => {
      const camera = viewportMap.get(String(slot));
      if (Array.isArray(camera) && camera.length) this._cells[`${r},${c}`] = camera[0];
    }));
    this._panelId = panelId;
    this._panelName = String(panel.name || panelId);
    const hasMultiFeedCell = sourceViewports.some(vp => Array.isArray(vp?.feeds) && vp.feeds.length > 1);
    this._status = hasMultiFeedCell
      ? `Загружена панель «${this._panelName}». В ячейках с несколькими камерами оставлена первая; при сохранении остальные будут удалены.`
      : `Загружена панель «${this._panelName}». Проверьте ячейки перед сохранением.`;
    this._error = false;
    this._render();
  }

  async _savePanel(button) {
    const panelName = (this._panelName || "").trim();
    const panelId = this._selectedPanel || this._generatePanelId(panelName);
    if (!panelName) {
      this._status = "Укажите название панели.";
      this._error = true; this._render(); return;
    }
    if (!this._hass) return;
    let regions;
    try { regions = this._getCameraRegions(); }
    catch (err) { this._status = err.message || String(err); this._error = true; this._render(); return; }
    button.disabled = true;
    this._status = this._selectedPanel ? "Сохраняю изменения панели…" : "Создаю панель…";
    this._error = false; this._render();
    try {
      const matrix = Array.from({ length: this._rows }, () => Array(this._cols).fill("."));
      const viewports = [];
      regions.forEach((region, index) => {
        const slot = `s${index}`;
        region.cells.forEach(cell => {
          const [r, c] = cell.split(",").map(Number);
          matrix[r][c] = slot;
        });
        viewports.push({ slot, feeds: [region.camera] });
      });
      const data = {
        operation: this._selectedPanel ? "update" : "create",
        panel_id: panelId, name: panelName,
        layout: matrix.map(row => row.join(" ")).join("\n"), viewports
      };
      if (this._entryId) data.entry_id = this._entryId;
      await this._hass.callService("viewpie", "manage_panel", data);
      this._status = `Панель «${panelName}» сохранена. Reload config выполнен.`;
      this._error = false;
      this._panelId = panelId; this._selectedPanel = panelId;
      this._panelDetails = this._panelDetails || {};
      this._panelDetails[panelId] = { id: panelId, panel: { name: panelName, layout: data.layout, viewports } };
      this._panelOptions = [...new Set([...(this._panelOptions || []), panelId])];
    } catch (err) {
      this._status = `Не удалось сохранить панель: ${err?.message || err}`;
      this._error = true;
    } finally { this._render(); }
  }

  async _deletePanel(button) {
    const panelId = this._selectedPanel;
    if (!panelId || !this._hass) return;
    const panelName = this._panelName || panelId;
    if (!window.confirm("Удалить панель «" + panelName + "» (" + panelId + ") из Viewpie? Это действие нельзя отменить.")) return;
    button.disabled = true;
    this._status = "Удаляю панель «" + panelName + "»…";
    this._error = false;
    this._render();
    try {
      const data = { operation: "delete", panel_id: panelId };
      if (this._entryId) data.entry_id = this._entryId;
      await this._hass.callService("viewpie", "manage_panel", data);
      this._panelOptions = (this._panelOptions || []).filter(id => id !== panelId);
      if (this._panelDetails) delete this._panelDetails[panelId];
      this._selectedPanel = "";
      this._panelId = "";
      this._panelName = "";
      this._cells = {};
      this._rows = this._clamp(this._config.rows ?? 2, 1, 8);
      this._cols = this._clamp(this._config.columns ?? 2, 1, 8);
      this._status = "Панель «" + panelName + "» удалена.";
      this._error = false;
    } catch (err) {
      this._status = "Не удалось удалить панель: " + (err?.message || err);
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
