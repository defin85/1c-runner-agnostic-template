"""Pure meta-info report, adapted mechanically from cc-1c-skills meta-info v1.1.

Copyright 2025-2026 Nick Shirokov, MIT; see
 automation/vendor/cc-1c-skills/LICENSE. Formatting only, without reads or writes.
"""

import re

import lxml.etree as etree


def object_report(type_node, mode="overview", drill_name="") -> list[str]:
    """Return the legacy report before pagination for an already parsed object."""
    if mode not in {"overview", "brief", "full"}:
        raise ValueError("Unknown report mode")
    if type_node is None or not isinstance(type_node.tag, str):
        raise ValueError("Missing metadata object")
    md_type = etree.QName(type_node).localname
    lines = []

    def out(text):
        lines.append(text)

    NS = {
        "md": "http://v8.1c.ru/8.3/MDClasses",
        "v8": "http://v8.1c.ru/8.1/data/core",
        "xr": "http://v8.1c.ru/8.3/xcf/readable",
        "xsi": "http://www.w3.org/2001/XMLSchema-instance",
        "xs": "http://www.w3.org/2001/XMLSchema",
        "cfg": "http://v8.1c.ru/8.1/data/enterprise/current-config",
        "app": "http://v8.1c.ru/8.2/managed-application/core",
    }

    XSI_NS = NS["xsi"]

    def find(parent, xpath):
        if parent is None:
            return None
        r = parent.xpath(xpath, namespaces=NS)
        return r[0] if r else None

    def find_all(parent, xpath):
        if parent is None:
            return []
        return parent.xpath(xpath, namespaces=NS)

    def inner_text(node):
        if node is None:
            return ""
        return node.text or ""

    def text_of(node):
        if node is None:
            return ""
        return (node.text or "").strip()

    type_name_map = {
        "Catalog": "Справочник",
        "Document": "Документ",
        "Enum": "Перечисление",
        "Constant": "Константа",
        "InformationRegister": "Регистр сведений",
        "AccumulationRegister": "Регистр накопления",
        "AccountingRegister": "Регистр бухгалтерии",
        "CalculationRegister": "Регистр расчёта",
        "ChartOfAccounts": "План счетов",
        "ChartOfCharacteristicTypes": "План видов характеристик",
        "ChartOfCalculationTypes": "План видов расчёта",
        "BusinessProcess": "Бизнес-процесс",
        "Task": "Задача",
        "ExchangePlan": "План обмена",
        "DocumentJournal": "Журнал документов",
        "Report": "Отчёт",
        "DataProcessor": "Обработка",
        "DefinedType": "Определяемый тип",
        "CommonModule": "Общий модуль",
        "ScheduledJob": "Регламентное задание",
        "EventSubscription": "Подписка на событие",
        "HTTPService": "HTTP-сервис",
        "WebService": "Веб-сервис",
    }

    ref_type_map = {
        "CatalogRef": "СправочникСсылка",
        "DocumentRef": "ДокументСсылка",
        "EnumRef": "ПеречислениеСсылка",
        "ChartOfAccountsRef": "ПланСчетовСсылка",
        "ChartOfCharacteristicTypesRef": "ПВХСсылка",
        "ChartOfCalculationTypesRef": "ПВРСсылка",
        "ExchangePlanRef": "ПланОбменаСсылка",
        "BusinessProcessRef": "БизнесПроцессСсылка",
        "TaskRef": "ЗадачаСсылка",
    }

    reg_type_map = {
        "AccumulationRegister": "РН",
        "AccountingRegister": "РБ",
        "CalculationRegister": "РР",
        "InformationRegister": "РС",
    }

    period_map = {
        "Nonperiodical": "Непериодический",
        "Day": "День",
        "Month": "Месяц",
        "Quarter": "Квартал",
        "Year": "Год",
        "Second": "Секунда",
    }

    write_mode_map = {
        "Independent": "независимая",
        "RecorderSubordinate": "подчинение регистратору",
    }

    reuse_map = {
        "DontUse": "нет",
        "DuringRequest": "на время вызова",
        "DuringSession": "на время сеанса",
    }

    event_map = {
        "BeforeWrite": "ПередЗаписью",
        "OnWrite": "ПриЗаписи",
        "AfterWrite": "ПослеЗаписи",
        "BeforeDelete": "ПередУдалением",
        "Posting": "ОбработкаПроведения",
        "UndoPosting": "ОбработкаУдаленияПроведения",
        "OnReadAtServer": "ПриЧтенииНаСервере",
        "FillCheckProcessing": "ОбработкаПроверкиЗаполнения",
    }

    object_type_map = {
        "CatalogObject": "СправочникОбъект",
        "DocumentObject": "ДокументОбъект",
        "ChartOfAccountsObject": "ПланСчетовОбъект",
        "ChartOfCharacteristicTypesObject": "ПВХОбъект",
        "BusinessProcessObject": "БизнесПроцессОбъект",
        "TaskObject": "ЗадачаОбъект",
        "ExchangePlanObject": "ПланОбменаОбъект",
        "InformationRegisterRecordSet": "НаборЗаписейРС",
        "AccumulationRegisterRecordSet": "НаборЗаписейРН",
        "AccountingRegisterRecordSet": "НаборЗаписейРБ",
    }

    number_period_map = {
        "Year": "по году",
        "Quarter": "по кварталу",
        "Month": "по месяцу",
        "Day": "по дню",
        "WholeCatalog": "сквозная",
    }

    ru_type_name = type_name_map.get(md_type, md_type)

    # ── Helpers ──────────────────────────────────────────────────

    def get_ml_text(node):
        if node is None:
            return ""
        c = find(node, "v8:item[v8:lang='ru']/v8:content")
        if c is not None:
            return inner_text(c)
        c = find(node, "v8:item/v8:content")
        if c is not None:
            return inner_text(c)
        t = text_of(node)
        if t:
            return t
        return ""

    def format_type(type_node_el):
        if type_node_el is None:
            return ""
        types = []
        for t in find_all(type_node_el, "v8:Type"):
            types.append(format_single_type(inner_text(t), type_node_el))
        for t in find_all(type_node_el, "v8:TypeSet"):
            raw = inner_text(t)
            m = re.match(r"^cfg:DefinedType\.(.+)$", raw)
            if m:
                types.append(f"ОпределяемыйТип.{m.group(1)}")
                continue
            m = re.match(r"^cfg:Characteristic\.(.+)$", raw)
            if m:
                types.append(f"Характеристика.{m.group(1)}")
                continue
            types.append(raw)
        if len(types) == 0:
            return ""
        if len(types) == 1:
            return types[0]
        return " | ".join(types)

    def format_single_type(raw, parent_node):
        if raw == "xs:string":
            sq = find(parent_node, "v8:StringQualifiers/v8:Length")
            length = inner_text(sq) if sq is not None else ""
            return f"Строка({length})" if length else "Строка"
        if raw == "xs:decimal":
            dg = find(parent_node, "v8:NumberQualifiers/v8:Digits")
            fr = find(parent_node, "v8:NumberQualifiers/v8:FractionDigits")
            d = inner_text(dg) if dg is not None else ""
            f = inner_text(fr) if fr is not None else "0"
            return f"Число({d},{f})" if d else "Число"
        if raw == "xs:boolean":
            return "Булево"
        if raw == "xs:dateTime":
            dq = find(parent_node, "v8:DateQualifiers/v8:DateFractions")
            if dq is not None:
                dv = inner_text(dq)
                if dv == "Date":
                    return "Дата"
                if dv == "Time":
                    return "Время"
                if dv == "DateTime":
                    return "ДатаВремя"
                return "Дата"
            return "ДатаВремя"
        if raw == "v8:ValueStorage":
            return "ХранилищеЗначения"
        if raw == "v8:UUID":
            return "УникальныйИдентификатор"
        if raw == "v8:Null":
            return "Null"
        # Normalize d5p1:/dNpN: → cfg: (both map to same namespace)
        raw = re.sub(r"^d\d+p\d+:", "cfg:", raw)
        # cfg:CatalogRef.Xxx -> СправочникСсылка.Xxx
        m = re.match(r"^cfg:(\w+)Ref\.(.+)$", raw)
        if m:
            prefix = f"{m.group(1)}Ref"
            objn = m.group(2)
            if prefix in ref_type_map:
                return f"{ref_type_map[prefix]}.{objn}"
        # cfg:EnumRef.Xxx
        m = re.match(r"^cfg:EnumRef\.(.+)$", raw)
        if m:
            return f"ПеречислениеСсылка.{m.group(1)}"
        # cfg:Characteristic.Xxx
        m = re.match(r"^cfg:Characteristic\.(.+)$", raw)
        if m:
            return f"Характеристика.{m.group(1)}"
        # cfg:DefinedType.Xxx
        m = re.match(r"^cfg:DefinedType\.(.+)$", raw)
        if m:
            return f"ОпределяемыйТип.{m.group(1)}"
        # Strip cfg: prefix
        m = re.match(r"^cfg:(.+)$", raw)
        if m:
            return m.group(1)
        return raw

    def format_flags(a_props, is_dimension=False):
        flags = []
        fc = find(a_props, "md:FillChecking")
        if fc is not None and inner_text(fc) == "ShowError":
            flags.append("обязательный")
        idx = find(a_props, "md:Indexing")
        if idx is not None:
            iv = inner_text(idx)
            if iv == "Index":
                flags.append("индекс")
            elif iv == "IndexWithAdditionalOrder":
                flags.append("индекс+доп")
        if is_dimension:
            master = find(a_props, "md:Master")
            if master is not None and inner_text(master) == "true":
                flags.append("ведущее")
        ml = find(a_props, "md:MultiLine")
        if ml is not None and inner_text(ml) == "true":
            flags.append("многострочный")
        use = find(a_props, "md:Use")
        if use is not None:
            uv = inner_text(use)
            if uv == "ForFolder":
                flags.append("для папок")
            elif uv == "ForFolderAndItem":
                flags.append("для папок и элементов")
        if not flags:
            return ""
        return f"  [{', '.join(flags)}]"

    def get_attributes(parent_node, child_tag="Attribute", is_dimension=False):
        result = []
        for attr in find_all(parent_node, f"md:{child_tag}"):
            aprops = find(attr, "md:Properties")
            if aprops is None:
                continue
            attr_name = inner_text(find(aprops, "md:Name"))
            type_str = format_type(find(aprops, "md:Type"))
            aflags = format_flags(aprops, is_dimension)
            result.append({"Name": attr_name, "Type": type_str, "Flags": aflags, "Props": aprops})
        return result

    def get_tabular_sections(parent_node):
        result = []
        for ts in find_all(parent_node, "md:TabularSection"):
            tprops = find(ts, "md:Properties")
            ts_name = inner_text(find(tprops, "md:Name"))
            tchild_objs = find(ts, "md:ChildObjects")
            cols = get_attributes(tchild_objs) if tchild_objs is not None else []
            result.append({"Name": ts_name, "Columns": cols, "ColCount": len(cols)})
        return result

    def format_attr_line(attr, max_name_len=30):
        padded = attr["Name"].ljust(max_name_len)
        return f"  {padded} {attr['Type']}{attr['Flags']}"

    def get_max_name_len(attrs):
        mx = 10
        for a in attrs:
            if len(a["Name"]) > mx:
                mx = len(a["Name"])
        return min(mx + 2, 40)

    def get_simple_children(parent_node, tag):
        result = []
        for child in find_all(parent_node, f"md:{tag}"):
            result.append(inner_text(child))
        return result

    def sort_attrs_ref_first(attrs):
        refs = []
        prims = []
        for a in attrs:
            t = a["Type"]
            if (
                re.search(r"Ссылка\.", t)
                or re.search(r"Характеристика\.", t)
                or re.search(r"ОпределяемыйТип\.", t)
                or re.search(r"ПланСчетовСсылка", t)
                or re.search(r"ПВХСсылка", t)
                or re.search(r"ПВРСсылка", t)
            ):
                refs.append(a)
            else:
                prims.append(a)
        return refs + prims

    def decline_cols(n):
        m = n % 10
        h = n % 100
        if 11 <= h <= 19:
            return "колонок"
        if m == 1:
            return "колонка"
        if 2 <= m <= 4:
            return "колонки"
        return "колонок"

    def format_source_type(raw):
        raw = re.sub(r"^d\d+p\d+:", "cfg:", raw)
        m = re.match(r"^cfg:(\w+)\.(.+)$", raw)
        if m:
            prefix = m.group(1)
            name = m.group(2)
            if prefix in object_type_map:
                return f"{object_type_map[prefix]}.{name}"
        m = re.match(r"^cfg:(.+)$", raw)
        if m:
            return m.group(1)
        return raw

    def get_http_endpoints(child_objs):
        result = []
        for tpl in find_all(child_objs, "md:URLTemplate"):
            tp = find(tpl, "md:Properties")
            tpl_name = inner_text(find(tp, "md:Name"))
            template = inner_text(find(tp, "md:Template"))
            methods = []
            tpl_co = find(tpl, "md:ChildObjects")
            if tpl_co is not None:
                for m in find_all(tpl_co, "md:Method"):
                    mp = find(m, "md:Properties")
                    http_method = inner_text(find(mp, "md:HTTPMethod"))
                    handler = inner_text(find(mp, "md:Handler"))
                    methods.append(
                        {"HTTPMethod": http_method, "Handler": handler, "Name": inner_text(find(mp, "md:Name"))}
                    )
            result.append({"Name": tpl_name, "Template": template, "Methods": methods})
        return result

    def get_ws_operations(child_objs):
        result = []
        for op in find_all(child_objs, "md:Operation"):
            oprops = find(op, "md:Properties")
            op_name = inner_text(find(oprops, "md:Name"))
            ret_type_el = find(oprops, "md:XDTOReturningValueType")
            ret_str = inner_text(ret_type_el) if ret_type_el is not None and inner_text(ret_type_el) else "void"
            proc_name_el = find(oprops, "md:ProcedureName")
            params = []
            op_co = find(op, "md:ChildObjects")
            if op_co is not None:
                for p in find_all(op_co, "md:Parameter"):
                    pp = find(p, "md:Properties")
                    p_name = inner_text(find(pp, "md:Name"))
                    p_type_el = find(pp, "md:XDTOValueType")
                    p_type_str = inner_text(p_type_el) if p_type_el is not None else "?"
                    dir_el = find(pp, "md:TransferDirection")
                    dir_str = (
                        f" [{inner_text(dir_el).lower()}]" if dir_el is not None and inner_text(dir_el) != "In" else ""
                    )
                    params.append(f"{p_name}: {p_type_str}{dir_str}")
            param_str = ", ".join(params)
            result.append(
                {
                    "Name": op_name,
                    "Params": param_str,
                    "ReturnType": ret_str,
                    "ProcName": inner_text(proc_name_el) if proc_name_el is not None else "",
                }
            )
        return result

    # ── Extract metadata ─────────────────────────────────────────

    props = find(type_node, "md:Properties")
    child_objs = find(type_node, "md:ChildObjects")
    obj_name = inner_text(find(props, "md:Name"))
    syn_node = find(props, "md:Synonym")
    synonym = get_ml_text(syn_node)

    # ── Handle -Name drill-down ──────────────────────────────────

    drill_done = False

    if drill_name and child_objs is not None:
        # Search in attributes/dimensions/resources
        attr_tags = ["Attribute", "Dimension", "Resource"]
        for tag in attr_tags:
            if drill_done:
                break
            for attr in find_all(child_objs, f"md:{tag}"):
                ap = find(attr, "md:Properties")
                if ap is None:
                    continue
                an = inner_text(find(ap, "md:Name"))
                if an == drill_name:
                    tag_ru = {"Attribute": "Реквизит", "Dimension": "Измерение", "Resource": "Ресурс"}[tag]
                    out(f"{tag_ru}: {an}")
                    type_str = format_type(find(ap, "md:Type"))
                    out(f"  Тип: {type_str}")
                    fc = find(ap, "md:FillChecking")
                    out(f"  Обязательный: {'да' if fc is not None and inner_text(fc) == 'ShowError' else 'нет'}")
                    idx = find(ap, "md:Indexing")
                    idx_val = inner_text(idx) if idx is not None else "DontIndex"
                    if idx_val == "DontIndex" or not idx_val:
                        idx_ru = "нет"
                    elif idx_val == "Index":
                        idx_ru = "Индекс"
                    elif idx_val == "IndexWithAdditionalOrder":
                        idx_ru = "Индекс с доп. упорядочиванием"
                    else:
                        idx_ru = idx_val
                    out(f"  Индексирование: {idx_ru}")
                    ml = find(ap, "md:MultiLine")
                    if ml is not None and inner_text(ml) == "true":
                        out("  Многострочный: да")
                    use = find(ap, "md:Use")
                    if use is not None and inner_text(use) != "ForItem":
                        use_val = inner_text(use)
                        use_ru = {"ForFolder": "для папок", "ForFolderAndItem": "для папок и элементов"}.get(
                            use_val, use_val
                        )
                        out(f"  Использование: {use_ru}")
                    fv = find(ap, "md:FillValue")
                    if fv is not None and fv.get(f"{{{XSI_NS}}}nil") != "true" and inner_text(fv):
                        fv_text = inner_text(fv)
                        if fv_text.endswith(".EmptyRef"):
                            fv_text = "Пустая ссылка"
                        elif fv_text == "false":
                            fv_text = "Ложь"
                        elif fv_text == "true":
                            fv_text = "Истина"
                        out(f"  Значение заполнения: {fv_text}")
                    else:
                        out("  Значение заполнения: \u2014")
                    if tag == "Dimension":
                        master = find(ap, "md:Master")
                        out(f"  Ведущее: {'да' if master is not None and inner_text(master) == 'true' else 'нет'}")
                        mf = find(ap, "md:MainFilter")
                        out(f"  Основной отбор: {'да' if mf is not None and inner_text(mf) == 'true' else 'нет'}")
                    syn_a = find(ap, "md:Synonym")
                    syn_text = get_ml_text(syn_a)
                    if syn_text and syn_text != an:
                        out(f"  Синоним: {syn_text}")
                    drill_done = True
                    break

        # Search in tabular sections
        if not drill_done:
            for ts in find_all(child_objs, "md:TabularSection"):
                tp = find(ts, "md:Properties")
                tn = inner_text(find(tp, "md:Name"))
                if tn == drill_name:
                    ts_co = find(ts, "md:ChildObjects")
                    cols = get_attributes(ts_co) if ts_co is not None else []
                    out(f"ТЧ: {tn} ({len(cols)} {decline_cols(len(cols))}):")
                    if cols:
                        ml = get_max_name_len(cols)
                        for c in cols:
                            out(format_attr_line(c, ml))
                    drill_done = True
                    break

        # Search in enum values
        if not drill_done:
            for ev in find_all(child_objs, "md:EnumValue"):
                ep = find(ev, "md:Properties")
                en = inner_text(find(ep, "md:Name"))
                if en == drill_name:
                    syn_e = find(ep, "md:Synonym")
                    syn_text = get_ml_text(syn_e)
                    out(f"Значение перечисления: {en}")
                    if syn_text:
                        out(f'  Синоним: "{syn_text}"')
                    cm = find(ep, "md:Comment")
                    if cm is not None and inner_text(cm):
                        out(f"  Комментарий: {inner_text(cm)}")
                    drill_done = True
                    break

        # Search in HTTPService URLTemplates
        if not drill_done and md_type == "HTTPService":
            for tpl in find_all(child_objs, "md:URLTemplate"):
                tp = find(tpl, "md:Properties")
                if inner_text(find(tp, "md:Name")) == drill_name:
                    template = inner_text(find(tp, "md:Template"))
                    out(f"Шаблон URL: {drill_name}")
                    out(f"  Путь: {template}")
                    tpl_co = find(tpl, "md:ChildObjects")
                    if tpl_co is not None:
                        for m in find_all(tpl_co, "md:Method"):
                            mp = find(m, "md:Properties")
                            http_method = inner_text(find(mp, "md:HTTPMethod"))
                            handler = inner_text(find(mp, "md:Handler"))
                            out(f"  {http_method} \u2192 {handler}")
                    drill_done = True
                    break

        # Search in WebService Operations
        if not drill_done and md_type == "WebService":
            for op in find_all(child_objs, "md:Operation"):
                oprops = find(op, "md:Properties")
                if inner_text(find(oprops, "md:Name")) == drill_name:
                    out(f"Операция: {drill_name}")
                    ret_type_el = find(oprops, "md:XDTOReturningValueType")
                    out(
                        f"  Возвращает: {inner_text(ret_type_el) if ret_type_el is not None and inner_text(ret_type_el) else 'void'}"
                    )
                    proc_name_el = find(oprops, "md:ProcedureName")
                    if proc_name_el is not None and inner_text(proc_name_el):
                        out(f"  Процедура: {inner_text(proc_name_el)}")
                    comment_el = find(oprops, "md:Comment")
                    if comment_el is not None and inner_text(comment_el):
                        out(f"  Комментарий: {inner_text(comment_el)}")
                    op_co = find(op, "md:ChildObjects")
                    if op_co is not None:
                        params_els = find_all(op_co, "md:Parameter")
                        if params_els:
                            out("  Параметры:")
                            for p in params_els:
                                pp = find(p, "md:Properties")
                                p_name = inner_text(find(pp, "md:Name"))
                                p_type_el = find(pp, "md:XDTOValueType")
                                dir_el = find(pp, "md:TransferDirection")
                                dir_str = (
                                    f" [{inner_text(dir_el).lower()}]"
                                    if dir_el is not None and inner_text(dir_el) != "In"
                                    else ""
                                )
                                out(f"    {p_name}: {inner_text(p_type_el) if p_type_el is not None else '?'}{dir_str}")
                    drill_done = True
                    break

        if not drill_done:
            raise ValueError(f"'{drill_name}' not found in {obj_name}")

    # ── Main output (not drill-down) ─────────────────────────────

    if drill_name and not drill_done:
        raise ValueError(f"'{drill_name}' not found in {obj_name}")

    if not drill_done:
        # Build header
        header = f"=== {ru_type_name}: {obj_name}"
        if synonym and synonym != obj_name:
            header += f' \u2014 "{synonym}"'
        header += " ==="
        out(header)

        if mode == "brief":
            # Attributes
            attrs = get_attributes(child_objs) if child_objs is not None else []
            if attrs:
                names = ", ".join(a["Name"] for a in attrs)
                out(f"Реквизиты ({len(attrs)}): {names}")

            # Dimensions/Resources for registers
            if md_type.endswith("Register"):
                dims = get_attributes(child_objs, "Dimension", True) if child_objs is not None else []
                if dims:
                    names = ", ".join(d["Name"] for d in dims)
                    out(f"Измерения ({len(dims)}): {names}")
                res = get_attributes(child_objs, "Resource") if child_objs is not None else []
                if res:
                    names = ", ".join(r["Name"] for r in res)
                    out(f"Ресурсы ({len(res)}): {names}")

            # Tabular sections
            tss = get_tabular_sections(child_objs) if child_objs is not None else []
            if tss:
                ts_parts = [f"{t['Name']}({t['ColCount']})" for t in tss]
                out(f"ТЧ ({len(tss)}): {', '.join(ts_parts)}")

            # Enum values
            if md_type == "Enum" and child_objs is not None:
                vals = []
                for ev in find_all(child_objs, "md:EnumValue"):
                    ep = find(ev, "md:Properties")
                    vals.append(inner_text(find(ep, "md:Name")))
                if vals:
                    out(f"Значения ({len(vals)}): {', '.join(vals)}")

            # DefinedType brief
            if md_type == "DefinedType":
                type_node2 = find(props, "md:Type")
                if type_node2 is not None:
                    types = []
                    for t in find_all(type_node2, "v8:Type"):
                        types.append(format_single_type(inner_text(t), type_node2))
                    if types:
                        out(f"Типы ({len(types)}): {', '.join(types)}")

            # CommonModule brief
            if md_type == "CommonModule":
                flags = []
                for flag_name, flag_label in [
                    ("Global", "Глобальный"),
                    ("Server", "Сервер"),
                    ("ServerCall", "Вызов сервера"),
                    ("ClientManagedApplication", "Клиент управляемое"),
                    ("ClientOrdinaryApplication", "Обычный клиент"),
                    ("ExternalConnection", "Внешнее соединение"),
                    ("Privileged", "Привилегированный"),
                ]:
                    n = find(props, f"md:{flag_name}")
                    if n is not None and inner_text(n) == "true":
                        flags.append(flag_label)
                reuse = find(props, "md:ReturnValuesReuse")
                if reuse is not None and inner_text(reuse) != "DontUse":
                    reuse_ru = reuse_map.get(inner_text(reuse), inner_text(reuse))
                    flags.append(f"Повторное использование: {reuse_ru}")
                if flags:
                    out(" | ".join(flags))

            # ScheduledJob brief
            if md_type == "ScheduledJob":
                method = find(props, "md:MethodName")
                if method is not None and inner_text(method):
                    m_name = inner_text(method)
                    m2 = re.match(r"^CommonModule\.(.+)$", m_name)
                    if m2:
                        m_name = m2.group(1)
                    out(f"Метод: {m_name}")
                sj_parts = []
                use = find(props, "md:Use")
                sj_parts.append(f"Использование: {'да' if use is not None and inner_text(use) == 'true' else 'нет'}")
                predef = find(props, "md:Predefined")
                sj_parts.append(
                    f"Предопределённое: {'да' if predef is not None and inner_text(predef) == 'true' else 'нет'}"
                )
                restart_cnt = find(props, "md:RestartCountOnFailure")
                restart_int = find(props, "md:RestartIntervalOnFailure")
                if restart_cnt is not None and inner_text(restart_cnt).isdigit() and int(inner_text(restart_cnt)) > 0:
                    sj_parts.append(f"Перезапуск: {inner_text(restart_cnt)} (через {inner_text(restart_int)} сек)")
                out(" | ".join(sj_parts))

            # EventSubscription brief
            if md_type == "EventSubscription":
                es_parts = []
                event = find(props, "md:Event")
                if event is not None and inner_text(event):
                    ev_ru = event_map.get(inner_text(event), inner_text(event))
                    es_parts.append(f"Событие: {ev_ru}")
                handler = find(props, "md:Handler")
                if handler is not None and inner_text(handler):
                    h_name = inner_text(handler)
                    m2 = re.match(r"^CommonModule\.(.+)$", h_name)
                    if m2:
                        h_name = m2.group(1)
                    es_parts.append(f"Обработчик: {h_name}")
                source = find(props, "md:Source")
                if source is not None:
                    src_count = len(find_all(source, "v8:Type"))
                    if src_count > 0:
                        es_parts.append(f"Источники: {src_count}")
                if es_parts:
                    out(" | ".join(es_parts))

            # HTTPService brief
            if md_type == "HTTPService":
                root_url = find(props, "md:RootURL")
                if root_url is not None and inner_text(root_url):
                    out(f"Корневой URL: /{inner_text(root_url)}")
                if child_objs is not None:
                    endpoints = get_http_endpoints(child_objs)
                    if endpoints:
                        total_methods = sum(len(ep["Methods"]) for ep in endpoints)
                        out(f"Шаблоны: {len(endpoints)} | Методы: {total_methods}")

            # WebService brief
            if md_type == "WebService":
                ns_url = find(props, "md:Namespace")
                if ns_url is not None and inner_text(ns_url):
                    out(f"Пространство имён: {inner_text(ns_url)}")
                if child_objs is not None:
                    ops = get_ws_operations(child_objs)
                    if ops:
                        out(f"Операции: {len(ops)}")

        else:
            # mode: overview / full

            # Document-specific header
            if md_type == "Document":
                num_type = find(props, "md:NumberType")
                num_len = find(props, "md:NumberLength")
                num_per = find(props, "md:NumberPeriodicity")
                auto_num = find(props, "md:Autonumbering")
                posting = find(props, "md:Posting")
                parts = []
                if num_type is not None and num_len is not None:
                    nt = "Строка" if inner_text(num_type) == "String" else "Число"
                    piece = f"Номер: {nt}({inner_text(num_len)})"
                    if num_per is not None:
                        per_ru = number_period_map.get(inner_text(num_per), inner_text(num_per))
                        piece += f", {per_ru}"
                    if auto_num is not None and inner_text(auto_num) == "true":
                        piece += ", авто"
                    parts.append(piece)
                if posting is not None:
                    parts.append(f"Проведение: {'да' if inner_text(posting) == 'Allow' else 'нет'}")
                if parts:
                    out(" | ".join(parts))

            # Catalog-specific header
            if md_type == "Catalog":
                parts = []
                hier = find(props, "md:Hierarchical")
                if hier is not None and inner_text(hier) == "true":
                    ht = find(props, "md:HierarchyType")
                    ht_text = (
                        "группы и элементы"
                        if ht is not None and inner_text(ht) == "HierarchyFoldersAndItems"
                        else "элементы"
                    )
                    limit_node = find(props, "md:LimitLevelCount")
                    level_node = find(props, "md:LevelCount")
                    if limit_node is not None and inner_text(limit_node) == "true" and level_node is not None:
                        ht_text += f", уровней: {inner_text(level_node)}"
                    else:
                        ht_text += ", без ограничения уровней"
                    parts.append(f"Иерархический: {ht_text}")
                code_len = find(props, "md:CodeLength")
                desc_len = find(props, "md:DescriptionLength")
                if code_len is not None and inner_text(code_len).isdigit() and int(inner_text(code_len)) > 0:
                    parts.append(f"Код({inner_text(code_len)})")
                if desc_len is not None and inner_text(desc_len).isdigit() and int(inner_text(desc_len)) > 0:
                    parts.append(f"Наименование({inner_text(desc_len)})")
                if parts:
                    out(" | ".join(parts))

            # Register-specific header
            if md_type.endswith("Register"):
                parts = []
                if md_type == "InformationRegister":
                    per = find(props, "md:InformationRegisterPeriodicity")
                    if per is not None:
                        per_ru = period_map.get(inner_text(per), inner_text(per))
                        parts.append(f"Периодичность: {per_ru}")
                    wm = find(props, "md:WriteMode")
                    if wm is not None:
                        wm_ru = write_mode_map.get(inner_text(wm), inner_text(wm))
                        parts.append(f"Запись: {wm_ru}")
                if md_type == "AccumulationRegister":
                    reg_kind = find(props, "md:RegisterType")
                    if reg_kind is not None:
                        rk_val = inner_text(reg_kind)
                        rk_ru = {"Balances": "остатки", "Turnovers": "обороты"}.get(rk_val, rk_val)
                        parts.append(f"Вид: {rk_ru}")
                if parts:
                    out(" | ".join(parts))

            # Constant
            if md_type == "Constant":
                type_str = format_type(find(props, "md:Type"))
                if type_str:
                    out(f"Тип: {type_str}")

            # Report: MainDataCompositionSchema
            if md_type == "Report":
                main_dcs = find(props, "md:MainDataCompositionSchema")
                if main_dcs is not None and inner_text(main_dcs):
                    dcs_name = inner_text(main_dcs)
                    m2 = re.search(r"\.Template\.(.+)$", dcs_name)
                    if m2:
                        dcs_name = m2.group(1)
                    out(f"Основная СКД: {dcs_name}")

            # DefinedType
            if md_type == "DefinedType":
                type_node2 = find(props, "md:Type")
                if type_node2 is not None:
                    types = []
                    for t in find_all(type_node2, "v8:Type"):
                        types.append(format_single_type(inner_text(t), type_node2))
                    if types:
                        out(f"Типы ({len(types)}):")
                        for t in types:
                            out(f"  {t}")

            # CommonModule
            if md_type == "CommonModule":
                flags = []
                for flag_name, flag_label in [
                    ("Global", "Глобальный"),
                    ("Server", "Сервер"),
                    ("ServerCall", "Вызов сервера"),
                    ("ClientManagedApplication", "Клиент управляемое"),
                    ("ClientOrdinaryApplication", "Обычный клиент"),
                    ("ExternalConnection", "Внешнее соединение"),
                    ("Privileged", "Привилегированный"),
                ]:
                    n = find(props, f"md:{flag_name}")
                    if n is not None and inner_text(n) == "true":
                        flags.append(flag_label)
                reuse = find(props, "md:ReturnValuesReuse")
                if reuse is not None and inner_text(reuse) != "DontUse":
                    reuse_ru = reuse_map.get(inner_text(reuse), inner_text(reuse))
                    flags.append(f"Повторное использование: {reuse_ru}")
                if flags:
                    out(" | ".join(flags))

            # ScheduledJob
            if md_type == "ScheduledJob":
                method = find(props, "md:MethodName")
                if method is not None and inner_text(method):
                    m_name = inner_text(method)
                    m2 = re.match(r"^CommonModule\.(.+)$", m_name)
                    if m2:
                        m_name = m2.group(1)
                    out(f"Метод: {m_name}")
                sj_parts = []
                use = find(props, "md:Use")
                sj_parts.append(f"Использование: {'да' if use is not None and inner_text(use) == 'true' else 'нет'}")
                predef = find(props, "md:Predefined")
                sj_parts.append(
                    f"Предопределённое: {'да' if predef is not None and inner_text(predef) == 'true' else 'нет'}"
                )
                restart_cnt = find(props, "md:RestartCountOnFailure")
                restart_int = find(props, "md:RestartIntervalOnFailure")
                if restart_cnt is not None and inner_text(restart_cnt).isdigit() and int(inner_text(restart_cnt)) > 0:
                    sj_parts.append(f"Перезапуск: {inner_text(restart_cnt)} (через {inner_text(restart_int)} сек)")
                out(" | ".join(sj_parts))

            # EventSubscription
            if md_type == "EventSubscription":
                event = find(props, "md:Event")
                if event is not None and inner_text(event):
                    ev_ru = event_map.get(inner_text(event), inner_text(event))
                    out(f"Событие: {ev_ru}")
                handler = find(props, "md:Handler")
                if handler is not None and inner_text(handler):
                    h_name = inner_text(handler)
                    m2 = re.match(r"^CommonModule\.(.+)$", h_name)
                    if m2:
                        h_name = m2.group(1)
                    out(f"Обработчик: {h_name}")
                source = find(props, "md:Source")
                if source is not None:
                    src_types = []
                    for t in find_all(source, "v8:Type"):
                        src_types.append(format_source_type(inner_text(t)))
                    if src_types:
                        if mode == "full":
                            out(f"Источники ({len(src_types)}):")
                            for s in src_types:
                                out(f"  {s}")
                        else:
                            out(f"Источники ({len(src_types)})")

            # HTTPService
            if md_type == "HTTPService":
                root_url = find(props, "md:RootURL")
                if root_url is not None and inner_text(root_url):
                    out(f"Корневой URL: /{inner_text(root_url)}")
                if child_objs is not None:
                    endpoints = get_http_endpoints(child_objs)
                    if endpoints:
                        out("")
                        out(f"Шаблоны URL ({len(endpoints)}):")
                        for ep in endpoints:
                            out(f"  {ep['Template']}")
                            for m in ep["Methods"]:
                                out(f"    {m['HTTPMethod'].ljust(6)} \u2192 {m['Handler']}")

            # WebService
            if md_type == "WebService":
                ns_url = find(props, "md:Namespace")
                if ns_url is not None and inner_text(ns_url):
                    out(f"Пространство имён: {inner_text(ns_url)}")
                if child_objs is not None:
                    ops = get_ws_operations(child_objs)
                    if ops:
                        out("")
                        out(f"Операции ({len(ops)}):")
                        for op in ops:
                            out(f"  {op['Name']}({op['Params']}) \u2192 {op['ReturnType']}")

            # Enum values
            if md_type == "Enum" and child_objs is not None:
                vals = []
                for ev in find_all(child_objs, "md:EnumValue"):
                    ep = find(ev, "md:Properties")
                    v_name = inner_text(find(ep, "md:Name"))
                    v_syn = get_ml_text(find(ep, "md:Synonym"))
                    vals.append({"Name": v_name, "Synonym": v_syn})
                if vals:
                    out("")
                    out(f"Значения ({len(vals)}):")
                    ml = get_max_name_len(vals)
                    for v in vals:
                        padded = v["Name"].ljust(ml)
                        syn_text = f'"{v["Synonym"]}"' if v["Synonym"] and v["Synonym"] != v["Name"] else ""
                        out(f"  {padded} {syn_text}")

            # Dimensions (registers)
            if md_type.endswith("Register") and child_objs is not None:
                dims = get_attributes(child_objs, "Dimension", True)
                if dims:
                    out("")
                    out(f"Измерения ({len(dims)}):")
                    ml = get_max_name_len(dims)
                    for d in dims:
                        out(format_attr_line(d, ml))

            # Resources (registers)
            if md_type.endswith("Register") and child_objs is not None:
                res = get_attributes(child_objs, "Resource")
                if res:
                    out("")
                    out(f"Ресурсы ({len(res)}):")
                    ml = get_max_name_len(res)
                    for r in res:
                        out(format_attr_line(r, ml))

            # Attributes
            if child_objs is not None and md_type != "Enum":
                attrs = get_attributes(child_objs)
                if attrs:
                    out("")
                    out(f"Реквизиты ({len(attrs)}):")
                    sorted_attrs = sort_attrs_ref_first(attrs)
                    ml = get_max_name_len(sorted_attrs)
                    for a in sorted_attrs:
                        out(format_attr_line(a, ml))

            # Tabular sections
            if child_objs is not None and md_type != "Enum":
                tss = get_tabular_sections(child_objs)
                if tss:
                    if mode == "full":
                        for ts in tss:
                            out("")
                            out(f"ТЧ {ts['Name']} ({ts['ColCount']} {decline_cols(ts['ColCount'])}):")
                            if ts["ColCount"] > 0:
                                sorted_cols = sort_attrs_ref_first(ts["Columns"])
                                ml = get_max_name_len(sorted_cols)
                                for c in sorted_cols:
                                    out(format_attr_line(c, ml))
                    else:
                        out("")
                        ts_parts = [f"{t['Name']}({t['ColCount']})" for t in tss]
                        out(f"ТЧ ({len(tss)}): {', '.join(ts_parts)}")

            # Forms/Templates/Commands in overview for Reports & DataProcessors
            if mode == "overview" and child_objs is not None and md_type in ("Report", "DataProcessor"):
                forms = get_simple_children(child_objs, "Form")
                if forms:
                    out(f"Формы: {', '.join(forms)}")
                templates = get_simple_children(child_objs, "Template")
                if templates:
                    out(f"Макеты: {', '.join(templates)}")
                commands = get_simple_children(child_objs, "Command")
                if commands:
                    out(f"Команды: {', '.join(commands)}")

            # Full mode: additional sections
            if mode == "full" and child_objs is not None:
                # Register records (documents)
                if md_type == "Document":
                    reg_recs = []
                    for item in find_all(props, "md:RegisterRecords/xr:Item"):
                        raw = inner_text(item)
                        m2 = re.match(r"^(\w+)\.(.+)$", raw)
                        if m2:
                            prefix = m2.group(1)
                            rname = m2.group(2)
                            short = reg_type_map.get(prefix, prefix)
                            reg_recs.append(f"{short}.{rname}")
                        else:
                            reg_recs.append(raw)
                    if reg_recs:
                        out("")
                        out(f"Движения ({len(reg_recs)}): {', '.join(reg_recs)}")

                    # BasedOn
                    based_on = []
                    for item in find_all(props, "md:BasedOn/xr:Item"):
                        raw = inner_text(item)
                        m2 = re.match(r"^\w+\.(.+)$", raw)
                        if m2:
                            based_on.append(m2.group(1))
                        else:
                            based_on.append(raw)
                    if based_on:
                        out(f"Ввод на основании: {', '.join(based_on)}")

                # Forms
                forms = get_simple_children(child_objs, "Form")
                if forms:
                    out(f"Формы: {', '.join(forms)}")

                # Templates
                templates = get_simple_children(child_objs, "Template")
                if templates:
                    out(f"Макеты: {', '.join(templates)}")

                # Commands
                commands = get_simple_children(child_objs, "Command")
                if commands:
                    out(f"Команды: {', '.join(commands)}")

    return lines


