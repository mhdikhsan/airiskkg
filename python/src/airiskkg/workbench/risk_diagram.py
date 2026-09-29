"""The BEAM risk notation, drawn from a run rather than by hand.

A list of findings makes a reader carry the graph in their head. The notation
does not: a risk sits above the element it concerns, its source points at what
produces it, its consequence and impact sit above that, and a control hangs off
the risk it modifies. Everything in it is already in the graph -

    beamr:RiskSource  -> beamr:Risk -> beamr:Consequence -> beamr:Impact
    beamr:RiskControl -> the risk concept it modifies

so this module maps what an assessment produced onto the AIRO-aligned chain
BEAM already declares, and adds what a person drew by hand alongside it. The
two are marked apart: a candidate risk finding is the library's claim, a
beamr:Risk is somebody's.

Impact is drawn only where a person stated one. The harm domain a finding rolls
up to is a taxonomy link, not an impact on this system, and drawing it as one
said more than the run knows.

Bands are the notation's rows, top to bottom, and the canvas draws them in this
order above the architecture flow.
"""

from __future__ import annotations

from rdflib import RDF, Graph, Namespace, URIRef

from airiskkg.assessment_runner import BEAM, PAIR
from airiskkg.graph_view import _members_of
from airiskkg.workbench.risk_lens import _categories_tested, _category_tree
from airiskkg.workbench.terms import label, short

BEAMR = Namespace("http://w3id.org/beam/risk#")
_BP = Namespace("https://sBPMN.github.io/2.0/properties#")

BANDS = ("business", "impact", "consequence", "context", "risk", "source", "control", "system")


def _text(graph: Graph, node: URIRef) -> str | None:
    from airiskkg.workbench.scope import _text as read_text

    return read_text(graph, node)


def _node(
    node_id: str,
    band: str,
    title: str,
    *,
    body: str | None = None,
    origin: str = "derived",
    status: str | None = None,
    extra: dict | None = None,
) -> dict:
    """`origin` is the distinction the notation must not blur: `stated` is a
    person's claim, `derived` is what this run produced."""
    entry = {
        "id": node_id,
        "band": band,
        "title": title,
        "body": body,
        "origin": origin,
    }
    if status:
        entry["status"] = status
    if extra:
        entry.update(extra)
    return entry


def _link(source: str, target: str, kind: str, *, label_text: str | None = None,
          editable: bool = False, contains: bool = False) -> dict:
    """`attaches` reaches down to an architecture element; `chain` runs along
    the AIRO relation it is named for.

    `editable` marks a line that stands for one triple somebody wrote, so it can
    be taken back. A derived line is recomputed by the next run, and removing it
    would only mean it came straight back.
    """
    entry = {"source": source, "target": target, "kind": kind, "label": label_text,
             "editable": editable}
    # A system down to one of its own parts, drawn only where that part is.
    if contains:
        entry["contains"] = True
    return entry


def _stated_layer(graph: Graph, nodes: dict, links: list) -> None:
    """What somebody drew: risk storming's notes, in the notation they belong to."""
    hand = (
        (BEAMR.Impact, "impact"),
        (BEAMR.Consequence, "consequence"),
        (BEAMR.Risk, "risk"),
        (BEAMR.RiskSource, "source"),
        (BEAMR.RiskControl, "control"),
    )
    for cls, band in hand:
        for node in graph.subjects(RDF.type, cls):
            key = str(node)
            if key in nodes:
                continue
            nodes[key] = _node(key, band, label(graph, node),
                               body=_text(graph, node), origin="stated")

    # element -> risk, the attachment risk storming is built on
    for element, _p, risk in graph.triples((None, BEAMR.hasRisk, None)):
        links.append(_link(str(risk), str(element), "attaches",
                           label_text="hasRisk", editable=True))
    for source, _p, element in graph.triples((None, BEAMR.originatedFrom, None)):
        links.append(_link(str(source), str(element), "attaches",
                           label_text="originatedFrom", editable=True))

    chain = (
        (BEAMR.isRiskSourceFor, "isRiskSourceFor"),
        (BEAMR.hasConsequence, "hasConsequence"),
        (BEAMR.hasImpact, "hasImpact"),
        (BEAMR.modifiesRiskConcept, "modifiesRiskConcept"),
    )
    for predicate, name in chain:
        for subject, _p, obj in graph.triples((None, predicate, None)):
            if str(subject) in nodes and str(obj) in nodes:
                links.append(_link(str(subject), str(obj), "chain",
                                   label_text=name, editable=True))


