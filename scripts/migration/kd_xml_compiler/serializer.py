"""Deterministic XML serializer for KD 2.01 specifications."""

from __future__ import annotations

from typing import Any


def escape_text(value: Any) -> str:
    """Escape text for XML content (preserving quotes)."""
    if value is None:
        return ""
    text = str(value)
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def escape_attr(value: Any) -> str:
    """Escape text for XML attribute values."""
    if value is None:
        return ""
    text = str(value)
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


class XmlNode:
    """Lightweight XML node with deterministic KD 2.01 indentation formatting."""

    __slots__ = (
        "tag",
        "text",
        "attrs",
        "children",
        "compact_children",
        "trailing_tag",
        "omit_opening_tag",
    )

    def __init__(
        self,
        tag: str,
        text: str | None = None,
        attrs: dict[str, Any] | None = None,
        compact_children: bool = False,
        omit_opening_tag: bool = False,
    ) -> None:
        self.tag = tag
        self.text = text
        self.attrs = {k: str(v) for k, v in (attrs or {}).items()}
        self.children: list[XmlNode] = []
        self.compact_children = compact_children
        self.trailing_tag: str | None = None
        self.omit_opening_tag = omit_opening_tag

    def add_child(self, child: XmlNode) -> XmlNode:
        self.children.append(child)
        return child

    def sub_element(
        self,
        tag: str,
        text: str | None = None,
        attrs: dict[str, Any] | None = None,
        compact_children: bool = False,
        omit_opening_tag: bool = False,
    ) -> XmlNode:
        node = XmlNode(tag, text, attrs, compact_children, omit_opening_tag)
        self.children.append(node)
        return node

    def to_xml(self, indent: int = 0) -> str:
        """Render node to KD 2.01 XML string with tab indentation."""
        parts: list[str] = []
        tabs = "\t" * indent
        attr_str = ""
        if self.attrs:
            attr_parts = [f'{k}="{escape_attr(v)}"' for k, v in self.attrs.items()]
            attr_str = " " + " ".join(attr_parts)

        if not self.children and (self.text is None or self.text == ""):
            # Self-closing empty element
            return f"{tabs}<{self.tag}{attr_str}/>\r\n"

        if not self.children and self.text is not None:
            escaped = escape_text(self.text)
            if "\n" in self.text:
                # Multi-line text (e.g. BSL handler): opening tag with indent,
                # text verbatim, and closing tag immediately after last character.
                return f"{tabs}<{self.tag}{attr_str}>{escaped}</{self.tag}>\r\n"
            # Single-line text
            return f"{tabs}<{self.tag}{attr_str}>{escaped}</{self.tag}>\r\n"

        # Has children
        if self.compact_children:
            # Write all children compacted on one line without indentation/newlines
            inner_parts: list[str] = []
            for child in self.children:
                c_attrs = ""
                if child.attrs:
                    c_attrs = " " + " ".join(f'{k}="{escape_attr(v)}"' for k, v in child.attrs.items())
                if not child.children and (child.text is None or child.text == ""):
                    inner_parts.append(f"<{child.tag}{c_attrs}/>")
                elif not child.children and child.text is not None:
                    inner_parts.append(f"<{child.tag}{c_attrs}>{escape_text(child.text)}</{child.tag}>")
                else:
                    inner_parts.append(child.to_xml(0).strip())
            joined = "".join(inner_parts)
            line = f"{tabs}<{self.tag}{attr_str}>{joined}</{self.tag}>"
            if self.trailing_tag:
                line += self.trailing_tag
            return line + "\r\n"

        if not self.omit_opening_tag:
            parts.append(f"{tabs}<{self.tag}{attr_str}>\r\n")
        for child in self.children:
            parts.append(child.to_xml(indent + 1))
        parts.append(f"{tabs}</{self.tag}>\r\n")
        return "".join(parts)


def serialize_xml_root(root: XmlNode) -> str:
    """Serialize the XML root node without an XML declaration in UTF-8."""
    return root.to_xml(0)
