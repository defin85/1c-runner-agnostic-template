"""Identity allocation leaves original trees unchanged and fails on collisions."""

import tests.python.metadata_test_support  # noqa: F401, I001 — runs first: skips the module without pytest, lxml, jsonschema
import uuid

import pytest
import lxml.etree as etree

from scripts.python import metadata as editor


ROOT_UUID = "280179ba-92e8-47b4-b0b2-e9bcece0df19"


def test_uuid_repeat_preservation_and_namespace():
    inventory = {}
    key = ("Catalog", "Catalog.Демо_Заказы", "object")
    first = editor.allocate_uuid(ROOT_UUID, *key, inventory)
    assert uuid.UUID(first).version == 5
    assert editor.allocate_uuid(ROOT_UUID, *key, inventory) == first
    assert editor.allocate_uuid(ROOT_UUID, *key, {}) == first
    other_root = "65902944-63ec-4bb7-883d-55a72d162598"
    assert editor.allocate_uuid(other_root, *key, {}) != first
    assert editor.allocate_uuid(ROOT_UUID, key[0], key[1], "generatedType", {}) != first
    previous = "c16aefea-c3c2-4fa3-9d50-e91d736d223a"
    assert editor.allocate_uuid(ROOT_UUID, *key, {key: previous}) == previous


def test_uuid_collision_rejected_before_inventory_mutation():
    key = ("Catalog", "Catalog.X", "object")
    generated = editor.allocate_uuid(ROOT_UUID, *key, {})
    inventory = {("Catalog", "Catalog.Y", "object"): generated}
    original = dict(inventory)
    with pytest.raises(editor.Rejected, match="collision"):
        editor.allocate_uuid(ROOT_UUID, *key, inventory)
    assert inventory == original
    inventory[key] = generated
    with pytest.raises(editor.Rejected, match="collision"):
        editor.allocate_uuid(ROOT_UUID, *key, inventory)


@pytest.mark.parametrize("root", ["", "bad", str(uuid.UUID(int=0))])
def test_invalid_root_does_not_allocate(root):
    inventory = {}
    with pytest.raises(editor.Rejected):
        editor.allocate_uuid(root, "Catalog", "Catalog.X", "object", inventory)
    assert inventory == {}


def form(body):
    return etree.fromstring(f'<Form xmlns="{editor.FORM}">{body}</Form>'.encode())


def test_ids_reserve_every_section_without_renumbering():
    tree = form("""<AutoCommandBar id="-1"><ChildItems><Button name="Кнопка" id="9">
        <ContextMenu name="КнопкаКонтекстноеМеню" id="80"/></Button></ChildItems></AutoCommandBar>
        <ChildItems><InputField name="Поле" id="1"/></ChildItems>
        <Attributes><Attribute name="Атрибут" id="100"/></Attributes>
        <Commands><Command name="Команда" id="200"/></Commands>""")
    before = etree.tostring(tree)
    assert editor.allocate_form_ids(tree, 3) == [201, 202, 203]
    assert editor.allocate_form_ids(tree, 3) == [201, 202, 203]
    assert etree.tostring(tree) == before
    editor.check_new_element_names(tree, ["Новое", "НовоеКонтекстноеМеню"])
    with pytest.raises(editor.Rejected):
        editor.check_new_element_names(tree, ["кнопкаконтекстноеменю"])
    with pytest.raises(editor.Rejected):
        editor.check_new_element_names(tree, ["Новое", "новое"])


def test_borrowed_pool_accounts_for_base_commands_and_companions():
    tree = form("""<ChildItems><InputField name="Поле" id="1"/></ChildItems>
        <BaseForm><AutoCommandBar id="-1"><ChildItems>
        <Button name="БазоваяКнопка" id="1000050"><ExtendedTooltip name="Подсказка" id="1000051"/>
        </Button></ChildItems></AutoCommandBar><ChildItems><InputField name="Поле" id="1"/></ChildItems>
        </BaseForm>""")
    before = etree.tostring(tree)
    assert editor.allocate_form_ids(tree, 2) == [1000052, 1000053]
    with pytest.raises(editor.Rejected):
        editor.check_new_element_names(tree, ["подсказка"])
    assert etree.tostring(tree) == before
    assert editor.allocate_form_ids(form("<BaseForm/>"), 2) == [1000000, 1000001]


@pytest.mark.parametrize("value", ["bad", "1.5", "-2", "2147483648"])
def test_malformed_existing_id_is_not_ignored(value):
    with pytest.raises(editor.Rejected):
        editor.allocate_form_ids(form(f'<ChildItems><InputField id="{value}"/></ChildItems>'), 1)


def test_id_exhaustion_and_empty_batch():
    with pytest.raises(editor.Rejected):
        editor.allocate_form_ids(form('<ChildItems><InputField id="2147483647"/></ChildItems>'), 1)
    # Exactly one free ID below the maximum: one addition succeeds, two do not.
    last_free = form('<ChildItems><InputField id="2147483646"/></ChildItems>')
    assert editor.allocate_form_ids(last_free, 1) == [2147483647]
    with pytest.raises(editor.Rejected):
        editor.allocate_form_ids(last_free, 2)
    with pytest.raises(editor.Rejected):
        editor.allocate_form_ids(form(""), 0)


def test_event_names_are_not_element_names():
    tree = form("""<ChildItems><InputField name="First" id="1"><Events>
        <Event name="OnChange">FirstOnChange</Event></Events></InputField>
        <InputField name="Second" id="2"><Events>
        <Event name="OnChange">SecondOnChange</Event></Events></InputField></ChildItems>""")
    assert set(editor.named(tree)) == {"first", "second"}
    editor.check_new_element_names(tree, ["OnChange"])
    tree.find('f:ChildItems/f:InputField[@name="Second"]', editor.NS).set("name", "first")
    with pytest.raises(editor.Rejected, match="Duplicate existing element name"):
        editor.named(tree)
