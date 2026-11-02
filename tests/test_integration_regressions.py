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
        self.assertEqual(manifest["version"], "1.0.8")
        entity = (INTEGRATION / "entity.py").read_text(encoding="utf-8")
        self.assertIn('manufacturer": "Viewpie"', entity)
        self.assertNotIn("AI-generated integration", entity)
        self.assertTrue((INTEGRATION / "brand" / "icon.png").is_file())

    def test_installed_software_version_and_build_date_sensors_are_exposed(self):
        source = (INTEGRATION / "sensor.py").read_text(encoding="utf-8")
        self.assertIn("ViewpieSoftwareVersionSensor(coordinator)", source)
        self.assertIn("ViewpieSoftwareBuildDateSensor(coordinator)", source)
        self.assertIn('_key = "software_version"', source)
        self.assertIn('_key = "software_build_date"', source)
        entity = (INTEGRATION / "entity.py").read_text(encoding="utf-8")
        self.assertIn('status.get("software_version")', entity)
        self.assertIn('device_info["sw_version"]', entity)


if __name__ == "__main__":
    unittest.main()