def _scope_layer(scope: dict, nodes: dict, links: list) -> None:
    """The frame, as the notation's Context box and the outcomes it forbids."""
    if not scope.get("present"):
        return
    context_id = scope["id"]
    nodes[context_id] = _node(
        context_id, "context", "Context",
        body=scope.get("desiredOutcome"), origin="stated",
        extra={"statedBy": scope.get("statedBy")},
    )
    for outcome in scope.get("undesiredOutcomes", []):
        nodes.setdefault(outcome["id"], _node(
            outcome["id"], "consequence", outcome["label"],
            body=outcome.get("description"), origin="stated",
        ))
        links.append(_link(context_id, outcome["id"], "chain", label_text="undesiredOutcome"))


def _owners(graph: Graph) -> dict[str, set[str]]:
    """Which architecture holds each element, so one can be focused on."""
    held: dict[str, set[str]] = {}
    for system in graph.subjects(RDF.type, BEAM.System):
        for member in _members_of(graph, system):
            held.setdefault(str(member), set()).add(str(system))
    return held


def _business_layer(graph: Graph, nodes: dict, links: list) -> None:
    """The work each architecture is put to.

    Drawn so a reader can follow a risk out to the activity it belongs to
    instead of reading the boxes that raised it in isolation. Joined by
    pair:refinedBy, which is the only thing tying the two layers together.
    """
    for activity, _p, system in graph.triples((None, PAIR.refinedBy, None)):
        key = str(activity)
        name = graph.value(activity, _BP.name)
        entry = nodes.setdefault(key, _node(
            key, "business", str(name) if name else label(graph, activity),
            origin="stated", extra={"refines": [], "isActivity": True},
        ))
        if str(system) not in entry["refines"]:
            entry["refines"].append(str(system))
        links.append(_link(key, str(system), "chain", label_text="refinedBy"))


def _system_layer(graph: Graph, nodes: dict, links: list) -> None:
    """The architecture as one box, and a line down to each part it holds.

    A risk view that opens on every element of every architecture is read as a
    wiring diagram with risks stuck to it. The system is the coarse handle: it
    is what a risk is rolled up to while its parts are folded away, and the
    lines to those parts are what the canvas draws once they are unfolded.
    """
    for system in graph.subjects(RDF.type, BEAM.System):
        key = str(system)
        members = sorted(str(member) for member in _members_of(graph, system))
        nodes[key] = _node(
            key, "system", label(graph, system),
            body=_text(graph, system) or str(graph.value(system, BEAM.description) or "") or None,
            origin="stated", extra={"isSystem": True, "members": members},
        )
        for member in members:
            links.append(_link(key, member, "attaches", label_text="contains", contains=True))


def _is_step(graph: Graph, element: URIRef) -> bool:
    """A step is what reads or writes; the class hierarchy is not needed to see it."""
    return (element, BEAM.use, None) in graph or (element, BEAM.produce, None) in graph


def _risk_sources(graph: Graph, group: dict, tested: dict, below: dict) -> dict[URIRef, str]:
    """AIRO's Risk Source: an element with the potential to give rise to the risk.

    Read off this run rather than curated. Among the elements the finding cites
    and the ones its steps read, an element counts when it carries a data
    category the risk pattern's query actually tests. Where the pattern tests no
    category, what enters the path is what the risk arises from. Anything the
    cited path produces is excluded: that is where the risk ends up, not where
    it comes from.
    """
    cited = {URIRef(element["id"]) for element in group["evidence"]}
    steps = {element for element in cited if _is_step(graph, element)}
    produced = {target for step in steps for target in graph.objects(step, BEAM.produce)}
    upstream = {target for step in steps for target in graph.objects(step, BEAM.use)}

    pattern = (group.get("riskPattern") or {}).get("id") or ""
    wanted: set[str] = set()
    for name in tested.get(pattern, set()):
        wanted |= below.get(name, {name})

    carrying: dict[URIRef, str] = {}
    entering: dict[URIRef, str] = {}
    for element in (cited | upstream) - steps - produced:
        carried = sorted(
            label(graph, category)
            for category in graph.objects(element, PAIR.containsDataCategory)
            if short(category) in wanted
        )
        if carried:
            carrying[element] = "carries " + ", ".join(carried)
        else:
            entering[element] = "enters the path here"
    return carrying or entering


