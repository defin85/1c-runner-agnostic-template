"""Catalog description checking must not change other generated attributes."""

import tests.python.metadata_test_support  # noqa: F401, I001 — runs first: skips the module without pytest, lxml, jsonschema
import uuid

import pytest
from jsonschema import Draft202012Validator, ValidationError
import lxml.etree as etree

from scripts.python import metadata_create, metadata_object_schema


def test_description_fill_checking():
    definition = {"type": "Catalog", "name": "Бюджеты"}
    schema = Draft202012Validator(metadata_object_schema.CREATE_DEFINITION)
    for checking in (None, "DontCheck", "ShowError", "ShowWarning"):
        value = dict(definition)
        if checking is not None:
            value["descriptionFillChecking"] = checking
        schema.validate(value)
        xml = etree.fromstring(metadata_create.render_object(value, str(uuid.uuid4()), {}))
        for attribute in xml.xpath("//*[local-name()='StandardAttribute']"):
            actual = attribute.xpath("string(*[local-name()='FillChecking'])")
            assert actual == ((checking or "DontCheck") if attribute.get("name") == "Description" else "DontCheck")
    with pytest.raises(ValidationError):
        schema.validate({**definition, "descriptionFillChecking": "invalid"})
