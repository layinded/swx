# pyright: reportAny=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false

from unittest.mock import AsyncMock, patch

import pytest

from swx_core.models.system_config import SettingValueType
from swx_core.services.settings_crud_service import validate_setting_value
from swx_core.services.settings_service import SettingsService, _unwrap_scalar


@pytest.fixture
def svc() -> SettingsService:
    return SettingsService(session=AsyncMock())


class TestUnwrapScalar:
    def test_single_key_dict_returns_value(self):
        assert _unwrap_scalar({"threshold": 0.7}) == 0.7

    def test_single_key_dict_with_int_value(self):
        assert _unwrap_scalar({"max_length": 50000}) == 50000

    def test_single_key_dict_with_bool_value(self):
        assert _unwrap_scalar({"enabled": True}) is True

    def test_single_key_dict_with_string_value(self):
        assert _unwrap_scalar({"name": "test"}) == "test"

    def test_multi_key_dict_returned_unchanged(self):
        d = {"a": 1, "b": 2}
        assert _unwrap_scalar(d) is d

    def test_empty_dict_returned_unchanged(self):
        d: dict[str, int] = {}
        assert _unwrap_scalar(d) is d

    def test_non_dict_returned_unchanged(self):
        assert _unwrap_scalar(42) == 42
        assert _unwrap_scalar("hello") == "hello"
        assert _unwrap_scalar(0.75) == 0.75
        assert _unwrap_scalar(None) is None
        assert _unwrap_scalar(True) is True

    def test_list_returned_unchanged(self):
        lst = [1, 2, 3]
        assert _unwrap_scalar(lst) is lst


class TestConvertValueFloat:
    def test_float_bare_float(self, svc: SettingsService):
        assert svc._convert_value(0.7, SettingValueType.FLOAT) == 0.7

    def test_float_bare_int(self, svc: SettingsService):
        assert svc._convert_value(5, SettingValueType.FLOAT) == 5.0

    def test_float_string(self, svc: SettingsService):
        assert svc._convert_value("0.75", SettingValueType.FLOAT) == 0.75

    def test_float_wrapped_dict(self, svc: SettingsService):
        assert svc._convert_value({"threshold": 0.7}, SettingValueType.FLOAT) == 0.7

    def test_float_wrapped_dict_int_value(self, svc: SettingsService):
        assert svc._convert_value({"value": 3}, SettingValueType.FLOAT) == 3.0

    def test_float_invalid_string_returns_zero(self, svc: SettingsService):
        assert svc._convert_value("not-a-float", SettingValueType.FLOAT) == 0.0

    def test_float_none_returns_zero(self, svc: SettingsService):
        assert svc._convert_value(None, SettingValueType.FLOAT) == 0.0

    def test_float_bool_converted_to_float(self, svc: SettingsService):
        result = svc._convert_value(True, SettingValueType.FLOAT)
        assert isinstance(result, float)
        assert result == 1.0


class TestConvertValueIntUnwrapping:
    def test_int_wrapped_dict_extracts_value(self, svc: SettingsService):
        assert svc._convert_value({"max_length": 50000}, SettingValueType.INT) == 50000

    def test_int_bare_int_unchanged(self, svc: SettingsService):
        assert svc._convert_value(42, SettingValueType.INT) == 42

    def test_int_string_converted(self, svc: SettingsService):
        assert svc._convert_value("42", SettingValueType.INT) == 42

    def test_integer_alias_same_as_int(self, svc: SettingsService):
        assert svc._convert_value({"max_length": 50000}, SettingValueType.INTEGER) == 50000
        assert svc._convert_value(42, SettingValueType.INTEGER) == 42
        assert svc._convert_value("42", SettingValueType.INTEGER) == 42

    def test_int_invalid_returns_zero(self, svc: SettingsService):
        assert svc._convert_value("not-a-number", SettingValueType.INT) == 0