# Adapted from cc-1c-skills form-info v1.2 (Nick Shirokov, MIT).
def form_report(root, form_name, object_context="", expand="") -> list[str]:
    """Return the legacy managed-form report before pagination, without I/O."""
    NSMAP = {
        "d": "http://v8.1c.ru/8.3/xcf/logform",
        "v8": "http://v8.1c.ru/8.1/data/core",
        "v8ui": "http://v8.1c.ru/8.1/data/ui",
        "xr": "http://v8.1c.ru/8.3/xcf/readable",
        "xs": "http://www.w3.org/2001/XMLSchema",
        "xsi": "http://www.w3.org/2001/XMLSchema-instance",
        "cfg": "http://v8.1c.ru/8.1/data/enterprise/current-config",
        "dcsset": "http://v8.1c.ru/8.1/data-composition-system/settings",
    }

    # --- Skip elements ---

    SKIP_ELEMENTS = {
        "ExtendedTooltip",
        "ContextMenu",
        "AutoCommandBar",
        "SearchStringAddition",
        "ViewStatusAddition",
        "SearchControlAddition",
        "ColumnGroup",
    }

    # --- Helper: extract multilang text ---

    def get_ml_text(node):
        if node is None:
            return ""
        content = node.find("v8:item/v8:content", NSMAP)
        if content is not None and content.text:
            return content.text
        # Fallback: concatenate all text
        text = "".join(node.itertext()).strip()
        if text:
            return text
        return ""

    # --- Helper: format type compactly ---

    def format_type(type_node):
        if type_node is None or len(type_node) == 0:
            return ""

        type_set = type_node.find("v8:TypeSet", NSMAP)
        if type_set is not None:
            val = type_set.text or ""
            if val.startswith("cfg:"):
                val = val[4:]
            return val

        types = type_node.findall("v8:Type", NSMAP)
        if len(types) == 0:
            return ""

        parts = []
        for t in types:
            raw = t.text or ""
            if raw == "xs:string":
                sq = type_node.find("v8:StringQualifiers/v8:Length", NSMAP)
                length = int(sq.text) if sq is not None and sq.text else 0
                if length > 0:
                    parts.append(f"string({length})")
                else:
                    parts.append("string")
            elif raw == "xs:decimal":
                nq = type_node.find("v8:NumberQualifiers", NSMAP)
                if nq is not None:
                    d = nq.find("v8:Digits", NSMAP)
                    f = nq.find("v8:FractionDigits", NSMAP)
                    digits = d.text if d is not None and d.text else "0"
                    frac = f.text if f is not None and f.text else "0"
                    parts.append(f"decimal({digits},{frac})")
                else:
                    parts.append("decimal")
            elif raw == "xs:boolean":
                parts.append("boolean")
            elif raw == "xs:dateTime":
                dq = type_node.find("v8:DateQualifiers/v8:DateFractions", NSMAP)
                if dq is not None:
                    frac_text = dq.text or ""
                    if frac_text == "Date":
                        parts.append("date")
                    elif frac_text == "Time":
                        parts.append("time")
                    else:
                        parts.append("dateTime")
                else:
                    parts.append("dateTime")
            elif raw == "xs:binary":
                parts.append("binary")
            elif raw.startswith("cfg:") or re.match(r"^d\d+p\d+:", raw):
                parts.append(re.sub(r"^(?:cfg|d\d+p\d+):", "", raw))
            elif raw == "v8:ValueTable":
                parts.append("ValueTable")
            elif raw == "v8:ValueTree":
                parts.append("ValueTree")
            elif raw == "v8:ValueListType":
                parts.append("ValueList")
            elif raw == "v8:TypeDescription":
                parts.append("TypeDescription")
            elif raw == "v8:Universal":
                parts.append("Universal")
            elif raw == "v8:FixedArray":
                parts.append("FixedArray")
            elif raw == "v8:FixedStructure":
                parts.append("FixedStructure")
            elif raw == "v8ui:FormattedString":
                parts.append("FormattedString")
            elif raw == "v8ui:Picture":
                parts.append("Picture")
            elif raw == "v8ui:Color":
                parts.append("Color")
            elif raw == "v8ui:Font":
                parts.append("Font")
            elif raw.startswith("dcsset:"):
                parts.append(raw.replace("dcsset:", "DCS."))
            elif raw.startswith("dcssch:"):
                parts.append(raw.replace("dcssch:", "DCS."))
            elif raw.startswith("dcscor:"):
                parts.append(raw.replace("dcscor:", "DCS."))
            else:
                parts.append(raw)

        return " | ".join(parts)

    # --- Helper: check if title differs from name ---

    def test_title_differs(node, name):
        title_node = node.find("d:Title", NSMAP)
        if title_node is None:
            return None
        title_text = get_ml_text(title_node)
        if not title_text:
            return None
        # Normalize: remove spaces, lowercase
        norm_title = title_text.replace(" ", "").lower()
        norm_name = name.lower()
        if norm_title == norm_name:
            return None
        return title_text

    # --- Helper: get events as compact string ---

    def get_events_str(node):
        events_node = node.find("d:Events", NSMAP)
        if events_node is None:
            return ""
        evts = []
        for e in events_node.findall("d:Event", NSMAP):
            e_name = e.get("name", "")
            ct = e.get("callType", "")
            if ct:
                evts.append(f"{e_name}[{ct}]")
            else:
                evts.append(e_name)
        if len(evts) == 0:
            return ""
        return " {" + ", ".join(evts) + "}"

    # --- Helper: get flags ---

    def get_flags(node):
        flags = []
        vis = node.find("d:Visible", NSMAP)
        if vis is not None and vis.text == "false":
            flags.append("visible:false")
        en = node.find("d:Enabled", NSMAP)
        if en is not None and en.text == "false":
            flags.append("enabled:false")
        ro = node.find("d:ReadOnly", NSMAP)
        if ro is not None and ro.text == "true":
            flags.append("ro")
        if len(flags) == 0:
            return ""
        return " [" + ",".join(flags) + "]"

    # --- Element type abbreviations ---

    def get_element_tag(node):
        local_name = etree.QName(node.tag).localname
        if local_name == "UsualGroup":
            group_node = node.find("d:Group", NSMAP)
            orient = ""
            if group_node is not None:
                g_text = group_node.text or ""
                if g_text == "Vertical":
                    orient = ":V"
                elif g_text == "Horizontal":
                    orient = ":H"
                elif g_text == "AlwaysHorizontal":
                    orient = ":AH"
                elif g_text == "AlwaysVertical":
                    orient = ":AV"
            beh = node.find("d:Behavior", NSMAP)
            collapse = ""
            if beh is not None and beh.text == "Collapsible":
                collapse = ",collapse"
            return f"[Group{orient}{collapse}]"
        elif local_name == "InputField":
            return "[Input]"
        elif local_name == "CheckBoxField":
            return "[Check]"
        elif local_name == "LabelDecoration":
            return "[Label]"
        elif local_name == "LabelField":
            return "[LabelField]"
        elif local_name == "PictureDecoration":
            return "[Picture]"
        elif local_name == "PictureField":
            return "[PicField]"
        elif local_name == "CalendarField":
            return "[Calendar]"
        elif local_name == "Table":
            return "[Table]"
        elif local_name == "Button":
            return "[Button]"
        elif local_name == "CommandBar":
            return "[CmdBar]"
        elif local_name == "Pages":
            return "[Pages]"
        elif local_name == "Page":
            return "[Page]"
        elif local_name == "Popup":
            return "[Popup]"
        elif local_name == "ButtonGroup":
            return "[BtnGroup]"
        else:
            return f"[{local_name}]"

    # --- Count significant children (for Page summary) ---

    def count_significant_children(child_items_node):
        if child_items_node is None:
            return 0
        count = 0
        for child in child_items_node:
            if not isinstance(child.tag, str):
                continue
            ln = etree.QName(child.tag).localname
            if ln in SKIP_ELEMENTS:
                continue
            count += 1
        return count

    # --- Build element tree recursively ---

    def build_tree(child_items_node, prefix, tree_lines, expand="", state=None):
        if child_items_node is None:
            return

        # Collect significant children
        children = []
        for child in child_items_node:
            if not isinstance(child.tag, str):
                continue
            ln = etree.QName(child.tag).localname
            if ln in SKIP_ELEMENTS:
                continue
            children.append(child)

        for i, child in enumerate(children):
            last = i == len(children) - 1
            connector = "\u2514\u2500" if last else "\u251c\u2500"
            continuation = "  " if last else "\u2502 "

            tag = get_element_tag(child)
            name = child.get("name", "")
            flags = get_flags(child)
            events = get_events_str(child)

            # DataPath or CommandName
            binding = ""
            dp = child.find("d:DataPath", NSMAP)
            if dp is not None and dp.text:
                binding = f" -> {dp.text}"
            else:
                cn = child.find("d:CommandName", NSMAP)
                if cn is not None and cn.text:
                    cn_val = cn.text
                    m = re.match(r"^Form\.StandardCommand\.(.+)$", cn_val)
                    if m:
                        binding = f" -> {m.group(1)} [std]"
                    else:
                        m = re.match(r"^Form\.Command\.(.+)$", cn_val)
                        if m:
                            binding = f" -> {m.group(1)} [cmd]"
                        else:
                            binding = f" -> {cn_val}"

            # Title differs?
            title_str = ""
            diff_title = test_title_differs(child, name)
            if diff_title:
                title_str = f" [title:{diff_title}]"

            line = f"{prefix}{connector} {tag} {name}{binding}{flags}{title_str}{events}"
            tree_lines.append(line)

            # Recurse into containers (but not Page -- show summary unless expanded)
            local_name = etree.QName(child.tag).localname
            if local_name == "Page":
                ci = child.find("d:ChildItems", NSMAP)
                page_name = child.get("name", "")
                page_title = test_title_differs(child, page_name)
                should_expand = (expand == "*") or (expand == page_name) or (page_title and expand == page_title)
                if should_expand and ci is not None:
                    build_tree(ci, prefix + continuation, tree_lines, expand, state)
                else:
                    cnt = count_significant_children(ci)
                    tree_lines[-1] = tree_lines[-1] + f" ({cnt} items)"
                    if state is not None:
                        state["has_collapsed"] = True
            elif local_name in ("UsualGroup", "Pages", "Table", "CommandBar", "ButtonGroup", "Popup"):
                ci = child.find("d:ChildItems", NSMAP)
                if ci is not None:
                    build_tree(ci, prefix + continuation, tree_lines, expand, state)

    # --- Detect extension (BaseForm) ---
    base_form_node = root.find("d:BaseForm", NSMAP)
    is_extension = base_form_node is not None

    # --- Collect output ---
    lines = []

    # Header -- include Title if present
    title_node = root.find("d:Title", NSMAP)
    form_title = None
    if title_node is not None:
        form_title = get_ml_text(title_node)
        if not form_title:
            form_title = "".join(title_node.itertext()).strip() or None

    ext_marker = " [EXTENSION]" if is_extension else ""
    header = f"=== Form: {form_name}{ext_marker}"
    if form_title:
        header += f' — "{form_title}"'
    if object_context:
        header += f" ({object_context})"
    header += " ==="
    lines.append(header)

    # --- Form properties (Title excluded -- shown in header) ---
    prop_names = [
        "Width",
        "Height",
        "Group",
        "WindowOpeningMode",
        "EnterKeyBehavior",
        "AutoTitle",
        "AutoURL",
        "AutoFillCheck",
        "Customizable",
        "CommandBarLocation",
        "SaveDataInSettings",
        "AutoSaveDataInSettings",
        "AutoTime",
        "UsePostingMode",
        "RepostOnWrite",
        "UseForFoldersAndItems",
        "ReportResult",
        "DetailsData",
        "ReportFormType",
        "VerticalScroll",
        "ScalingMode",
    ]

    props = []
    for pn in prop_names:
        p_node = root.find(f"d:{pn}", NSMAP)
        if p_node is not None:
            val = get_ml_text(p_node)
            if not val:
                val = "".join(p_node.itertext()).strip()
            props.append(f"{pn}={val}")

    if len(props) > 0:
        lines.append("")
        lines.append("Properties: " + ", ".join(props))

    # --- Excluded commands ---
    excluded_cmds = []
    for ec in root.findall("d:CommandSet/d:ExcludedCommand", NSMAP):
        excluded_cmds.append(ec.text or "")

    # --- Form events ---
    form_events = root.find("d:Events", NSMAP)
    if form_events is not None and len(form_events) > 0:
        lines.append("")
        lines.append("Events:")
        for e in form_events.findall("d:Event", NSMAP):
            e_name = e.get("name", "")
            e_handler = e.text or ""
            ct = e.get("callType", "")
            ct_str = f"[{ct}]" if ct else ""
            lines.append(f"  {e_name}{ct_str} -> {e_handler}")

    # --- Element tree ---
    tree_state = {"has_collapsed": False}
    child_items = root.find("d:ChildItems", NSMAP)
    if child_items is not None:
        lines.append("")
        lines.append("Elements:")
        tree_lines = []
        build_tree(child_items, "  ", tree_lines, expand, tree_state)
        lines.extend(tree_lines)

    # --- Attributes ---
    attrs_node = root.find("d:Attributes", NSMAP)
    if attrs_node is not None:
        attr_lines = []
        for attr in attrs_node.findall("d:Attribute", NSMAP):
            a_name = attr.get("name", "")
            type_node = attr.find("d:Type", NSMAP)
            type_str = format_type(type_node)

            main_attr = attr.find("d:MainAttribute", NSMAP)
            is_main = main_attr is not None and main_attr.text == "true"

            prefix_char = "*" if is_main else " "
            main_suffix = " (main)" if is_main else ""

            # DynamicList: show MainTable
            settings = attr.find("d:Settings", NSMAP)
            dyn_table = ""
            if settings is not None and type_str == "DynamicList":
                mt = settings.find("d:MainTable", NSMAP)
                if mt is not None and mt.text:
                    dyn_table = f" -> {mt.text}"

            # ValueTable/ValueTree columns
            col_str = ""
            columns = attr.find("d:Columns", NSMAP)
            if columns is not None and type_str in ("ValueTable", "ValueTree"):
                cols = []
                for col in columns.findall("d:Column", NSMAP):
                    c_name = col.get("name", "")
                    c_type_node = col.find("d:Type", NSMAP)
                    c_type = format_type(c_type_node)
                    if c_type:
                        cols.append(f"{c_name}: {c_type}")
                    else:
                        cols.append(c_name)
                if len(cols) > 0:
                    col_str = " [" + ", ".join(cols) + "]"

            if type_str or col_str or dyn_table:
                line = f"  {prefix_char}{a_name}: {type_str}{col_str}{dyn_table}{main_suffix}"
            else:
                line = f"  {prefix_char}{a_name}{main_suffix}"
            attr_lines.append(line)

        if len(attr_lines) > 0:
            lines.append("")
            lines.append("Attributes:")
            lines.extend(attr_lines)

    # --- Parameters ---
    params_node = root.find("d:Parameters", NSMAP)
    if params_node is not None:
        param_lines = []
        for param in params_node.findall("d:Parameter", NSMAP):
            p_name = param.get("name", "")
            type_node = param.find("d:Type", NSMAP)
            type_str = format_type(type_node)

            key_param = param.find("d:KeyParameter", NSMAP)
            is_key = key_param is not None and key_param.text == "true"
            key_suffix = " (key)" if is_key else ""

            if type_str:
                param_lines.append(f"  {p_name}: {type_str}{key_suffix}")
            else:
                param_lines.append(f"  {p_name}{key_suffix}")

        if len(param_lines) > 0:
            lines.append("")
            lines.append("Parameters:")
            lines.extend(param_lines)

    # --- Commands ---
    cmds_node = root.find("d:Commands", NSMAP)
    if cmds_node is not None:
        cmd_lines = []
        for cmd in cmds_node.findall("d:Command", NSMAP):
            c_name = cmd.get("name", "")
            shortcut = cmd.find("d:Shortcut", NSMAP)
            sc_str = f" [{shortcut.text}]" if shortcut is not None and shortcut.text else ""

            # Collect all Action elements (may have multiple with callType)
            actions = cmd.findall("d:Action", NSMAP)
            if len(actions) > 1:
                act_parts = []
                for a in actions:
                    ct = a.get("callType", "")
                    ct_str = f"[{ct}]" if ct else ""
                    act_parts.append(f"{a.text or ''}{ct_str}")
                action_str = " -> " + ", ".join(act_parts)
            elif len(actions) == 1:
                ct = actions[0].get("callType", "")
                ct_str = f"[{ct}]" if ct else ""
                action_str = f" -> {actions[0].text or ''}{ct_str}"
            else:
                action_str = ""

            cmd_lines.append(f"  {c_name}{action_str}{sc_str}")

        if len(cmd_lines) > 0:
            lines.append("")
            lines.append("Commands:")
            lines.extend(cmd_lines)

    # --- BaseForm footer ---
    if is_extension:
        bf_version = base_form_node.get("version", "")
        bf_str = f"present (version {bf_version})" if bf_version else "present"
        lines.append("")
        lines.append(f"BaseForm: {bf_str}")

    # --- Expand hint ---
    if tree_state["has_collapsed"]:
        lines.append("")
        lines.append("Hint: use --expand <name> to expand a collapsed section, --expand * for all")

    return lines
