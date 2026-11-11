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
        self.assertEqual(manifest["version"], "1.2.6")
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

    def test_installed_software_version_and_build_date_sensors_are_exposed(self):
        source = (INTEGRATION / "sensor.py").read_text(encoding="utf-8")
        self.assertIn("ViewpieSoftwareVersionSensor(coordinator)", source)
        self.assertIn("ViewpieSoftwareBuildDateSensor(coordinator)", source)
        self.assertIn('_key = "software_version"', source)
        self.assertIn('_key = "software_build_date"', source)
        entity = (INTEGRATION / "entity.py").read_text(encoding="utf-8")
        self.assertIn('status.get("software_version")', entity)
        self.assertIn('device_info["sw_version"]', entity)


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
        self.assertIn("Переключить", selector)
        self.assertNotIn("_renderCameraManager", layout)
        self.assertNotIn("manage_camera", layout)
        self.assertIn("Создать панель", layout)
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
        self.assertIn("Технический ID", layout)
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

if __name__ == "__main__":
    unittest.main()