def _finding_layer(graph: Graph, groups: list[dict], nodes: dict, links: list) -> None:
    """Each concern as a Risk box, above the elements it cites.

    Suggested controls become Risk Controls, and one that a registered rewrite
    can actually build is marked - a control nothing can satisfy is not a
    control.
    """
    tested = _categories_tested()
    below, _family = _category_tree()
    held = _owners(graph)
    # Which work each architecture is put to, so a risk can name it without the
    # reader following pair:refinedBy by eye.
    work: dict[str, list[str]] = {}
    for activity, _p, system in graph.triples((None, PAIR.refinedBy, None)):
        work.setdefault(str(system), []).append(str(activity))
    for group in groups:
        key = group["key"]
        nodes[key] = _node(
            key, "risk", group["label"],
            body=group.get("description"),
            origin="derived",
            status=group.get("status"),
            extra={
                "corroboration": group["corroboration"],
                "scopeMatch": group.get("scopeMatch"),
                "settled": group.get("settled", False),
                "why": group.get("why", []),
                "motifs": group.get("motifs", []),
                "findingIds": group.get("findingIds", []),
                "clearable": group.get("clearable", False),
                "statedRisks": [r["id"] for r in group.get("statedRisks", [])],
                # Which architectures this concern stands in, so the reader can
                # focus on one instead of reading every risk at once.
                "systems": sorted({
                    system
                    for element in group["evidence"]
                    for system in held.get(element["id"], ())
                }),
            },
        )
        nodes[key]["activities"] = sorted({
            activity
            for system in nodes[key]["systems"]
            for activity in work.get(system, ())
        })
        for element in group["evidence"]:
            links.append(_link(key, element["id"], "attaches", label_text="concerns"))

        # The Risk Source is an element of the design, so the box names that
        # element and hangs off it - beamr:originatedFrom, drawn.
        for element, why in _risk_sources(graph, group, tested, below).items():
            source_id = "source:" + str(element)
            nodes.setdefault(source_id, _node(
                source_id, "source", label(graph, element), body=why, origin="derived",
                extra={"element": str(element), "systems": sorted(held.get(str(element), ()))},
            ))
            links.append(_link(source_id, key, "chain", label_text="isRiskSourceFor"))
            links.append(_link(source_id, str(element), "attaches",
                               label_text="originatedFrom"))

        for control in group.get("applicableControls", []) + group.get("otherControls", []):
            buildable = control in group.get("applicableControls", [])
            existing = nodes.get(control["id"])
            if existing is None:
                nodes[control["id"]] = _node(
                    control["id"], "control", control["label"], origin="derived",
                    extra={"buildable": buildable, "nature": control.get("nature")},
                )
            elif buildable:
                existing["buildable"] = True
            links.append(_link(control["id"], key, "chain", label_text="modifiesRiskConcept"))

        # A person said the same thing here: draw the agreement.
        for stated in group.get("statedRisks", []):
            links.append(_link(stated["id"], key, "chain", label_text="corroborates"))


def risk_diagram(graph: Graph, scope: dict, groups: list[dict]) -> dict:
    """The risk layer that sits above the architecture flow on the canvas.

    The flow itself is not repeated here - the canvas already has it from
    ``/api/graph``, and a second copy would drift from the first.
    """
    nodes: dict[str, dict] = {}
    links: list[dict] = []

    _finding_layer(graph, groups, nodes, links)
    _scope_layer(scope, nodes, links)
    _stated_layer(graph, nodes, links)
    _business_layer(graph, nodes, links)

    _system_layer(graph, nodes, links)

    for note in graph.subjects(RDF.type, BEAM.Note):
        key = str(note)
        nodes.setdefault(key, _node(key, "context", label(graph, note),
                                    body=_text(graph, note), origin="stated",
                                    extra={"isNote": True}))

    drawn = set(nodes)
    return {
        "nodes": sorted(nodes.values(), key=lambda row: (BANDS.index(row["band"]), row["title"])),
        # A link to something the diagram does not draw would be a dangling arrow.
        "links": [
            link for link in links
            if link["source"] in drawn and (link["kind"] == "attaches" or link["target"] in drawn)
        ],
        "bands": list(BANDS),
    }