class TestConvertValueBoolUnwrapping:
    def test_bool_wrapped_dict_extracts_value(self, svc: SettingsService):
        assert svc._convert_value({"enabled": True}, SettingValueType.BOOL) is True

    def test_boolean_alias_same_as_bool(self, svc: SettingsService):
        assert svc._convert_value({"enabled": True}, SettingValueType.BOOLEAN) is True
        assert svc._convert_value(True, SettingValueType.BOOLEAN) is True
        assert svc._convert_value("true", SettingValueType.BOOLEAN) is True

    def test_bool_bare_bool_unchanged(self, svc: SettingsService):
        assert svc._convert_value(False, SettingValueType.BOOL) is False


class TestConvertValueStringUnwrapping:
    def test_string_wrapped_dict_extracts_value(self, svc: SettingsService):
        assert svc._convert_value({"name": "test"}, SettingValueType.STRING) == "test"

    def test_string_bare_string_unchanged(self, svc: SettingsService):
        assert svc._convert_value("hello", SettingValueType.STRING) == "hello"


class TestConvertValueJsonNoUnwrap:
    def test_json_dict_not_unwrapped(self, svc: SettingsService):
        d = {"threshold": 0.7}
        assert svc._convert_value(d, SettingValueType.JSON) == d

    def test_json_multi_key_dict_not_unwrapped(self, svc: SettingsService):
        d = {"a": 1, "b": 2}
        assert svc._convert_value(d, SettingValueType.JSON) == d

    def test_json_string_parsed(self, svc: SettingsService):
        assert svc._convert_value('{"key": "val"}', SettingValueType.JSON) == {"key": "val"}


class TestConvertValueNoneType:
    def test_none_value_type_returns_value_unchanged(self, svc: SettingsService):
        assert svc._convert_value({"threshold": 0.7}, None) == {"threshold": 0.7}
        assert svc._convert_value(42, None) == 42


class TestGetFloat:
    @pytest.mark.asyncio
    async def test_get_float_returns_float(self):
        svc = SettingsService(session=AsyncMock())
        with patch.object(svc, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = 0.75
            result = await svc.get_float("detection.threshold", default=0.0)
            assert result == 0.75
            mock_get.assert_awaited_once_with(
                "detection.threshold", 0.0, SettingValueType.FLOAT
            )

    @pytest.mark.asyncio
    async def test_get_float_default_when_none(self):
        svc = SettingsService(session=AsyncMock())
        with patch.object(svc, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None
            result = await svc.get_float("missing.key", default=0.5)
            assert result == 0.5

    @pytest.mark.asyncio
    async def test_get_float_converts_int_to_float(self):
        svc = SettingsService(session=AsyncMock())
        with patch.object(svc, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = 3
            result = await svc.get_float("some.int", default=0.0)
            assert isinstance(result, float)
            assert result == 3.0


class TestValidateSettingValue:
    def test_float_valid_float(self):
        assert validate_setting_value(0.7, SettingValueType.FLOAT) is True

    def test_float_valid_int(self):
        assert validate_setting_value(5, SettingValueType.FLOAT) is True

    def test_float_valid_string(self):
        assert validate_setting_value("0.75", SettingValueType.FLOAT) is True

    def test_float_invalid_string(self):
        assert validate_setting_value("not-a-float", SettingValueType.FLOAT) is False

    def test_integer_alias_valid(self):
        assert validate_setting_value(42, SettingValueType.INTEGER) is True
        assert validate_setting_value("42", SettingValueType.INTEGER) is True

    def test_integer_alias_invalid(self):
        assert validate_setting_value("abc", SettingValueType.INTEGER) is False

    def test_boolean_alias_valid(self):
        assert validate_setting_value(True, SettingValueType.BOOLEAN) is True
        assert validate_setting_value("true", SettingValueType.BOOLEAN) is True
        assert validate_setting_value("false", SettingValueType.BOOLEAN) is True

    def test_boolean_alias_invalid(self):
        assert validate_setting_value("maybe", SettingValueType.BOOLEAN) is False

    def test_int_still_valid(self):
        assert validate_setting_value(42, SettingValueType.INT) is True

    def test_bool_still_valid(self):
        assert validate_setting_value(True, SettingValueType.BOOL) is True

    def test_json_still_valid(self):
        assert validate_setting_value({"a": 1}, SettingValueType.JSON) is True
        assert validate_setting_value('[1, 2]', SettingValueType.JSON) is True
