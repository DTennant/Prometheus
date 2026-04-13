import pytest
from prometheus.config.harness_config import HarnessConfig, HarnessParameters
from prometheus.config.experiment_config import ExperimentConfig
from prometheus.config.schema_validator import validate_harness_config


class TestHarnessConfig:
    def test_default_construction(self):
        config = HarnessConfig(system_prompt="test")
        assert config.system_prompt == "test"
        assert config.generation == 0

    def test_json_roundtrip(self):
        config = HarnessConfig(system_prompt="test prompt")
        json_str = config.model_dump_json()
        restored = HarnessConfig.model_validate_json(json_str)
        assert restored.system_prompt == config.system_prompt

    def test_frozen_rejects_mutation(self):
        config = HarnessConfig(system_prompt="test")
        with pytest.raises(Exception):
            config.system_prompt = "changed"

    def test_model_copy_creates_new(self):
        config = HarnessConfig(system_prompt="original")
        new = config.model_copy(update={"system_prompt": "modified"})
        assert new.system_prompt == "modified"
        assert config.system_prompt == "original"

    def test_parameter_bounds(self):
        with pytest.raises(Exception):
            HarnessParameters(max_iterations=0)
        with pytest.raises(Exception):
            HarnessParameters(temperature=3.0)


class TestExperimentConfig:
    def test_default_construction(self):
        config = ExperimentConfig()
        assert config.generations == 20

    def test_field_validation(self):
        with pytest.raises(Exception):
            ExperimentConfig(generations=0)


class TestSchemaValidator:
    def test_valid_config(self):
        config = HarnessConfig(system_prompt="valid prompt")
        assert validate_harness_config(config) == []

    def test_empty_prompt(self):
        config = HarnessConfig(system_prompt="   ")
        errors = validate_harness_config(config)
        assert any("empty" in e for e in errors)

    def test_long_prompt(self):
        config = HarnessConfig(system_prompt="x" * 10001)
        errors = validate_harness_config(config)
        assert any("exceeds" in e for e in errors)
