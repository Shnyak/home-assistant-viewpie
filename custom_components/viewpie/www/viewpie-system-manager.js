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
    const findNamed = (domain, aliases) => states.find(item => {
      if (!item.entity_id.startsWith(domain + ".") || !belongsToEntry(item)) return false;
      const candidates = [
        item.attributes?.friendly_name,
        item.entity_id.split(".").pop().replace(/^viewpie_?/, "").replaceAll("_", " "),
      ].map(normalize);
      return aliases.some(alias => candidates.some(name => name === alias || name.endsWith(" " + alias)));
    }) || null;
    this._controls = {
      screen: findNamed("switch", ["экран"]),
      autoPause: findNamed("switch", ["авто пауза видео"]),
      debugOverlay: findNamed("switch", ["диагностическая информация"]),
      hardwareLimit: findNamed("number", ["лимит аппаратных декодеров"]),
      screenBootMode: findNamed("select", ["поведение экрана после подачи питания"]),
      startupPanel: findNamed("select", ["стартовая панель"]),
    };
    const buttons = states.filter(s => s.entity_id.startsWith("button.") && belongsToEntry(s));
    const restartName = normalize("Перезагрузить Raspberry Pi");
    this._checkUpdateButton = buttons.find(s => normalize(s.attributes?.friendly_name).endsWith(normalize("Проверить обновления Viewpie"))) || null;
    this._installUpdateButton = buttons.find(s => normalize(s.attributes?.friendly_name).endsWith(normalize("Установить обновление Viewpie"))) || null;
    this._button = buttons.find(s => {
      const name = normalize(s.attributes?.friendly_name);
      return name === restartName || name.endsWith(` ${restartName}`);
    }) || null;
    this._updateJournal = this._rows?.find(row => row.label === "Update process")?.state?.attributes || {};
    if (this._terminalClearPending && this._updateJournal.started_at &&
        this._updateJournal.started_at !== this._terminalClearBaselineStartedAt &&
        ["running", "success", "failed"].includes(this._updateJournal.status)) {
      this._terminalClearPending = false;
    }
    this._render();
  }

  _formatValue(row) {
    const state = row.state;
    if (!state || ["unknown", "unavailable"].includes(state.state)) return "Неизвестно";
    if (row.label === "Paused" || row.label === "Screen off") {
      return state.state === "on" ? "Да" : "Нет";
    }
    if (row.label === "Uptime") {
      const seconds = Math.max(0, Number(state.state) || 0);
      const days = Math.floor(seconds / 86400);
      const hours = Math.floor((seconds % 86400) / 3600);
      const minutes = Math.floor((seconds % 3600) / 60);
      if (days) return days + " дн. " + hours + " ч. " + minutes + " мин.";
      if (hours) return hours + " ч. " + minutes + " мин.";
      if (minutes) return minutes + " мин.";
      return Math.floor(seconds) + " сек.";
    }
    const unit = state.attributes?.unit_of_measurement;
    return unit ? `${state.state} ${unit}` : state.state;
  }

  _formatUpdateLog(log) {
    const timeZone = this._hass?.config?.time_zone || undefined;
    let formatter;
    try {
      formatter = new Intl.DateTimeFormat("ru-RU", {
        timeZone,
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hourCycle: "h23",
      });
    } catch (_) {
      formatter = new Intl.DateTimeFormat("ru-RU", {
        day: "2-digit", month: "2-digit", year: "numeric",
        hour: "2-digit", minute: "2-digit", second: "2-digit",
        hourCycle: "h23",
      });
    }
    return String(log || "").replace(
      /\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})\b/g,
      timestamp => {
        const date = new Date(timestamp);
        return Number.isNaN(date.getTime()) ? timestamp : formatter.format(date);
      }
    );
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
      button{font:inherit;border:0;border-radius:8px;padding:11px 12px;background:var(--primary-color);
        color:var(--text-primary-color,#fff);cursor:pointer;width:100%;margin:0;min-width:0;overflow-wrap:anywhere}
      button:disabled{opacity:.55;cursor:default}
      .update-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin-top:8px}
      .update-column{display:flex;flex-direction:column;gap:8px;min-width:0}
      .update-column-title{font-size:.92rem;font-weight:700;color:var(--primary-text-color);margin:0 0 2px}
      .update-actions{display:flex;flex-direction:column;gap:8px}
      .update-hint{margin-top:4px;color:var(--secondary-text-color);font-size:.84rem;overflow-wrap:anywhere}
      @media(max-width:420px){.update-grid{gap:8px}.update-column-title{font-size:.86rem}}
      .hint{margin-top:10px;color:var(--secondary-text-color);font-size:.88rem}
      .controls{display:flex;flex-direction:column;gap:10px}
      .control-row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:10px;align-items:center;
        padding:8px 0;border-bottom:1px solid var(--divider-color)}
      .control-name{color:var(--primary-text-color);font-size:.92rem}
      .control-input{max-width:180px;min-width:90px;font:inherit;color:var(--primary-text-color);
        background:var(--input-fill-color, var(--secondary-background-color));border:1px solid var(--divider-color);
        border-radius:8px;padding:7px 9px}
      .control-action{width:auto;margin:0;padding:8px 12px}
      .control-value{display:flex;align-items:center;gap:8px}
      .control-value input[type=checkbox]{width:22px;height:22px;accent-color:var(--primary-color)}
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

    const controlsSection = document.createElement("div");
    controlsSection.className = "section";
    controlsSection.textContent = "Управление";
    const controls = document.createElement("div");
    controls.className = "controls";

    const addSwitchControl = (label, entity) => {
      const row = document.createElement("div");
      row.className = "control-row";
      const name = document.createElement("span");
      name.className = "control-name";
      name.textContent = label;
      const input = document.createElement("input");
      input.type = "checkbox";
      input.checked = entity?.state === "on";
      input.disabled = !entity || ["unknown", "unavailable"].includes(entity.state);
      input.setAttribute("aria-label", label);
      input.addEventListener("change", async () => {
        if (!this._hass || !entity) return;
        const turnOn = input.checked;
        // The displayed value remains the last state confirmed by Home Assistant.
        input.checked = entity.state === "on";
        input.disabled = true;
        try {
          await this._hass.callService("switch", turnOn ? "turn_on" : "turn_off", {
            entity_id: entity.entity_id,
          });
        } catch (err) {
          input.disabled = false;
          window.alert("Не удалось изменить настройку «" + label + "»: " + (err?.message || err));
        }
      });
      const value = document.createElement("span");
      value.className = "control-value";
      value.append(input);
      row.append(name, value);
      controls.append(row);
    };

    const addNumberControl = (label, entity) => {
      const row = document.createElement("div");
      row.className = "control-row";
      const name = document.createElement("label");
      name.className = "control-name";
      name.textContent = label;
      const value = document.createElement("div");
      value.className = "control-value";
      const input = document.createElement("input");
      input.className = "control-input";
      input.type = "number";
      input.min = "0";
      input.max = "16";
      input.step = "1";
      input.value = entity?.state ?? "6";
      input.disabled = !entity || ["unknown", "unavailable"].includes(entity.state);
      input.setAttribute("aria-label", label);
      const apply = document.createElement("button");
      apply.className = "control-action";
      apply.type = "button";
      apply.textContent = "Применить";
      apply.disabled = input.disabled;
      apply.addEventListener("click", async () => {
        if (!this._hass || !entity) return;
        const next = Number(input.value);
        if (!Number.isInteger(next) || next < 0 || next > 16) {
          window.alert("Укажите целое число от 0 до 16.");
          return;
        }
        input.disabled = true;
        apply.disabled = true;
        try {
          await this._hass.callService("number", "set_value", {
            entity_id: entity.entity_id,
            value: next,
          });
        } catch (err) {
          input.disabled = false;
          apply.disabled = false;
          input.value = entity.state;
          window.alert("Не удалось изменить количество аппаратных декодеров: " + (err?.message || err));
        }
      });
      value.append(input, apply);
      row.append(name, value);
      controls.append(row);
    };

    const addSelectControl = (label, entity) => {
      const row = document.createElement("div");
      row.className = "control-row";
      const name = document.createElement("label");
      name.className = "control-name";
      name.textContent = label;
      const select = document.createElement("select");
      select.className = "control-input";
      const options = entity?.attributes?.options || [];
      for (const option of options) {
        const item = document.createElement("option");
        item.value = option;
        item.textContent = option;
        select.append(item);
      }
      if (entity?.state && options.includes(entity.state)) select.value = entity.state;
      select.disabled = !entity || ["unknown", "unavailable"].includes(entity.state);
      select.setAttribute("aria-label", label);
      select.addEventListener("change", async () => {
        if (!this._hass || !entity) return;
        const option = select.value;
        select.value = entity.state;
        select.disabled = true;
        try {
          await this._hass.callService("select", "select_option", {
            entity_id: entity.entity_id,
            option,
          });
        } catch (err) {
          select.disabled = false;
          window.alert("Не удалось изменить настройку «" + label + "»: " + (err?.message || err));
        }
      });
      row.append(name, select);
      controls.append(row);
    };

    addSwitchControl("Экран", this._controls?.screen);
    addSwitchControl("Авто пауза видео", this._controls?.autoPause);
    addSwitchControl("Диагностическая информация", this._controls?.debugOverlay);
    addNumberControl("Количество аппаратных декодеров", this._controls?.hardwareLimit);
    addSelectControl("После подачи питания на экран", this._controls?.screenBootMode);
    addSelectControl("Панель при запуске", this._controls?.startupPanel);
    controlsSection.append(controls);

    const restartPiButton = document.createElement("button");
    restartPiButton.textContent = "Перезагрузить Raspberry Pi";
    restartPiButton.disabled = !this._button || this._button.state === "unavailable";
    restartPiButton.addEventListener("click", async () => {
      if (!this._hass || !this._button) return;
      if (!window.confirm("Перезагрузить Raspberry Pi? Видеостена временно станет недоступна.")) return;
      restartPiButton.disabled = true;
      try {
        await this._hass.callService("button", "press", {entity_id:this._button.entity_id});
      } catch (err) {
        window.alert("Не удалось отправить команду перезагрузки: " + (err?.message || err));
      } finally {
        restartPiButton.disabled = false;
      }
    });
    const updateSection = document.createElement("div");
    updateSection.className = "section";
    updateSection.textContent = "Обновление Viewpie";
    const updateActions = document.createElement("div");
    updateActions.className = "update-actions";

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

    const updateAvailable = this._rows?.find(row => row.label === "Update available")?.state?.state;
    const latestVersion = this._rows?.find(row => row.label === "Latest version")?.state?.state;
    const updateAttrs = this._rows?.find(row => row.label === "Update available")?.state?.attributes || {};
    const installJournal = this._updateJournal || {};
    const installInProgress = Boolean(this._terminalClearPending) || ["starting", "running"].includes(installJournal.status);
    const installedVersion = installJournal.version || updateAttrs.installed_version || "";
    const installButton = document.createElement("button");
    const installedAfterSuccess = installJournal.status === "success" &&
      (updateAvailable !== "Да" || updateAttrs.manual_check_required);
    installButton.textContent = installInProgress
      ? "Идёт установка"
      : installJournal.status === "failed"
        ? "Установить обновление"
        : updateAvailable === "Да" && !updateAttrs.manual_check_required
          ? "Установить обновление"
          : installedAfterSuccess || updateAvailable === "Нет" || updateAttrs.manual_check_required
            ? `Установлена ${installedVersion || latestVersion || ""}`
            : "Установить обновление";
    installButton.disabled = installInProgress || updateAvailable !== "Да" ||
      Boolean(updateAttrs.manual_check_required) ||
      !this._installUpdateButton || this._installUpdateButton.state === "unavailable";
    installButton.addEventListener("click", async () => {
      if (!this._hass || !this._installUpdateButton) return;
      if (!window.confirm("Установить последнюю проверенную версию Viewpie? Видеостена временно перезапустится.")) return;
      installButton.disabled = true;
      this._terminalClearBaselineStartedAt = this._updateJournal?.started_at || "";
      this._terminalClearPending = true;
      this._render();
      try {
        await this._hass.callService("button", "press", {entity_id:this._installUpdateButton.entity_id});
        window.alert("Команда обновления принята. Журнал предыдущей установки очищен; ожидается начало нового процесса.");
      } catch (err) {
        this._terminalClearPending = false;
        this._render();
        window.alert("Не удалось запустить обновление: " + (err?.message || err));
      }
    });
    updateActions.append(checkButton, installButton, restartPiButton);
    const updateHint = document.createElement("div");
    updateHint.className = "hint";
    if (updateAvailable === "Да" && updateAttrs.bootstrap_required) {
      installButton.disabled = true;
      const bootstrapCommand = String(updateAttrs.bootstrap_command || "");
      updateHint.style.whiteSpace = "pre-line";
      updateHint.style.overflowWrap = "anywhere";
      updateHint.textContent =
        `Установлена старая версия ${updateAttrs.installed_version || ""}. Её встроенный установщик не может проверить новый Debian-пакет. Для первого перехода на ${latestVersion || updateAttrs.latest_version || "0.2.27-fork"} выполните на Raspberry Pi по SSH:\n\n${bootstrapCommand}\n\nСкрипт проверит архитектуру и SHA-256, установит Viewpie и автоматически перезагрузит Raspberry Pi.`;
      const copyBootstrap = document.createElement("button");
      copyBootstrap.textContent = "Копировать команду первоначального обновления";
      copyBootstrap.addEventListener("click", async () => {
        try {
          let copied = false;
          if (navigator.clipboard?.writeText) {
            try {
              await navigator.clipboard.writeText(bootstrapCommand);
              copied = true;
            } catch (_) {}
          }
          if (!copied) {
            const fallback = document.createElement("textarea");
            fallback.value = bootstrapCommand;
            fallback.setAttribute("readonly", "");
            fallback.style.position = "fixed";
            fallback.style.opacity = "0";
            document.body.appendChild(fallback);
            fallback.select();
            copied = document.execCommand("copy");
            fallback.remove();
          }
          if (!copied) throw new Error("Clipboard unavailable");
          copyBootstrap.textContent = "Команда скопирована";
        } catch (err) {
          window.alert("Не удалось скопировать команду: " + (err?.message || err));
        }
      });
      updateActions.insertBefore(copyBootstrap, installButton);
    } else if (installInProgress) {
      updateHint.textContent = "Обновление выполняется. После завершения Viewpie автоматически перезагрузит Raspberry Pi.";
    } else if (installJournal.status === "failed") {
      updateHint.textContent = `Предыдущая установка завершилась ошибкой: ${installJournal.error || installJournal.message || "подробности в журнале ниже"}. После устранения причины нажмите «Проверить обновления».`;
    } else if (installedAfterSuccess) {
      updateHint.textContent = `Установлена версия Viewpie ${installedVersion || latestVersion || ""}. Нажмите «Проверить обновления», чтобы проверить наличие следующей версии.`;
    } else if (updateAvailable === "Нет") {
      updateHint.textContent = `Обновлений нет. Установлена последняя версия Viewpie ${updateAttrs.installed_version || latestVersion || ""}.`;
    } else if (updateAvailable === "Да" && updateAttrs.manual_check_required) {
      updateHint.textContent = `Автоматически обнаружена новая версия Viewpie ${latestVersion || updateAttrs.latest_version || ""}. Нажмите «Проверить обновления», чтобы подтвердить её и включить установку.`;
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

    const integrationUpdateSection = document.createElement("div");
    integrationUpdateSection.className = "section";
    integrationUpdateSection.textContent = "Обновление интеграции Home Assistant";
    const integrationUpdateStatus = document.createElement("div");
    integrationUpdateStatus.className = "hint";
    integrationUpdateStatus.textContent = "Установленная версия: 1.6.10. Нажмите «Проверить», чтобы найти обновление.";
    const integrationUpdateActions = document.createElement("div");
    integrationUpdateActions.className = "update-actions";
    const integrationCheck = document.createElement("button");
    integrationCheck.textContent = "Проверить обновления";
    const integrationInstall = document.createElement("button");
    integrationInstall.textContent = "Установить обновление";
    integrationInstall.disabled = true;
    integrationInstall.addEventListener("click", async () => {
      const release = this._integrationRelease;
      const repositoryId = this._integrationHacsRepositoryId;
      if (!this._hass || !release?.tag_name || !repositoryId) return;
      if (!window.confirm("Установить интеграцию Viewpie " + release.tag_name + " через HACS? После установки потребуется перезапустить Home Assistant.")) return;
      integrationInstall.disabled = true;
      integrationUpdateStatus.textContent = "Устанавливаем " + release.tag_name + " через HACS…";
      try {
        await this._hass.callWS({
          type: "hacs/repository/download",
          repository: String(repositoryId),
          version: release.tag_name
        });
        integrationUpdateStatus.textContent = "Интеграция " + release.tag_name + " загружена через HACS. Теперь нажмите «Перезапустить HA».";
      } catch (err) {
        integrationUpdateStatus.textContent = "HACS не смог установить обновление: " + (err?.message || err);
        integrationInstall.disabled = false;
      }
    });
    integrationCheck.addEventListener("click", async () => {
      integrationCheck.disabled = true;
      integrationInstall.disabled = true;
      this._integrationRelease = null;
      this._integrationHacsRepositoryId = null;
      integrationUpdateStatus.textContent = "Проверяем последний стабильный релиз на GitHub…";
      try {
        const accessToken = this._hass?.auth?.data?.access_token;
        const headers = accessToken ? {Authorization: `Bearer ${accessToken}`} : {};
        const response = await fetch("/api/viewpie/integration/latest-release", {
          headers, credentials:"same-origin", cache:"no-store"
        });
        if (!response.ok) throw new Error("GitHub API HTTP " + response.status);
        const release = await response.json();
        const latest = String(release.tag_name || "").replace(/^v/i,"");
        const current = "1.6.10";
        const parse = value => value.split(".").map(part => Number.parseInt(part,10) || 0);
        const a=parse(latest), b=parse(current);
        const newer=a.some((value,index)=>value>(b[index]||0) && a.slice(0,index).every((n,i)=>n===(b[i]||0)));
        if (!newer) {
          integrationUpdateStatus.textContent = "Установлена актуальная версия интеграции " + current + ". Последний релиз: " + (release.tag_name || "неизвестно") + ".";
          return;
        }
        const repositoryResponse = await this._hass.callWS({
          type: "hacs/repositories/list",
          categories: ["integration"]
        });
        const repositories = Array.isArray(repositoryResponse?.result)
          ? repositoryResponse.result
          : (repositoryResponse?.result?.repositories || []);
        const repository = repositories.find(item =>
          String(item.full_name || "").toLowerCase() === "shnyak/home-assistant-viewpie"
        );
        if (!repository || !repository.installed) {
          integrationUpdateStatus.textContent = "Доступна версия " + release.tag_name + ", но установленный репозиторий не найден в HACS. Установка кнопкой доступна только для интеграции, установленной через HACS.";
          return;
        }
        this._integrationRelease = release;
        this._integrationHacsRepositoryId = repository.id;
        integrationInstall.disabled = false;
        integrationUpdateStatus.textContent = "Доступна версия " + release.tag_name + ". Установлена версия " + current + ". Нажмите «Установить обновление», затем перезапустите HA.";
      } catch (err) {
        integrationUpdateStatus.textContent = "Не удалось проверить или подготовить обновление интеграции: " + (err?.message || err);
      } finally {
        integrationCheck.disabled = false;
      }
    });
    const restartHa = document.createElement("button");
    restartHa.textContent = "Перезапустить Home Assistant";
    restartHa.addEventListener("click", async () => {
      if (!this._hass || !window.confirm("Перезапустить Home Assistant сейчас? Все интеграции и автоматизации временно станут недоступны.")) return;
      restartHa.disabled = true;
      try {
        await this._hass.callService("homeassistant","restart");
      } catch (err) {
        restartHa.disabled = false;
        window.alert("Не удалось отправить команду перезапуска Home Assistant: " + (err?.message || err));
      }
    });
    restartHa.textContent = "Перезапустить HA";
    integrationUpdateActions.append(integrationCheck, integrationInstall, restartHa);

    const journalEntity = this._rows?.find(row => row.label === "Update process")?.state;
    const journal = journalEntity?.attributes || {};
    const waitingForNewUpdate = Boolean(this._terminalClearPending);
    const terminal = document.createElement("section");
    terminal.className = "terminal";
    const terminalHead = document.createElement("div");
    terminalHead.className = "terminal-head";
    const terminalState = document.createElement("span");
    terminalState.className = "terminal-state";
    const progressValue = journal.progress_percent !== null && journal.progress_percent !== undefined && Number.isFinite(Number(journal.progress_percent))
      ? Math.max(0, Math.min(100, Number(journal.progress_percent))) : null;
    const progress = progressValue !== null ? ` — ${progressValue}%` : "";
    terminalState.textContent = waitingForNewUpdate
      ? "● Ожидание нового процесса обновления"
      : journal.status === "running"
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
    copyLog.disabled = waitingForNewUpdate;
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
    if (progressValue !== null && !waitingForNewUpdate) {
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
    terminalLog.textContent = waitingForNewUpdate
      ? "Предыдущий журнал очищен. Ожидаем, пока интеграция запустит новую установку…"
      : this._formatUpdateLog(journal.log || "Обновление ещё не запускалось. После нажатия «Установить обновление» здесь появятся выполняемые команды и их вывод.");
    terminalLog.className = waitingForNewUpdate || !journal.log ? "terminal-empty" : "";
    terminal.append(terminalLog);

    updateSection.textContent = "Обновления";
    const updateGrid = document.createElement("div");
    updateGrid.className = "update-grid";
    const viewpieColumn = document.createElement("section");
    viewpieColumn.className = "update-column";
    const viewpieColumnTitle = document.createElement("div");
    viewpieColumnTitle.className = "update-column-title";
    viewpieColumnTitle.textContent = "ViewPie";
    const viewpieHint = document.createElement("div");
    viewpieHint.className = "update-hint";
    viewpieHint.append(updateHint);
    viewpieColumn.append(viewpieColumnTitle, updateActions, viewpieHint);
    const integrationColumn = document.createElement("section");
    integrationColumn.className = "update-column";
    const integrationColumnTitle = document.createElement("div");
    integrationColumnTitle.className = "update-column-title";
    integrationColumnTitle.textContent = "Интеграция";
    const integrationHint = document.createElement("div");
    integrationHint.className = "update-hint";
    integrationHint.append(integrationUpdateStatus);
    integrationColumn.append(integrationColumnTitle, integrationUpdateActions, integrationHint);
    updateGrid.append(viewpieColumn, integrationColumn);
    card.append(title, section, rows, controlsSection, updateSection, updateGrid, terminal);
    root.append(style, card);
    // The card is rebuilt on every Home Assistant state update. Scroll after
    // the new content has been laid out so the newest log line stays visible.
    requestAnimationFrame(() => {
      if (terminalLog.isConnected) terminalLog.scrollTop = terminalLog.scrollHeight;
    });
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
