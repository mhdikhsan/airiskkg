"""Import a draw.io / diagrams.net XML diagram as a BEAM architecture model.

Best-effort conversion for the workbench's "Import XML" feature: vertices
become BEAM elements, edges become flow relations. Element kinds are guessed
from the draw.io shape style and the label text; every guess is reported as a
warning so the user can correct kinds in Draw mode before assessing.

Mapping rules
-------------
- vertex kind:  hexagon/rhombus style or model-ish label  -> beam:StatisticalModel
                ellipse/cylinder style or data-ish label  -> beam:Data
                anything else                             -> beam:Process
- edge kind:    resource -> process  = beam:use
                process  -> resource = beam:produce
                process  -> process  = beam:inform
                resource -> resource = skipped (warning)
"""

from __future__ import annotations

import base64
import re
import zlib
from urllib.parse import unquote
from xml.etree import ElementTree

from airiskkg.architecture_builder import build_ttl

_BEAM = "http://w3id.org/beam/core#"

_MODEL_STYLE = re.compile(r"hexagon|rhombus|mxgraph\.ai|shape=step")
_DATA_STYLE = re.compile(r"ellipse|cylinder|shape=datastore|shape=document|shape=parallelogram")
_MODEL_LABEL = re.compile(r"\b(llm|model|gpt|bert|encoder|transformer)\b", re.I)
_DATA_LABEL = re.compile(
    r"\b(data|dataset|store|db|database|index|corpus|document|query|prompt|answer|"
    r"output|input|embedding|vector|chunk|context|response|log|file)\b",
    re.I,
)
_PROCESS_LABEL = re.compile(
    r"\b(retriev|generat|train|embed|chunk|rerank|search|transform|preprocess|"
    r"process|step|pipeline|infer|predict|parse|build|validat)\w*",
    re.I,
)

_TAG_RE = re.compile(r"<[^>]+>")
_NAME_STRIP_RE = re.compile(r"[^A-Za-z0-9_]")


class DrawioImportError(Exception):
    """Raised when the XML cannot be read as a draw.io diagram."""


def _decode_diagram(diagram: ElementTree.Element) -> ElementTree.Element:
    """A <diagram> holds either a nested <mxGraphModel> or deflate+base64 text."""
    model = diagram.find("mxGraphModel")
    if model is not None:
        return model
    text = (diagram.text or "").strip()
    if not text:
        raise DrawioImportError("Diagram element is empty.")
    try:
        raw = zlib.decompress(base64.b64decode(text), -15)
        xml = unquote(raw.decode("utf-8"))
        return ElementTree.fromstring(xml)
    except Exception as error:  # noqa: BLE001
        raise DrawioImportError(f"Could not decode compressed diagram: {error}") from error


def _graph_model(xml_text: str) -> ElementTree.Element:
    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError as error:
        raise DrawioImportError(f"Not valid XML: {error}") from error
    if root.tag == "mxGraphModel":
        return root
    if root.tag == "mxfile":
        diagram = root.find("diagram")
        if diagram is None:
            raise DrawioImportError("mxfile contains no <diagram>.")
        return _decode_diagram(diagram)
    if root.tag == "diagram":
        return _decode_diagram(root)
    raise DrawioImportError(f"Unsupported root element <{root.tag}> - expected an mxfile or mxGraphModel.")


def _clean_label(value: str) -> str:
    text = _TAG_RE.sub(" ", value or "")
    return re.sub(r"\s+", " ", text).strip()


def _identifier(label: str, taken: set[str], fallback: str) -> str:
    base = _NAME_STRIP_RE.sub("", label.title().replace(" ", "")) or fallback
    if base[0].isdigit():
        base = "El" + base
    name = base
    counter = 2
    while name in taken:
        name = f"{base}{counter}"
        counter += 1
    taken.add(name)
    return name


def _guess_kind(style: str, label: str) -> tuple[str, str]:
    """Return (builder kind, BEAM class URI).

    Precedence: explicit shape style first, then process verbs ("Train Model"
    is a process, not a model), then model/data nouns, default process.
    """
    style = style or ""
    if _MODEL_STYLE.search(style):
        return "resource", _BEAM + "StatisticalModel"
    if _DATA_STYLE.search(style):
        return "resource", _BEAM + "Data"
    if _PROCESS_LABEL.search(label):
        return "process", _BEAM + "Process"
    if _MODEL_LABEL.search(label):
        return "resource", _BEAM + "StatisticalModel"
    if _DATA_LABEL.search(label):
        return "resource", _BEAM + "Data"
    return "process", _BEAM + "Process"


def drawio_to_model(xml_text: str) -> tuple[dict, list[str]]:
    """Parse draw.io XML into an architecture-builder model + warnings."""
    model_root = _graph_model(xml_text)
    warnings: list[str] = []

    vertices: dict[str, dict] = {}
    edges: list[tuple[str, str]] = []
    taken_names: set[str] = set()

    for cell in model_root.iter("mxCell"):
        cell_id = cell.get("id")
        if cell.get("vertex") == "1":
            label = _clean_label(cell.get("value", ""))
            if not label and not cell.get("style"):
                continue  # structural cells (layers, groups)
            kind, class_uri = _guess_kind(cell.get("style", ""), label)
            name = _identifier(label or f"Element{len(vertices) + 1}", taken_names, f"Element{len(vertices) + 1}")
            vertices[cell_id] = {"name": name, "label": label, "kind": kind, "class": class_uri}
            warnings.append(
                f"'{label or name}' imported as {class_uri.rsplit('#', 1)[-1]} (guessed from shape/label - adjust in Draw mode if wrong)."
            )
        elif cell.get("edge") == "1":
            source = cell.get("source")
            target = cell.get("target")
            if source and target:
                edges.append((source, target))
            else:
                warnings.append("An edge without a source or target was skipped.")

    if not vertices:
        raise DrawioImportError("No shapes found in the diagram.")

    resources = [v for v in vertices.values() if v["kind"] == "resource"]
    processes = {v["name"]: {**v, "use": [], "produce": [], "inform": []}
                 for v in vertices.values() if v["kind"] == "process"}

    for source_id, target_id in edges:
        source = vertices.get(source_id)
        target = vertices.get(target_id)
        if not source or not target:
            warnings.append("An edge referencing an unknown shape was skipped.")
            continue
        if source["kind"] == "resource" and target["kind"] == "process":
            processes[target["name"]]["use"].append(source["name"])
        elif source["kind"] == "process" and target["kind"] == "resource":
            processes[source["name"]]["produce"].append(target["name"])
        elif source["kind"] == "process" and target["kind"] == "process":
            processes[source["name"]]["inform"].append(target["name"])
        else:
            warnings.append(
                f"Edge {source['name']} -> {target['name']} connects two resources and was skipped "
                "(BEAM flow always passes through a process)."
            )

    model = {
        "systemName": "ImportedSystem",
        "systemLabel": "Imported from draw.io diagram",
        "resources": [
            {"name": r["name"], "label": r["label"], "class": r["class"], "roles": [], "dataCategories": []}
            for r in resources
        ],
        "processes": [
            {"name": p["name"], "label": p["label"], "class": p["class"], "roles": [],
             "use": p["use"], "produce": p["produce"], "inform": p["inform"]}
            for p in processes.values()
        ],
    }
    warnings.append(
        "No pattern roles or data categories could be derived from the diagram - "
        "annotate elements in Draw mode so motifs and risk patterns can match."
    )
    return model, warnings


def drawio_to_ttl(xml_text: str) -> tuple[str, list[str]]:
    model, warnings = drawio_to_model(xml_text)
    return build_ttl(model), warnings
