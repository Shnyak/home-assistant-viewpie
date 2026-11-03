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

    def test_camera_entities_are_created_dynamically(self):
        source = (INTEGRATION / "binary_sensor.py").read_text(encoding="utf-8")
        self.assertIn("coordinator.async_add_listener(add_camera_entities)", source)
        self.assertIn("ViewpieCameraRunningBinarySensor", source)
        self.assertIn("ViewpieCameraInUseBinarySensor", source)

    def test_editor_resource_registration_is_idempotent_and_storage_only(self):
        source = (INTEGRATION / "__init__.py").read_text(encoding="utf-8")
        self.assertIn('resources.async_items()', source)
        self.assertIn('resources.async_create_item({"res_type": "module", "url": url_path})', source)
        self.assertIn('hasattr(resources, "async_create_item")', source)
        manifest = __import__("json").loads((INTEGRATION / "manifest.json").read_text(encoding="utf-8"))
        self.assertIn("lovelace", manifest["dependencies"])
        self.assertIn("http", manifest["dependencies"])

    def test_integration_metadata_and_branding(self):
        import json

        manifest = json.loads((INTEGRATION / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["version"], "1.1.0")
        entity = (INTEGRATION / "entity.py").read_text(encoding="utf-8")
        self.assertIn('manufacturer": "Viewpie"', entity)
        self.assertNotIn("AI-generated integration", entity)
        self.assertTrue((INTEGRATION / "brand" / "icon.png").is_file())


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
        self.assertIn("const area = (bottom - top + 1) * (right - left + 1)", source)
        self.assertIn("matrix[r][c] = slot;", source)
        self.assertIn("viewports.push({ slot, feeds: [region.camera] });", source)
        self.assertIn('layout: matrix.map(row => row.join(" ")).join("\\n")', source)
        self.assertIn("должны образовывать один сплошной прямоугольник", source)

    def test_camera_management_ui_and_confirmed_delete_are_present(self):
        source = (INTEGRATION / "www" / "viewpie-layout-editor.js").read_text(encoding="utf-8")
        self.assertIn("_renderCameraManager(card)", source)
        for label in ('"Добавить камеру"', '"Сохранить изменения"', '"Проверить RTSP"', '"Удалить камеру"'):
            self.assertIn(label, source)
        self.assertIn("window.confirm(", source)
        init = (INTEGRATION / "__init__.py").read_text(encoding="utf-8")
        self.assertIn("await client.delete_camera(name)", init)
        self.assertIn("await client.reload_config()", init)
        self.assertIn("supports_response=SupportsResponse.ONLY", init)
        self.assertIn("supports_response=SupportsResponse.OPTIONAL", init)

    def test_panel_mutations_reload_viewpie_config(self):
        source = (INTEGRATION / "__init__.py").read_text(encoding="utf-8")
        panel_handler = source[source.index("    async def handle_manage_panel"):source.index("    hass.services.async_register(")]
        self.assertIn("await coordinator.async_reload_config()", panel_handler)

    def test_layout_editor_unwraps_panel_dto_before_loading(self):
        source = (INTEGRATION / "www" / "viewpie-layout-editor.js").read_text(encoding="utf-8")
        self.assertIn("const panel = response?.panel || response;", source)


if __name__ == "__main__":
    unittest.main()
