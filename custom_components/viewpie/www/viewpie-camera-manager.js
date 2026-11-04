class ViewpieCameraManager extends HTMLElement {
  setConfig(config) {
    if (!config || typeof config !== "object") throw new Error("A card configuration object is required");
    this._config = config;
    this._entryId = config.entry_id || "";
    this._cameraName = "";
    this._cameraUrl = "";
    this._cameraFullscreenUrl = "";
    this._cameraOptions = [];
    this._panelOptions = [];
    this._fullscreenEntity = null;
    this._panelEntity = null;
    this._status = "";
    this._error = false;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    const states = Object.values(hass?.states || {});
    const matchesEntry = s => !this._entryId || s.entity_id.includes(this._entryId);
    const fullscreen = states.find(s => s.entity_id.startsWith("select.") &&
      s.entity_id.endsWith("_fullscreen_camera") && s.attributes?.options && matchesEntry(s));
    const panel = states.find(s => s.entity_id.startsWith("select.") &&
      s.entity_id.endsWith("_panel") && s.attributes?.options && matchesEntry(s));
    const signature = JSON.stringify([
      fullscreen?.entity_id, fullscreen?.attributes?.options, fullscreen?.state,
      panel?.entity_id, panel?.attributes?.options, panel?.state
    ]);
    if (signature !== this._signature) {
      this._signature = signature;
      this._fullscreenEntity = fullscreen || null;
      this._panelEntity = panel || null;
      this._cameraOptions = fullscreen ? fullscreen.attributes.options.filter(x => x !== "Grid") : [];
      this._panelOptions = panel ? panel.attributes.options : [];
      if (this._cameraName && !this._cameraOptions.includes(this._cameraName)) {
        this._cameraName = "";
        this._cameraUrl = "";
        this._cameraFullscreenUrl = "";
      }
      this._render();
    }
  }

  _el(tag, attrs = {}, value = "") {
    const node = document.createElement(tag);
    Object.entries(attrs).forEach(([key, val]) => {
      if (key === "class") node.className = val;
      else if (key === "value") node.value = val;
      else node.setAttribute(key, val);
    });
    if (value) node.textContent = value;
    return node;
  }

  _field(label, input) {
    const wrap = this._el("label", {class:"field"});
    wrap.append(this._el("span", {}, label), input);
    return wrap;
  }

  _render() {
    if (!this._config) return;
    const root = this.shadowRoot || this.attachShadow({mode:"open"});
    root.replaceChildren();
    const style = this._el("style");
    style.textContent = `
      :host{display:block} ha-card{padding:16px} h2{font-size:1.25rem;margin:0 0 14px}
      .fields{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px}
      .field{display:flex;flex-direction:column;gap:5px;font-size:.9rem}
      input,select{box-sizing:border-box;width:100%;min-width:0;padding:10px;color:var(--primary-text-color);background:var(--card-background-color);border:1px solid var(--divider-color);border-radius:6px}
      button{border:0;border-radius:6px;padding:10px 14px;cursor:pointer;background:var(--primary-color);color:var(--text-primary-color,#fff);font-weight:600}
      button:disabled{opacity:.45;cursor:not-allowed}.actions{display:flex;flex-wrap:wrap;gap:8px;margin-top:14px}
      .muted{color:var(--secondary-text-color);font-size:.85rem}.status{margin-top:12px;white-space:pre-wrap}
      .error{color:var(--error-color)}.camera-list{margin:12px 0;padding-left:20px}
      .control-section{margin:16px 0}.control-section h3{font-size:1rem;margin:0 0 8px}
      .choice-grid{display:flex;flex-wrap:wrap;gap:8px}
      button.choice{background:var(--secondary-background-color);color:var(--primary-text-color);border:1px solid var(--divider-color)}
      button.choice.active{background:var(--primary-color);color:var(--text-primary-color,#fff);border-color:var(--primary-color)}
      button.choice:focus-visible{outline:2px solid var(--primary-color);outline-offset:2px}
    `;
    const card=this._el("ha-card");
    card.append(this._el("h2",{},this._config.title || "Управление камерами Viewpie"));
    card.append(this._el("p",{class:"muted"},"Добавление, редактирование, проверка RTSP и удаление камер Viewpie. Изменения применяются командой Reload config."));
    const controls=this._el("div",{class:"control-section"});
    controls.append(this._el("h3",{},"Панели"));
    const panelButtons=this._el("div",{class:"choice-grid"});
    const fullscreenActive=this._fullscreenEntity && this._fullscreenEntity.state !== "Grid";
    this._panelOptions.forEach(panelId=>{
      const button=this._el("button",{class:"choice"+(!fullscreenActive && this._panelEntity?.state===panelId?" active":"")},panelId);
      button.setAttribute("aria-pressed",String(!fullscreenActive && this._panelEntity?.state===panelId));
      button.addEventListener("click",()=>this._selectPanel(panelId));
      panelButtons.append(button);
    });
    if(!this._panelOptions.length) panelButtons.append(this._el("span",{class:"muted"},"Панели пока не найдены."));
    controls.append(panelButtons);
    controls.append(this._el("h3",{},"Полноэкранный режим"));
    const cameraButtons=this._el("div",{class:"choice-grid"});
    this._cameraOptions.forEach(name=>{
      const active=this._fullscreenEntity?.state===name;
      const button=this._el("button",{class:"choice"+(active?" active":"")},name);
      button.setAttribute("aria-pressed",String(!!active));
      button.addEventListener("click",()=>this._selectCamera(name,active));
      cameraButtons.append(button);
    });
    if(!this._cameraOptions.length) cameraButtons.append(this._el("span",{class:"muted"},"Камеры пока не найдены."));
    controls.append(cameraButtons);
    card.append(controls);

    const fields=this._el("div",{class:"fields"});
    const select=this._el("select");
    select.append(this._el("option",{value:""},"Новая камера — добавить"));
    this._cameraOptions.forEach(name=>select.append(this._el("option",{value:name},name)));
    select.value=this._cameraName;
    select.addEventListener("change",async()=>{
      this._cameraName=select.value; this._cameraUrl=""; this._cameraFullscreenUrl="";
      if(this._cameraName){
        try{
          const data={name:this._cameraName}; if(this._entryId)data.entry_id=this._entryId;
          const result=await this._hass.callWS({type:"call_service",domain:"viewpie",service:"get_camera",service_data:data,return_response:true});
          const camera=result?.response||result;
          this._cameraUrl=camera?.url||""; this._cameraFullscreenUrl=camera?.fullscreen_url||"";
          this._status="Параметры камеры загружены."; this._error=false;
        }catch(err){this._status="Не удалось загрузить параметры: "+(err?.message||err);this._error=true;}
      } else this._status="";
      this._render();
    });
    fields.append(this._field("Выбрать существующую камеру",select));
    const name=this._el("input",{placeholder:"например, side_gate",value:this._cameraName});
    name.value=this._cameraName;
    name.disabled=this._cameraOptions.includes(this._cameraName);
    name.addEventListener("input",()=>this._cameraName=name.value);
    fields.append(this._field("Имя камеры",name));
    const url=this._el("input",{placeholder:"rtsp://user:password@192.168.1.10/stream",value:this._cameraUrl});
    url.value=this._cameraUrl;
    url.addEventListener("input",()=>this._cameraUrl=url.value);
    fields.append(this._field("RTSP URL",url));
    const full=this._el("input",{placeholder:"Необязательно",value:this._cameraFullscreenUrl});
    full.value=this._cameraFullscreenUrl;
    full.addEventListener("input",()=>this._cameraFullscreenUrl=full.value);
    fields.append(this._field("RTSP URL для fullscreen",full));
    card.append(fields);

    const actions=this._el("div",{class:"actions"});
    const existing=this._cameraOptions.includes(this._cameraName);
    const add=this._el("button",{},"Добавить камеру");
    add.disabled=existing; add.addEventListener("click",()=>this._manage("create")); actions.append(add);
    const update=this._el("button",{},"Сохранить изменения");
    update.disabled=!existing; update.style.background="var(--secondary-text-color)";
    update.addEventListener("click",()=>this._manage("update")); actions.append(update);
    const test=this._el("button",{},"Проверить RTSP");
    test.disabled=!existing; test.style.background="var(--secondary-text-color)";
    test.addEventListener("click",()=>this._manage("test")); actions.append(test);
    const remove=this._el("button",{},"Удалить камеру");
    remove.disabled=!existing; remove.style.background="var(--error-color)";
    remove.addEventListener("click",()=>this._manage("delete")); actions.append(remove);
    card.append(actions);
    card.append(this._el("div",{class:"status"+(this._error?" error":"")},this._status));
    root.append(style,card);
  }

  async _selectPanel(panelId) {
    if(!this._hass || !this._panelEntity) return;
    this._status="Переключаю панель…";this._error=false;this._render();
    try{
      // Clear fullscreen first so exactly one display choice is active.
      await this._hass.callService("select","select_option",{
        entity_id:this._fullscreenEntity.entity_id,option:"Grid"
      });
      await this._hass.callService("select","select_option",{
        entity_id:this._panelEntity.entity_id,option:panelId
      });
      this._status="Активна панель: "+panelId;
    }catch(err){this._status="Не удалось переключить панель: "+(err?.message||err);this._error=true;}
    this._render();
  }

  async _selectCamera(camera,active) {
    if(!this._hass || !this._fullscreenEntity) return;
    this._status=active?"Возвращаюсь к панели…":"Включаю полноэкранный режим…";this._error=false;this._render();
    try{
      await this._hass.callService("select","select_option",{
        entity_id:this._fullscreenEntity.entity_id,option:active?"Grid":camera
      });
      this._status=active?"Полноэкранный режим выключен":"Полноэкранная камера: "+camera;
    }catch(err){this._status="Не удалось переключить камеру: "+(err?.message||err);this._error=true;}
    this._render();
  }

  async _manage(operation) {
    const name=(this._cameraName||"").trim();
    if(!name||!this._hass){this._status="Укажите имя камеры.";this._error=true;this._render();return;}
    if(operation==="delete"&&!window.confirm(`Удалить камеру «${name}»? Если она используется в панелях, соответствующие ячейки будут очищены.`))return;
    if(operation!=="test"&&operation!=="delete"&&!(this._cameraUrl||"").trim()){
      this._status="Укажите RTSP URL камеры.";this._error=true;this._render();return;
    }
    this._status=operation==="test"?"Проверяю RTSP…":"Выполняю операцию…";this._error=false;this._render();
    try{
      const data={name};if(this._entryId)data.entry_id=this._entryId;
      if(operation==="test"){
        const result=await this._hass.callWS({type:"call_service",domain:"viewpie",service:"test_camera",service_data:data,return_response:true});
        const value=result?.response||result||{};
        this._status=value.ok?`RTSP доступен. Задержка: ${value.latency_ms??"—"} мс.`:`RTSP недоступен: ${value.error||"Viewpie не подтвердил соединение"}`;
        this._error=!value.ok;
      }else{
        data.operation=operation;
        if(operation!=="delete"){data.url=this._cameraUrl.trim();data.fullscreen_url=this._cameraFullscreenUrl||"";}
        await this._hass.callService("viewpie","manage_camera",data);
        if(operation==="delete"){
          this._cameraOptions=this._cameraOptions.filter(item=>item!==name);
          this._cameraName="";this._cameraUrl="";this._cameraFullscreenUrl="";
          this._status=`Камера «${name}» удалена. Использовавшиеся ячейки панелей очищены; Reload config выполнен.`;
        }else{
          this._cameraOptions=[...new Set([...this._cameraOptions,name])];
          this._status=operation==="create"?`Камера «${name}» добавлена. Reload config выполнен.`:`Камера «${name}» обновлена. Reload config выполнен.`;
        }
      }
    }catch(err){this._status=`Операция не выполнена: ${err?.message||err}`;this._error=true;}
    this._render();
  }

  getCardSize(){return 4;}
}
if(!customElements.get("viewpie-camera-manager"))customElements.define("viewpie-camera-manager",ViewpieCameraManager);
window.customCards=window.customCards||[];
if(!window.customCards.some(card=>card.type==="viewpie-camera-manager"))window.customCards.push({
  type:"viewpie-camera-manager",name:"Управление камерами Viewpie",
  description:"Отдельная карточка добавления, редактирования, проверки и удаления камер Viewpie"
});
