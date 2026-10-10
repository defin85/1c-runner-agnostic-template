"""KD 2.01 documents built from neutral metadata and explicit rule nodes."""

from __future__ import annotations

from datetime import datetime

from .metadata import Configuration
from .serializer import XmlNode


def _configuration(node: XmlNode, tag: str, configuration: Configuration, platform: str) -> None:
    node.sub_element(
        tag,
        configuration.name,
        attrs={
            "ВерсияПлатформы": platform,
            "ВерсияКонфигурации": configuration.version,
            "СинонимКонфигурации": configuration.synonym,
        },
    )


def exchange_document(
    source: Configuration,
    target: Configuration,
    *,
    identifier: str,
    name: str,
    created_at: str,
    comment: str,
    handlers: dict[str, str],
    parameters: list[dict[str, str]],
    conversions: XmlNode,
    exports: XmlNode,
) -> str:
    root = XmlNode("ПравилаОбмена")
    root.sub_element("ВерсияФормата", "2.01", attrs={"РежимСовместимости": "РежимСовместимостиСБСП21"})
    root.sub_element("Ид", identifier[-9:].ljust(40))
    root.sub_element("Наименование", name)
    root.sub_element("ДатаВремяСоздания", datetime.fromisoformat(created_at).replace(tzinfo=None).isoformat())
    _configuration(root, "Источник", source, "8.0")
    _configuration(root, "Приемник", target, "8.0")
    root.sub_element("Комментарий", comment)
    for event, handler in handlers.items():
        if handler:
            root.sub_element(event, handler)
    params = root.sub_element("Параметры")
    for parameter in parameters:
        params.sub_element("Параметр", attrs=parameter)
    root.sub_element("Обработки")
    root.add_child(conversions)
    root.add_child(exports)
    for tag in ("ПравилаОчисткиДанных", "Алгоритмы", "Запросы"):
        root.sub_element(tag)
    return root.to_xml().rstrip("\r\n")


def registration_document(
    configuration: Configuration,
    *,
    identifier: str,
    name: str,
    created_at: str,
    exchange_plan: str,
    comment: str,
    composition: list[str],
    rules: XmlNode,
) -> str:
    root = XmlNode("ПравилаРегистрации")
    root.sub_element("ВерсияФормата", "2.01")
    root.sub_element("Ид", identifier)
    root.sub_element("Наименование", name)
    root.sub_element("ДатаВремяСоздания", datetime.fromisoformat(created_at).replace(tzinfo=None).isoformat())
    root.sub_element("ПланОбмена", "ПланОбменаСсылка." + exchange_plan, attrs={"Имя": exchange_plan})
    _configuration(root, "Конфигурация", configuration, "8.2")
    root.sub_element("Комментарий", comment)
    content = root.sub_element("СоставПланаОбмена", compact_children=True)
    for type_name in composition:
        item = content.sub_element("Элемент", compact_children=True)
        item.sub_element("Тип", type_name)
        item.sub_element("Авторегистрация", "false")
    root.add_child(rules)
    return root.to_xml().rstrip("\r\n")
