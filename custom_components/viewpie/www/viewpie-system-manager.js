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
      ["Latest version", ["latest version"]],
      ["Update available", ["update available"]],
      ["Update process", ["update process"]],
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
    this._checkUpdateButton = buttons.find(s => normalize(s.attributes?.friendly_name).endsWith(normalize("Проверить обновления Viewpie"))) || null;
    this._installUpdateButton = buttons.find(s => normalize(s.attributes?.friendly_name).endsWith(normalize("Установить обновление Viewpie"))) || null;
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
    const previousLog = root.querySelector(".terminal pre");
    const previousScrollTop = previousLog?.scrollTop || 0;
    const wasAtBottom = !previousLog ||
      previousLog.scrollHeight - previousLog.scrollTop - previousLog.clientHeight < 24;
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
      .terminal{margin-top:12px;border:1px solid var(--divider-color);border-radius:10px;overflow:hidden;background:#101418;color:#d8e2dc}
      .terminal-head{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:9px 11px;background:#20282e;font-size:.82rem}
      .terminal-state{font-weight:600}
      .terminal pre{margin:0;padding:12px;max-height:300px;overflow:auto;white-space:pre-wrap;overflow-wrap:anywhere;
        font:12px/1.5 ui-monospace,SFMono-Regular,Consolas,monospace;color:#d8e2dc}
      .terminal .copy{width:auto;margin:0;padding:6px 10px;background:#39464e;color:#fff;font-size:.8rem}
      .progress-track{height:4px;background:#39464e}
      .progress-fill{height:4px;background:#69b783;transition:width .25s ease}
      .terminal-empty{color:#aeb9b3}
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
    const updateSection = document.createElement("div");
    updateSection.className = "section";
    updateSection.textContent = "Обновление Viewpie";
    const updateActions = document.createElement("div");
    updateActions.style.display = "grid";
    updateActions.style.gap = "8px";

    const checkButton = document.createElement("button");
    checkButton.textContent = "Проверить обновления";
    checkButton.disabled = !this._checkUpdateButton || this._checkUpdateButton.state === "unavailable";
    checkButton.addEventListener("click", async () => {
      if (!this._hass || !this._checkUpdateButton) return;
      checkButton.disabled = true;
      updateHint.textContent = "Проверяем наличие обновлений на GitHub…";
      try {
        await this._hass.callService("button", "press", {entity_id:this._checkUpdateButton.entity_id});
      } catch (err) {
        window.alert("Не удалось проверить обновления: " + (err?.message || err));
      } finally {
        checkButton.disabled = false;
      }
    });

    const installButton = document.createElement("button");
    installButton.textContent = "Установить обновление";
    installButton.disabled = !this._installUpdateButton || this._installUpdateButton.state === "unavailable";
    installButton.addEventListener("click", async () => {
      if (!this._hass || !this._installUpdateButton) return;
      if (!window.confirm("Установить последнюю проверенную версию Viewpie? Видеостена временно перезапустится.")) return;
      installButton.disabled = true;
      try {
        await this._hass.callService("button", "press", {entity_id:this._installUpdateButton.entity_id});
        window.alert("Команда обновления принята. После установки проверьте версию Viewpie.");
      } catch (err) {
        window.alert("Не удалось запустить обновление: " + (err?.message || err));
      } finally {
        installButton.disabled = false;
      }
    });
    updateActions.append(checkButton, installButton);
    const updateHint = document.createElement("div");
    updateHint.className = "hint";
    const updateAvailable = this._rows?.find(row => row.label === "Update available")?.state?.state;
    const latestVersion = this._rows?.find(row => row.label === "Latest version")?.state?.state;
    const updateAttrs = this._rows?.find(row => row.label === "Update available")?.state?.attributes || {};
    if (updateAvailable === "Нет") {
      updateHint.textContent = `Обновлений нет. Установлена последняя версия Viewpie ${updateAttrs.installed_version || latestVersion || ""}.`;
    } else if (updateAvailable === "Да") {
      updateHint.textContent = this._installUpdateButton?.state === "unavailable"
        ? `Доступна версия ${latestVersion || updateAttrs.latest_version || ""}, но установка пока недоступна: проверьте наличие пакета, SHA-256 и токена обновления.`
        : `Доступно обновление Viewpie до версии ${latestVersion || updateAttrs.latest_version || ""}. Пакет и контрольная сумма проверяются перед установкой.`;
    } else if (updateAvailable === "Ошибка проверки") {
      updateHint.textContent = `Не удалось проверить обновления: ${updateAttrs.check_message || "ошибка соединения с GitHub"}. Попробуйте ещё раз.`;
    } else if (updateAvailable === "Неизвестно") {
      updateHint.textContent = "Не удалось получить состояние обновлений. Проверьте соединение с Viewpie.";
    } else {
      updateHint.textContent = "Проверка ещё не выполнялась. Нажмите «Проверить обновления», чтобы получить актуальный результат.";
    }

    const journalEntity = this._rows?.find(row => row.label === "Update process")?.state;
    const journal = journalEntity?.attributes || {};
    const terminal = document.createElement("section");
    terminal.className = "terminal";
    const terminalHead = document.createElement("div");
    terminalHead.className = "terminal-head";
    const terminalState = document.createElement("span");
    terminalState.className = "terminal-state";
    const progressValue = journal.progress_percent !== null && journal.progress_percent !== undefined && Number.isFinite(Number(journal.progress_percent))
      ? Math.max(0, Math.min(100, Number(journal.progress_percent))) : null;
    const progress = progressValue !== null ? ` — ${progressValue}%` : "";
    terminalState.textContent = journal.status === "running"
      ? `● Выполняется: ${journal.phase || "подготовка"}${progress}`
      : journal.status === "failed"
        ? `● Ошибка: ${journal.phase || "этап неизвестен"}`
        : journal.status === "success"
          ? "● Обновление завершено"
          : "● Журнал обновления";
    const copyLog = document.createElement("button");
    copyLog.type = "button";
    copyLog.className = "copy";
    copyLog.textContent = "Копировать журнал";
    copyLog.addEventListener("click", async () => {
      const report = [
        "Viewpie update diagnostic report",
        `status: ${journal.status || "unknown"}`,
        `phase: ${journal.phase || "unknown"}`,
        `message: ${journal.message || ""}`,
        `error: ${journal.error || ""}`,
        `version: ${journal.version || ""}`,
        `architecture: ${journal.architecture || ""}`,
        `started_at: ${journal.started_at || ""}`,
        `updated_at: ${journal.updated_at || ""}`,
        `finished_at: ${journal.finished_at || ""}`,
        `exit_code: ${journal.exit_code ?? ""}`,
        "",
        "----- journal -----",
        journal.log || "Журнал пока пуст.",
      ].join("\n");
      try {
        let copied = false;
        if (navigator.clipboard?.writeText) {
          try {
            await navigator.clipboard.writeText(report);
            copied = true;
          } catch (_) {
            // Continue with the legacy selection-based fallback below.
          }
        }
        if (!copied) {
          const fallback = document.createElement("textarea");
          fallback.value = report;
          fallback.setAttribute("readonly", "");
          fallback.style.position = "fixed";
          fallback.style.opacity = "0";
          document.body.appendChild(fallback);
          fallback.select();
          copied = document.execCommand("copy");
          fallback.remove();
        }
        if (!copied) throw new Error("Clipboard is unavailable");
        copyLog.textContent = "Скопировано";
      } catch (err) {
        copyLog.textContent = "Не удалось скопировать";
        window.alert("Браузер не разрешил копирование. Откройте атрибут log датчика Update process и скопируйте его вручную.");
      }
    });
    terminalHead.append(terminalState, copyLog);
    if (progressValue !== null) {
      const progressTrack = document.createElement("div");
      progressTrack.className = "progress-track";
      const progressFill = document.createElement("div");
      progressFill.className = "progress-fill";
      progressFill.style.width = `${progressValue}%`;
      progressTrack.append(progressFill);
      terminal.append(terminalHead, progressTrack);
    } else {
      terminal.append(terminalHead);
    }
    const terminalLog = document.createElement("pre");
    terminalLog.textContent = journal.log || "Обновление ещё не запускалось. После нажатия «Установить обновление» здесь появятся выполняемые команды и их вывод.";
    terminalLog.className = journal.log ? "" : "terminal-empty";
    terminal.append(terminalLog);

    card.append(title, section, rows, button, hint, updateSection, updateActions, updateHint, terminal);
    root.append(style, card);
    terminalLog.scrollTop = wasAtBottom ? terminalLog.scrollHeight : previousScrollTop;
  }

  getCardSize() { return 14; }
  static getStubConfig() { return {title:"Управление системой"}; }
}
if (!customElements.get("viewpie-system-manager")) {
  customElements.define("viewpie-system-manager", ViewpieSystemManager);
}
window.customCards = window.customCards || [];
if (!window.customCards.some(card => card.type === "viewpie-system-manager")) {
  window.customCards.push({type:"viewpie-system-manager",name:"Viewpie — управление системой",description:"Состояние системы, сенсоры и перезагрузка Raspberry Pi"});
}
