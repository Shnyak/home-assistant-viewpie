from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "viewpie"


class IntegrationSetupRegressionTests(unittest.TestCase):
    def test_runtime_is_registered_before_platform_forwarding(self):
        source = (INTEGRATION / "__init__.py").read_text(encoding="utf-8")
        runtime_registration = source.index('hass.data.setdefault(DOMAIN, {})[entry.entry_id] = runtime')
        platform_forwarding = source.index('await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)')
        self.assertLess(runtime_registration, platform_forwarding)

    def test_all_entity_platform_modules_are_registered(self):
        constants = (INTEGRATION / "const.py").read_text(encoding="utf-8")
        for platform in ("switch", "select", "number", "button", "sensor", "binary_sensor"):
            with self.subTest(platform=platform):
                self.assertIn(f'"{platform}"', constants)
                self.assertTrue((INTEGRATION / f"{platform}.py").is_file())

    def test_lovelace_cards_discover_selects_by_stable_entity_icons(self):
        expected = {
            "viewpie-layout-editor.js": ("mdi:view-dashboard", "mdi:fullscreen"),
            "viewpie-camera-manager.js": ("mdi:fullscreen",),
            "viewpie-view-selector.js": ("mdi:view-dashboard", "mdi:fullscreen"),
        }
        for filename, icons in expected.items():
            source = (INTEGRATION / "www" / filename).read_text(encoding="utf-8")
            with self.subTest(card=filename):
                for icon in icons:
                    self.assertIn(f'attributes?.icon === "{icon}"', source)
                self.assertNotIn('_fullscreen_camera', source)
                self.assertNotIn('s.entity_id.includes(this._entryId)', source)

    def test_camera_entities_are_created_dynamically(self):
        source = (INTEGRATION / "binary_sensor.py").read_text(encoding="utf-8")
        self.assertIn("coordinator.async_add_listener(add_camera_entities)", source)
        self.assertIn("ViewpieCameraRunningBinarySensor", source)
        self.assertIn("ViewpieCameraInUseBinarySensor", source)

    def test_editor_resource_registration_is_idempotent_and_storage_only(self):
        source = (INTEGRATION / "__init__.py").read_text(encoding="utf-8")
        self.assertIn('resources.async_items()', source)
        self.assertIn('for _, url, label in static_paths:', source)
        self.assertIn('resources.async_create_item({"res_type": "module", "url": versioned_url})', source)
        self.assertIn("resources.async_update_item(current[\"id\"], {\"url\": versioned_url})", source)
        self.assertIn('version = json.loads((integration_dir / "manifest.json")', source)
        self.assertIn('("viewpie-camera-manager.js", "/viewpie/viewpie-camera-manager.js", "camera manager")', source)
        self.assertIn('hasattr(resources, "async_create_item")', source)
        manifest = __import__("json").loads((INTEGRATION / "manifest.json").read_text(encoding="utf-8"))
        self.assertIn("lovelace", manifest["dependencies"])
        self.assertIn("http", manifest["dependencies"])

    def test_integration_metadata_and_branding(self):
        import json

        manifest = json.loads((INTEGRATION / "manifest.json").read_text(encoding="utf-8"))
        self.assertRegex(manifest["version"], r"^\d+\.\d+\.\d+$")
        entity = (INTEGRATION / "entity.py").read_text(encoding="utf-8")
        self.assertIn('manufacturer": "Viewpie"', entity)
        self.assertNotIn("AI-generated integration", entity)
        self.assertTrue((INTEGRATION / "brand" / "icon.png").is_file())
        self.assertTrue((INTEGRATION / "brand" / "logo.png").is_file())
        self.assertTrue((INTEGRATION / "brand" / "logo@2x.png").is_file())


    def test_layout_editor_preserves_other_selected_cameras_when_replacing_one(self):
        source = (INTEGRATION / "www" / "viewpie-layout-editor.js").read_text(encoding="utf-8")
        # Each contiguous rectangular region of one camera maps to one slot.
        self.assertIn("_getCameraRegions()", source)
        self.assertIn("matrix[r][c] = slot;", source)
        self.assertIn("viewports.push({ slot, feeds: [region.camera] });", source)
        self.assertIn('this._cells[`${r},${c}`] = camera[0];', source)

    def test_layout_editor_splits_layout_rows_on_whitespace(self):
        source = (INTEGRATION / "www" / "viewpie-layout-editor.js").read_text(encoding="utf-8")
        self.assertIn('.map(row => row.trim().split(/\\s+/))', source)

    def test_update_check_has_visible_result_and_release_metadata(self):
        coordinator = (INTEGRATION / "coordinator.py").read_text(encoding="utf-8")
        self.assertIn('"update_check_status": "checked"', coordinator)
        self.assertIn('"update_check_status": "error"', coordinator)
        self.assertIn('"update_checked_at": checked_at', coordinator)
        sensor = (INTEGRATION / "sensor.py").read_text(encoding="utf-8")
        self.assertIn('return "Ошибка проверки"', sensor)
        self.assertIn('"can_install": bool(self.status.get("can_install", False)) and not bootstrap_required', sensor)
        card = (INTEGRATION / "www" / "viewpie-system-manager.js").read_text(encoding="utf-8")
        self.assertIn("Обновлений нет. Установлена последняя версия Viewpie", card)
        self.assertIn("Доступно обновление Viewpie до версии", card)
        self.assertIn("Проверка ещё не выполнялась", card)

    def test_integration_release_check_uses_authenticated_home_assistant_proxy(self):
        source = (INTEGRATION / "__init__.py").read_text(encoding="utf-8")
        self.assertIn("class ViewpieIntegrationReleaseView(HomeAssistantView)", source)
        self.assertIn('url = "/api/viewpie/integration/latest-release"', source)
        self.assertIn("hass.http.register_view(ViewpieIntegrationReleaseView())", source)
        card = (INTEGRATION / "www" / "viewpie-system-manager.js").read_text(encoding="utf-8")
        self.assertIn('fetch("/api/viewpie/integration/latest-release"', card)
        self.assertIn('callService("homeassistant","restart")', card)

    def test_legacy_updater_versions_require_one_time_bootstrap(self):
        import runpy

        helpers = runpy.run_path(str(INTEGRATION / "update_utils.py"))
        requires_bootstrap = helpers["requires_bootstrap"]
        self.assertTrue(requires_bootstrap("0.2.25-fork"))
        self.assertTrue(requires_bootstrap("0.2.26-fork"))
        self.assertTrue(requires_bootstrap("0.2.33-fork"))
        self.assertTrue(requires_bootstrap("0.2.34-fork"))
        self.assertFalse(requires_bootstrap("0.2.35-fork"))
        self.assertFalse(requires_bootstrap(None))
        sensor = (INTEGRATION / "sensor.py").read_text(encoding="utf-8")
        self.assertIn('"bootstrap_required": bootstrap_required', sensor)
        self.assertIn('"bootstrap_command": BOOTSTRAP_COMMAND if bootstrap_required else None', sensor)
        button = (INTEGRATION / "button.py").read_text(encoding="utf-8")
        self.assertIn('requires_bootstrap(installed_version)', button)

    def test_installed_software_version_and_build_date_sensors_are_exposed(self):
        source = (INTEGRATION / "sensor.py").read_text(encoding="utf-8")
        self.assertIn("ViewpieSoftwareVersionSensor(coordinator)", source)
        self.assertIn("ViewpieSoftwareBuildDateSensor(coordinator)", source)
        self.assertIn('_key = "software_version"', source)
        self.assertIn('_key = "software_build_date"', source)
        entity = (INTEGRATION / "entity.py").read_text(encoding="utf-8")
        self.assertIn('status.get("software_version")', entity)
        self.assertIn('device_info["sw_version"]', entity)


    def test_layout_editor_loads_one_shot_camera_preview_and_releases_blob(self):
        source = (INTEGRATION / "www" / "viewpie-layout-editor.js").read_text(encoding="utf-8")
        self.assertIn("/api/viewpie/cameras/${encodeURIComponent(camera)}/snapshot", source)
        self.assertIn("URL.createObjectURL(blob)", source)
        self.assertIn("URL.revokeObjectURL(previewUrl)", source)
        self.assertIn("Обновить превью камер", source)
        self.assertIn("_refreshAllCameraPreviews", source)
        self.assertNotIn("this._initialPreviewLoadStarted", source)
        self.assertIn("const failures = []", source)
        self.assertIn("failures.slice(0, 5)", source)
        self.assertIn("cameraSelect?.attributes?.viewpie_entry_id", source)
        self.assertIn("this._cameraPreviewUrls.set(camera, nextUrl)", source)
        self.assertIn("this._cameraPreviewUrls?.get(camera)", source)
        self.assertIn("URL.revokeObjectURL(url)", source)
        init = (INTEGRATION / "__init__.py").read_text(encoding="utf-8")
        self.assertIn("class ViewpieCameraSnapshotView(HomeAssistantView)", init)
        self.assertIn('requires_auth = True', init)
        self.assertIn('hass.http.register_view(ViewpieCameraSnapshotView(hass))', init)
    def test_camera_previews_are_persisted_on_home_assistant_host(self):
        source = (INTEGRATION / "__init__.py").read_text(encoding="utf-8")
        self.assertIn('"viewpie_previews"', source)
        self.assertIn('request.query.get("refresh") == "1"', source)
        self.assertIn("preview_path.read_bytes", source)
        self.assertIn("temporary_path.write_bytes", source)
        self.assertIn('headers={"Cache-Control": "no-store"}', source)
        editor = (INTEGRATION / "www" / "viewpie-layout-editor.js").read_text(encoding="utf-8")
        self.assertIn("_loadStoredCameraPreviews", editor)
        self.assertIn("&refresh=1", editor)

    def test_layout_editor_serializes_adjacent_same_camera_cells_as_one_viewport(self):
        source = (INTEGRATION / "www" / "viewpie-layout-editor.js").read_text(encoding="utf-8")
        self.assertIn("const height = bottom - top + 1", source)
        self.assertIn("const width = right - left + 1", source)
        self.assertIn("matrix[r][c] = slot;", source)
        self.assertIn("viewports.push({ slot, feeds: [region.camera] });", source)
        self.assertIn('layout: matrix.map(row => row.join(" ")).join("\\n")', source)
        self.assertIn("должны образовывать один сплошной прямоугольник", source)

    def test_dedicated_view_selector_is_separate_and_refreshes_dynamic_lists(self):
        source = (INTEGRATION / "__init__.py").read_text(encoding="utf-8")
        self.assertIn('("viewpie-view-selector.js", "/viewpie/viewpie-view-selector.js", "view selector")', source)
        card = (INTEGRATION / "www" / "viewpie-view-selector.js").read_text(encoding="utf-8")
        self.assertIn('customElements.define("viewpie-view-selector"', card)
        self.assertIn('this._hass.callService("homeassistant", "update_entity"', card)
        self.assertIn('this._panels.forEach', card)
        self.assertIn('this._cameras.forEach', card)
        self.assertIn('async _choosePanel(panelId)', card)
        self.assertIn('async _chooseCamera(camera)', card)
        self.assertNotIn('manage_camera', card)
        self.assertNotIn('RTSP URL', card)
        self.assertIn("this._activeCamera()", card)
        self.assertIn("this._activePanel()", card)

    def test_three_viewpie_cards_have_separate_responsibilities(self):
        selector = (INTEGRATION / "www" / "viewpie-view-selector.js").read_text(encoding="utf-8")
        layout = (INTEGRATION / "www" / "viewpie-layout-editor.js").read_text(encoding="utf-8")
        manager = (INTEGRATION / "www" / "viewpie-camera-manager.js").read_text(encoding="utf-8")
        self.assertIn("choice-list", selector)
        self.assertIn("choice-row", selector)
        self.assertIn('class: "choice-row" + (active ? " active" : "")', selector)
        self.assertNotIn("_renderCameraManager", layout)
        self.assertNotIn("manage_camera", layout)
        self.assertIn('title:"Создать панель"', layout)
        self.assertIn("Добавить камеру", manager)
        self.assertNotIn("_selectPanel", manager)
        self.assertNotIn("_selectCamera", manager)


    def test_all_viewpie_cards_support_visual_lovelace_configuration(self):
        editor = (INTEGRATION / "www" / "viewpie-card-editor.js").read_text(encoding="utf-8")
        self.assertIn('customElements.define("viewpie-card-config-editor"', editor)
        self.assertIn('new CustomEvent("config-changed"', editor)
        self.assertIn('"title"', editor)
        for filename in ("viewpie-view-selector.js", "viewpie-layout-editor.js", "viewpie-camera-manager.js"):
            source = (INTEGRATION / "www" / filename).read_text(encoding="utf-8")
            self.assertIn("static getConfigElement()", source)
            self.assertIn("static getStubConfig()", source)
            self.assertIn('document.createElement("viewpie-card-config-editor")', source)
        init = (INTEGRATION / "__init__.py").read_text(encoding="utf-8")
        self.assertIn('("viewpie-card-editor.js", "/viewpie/viewpie-card-editor.js"', init)

    def test_panel_names_are_displayed_and_ids_are_generated_from_names(self):
        selector = (INTEGRATION / "www" / "viewpie-view-selector.js").read_text(encoding="utf-8")
        layout = (INTEGRATION / "www" / "viewpie-layout-editor.js").read_text(encoding="utf-8")
        self.assertIn("_panelLabel(panelId)", selector)
        self.assertIn("this._panelLabel(id)", selector)
        self.assertNotIn("Технический ID", layout)
        self.assertIn("_slugifyPanelName", layout)
        self.assertIn("_generatePanelId", layout)
        self.assertIn('ё:"yo"', layout)
        self.assertNotIn('ID новой панели', layout)

    def test_panel_and_camera_select_entities_are_mutually_exclusive(self):
        select_source = (INTEGRATION / "select.py").read_text(encoding="utf-8")
        self.assertIn('if self.status.get("fullscreen_camera"):', select_source)
        self.assertIn('return None', select_source)
        coordinator = (INTEGRATION / "coordinator.py").read_text(encoding="utf-8")
        panel_method = coordinator[coordinator.index("    async def async_activate_panel"):coordinator.index("    async def async_update_settings")]
        self.assertLess(panel_method.index("await self.client.grid()"), panel_method.index("await self.client.activate_panel(panel_id)"))

    def test_camera_management_ui_and_confirmed_delete_are_present(self):
        source = (INTEGRATION / "www" / "viewpie-camera-manager.js").read_text(encoding="utf-8")
        for label in ('"Добавить камеру"', '"Сохранить изменения"', '"Проверить RTSP"', '"Удалить камеру"'):
            self.assertIn(label, source)
        self.assertIn("window.confirm(", source)
        self.assertNotIn("_selectPanel", source)
        self.assertNotIn("_selectCamera", source)
        init = (INTEGRATION / "__init__.py").read_text(encoding="utf-8")
        self.assertIn("await client.delete_camera(name)", init)
        camera_handler = init[init.index("    async def handle_manage_camera"):init.index("    async def handle_get_camera")]
        self.assertIn('call.data.get("decoder", "auto")', camera_handler)
        self.assertNotIn("await client.reload_config()", camera_handler)
        camera_service = init[init.index('DOMAIN, "manage_camera"'):init.index('DOMAIN, "test_camera"')]
        self.assertIn('vol.Optional("decoder", default="auto")', camera_service)
        self.assertIn("supports_response=SupportsResponse.ONLY", init)
        self.assertIn("supports_response=SupportsResponse.OPTIONAL", init)

    def test_panel_mutations_reload_viewpie_config(self):
        source = (INTEGRATION / "__init__.py").read_text(encoding="utf-8")
        panel_handler = source[source.index("    async def handle_manage_panel"):source.index("    hass.services.async_register(")]
        self.assertIn("await coordinator.async_reload_config()", panel_handler)

    def test_layout_editor_unwraps_panel_dto_before_loading(self):
        source = (INTEGRATION / "www" / "viewpie-layout-editor.js").read_text(encoding="utf-8")
        self.assertIn("const panel = response?.panel || response;", source)


    def test_panel_update_restores_previously_active_panel_after_reload(self):
        source = (INTEGRATION / "__init__.py").read_text(encoding="utf-8")
        handler = source[source.index("    async def handle_manage_panel"):source.index("    hass.services.async_register(")]
        self.assertIn("previous_active_panel = None", handler)
        self.assertIn("status = await client.get_status()", handler)
        self.assertIn("await client.activate_panel(str(previous_active_panel))", handler)

    def test_editor_only_allows_square_merged_regions(self):
        source = (INTEGRATION / "www" / "viewpie-layout-editor.js").read_text(encoding="utf-8")
        self.assertIn("if (cells.length > 1 && height !== width)", source)
        self.assertIn("Прямоугольные объединения запрещены", source)

    def test_rotation_interval_entity_is_not_created(self):
        source = (INTEGRATION / "number.py").read_text(encoding="utf-8")
        setup = source[source.index("async def async_setup_entry"):source.index("class ViewpieNumberBase")]
        self.assertNotIn("ViewpieRotationIntervalNumber(coordinator)", setup)

    def test_view_selector_finds_screen_switch_with_composed_friendly_name(self):
        card = (INTEGRATION / "www" / "viewpie-view-selector.js").read_text(encoding="utf-8")
        self.assertIn('s.attributes?.icon === "mdi:pause-circle"', card)
        self.assertIn('.toLowerCase().includes("экран")', card)
        self.assertIn('s.entity_id.endsWith("_pause")', card)
        self.assertNotIn('friendly_name || "").trim().toLowerCase() === "экран"', card)

    def test_camera_and_panel_selection_wake_a_paused_screen_first(self):
        source = (INTEGRATION / "coordinator.py").read_text(encoding="utf-8")
        wake = source[source.index("    async def _async_ensure_screen_on"):source.index("    async def async_update_settings")]
        self.assertIn('get("paused", False)', wake)
        self.assertIn("await self.client.resume()", wake)
        self.assertLess(wake.index("await self._async_ensure_screen_on()"), wake.index("await self.client.fullscreen(camera, duration)"))
        self.assertLess(wake.index("await self._async_ensure_screen_on()"), wake.index("await self.client.grid()"))
        self.assertLess(wake.index("await self.client.grid()"), wake.index("await self.client.activate_panel(panel_id)"))

    def test_screen_switch_uses_screen_on_semantics(self):
        source = (INTEGRATION / "switch.py").read_text(encoding="utf-8")
        screen = source[source.index("class ViewpiePauseSwitch"):source.index("class ViewpiePauseOffScreenSwitch")]
        self.assertIn("return not bool(self.status.get(\"paused\", False))", screen)
        self.assertIn("await self.coordinator.async_resume()", screen)
        self.assertIn("await self.coordinator.async_pause()", screen)

    def test_system_manager_matches_device_prefixed_entities_and_opens_history(self):
        source = (INTEGRATION / "www" / "viewpie-system-manager.js").read_text(encoding="utf-8")
        self.assertIn("state.attributes?.viewpie_entry_id", source)
        self.assertIn("name.endsWith(` ${alias}`)", source)
        self.assertIn('item.entity_id.split(".").pop()', source)
        self.assertIn('new CustomEvent("hass-more-info"', source)
        self.assertIn("detail: {entityId: rowData.state.entity_id}", source)
        self.assertNotIn("state.attributes?.config_entry_id", source)

    def test_decoder_count_sensors_are_recorded_for_history(self):
        source = (INTEGRATION / "sensor.py").read_text(encoding="utf-8")
        decoder_counts = source[source.index("class ViewpieDecoderCountSensor"):source.index("class ViewpieHardwareDecoderCountSensor")]
        self.assertIn("SensorStateClass.MEASUREMENT", decoder_counts)
        entity = (INTEGRATION / "entity.py").read_text(encoding="utf-8")
        self.assertIn('"viewpie_entry_id": coordinator.entry.entry_id', entity)

    def test_system_manager_card_contains_update_controls(self):
        source = (INTEGRATION / "www" / "viewpie-system-manager.js").read_text(encoding="utf-8")
        self.assertIn("Обновление Viewpie", source)
        self.assertIn("Проверить обновления", source)
        self.assertIn("Установить обновление", source)
        self.assertIn("window.confirm(", source)

    def test_viewpie_client_uses_shared_restart_token_for_api_auth(self):
        source = (INTEGRATION / "__init__.py").read_text(encoding="utf-8")
        self.assertIn("entry.options.get(CONF_RESTART_TOKEN)", source)
        self.assertIn("entry.data.get(CONF_RESTART_TOKEN)", source)
        self.assertIn("entry.data.get(CONF_API_KEY)", source)
        flow = (INTEGRATION / "config_flow.py").read_text(encoding="utf-8")
        self.assertIn("auth_token = restart_token or api_key", flow)
        self.assertIn('errors["base"] = "missing_api_token"', flow)

    def test_initial_setup_accepts_optional_restart_update_token(self):
        source = (INTEGRATION / "config_flow.py").read_text(encoding="utf-8")
        self.assertIn('vol.Optional(CONF_RESTART_TOKEN, default=""): str', source)
        self.assertIn('CONF_RESTART_TOKEN: (user_input.get(CONF_RESTART_TOKEN) or "").strip()', source)

    def test_debug_overlay_switch_is_wired_to_native_display_setting(self):
        source = (INTEGRATION / "switch.py").read_text(encoding="utf-8")
        self.assertIn("ViewpieDebugOverlaySwitch(coordinator)", source)
        self.assertIn('"debug_overlay" in (', source)
        self.assertIn('async_update_settings(debug_overlay=True)', source)
        self.assertIn('async_update_settings(debug_overlay=False)', source)
        native_settings = (INTEGRATION / "coordinator.py").read_text(encoding="utf-8")
        self.assertIn("async def async_update_settings", native_settings)


    def test_update_client_and_buttons_are_wired(self):
        api = (INTEGRATION / "api_client.py").read_text(encoding="utf-8")
        button = (INTEGRATION / "button.py").read_text(encoding="utf-8")
        self.assertIn("async def check_update", api)
        self.assertIn("async def install_update", api)
        self.assertIn("ViewpieCheckUpdatesButton(coordinator)", button)
        self.assertIn("ViewpieInstallUpdateButton(coordinator)", button)


    def test_startup_panel_select_is_available_only_with_native_setting(self):
        source = (INTEGRATION / "select.py").read_text(encoding="utf-8")
        self.assertIn("ViewpieStartupPanelSelect(coordinator)", source)
        self.assertIn('"startup_panel" in (self.coordinator.data or {})', source)
        self.assertIn("async_update_settings(startup_panel=option)", source)

    def test_panel_order_is_exposed_through_validated_service_and_api(self):
        api = (INTEGRATION / "api_client.py").read_text(encoding="utf-8")
        coordinator = (INTEGRATION / "coordinator.py").read_text(encoding="utf-8")
        init = (INTEGRATION / "__init__.py").read_text(encoding="utf-8")
        card = (INTEGRATION / "www" / "viewpie-view-selector.js").read_text(encoding="utf-8")
        self.assertIn('f"{API_PANELS}/order"', api)
        self.assertIn('async def reorder_panels(self, order: list[str])', api)
        self.assertIn('async def async_reorder_panels(self, order: list[str])', coordinator)
        self.assertIn('DOMAIN, "reorder_panels", handle_reorder_panels', init)
        self.assertIn('set(order) != expected', init)
        self.assertIn('callService("viewpie", "reorder_panels"', card)
        self.assertIn('async _movePanel(panelId, delta)', card)

    def test_startup_panel_setting_is_in_system_management_card(self):
        selector = (INTEGRATION / "www" / "viewpie-view-selector.js").read_text(encoding="utf-8")
        manager = (INTEGRATION / "www" / "viewpie-system-manager.js").read_text(encoding="utf-8")
        self.assertNotIn("startupPanel", selector)
        self.assertIn('startupPanel: findNamed("select", ["стартовая панель"])', manager)
        screen_mode = manager.index('addSelectControl("После подачи питания на экран"')
        startup_panel = manager.index('addSelectControl("Панель при запуске"')
        self.assertLess(screen_mode, startup_panel)

    def test_update_console_is_cleared_for_each_new_installation(self):
        source = (INTEGRATION / "www" / "viewpie-system-manager.js").read_text(encoding="utf-8")
        self.assertIn("this._terminalClearPending = true", source)
        self.assertIn("this._terminalClearBaselineStartedAt", source)
        self.assertIn("Предыдущий журнал очищен", source)
        self.assertIn("this._terminalClearPending = false", source)
        self.assertIn('copyLog.disabled = waitingForNewUpdate', source)


    def test_update_install_keeps_entities_available_during_api_restart(self):
        coordinator = (INTEGRATION / "coordinator.py").read_text(encoding="utf-8")
        self.assertIn("self._update_install_pending = True", coordinator)
        self.assertIn("self._update_install_baseline_started_at", coordinator)
        self.assertIn('"status": "starting"', coordinator)
        self.assertIn("return dict(self.data)", coordinator)
        self.assertIn("self._update_journal_poll_attempts = 90", coordinator)
        self.assertIn("Ignore the previous run while waiting", coordinator)
        self.assertIn("previous = (self.data or {}).get(\"update_status\", {})", coordinator)

    def test_layout_editor_uses_camera_table_and_start_cell_size_constraints(self):
        source = (INTEGRATION / "www" / "viewpie-layout-editor.js").read_text(encoding="utf-8")
        self.assertIn("_renderCameraPicker", source)
        self.assertIn('this._el("th", {}, "Название камеры")', source)
        self.assertIn('class: "picker-camera"', source)
        self.assertIn('this._el("img", { alt: `Превью ${camera}` })', source)
        self.assertIn("Панели, где используется", source)
        self.assertIn("_allowedCameraSpans", source)
        self.assertIn("for (const side of [1, 2, 3, 4])", source)
        self.assertIn("row + side > this._rows || col + side > this._cols", source)
        self.assertIn("const candidateCells = []", source)
        self.assertNotIn("select.title = \"Выберите одну камеру", source)

    def test_update_button_tracks_running_and_installed_versions(self):
        card = (INTEGRATION / "www" / "viewpie-system-manager.js").read_text(encoding="utf-8")
        self.assertIn("Идёт установка", card)
        self.assertIn("Установлена ", card)
        self.assertIn('installJournal.status === "failed"', card)
        self.assertIn("installedVersion || latestVersion", card)
        self.assertIn('["starting", "running"].includes(installJournal.status)', card)
        coordinator = (INTEGRATION / "coordinator.py").read_text(encoding="utf-8")
        self.assertIn("async_start_update_checks", coordinator)
        self.assertIn("timedelta(hours=6)", coordinator)
        self.assertIn("_async_periodic_update_check(None)", coordinator)
        self.assertIn("manual_check_required", card)
        sensor = (INTEGRATION / "sensor.py").read_text(encoding="utf-8")
        self.assertIn('"manual_check_required"', sensor)


    def test_layout_editor_allows_geometric_merge_and_confirms_overwrite(self):
        source = (INTEGRATION / "www" / "viewpie-layout-editor.js").read_text(encoding="utf-8")
        self.assertIn("const overlappingRegions = regions.filter", source)
        self.assertIn("Затереть и продолжить", source)
        self.assertIn("Отменить", source)
        self.assertIn("overlappingRegions.forEach(region", source)
        self.assertNotIn("if (!free) continue", source)

    def test_camera_preview_sends_home_assistant_access_token(self):
        source = (INTEGRATION / "www" / "viewpie-layout-editor.js").read_text(encoding="utf-8")
        self.assertIn("this._hass?.auth?.data?.access_token", source)
        self.assertIn("Authorization: `Bearer ${accessToken}`", source)



    def test_layout_editor_supports_16x16_and_compact_controls_follow_create(self):
        source = (INTEGRATION / "www" / "viewpie-layout-editor.js").read_text(encoding="utf-8")
        self.assertIn("this._clamp(config.rows ?? 2, 1, 16)", source)
        self.assertIn('max:"16"', source)
        self.assertIn("Размер квадратной сетки (1–16)", source)
        self.assertIn("layout.slice(0, 16).forEach((row, r) => row.slice(0, 16)", source)
        self.assertIn('title:"Создать панель"}, "Создать")', source)
        self.assertIn("panelButtons.append(sizeControls)", source)
        self.assertNotIn("card.append(sizeControls)", source)
        self.assertIn(".panel-size button{box-sizing:border-box;flex:0 0 46%", source)
        self.assertIn(".panel-button.add{font-size:clamp(10px,12cqi,16px)}", source)

    def test_view_selector_keeps_two_wide_actions_and_three_column_choices(self):
        source = (INTEGRATION / "www" / "viewpie-view-selector.js").read_text(encoding="utf-8")
        self.assertIn(".top-actions button{grid-column:span 3", source)
        self.assertIn(".choice-list{display:grid;grid-template-columns:repeat(3,minmax(0,1fr))", source)
        self.assertIn("Выключить экран", source)
        self.assertIn("Обновить", source)

    def test_system_manager_places_startup_panel_after_screen_boot_mode_and_groups_updates(self):
        source = (INTEGRATION / "www" / "viewpie-system-manager.js").read_text(encoding="utf-8")
        self.assertLess(source.index('addSelectControl("После подачи питания на экран"'),
                        source.index('addSelectControl("Панель при запуске"'))
        self.assertIn(".update-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr))", source)
        self.assertIn('viewpieColumnTitle.textContent = "Обновление ViewPie"', source)
        self.assertIn('integrationColumnTitle.textContent = "Обновление интеграции"', source)
        self.assertIn('integrationInstall.textContent = "Обновить"', source)
        self.assertIn("restartPiButton.textContent = \"Перезагрузить Raspberry Pi\"", source)
        self.assertIn('restartHa.textContent = "Перезапустить HA"', source)

    def test_integration_update_discovery_handles_callws_payload_and_falls_back_to_hacs(self):
        source = (INTEGRATION / "www" / "viewpie-system-manager.js").read_text(encoding="utf-8")
        self.assertIn("const normalizeRepositoryList = response =>", source)
        self.assertIn("const payload = response?.result ?? response", source)
        self.assertIn("if (Array.isArray(payload)) return payload", source)
        self.assertIn('type: "marketplace/repositories/list"', source)
        self.assertIn('type: "hacs/repositories/list"', source)
        self.assertIn('String(item.full_name || "").trim().toLowerCase()', source)
        self.assertIn("candidate && candidate.installed === true", source)
        self.assertIn("for (const manager of managers)", source)
        self.assertIn('type:"marketplace/repository/install"', source)
        self.assertIn('type:"hacs/repository/download"', source)

if __name__ == "__main__":
    unittest.main()


    def test_system_manager_exposes_live_settings_and_formats_uptime(self):
        source = (INTEGRATION / "www" / "viewpie-system-manager.js").read_text(encoding="utf-8")
        for required in (
            'callService("switch"',
            'callService("number", "set_value"',
            'callService("select", "select_option"',
            "Количество аппаратных декодеров",
            "После подачи питания на экран",
            'row.label === "Uptime"',
        ):
            with self.subTest(required=required):
                self.assertIn(required, source)


    def test_update_console_formats_timestamps_in_home_assistant_timezone_and_scrolls_to_latest_line(self):
        source = (INTEGRATION / "www" / "viewpie-system-manager.js").read_text(encoding="utf-8")
        self.assertIn('this._hass?.config?.time_zone', source)
        self.assertIn('new Intl.DateTimeFormat("ru-RU"', source)
        self.assertIn('formatter.format(date)', source)
        self.assertIn('this._formatUpdateLog(journal.log', source)
        self.assertIn('requestAnimationFrame(() =>', source)
        self.assertIn('terminalLog.scrollTop = terminalLog.scrollHeight', source)
        self.assertNotIn('wasAtBottom', source)
