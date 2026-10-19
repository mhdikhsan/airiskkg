"""Possible risks: what the library would raise if a drawing said a little more.

A motif matches only an element whose role sits at or below the role its node
names. People draw and tag at their own level: a category or a parent role, an
untagged box, a part left out. Here each motif is matched again with those
relaxed (a reading), the tags and parts that would complete it become
suggestions, and the library's own queries run over a copy of the graph that
carries them. What the copy raises and the submitted graph does not is a
possible risk, reported with the suggestions it rests on. Nothing is written to
the submitted graph, and no query reads anything this module adds.
"""
from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

from rdflib import RDF, RDFS, Graph, Literal, URIRef

from airiskkg.assessment_runner import (
    BEAM,
    PAIR,
    REPO_ROOT,
    AssessmentResult,
    _derive_facts,
    load_base_graph,
    run_assessment_from_text,
    run_construct_query,
)
from airiskkg.workbench.templates import motif_templates
from airiskkg.workbench.terms import PROCESS_CLASS_NAMES, display_label, label, role_label, short

PLACEHOLDER = "urn:pair-ai:possible:"
_PAT = "http://w3id.org/airiskkg/patterns#"
EXACT, FREE = "exact", "free"
CATEGORY, PARENT, UNTAGGED, MISSING = "category", "parent", "untagged", "missing"
# What each way of falling short costs a reading: a category tag is the
# high-level tagging B-3 invites, a missing part is the most to ask for.
COST = {EXACT: 0, FREE: 0, CATEGORY: 1, PARENT: 2, UNTAGGED: 2, MISSING: 3}
MAX_COST_PER_NODE = 1.5
# Above the categories: tagging with one says nothing about which node it is.
_TOPS = {PAIR.ProcessingStep, PAIR.ResourceRole}
_FLOW = {"use": BEAM.use, "produce": BEAM.produce}
# What an untagged element's class already says it is. Plain Data says nothing.
_CLASS_KINDS = {
    BEAM.Train: (PAIR.TrainingEvaluationRoles,),
    BEAM.Generate: (PAIR.GenerationRoles,),
    BEAM.Infer: (PAIR.PredictionRoles, PAIR.GenerationRoles),
    BEAM.Transform: (PAIR.DataPreparationRoles,),
    BEAM.StatisticalModel: (PAIR.ModelRoles,),
}


@dataclass
class _Vocabulary:
    parents: dict[URIRef, set[URIRef]]
    subclass: dict[URIRef, set[URIRef]]
    categories: set[URIRef]
    risks: dict[str, list[URIRef]]
    match_query: dict[str, str]
    risk_query: dict[URIRef, str]
    anywhere: list[URIRef]
    reads: dict[URIRef, set[URIRef]]
    escapes: set[URIRef]
    barriers: dict[URIRef, set[URIRef]]
    match_reads: dict[str, set[URIRef]]
    feeds: set[URIRef]
    checked_by: dict[str, list[URIRef]]
    match_vars: dict[str, dict[str, str]]
    unioned: set[URIRef]

    def ancestors(self, role: URIRef) -> set[URIRef]:
        return _closure(role, self.parents)

    def class_ancestors(self, cls: URIRef) -> set[URIRef]:
        return _closure(cls, self.subclass)


def _closure(start: URIRef, up: dict[URIRef, set[URIRef]]) -> set[URIRef]:
    seen, frontier = {start}, [start]
    while frontier:
        for parent in up.get(frontier.pop(), ()):
            if parent not in seen:
                seen.add(parent)
                frontier.append(parent)
    return seen


_VOCABULARY: _Vocabulary | None = None


def _path_of(kb: Graph, owner: URIRef) -> str | None:
    implementation = kb.value(owner, PAIR.implementedBy)
    path = kb.value(implementation, PAIR.implementationPath) if implementation is not None else None
    return str(REPO_ROOT / str(path)) if path is not None else None


def _without_escapes(text: str) -> tuple[str, str]:
    """A risk query's text split into what must hold and its FILTER NOT EXISTS escapes."""
    kept, escapes, at = [], [], 0
    for found in re.finditer(r"FILTER\s+NOT\s+EXISTS\s*\{", text):
        if found.start() < at:
            continue
        depth, end = 1, found.end()
        while depth and end < len(text):
            depth += {"{": 1, "}": -1}.get(text[end], 0)
            end += 1
        kept.append(text[at:found.start()])
        escapes.append(text[found.start():end])
        at = end
    kept.append(text[at:])
    return "".join(kept), "".join(escapes)


def _roles_named(text: str, roles: set[URIRef]) -> set[URIRef]:
    return {PAIR[name] for name in re.findall(r"pair:(\w+)", text)} & roles


def _vocabulary() -> _Vocabulary:
    global _VOCABULARY
    if _VOCABULARY is None:
        kb = load_base_graph()
        parents: dict[URIRef, set[URIRef]] = {}
        for role, parent in kb.subject_objects(PAIR.subRoleOf):
            parents.setdefault(role, set()).add(parent)
        subclass: dict[URIRef, set[URIRef]] = {}
        for cls, parent in kb.subject_objects(RDFS.subClassOf):
            if isinstance(cls, URIRef) and isinstance(parent, URIRef):
                subclass.setdefault(cls, set()).add(parent)
        motifs = set(kb.subjects(RDF.type, PAIR.GraphMotif))
        patterns = set(kb.subjects(RDF.type, PAIR.RiskPattern))
        roles = set(kb.subjects(RDF.type, PAIR.PatternRole))
        risk_query = {r: p for r in patterns if (p := _path_of(kb, r))}
        match_query = {short(m): p for m in motifs if (p := _path_of(kb, m))}
        reads: dict[URIRef, set[URIRef]] = {}
        escapes: set[URIRef] = set()
        barriers: dict[URIRef, set[URIRef]] = {}
        for pattern, path in risk_query.items():
            must, unless = _without_escapes(Path(path).read_text(encoding="utf-8"))
            reads[pattern] = _roles_named(must, roles)
            barriers[pattern] = _roles_named(unless, roles)
            escapes |= barriers[pattern]
        # every risk query that reads a motif's match, linked to it or not
        texts = {r: Path(p).read_text(encoding="utf-8") for r, p in risk_query.items()}
        named = {r: set(re.findall(r"pat:(\w+)", text)) for r, text in texts.items()}
        every = {short(m) for m in motifs} | {short(n) for m in motifs for n in kb.objects(m, PAIR.hasPatternNode)}
        generic = {r for r, names in named.items() if not names & every}  # reads whatever match it is given
        checked_by: dict[str, list[URIRef]] = {}
        for motif in motifs:
            names = {short(motif)} | {short(n) for n in kb.objects(motif, PAIR.hasPatternNode)}
            linked = set(kb.objects(motif, PAIR.hasRiskPattern))
            checked_by[short(motif)] = sorted(
                (r for r in risk_query if named[r] & names or r in linked or r in generic), key=str)
        # what the propagation rules turn into data categories a risk query reads
        feeds: set[URIRef] = set()
        flow_escapes: set[URIRef] = set()
        for output_type in (PAIR.DataCategoryPropagation, PAIR.BusinessFlowDerivation):
            for implementation in kb.subjects(PAIR.producesOutputType, output_type):
                path = kb.value(implementation, PAIR.implementationPath)
                if path is not None:
                    must, unless = _without_escapes((REPO_ROOT / str(path)).read_text(encoding="utf-8"))
                    feeds |= _roles_named(must, roles)
                    flow_escapes |= _roles_named(unless, roles)
        escapes |= flow_escapes
        # a role that stops a category travelling bars every pattern; a query's own escape bars only it
        barriers = {pattern: own | flow_escapes for pattern, own in barriers.items()}
        _VOCABULARY = _Vocabulary(
            parents=parents,
            subclass=subclass,
            categories=set(kb.subjects(RDF.type, PAIR.RoleCategory)),
            risks={short(m): sorted(kb.objects(m, PAIR.hasRiskPattern), key=str) for m in motifs},
            match_query=match_query,
            risk_query=risk_query,
            anywhere=sorted((r for r in patterns if kb.value(r, PAIR.hasMotif) is None), key=str),
            reads=reads,
            escapes=escapes,
            # a role a query treats as a barrier is never suggested for it: it would clear the risk
            barriers=barriers,
            match_reads={m: _roles_named(Path(p).read_text(encoding="utf-8"), roles)
                         for m, p in match_query.items()},
            feeds=feeds,
            checked_by=checked_by,
            # a query reading several match shapes in a UNION runs slower bound than free
            unioned={r for r, text in texts.items() if text.count("pair:MotifMatch") > 2},
            # which query variable each pattern node's binding carries
            match_vars={m: dict(re.findall(r"bindsPatternNode\s+pat:(\w+)\s*;\s*pair:matchedElement\s+\?(\w+)",
                                           Path(p).read_text(encoding="utf-8")))
                        for m, p in match_query.items()},
        )
    return _VOCABULARY


def reset_cache() -> None:
    global _VOCABULARY
    _VOCABULARY = None


@dataclass
class _Element:
    iri: URIRef
    process: bool
    classes: set[URIRef]
    roles: set[URIRef]
    uses: set[URIRef] = field(default_factory=set)
    produces: set[URIRef] = field(default_factory=set)


def _elements(graph: Graph, vocab: _Vocabulary) -> dict[URIRef, _Element]:
    process_classes = {BEAM[name] for name in PROCESS_CLASS_NAMES}
    out: dict[URIRef, _Element] = {}
    for subject, cls in graph.subject_objects(RDF.type):
        if not isinstance(subject, URIRef) or not str(cls).startswith(str(BEAM)):
            continue
        if cls in (BEAM.System, BEAM.Agent, BEAM.Task):
            continue
        element = out.setdefault(subject, _Element(subject, False, set(), set()))
        element.classes |= vocab.class_ancestors(cls)
    for element in out.values():
        element.process = bool(element.classes & process_classes)
        element.roles = {r for r in graph.objects(element.iri, PAIR.playsRole) if isinstance(r, URIRef)}
        element.uses = {o for o in graph.objects(element.iri, BEAM.use) if o in out}
        element.produces = {o for o in graph.objects(element.iri, BEAM.produce) if o in out}
    return out


def _fit(element: _Element, node: dict, accepts: list[URIRef], vocab: _Vocabulary) -> tuple | None:
    """How an element can take a pattern node, and the role it would be asked for; None when it cannot."""
    wants_process = node["cls"] in PROCESS_CLASS_NAMES
    if wants_process != element.process:
        return None
    if not wants_process and BEAM[node["cls"]] not in element.classes:
        return None
    if not accepts:
        return FREE, None
    for wanted in accepts:
        if any(wanted in vocab.ancestors(role) for role in element.roles):
            return EXACT, wanted
    told = {role for role in element.roles if role not in _TOPS}
    if not told:
        return UNTAGGED, accepts[0]
    for wanted in accepts:
        coarser = {role for role in told if role in vocab.ancestors(wanted)}
        if coarser:
            return (CATEGORY if coarser <= vocab.categories else PARENT), wanted
    return None  # it says it is something else


def _accepts(motif: str, nodes: dict, vocab: _Vocabulary) -> dict[str, list[URIRef]]:
    """Each node's declared role, then the roles its matcher reads that no node declares.

    A pattern node holds one role, and four matchers accept more (External
    dependency reads a pre-trained model, an artifact and a serving image too).
    An extra goes to the node on its side whose role shares its category, or to
    that side's only node with a role.
    """
    process_tops = {PAIR.ProcessingStep, PAIR.ControlRoles}
    side = lambda role: bool(vocab.ancestors(role) & process_tops)
    accepts = {k: [PAIR[n["roles"][0]]] if n["roles"] else [] for k, n in nodes.items()}
    declared = {r for roles in accepts.values() for r in roles}
    for extra in sorted(vocab.match_reads.get(motif, set()) - declared, key=str):
        same_side = [k for k, roles in accepts.items() if roles and side(roles[0]) == side(extra)
                     and (nodes[k]["cls"] in PROCESS_CLASS_NAMES) == side(extra)]
        kin = [k for k in same_side if _category_of(accepts[k][0], vocab) == _category_of(extra, vocab)]
        for key in kin or (same_side if len(same_side) == 1 else []):
            accepts[key].append(extra)
    return accepts


@dataclass
class Reading:
    motif: str
    bound: dict[str, URIRef]
    fits: dict[str, str]
    missing: list[str]
    match: URIRef | None = None   # set when the motif's own matcher already found it
    asks: dict[str, URIRef] = field(default_factory=dict)   # the role each bound node would be tagged with

    @property
    def cost(self) -> int:
        return sum(COST[f] for f in self.fits.values()) + COST[MISSING] * len(self.missing)

    @property
    def evidence(self) -> int:
        return sum(1 for f in self.fits.values() if f in (EXACT, CATEGORY, PARENT))

    @property
    def complete(self) -> bool:
        return not self.missing and all(f in (EXACT, FREE) for f in self.fits.values())


def _neighbours(template: dict) -> dict[str, list[tuple[str, str, bool]]]:
    """For each node, (other node, predicate, this node is the edge's source)."""
    around: dict[str, list[tuple[str, str, bool]]] = {n["key"]: [] for n in template["nodes"]}
    for source, predicate, target in template["edges"]:
        around.setdefault(source, []).append((target, predicate, True))
        around.setdefault(target, []).append((source, predicate, False))
    return around


def _edge_holds(elements, source: URIRef, predicate: str, target: URIRef) -> bool:
    step = elements[source]
    return target in (step.uses if predicate == "use" else step.produces)


def _readings(motif: str, template: dict, elements: dict[URIRef, _Element], vocab) -> list[Reading]:
    nodes = {n["key"]: n for n in template["nodes"]}
    around = _neighbours(template)
    allowed_missing = len(nodes) // 3
    budget = MAX_COST_PER_NODE * len(nodes)
    accepts = _accepts(motif, nodes, vocab)
    fits = {
        key: {e.iri: fit for e in elements.values() if (fit := _fit(e, node, accepts[key], vocab))}
        for key, node in nodes.items()
    }
    found: dict[frozenset, Reading] = {}

    def spent(how: dict[str, str], missing: list[str]) -> int:
        return sum(COST[f[0]] for f in how.values()) + COST[MISSING] * len(missing)

    def grow(bound: dict[str, URIRef], how: dict[str, str], missing: list[str]) -> None:
        if spent(how, missing) > budget:
            return
        frontier = [k for k in nodes if k not in bound and k not in missing
                    and any(other in bound for other, _p, _s in around[k])]
        if not frontier:
            missing = missing + [k for k in nodes if k not in bound and k not in missing]
            if len(missing) > allowed_missing or len(bound) < 2:
                return
            reading = Reading(motif, dict(bound), {k: f[0] for k, f in how.items()}, missing,
                              asks={k: f[1] for k, f in how.items() if f[1] is not None})
            if reading.evidence and reading.cost <= budget:
                found.setdefault(frozenset(bound.items()), reading)
            return
        key = frontier[0]
        taken = set(bound.values())
        for element, fit in fits[key].items():
            if element in taken:
                continue
            if all(_edge_holds(elements, element if is_source else bound[other], predicate,
                               bound[other] if is_source else element)
                   for other, predicate, is_source in around[key] if other in bound):
                grow({**bound, key: element}, {**how, key: fit}, missing)
        if len(missing) < allowed_missing:
            grow(bound, how, missing + [key])

    # anchored on a step, so every reading is connected and has a step in it
    for anchor, node in nodes.items():
        if node["cls"] in PROCESS_CLASS_NAMES:
            for element, fit in fits[anchor].items():
                grow({anchor: element}, {anchor: fit}, [])
    return list(found.values())


def _best(readings: list[Reading]) -> list[Reading]:
    """Drop a reading another one extends: the larger says everything it says."""
    readings.sort(key=lambda r: (r.cost, -len(r.bound)))
    kept: list[Reading] = []
    for reading in readings:
        items = set(reading.bound.items())
        if any(items <= set(other.bound.items()) for other in kept):
            continue
        kept.append(reading)
    return kept


def find_readings(graph: Graph) -> list[Reading]:
    """Every relaxed match of a risk-carrying motif that the strict matcher misses."""
    vocab = _vocabulary()
    elements = _elements(graph, vocab)
    out: list[Reading] = []
    for motif, template in motif_templates().items():
        if not vocab.risks.get(motif) or motif not in vocab.match_query:
            continue
        out.extend(_best([r for r in _readings(motif, template, elements, vocab) if not r.complete]))
    return sorted(out, key=lambda r: (r.cost, r.motif))


# ---- what each reading would raise ----

@dataclass
class _Suggestion:
    kind: str                 # "role" or "add"
    element: URIRef
    role: URIRef | None
    node: dict
    links: list = field(default_factory=list)
    cost: int = 0
    condition: bool = False   # asked for by a risk pattern's condition, not by a motif node
    category: URIRef | None = None   # kind "category": the data category to mark it with
    why: str | None = None


def _placeholder(reading: Reading, key: str) -> URIRef:
    digest = hashlib.sha1("|".join(sorted(str(e) for e in reading.bound.values())).encode()).hexdigest()[:10]
    return URIRef(f"{PLACEHOLDER}{reading.motif}/{key}/{digest}")


def _suggestions(reading: Reading, graph: Graph) -> list[_Suggestion]:
    template = motif_templates()[reading.motif]
    nodes = {n["key"]: n for n in template["nodes"]}
    out = []
    for key, element in reading.bound.items():
        if reading.fits[key] in (CATEGORY, PARENT, UNTAGGED):
            out.append(_Suggestion("role", element, reading.asks[key], nodes[key]))
    for key in reading.missing:
        node = nodes[key]
        stand_in = _placeholder(reading, key)
        links = []
        for source, predicate, target in template["edges"]:
            if key in (source, target):
                other = target if key == source else source
                if other in reading.bound:
                    links.append((predicate, reading.bound[other], key == source))
        out.append(_Suggestion("add", stand_in, PAIR[node["roles"][0]] if node["roles"] else None, node, links))
    return out


def _triples(suggestions: list[_Suggestion], members: dict[URIRef, set[URIRef]]) -> list[tuple]:
    """What writing the suggestions into a graph adds."""
    out = []
    for s in suggestions:
        if s.kind == "category":
            out.append((s.element, PAIR.containsDataCategory, s.category))
            continue
        if s.kind == "role":
            out.append((s.element, PAIR.playsRole, s.role))
            continue
        is_step = s.node["cls"] in PROCESS_CLASS_NAMES
        out += [(s.element, RDF.type, BEAM[s.node["cls"]]), (s.element, RDFS.label, Literal(s.node["label"]))]
        if s.role is not None:
            out.append((s.element, PAIR.playsRole, s.role))
        for predicate, other, outgoing in s.links:
            out.append((s.element, _FLOW[predicate], other) if outgoing else (other, _FLOW[predicate], s.element))
            for system in members.get(other, ()):
                out.append((system, BEAM.hasProcess if is_step else BEAM.hasResource, s.element))
    return out


def _propagates(triples, vocab: _Vocabulary) -> bool:
    """Whether a propagation rule could read any of these: otherwise nothing new is derived."""
    for _s, predicate, obj in triples:
        if predicate in (PAIR.containsDataCategory, BEAM.use, BEAM.produce, RDF.type):
            return True
        if predicate == PAIR.playsRole and vocab.ancestors(obj) & vocab.feeds:
            return True
    return False


class _Trial:
    """Triples added to a working graph for one check and taken out again, with what they derive."""

    def __init__(self, graph: Graph):
        self.graph = graph
        self.added: list[tuple] = []

    def add(self, triples, derive: bool = True) -> None:
        new = [t for t in triples if t not in self.graph]
        for triple in new:
            self.graph.add(triple)
        self.added += new
        if derive and _propagates(new, _vocabulary()):
            self.added += list(_derive_facts(self.graph))

    def undo(self) -> None:
        for triple in self.added:
            self.graph.remove(triple)
        self.added = []


def _findings(graph: Graph) -> dict[URIRef, dict]:
    return {
        finding: {
            "pattern": graph.value(finding, PAIR.generatedByRiskPattern),
            "evidence": {e for e in graph.objects(finding, PAIR.hasEvidence)},
            "match": graph.value(finding, PAIR.generatedFromMatch),
            "label": graph.value(finding, RDFS.label),
        }
        for finding in graph.subjects(RDF.type, PAIR.RiskFinding)
    }


def _concern(pattern, evidence) -> tuple:
    return pattern, frozenset(e for e in evidence if not str(e).startswith(PLACEHOLDER))


def matched_readings(graph: Graph) -> list[Reading]:
    """The matches the strict matcher made, as readings: their conditions can still be short."""
    vocab = _vocabulary()
    out = []
    for match in graph.subjects(RDF.type, PAIR.MotifMatch):
        motif = graph.value(match, PAIR.matchesMotif)
        if motif is None or not vocab.risks.get(short(motif)):
            continue
        bound = {}
        for binding in graph.objects(match, PAIR.hasNodeBinding):
            node, element = graph.value(binding, PAIR.bindsPatternNode), graph.value(binding, PAIR.matchedElement)
            if node is not None and isinstance(element, URIRef):
                bound[short(node)] = element
        out.append(Reading(short(motif), bound, {k: EXACT for k in bound}, [], match))
    return out


def _category_of(role: URIRef, vocab: _Vocabulary) -> URIRef | None:
    hits = vocab.ancestors(role) & vocab.categories
    return min(hits, key=str) if hits else None


def _near(reading: Reading, elements: dict[URIRef, _Element], hops: int = 6) -> set[URIRef]:
    """Elements within a few flow hops of a reading: where its conditions look."""
    seen = {e for e in reading.bound.values() if e in elements}
    frontier = set(seen)
    for _ in range(hops):
        step = set()
        for iri in frontier:
            element = elements[iri]
            step |= element.uses | element.produces
            step |= {o.iri for o in elements.values() if iri in o.uses or iri in o.produces}
        frontier = step - seen
        seen |= frontier
    return seen


def _conditions(reading: Reading, nodes: dict, elements: dict[URIRef, _Element],
                vocab: _Vocabulary) -> dict[URIRef, list[_Suggestion]]:
    """The roles a reading's risk patterns read near it that the elements do not yet say.

    Only within what an element already says it is: a role under its coarse tag,
    or, for an element the reading binds, one of the same category as the node
    it takes. So an answer tagged "Prompts and responses" may be asked to say
    "User facing output", never "Agent goal"; an untagged element the reading
    does not bind is asked nothing.
    """
    out: dict[URIRef, list[_Suggestion]] = {}
    process_tops = {PAIR.ProcessingStep, PAIR.ControlRoles}
    node_of = {iri: key for key, iri in reading.bound.items()}
    for iri in _near(reading, elements):
        element = elements[iri]
        anchors = {r for r in element.roles if r not in _TOPS}
        key = node_of.get(iri)
        node = nodes.get(key, {}) if key else {}
        node_role = PAIR[node["roles"][0]] if node.get("roles") else None
        kinds = {_category_of(r, vocab) for r in anchors}
        if node_role is not None:
            kinds.add(_category_of(node_role, vocab))
        if not anchors:
            kinds |= {k for cls in element.classes for k in _CLASS_KINDS.get(cls, ())}
        kinds.discard(None)
        if not kinds:
            continue
        for pattern in vocab.checked_by.get(reading.motif, []) + vocab.anywhere:
            for role in vocab.reads.get(pattern, set()) | vocab.feeds:
                if role in vocab.barriers.get(pattern, ()) or role in _TOPS or role in vocab.categories:
                    continue
                above = vocab.ancestors(role)
                if any(role in vocab.ancestors(r) for r in element.roles):
                    continue  # it already says so
                if bool(above & process_tops) != element.process:
                    continue
                refines = anchors & above
                said_by_class = not anchors and _category_of(role, vocab) in kinds
                if not refines and not said_by_class and (key is None or _category_of(role, vocab) not in kinds):
                    continue
                cost = 1 if refines and refines <= vocab.categories else 2
                out.setdefault(pattern, []).append(
                    _Suggestion("role", iri, role, node, cost=cost, condition=True))
    # What the library says each link needs, on the elements the reading binds
    from airiskkg.workbench.risk_context import LINK_CONTEXT

    for pattern in vocab.checked_by.get(reading.motif, []):
        context = LINK_CONTEXT.get((short(pattern), reading.motif))
        if not context:
            continue
        why = "; ".join(context["says"])
        for key, kind, value in context["marks"]:
            iri = reading.bound.get(key)
            if iri is None or iri not in elements:
                continue
            if kind == "role":
                role = PAIR[value]
                if role in vocab.barriers.get(pattern, ()) or any(role in vocab.ancestors(r) for r in elements[iri].roles):
                    continue
                out.setdefault(pattern, []).append(
                    _Suggestion("role", iri, role, nodes.get(key, {}), cost=2, condition=True, why=why))
            elif kind == "cat":
                out.setdefault(pattern, []).append(
                    _Suggestion("category", iri, None, nodes.get(key, {}), cost=2, condition=True,
                                category=PAIR[value], why=why))
    # the same ask reached by two routes is asked once
    return {p: list({(a.kind, a.element, a.role, a.category): a for a in asks}.values()) for p, asks in out.items()}


def _confirmed(lean: Graph, reading: Reading, suggestions, vocab: _Vocabulary, members) -> tuple | None:
    """The motif's own matcher's match of a reading once its suggestions are in, or None.

    Run on the drawing and the role and class hierarchy alone: the knowledge base
    would only slow the matcher down, and a declaration is not trusted to say
    what its query matches.
    """
    if reading.match is not None:
        return reading.match, []
    wanted = {**reading.bound, **{x.node["key"]: x.element for x in suggestions if x.kind == "add"}}
    names = vocab.match_vars.get(reading.motif, {})
    # bound to the reading's own elements, so the matcher checks one candidate instead of searching
    bindings = {names[key]: element for key, element in wanted.items() if key in names}
    trial = _Trial(lean)
    trial.add(_triples(suggestions, members), derive=False)
    try:
        constructed = run_construct_query(lean, vocab.match_query[reading.motif], **bindings)
    finally:
        trial.undo()
    for match in constructed.subjects(RDF.type, PAIR.MotifMatch):
        bindings = list(constructed.objects(match, PAIR.hasNodeBinding))
        binds = {short(constructed.value(b, PAIR.bindsPatternNode)): constructed.value(b, PAIR.matchedElement)
                 for b in bindings if constructed.value(b, PAIR.bindsPatternNode) is not None}
        if all(binds.get(k, v) == v for k, v in wanted.items()) and set(wanted.values()) <= set(binds.values()):
            triples = list(constructed.triples((match, None, None)))
            for binding in bindings:
                triples += list(constructed.triples((binding, None, None)))
            return match, triples
    return None


def _raised(graph: Graph, vocab: _Vocabulary, pattern: URIRef, match: URIRef) -> dict[URIRef, dict]:
    if pattern in vocab.unioned:
        found = _findings(run_construct_query(graph, vocab.risk_query[pattern]))
        return {f: d for f, d in found.items() if d["match"] == match}
    return _findings(run_construct_query(graph, vocab.risk_query[pattern], match=match))


def _fewest(asks: list, still_raises) -> list:
    """A smallest set of asks that still raises it, dropping halves before single asks (ddmin)."""
    chunk = max(1, len(asks) // 2)
    while asks and chunk >= 1:
        at, dropped = 0, False
        while at < len(asks) and len(asks) > 1:
            fewer = asks[:at] + asks[at + chunk:]
            if fewer and still_raises(fewer):
                asks, dropped = fewer, True
            else:
                at += chunk
        if not dropped:
            chunk //= 2
        chunk = min(chunk, max(1, len(asks) // 2)) if chunk else 0
    return asks


def _check(graph: Graph, lean: Graph, reading: Reading, suggestions, vocab: _Vocabulary, members,
           elements, real: dict) -> list[tuple[Reading, list, dict]]:
    """What one reading's risk patterns raise on its match, each with exactly what it needed.

    First with the motif's own suggestions; then, pattern by pattern, with the
    condition roles that pattern reads, trimmed to the ones it cannot do
    without. Each risk query is bound to the one match: unbound, every query
    would walk every match in the graph again. Everything added is taken out.
    """
    confirmed = _confirmed(lean, reading, suggestions, vocab, members)
    if confirmed is None:
        return []
    match, match_triples = confirmed
    nodes = {n["key"]: n for n in motif_templates()[reading.motif]["nodes"]}
    patterns = [p for p in vocab.checked_by.get(reading.motif, []) + vocab.anywhere if p in vocab.risk_query]
    out = []
    seen = set(real)
    trial = _Trial(graph)
    try:
        trial.add(_triples(suggestions, members) + match_triples)
        for pattern in patterns if suggestions else []:  # a strict match raised its own already
            for finding, data in _raised(graph, vocab, pattern, match).items():
                if finding not in seen and suggestions:
                    seen.add(finding)
                    out.append((reading, list(suggestions), data))
        conditions = _conditions(reading, nodes, elements, vocab)
        asking = [p for p in patterns if conditions.get(p)]
        if not asking:
            return out
        tried: dict[tuple, dict[URIRef, dict]] = {}

        def raised_with(pattern: URIRef, asks: list[_Suggestion]) -> dict[URIRef, dict]:
            """What one pattern raises with exactly these conditions in; each set tried once."""
            key = (pattern, frozenset(id(a) for a in asks))
            if key not in tried:
                attempt = _Trial(graph)
                try:
                    attempt.add(_triples(asks, members))
                    tried[key] = _raised(graph, vocab, pattern, match)
                finally:
                    attempt.undo()
            return tried[key]

        # every pattern's conditions in at once, except for a pattern one of them would clear
        every = list({id(a): a for p in asking for a in conditions[p]}.values())
        roles = {a.role for a in every if a.role is not None}
        together = [p for p in asking if not roles & vocab.barriers.get(p, set())]
        fresh: dict[URIRef, list] = {}
        extra = _Trial(graph)
        try:
            extra.add(_triples(every, members))
            for pattern in together:
                for finding, data in _raised(graph, vocab, pattern, match).items():
                    if finding not in seen:
                        fresh.setdefault(pattern, []).append((finding, data))
        finally:
            extra.undo()
        for pattern in asking:
            if pattern not in together:
                for finding, data in raised_with(pattern, conditions[pattern]).items():
                    if finding not in seen:
                        fresh.setdefault(pattern, []).append((finding, data))
        for pattern, raised in fresh.items():
            for finding, data in raised:
                # another pattern's condition can be what makes it hold, so the fewest are cut from all of them
                asks = conditions[pattern]
                if finding not in raised_with(pattern, asks):
                    asks = every
                    if finding not in raised_with(pattern, asks):
                        continue
                here = data["evidence"] | set(reading.bound.values())
                own = [a for a in asks if a.element in here]
                needed = own if own and len(own) < len(asks) and finding in raised_with(pattern, own) else list(asks)
                needed = _fewest(needed, lambda fewer: finding in raised_with(pattern, fewer))
                seen.add(finding)
                out.append((reading, list(suggestions) + needed, data))
    finally:
        trial.undo()
    return out


def _overlap(a: frozenset, b: frozenset) -> float:
    return len(a & b) / len(a | b) if a | b else 0.0


def _distinct(entries: list[dict], raised: set[tuple]) -> list[dict]:
    """One possible risk per place: the cheapest of those that mostly cite the same elements.

    And none where the run already raised the same risk on mostly the same
    elements: that is the finding, read a second way.
    """
    kept: list[dict] = []
    for entry in sorted(entries, key=lambda e: (e["cost"], len(e["needs"]))):
        same = lambda p, ev: p == entry["pattern"] and _overlap(ev, entry["evidence"]) >= 0.5
        if any(same(p, ev) for p, ev in raised) or any(same(k["pattern"], k["evidence"]) for k in kept):
            continue
        kept.append(entry)
    return kept


BUDGET_SECONDS = 30.0


def possible_risks(ttl: str, result: AssessmentResult | None = None, budget: float | None = BUDGET_SECONDS,
                   stop=None) -> dict:
    """Possible risks for a submitted Turtle graph, each with the suggestions it rests on.

    Readings are checked cheapest first and the check stops at the budget, so a
    large drawing answers in bounded time with its likeliest readings; how many
    were left is reported.
    """
    started = time.monotonic()
    if result is None:
        result = run_assessment_from_text(ttl)
    base = result.combined_graph
    vocab = _vocabulary()
    # what the strict matcher found and only a condition keeps short goes first
    readings = sorted(matched_readings(base) + find_readings(base), key=lambda r: (r.cost, r.motif))
    if not readings:
        return {"risks": [], "readings": 0, "unchecked": 0}
    elements = _elements(base, vocab)
    members: dict[URIRef, set[URIRef]] = {}
    for system in base.subjects(RDF.type, BEAM.System):
        for predicate in (BEAM.hasProcess, BEAM.hasResource, BEAM.hasAgent, BEAM.contain):
            for element in base.objects(system, predicate):
                members.setdefault(element, set()).add(system)

    real = _findings(base)
    seen = {_concern(f["pattern"], f["evidence"]) for f in real.values()}
    lean = Graph().parse(data=ttl, format="turtle") if ttl.strip() else Graph()
    kb = load_base_graph()
    for predicate in (PAIR.subRoleOf, RDFS.subClassOf):
        for triple in kb.triples((None, predicate, None)):
            lean.add(triple)
    graph = Graph()
    for triple in base:
        graph.add(triple)
    grouped: dict[tuple, dict] = {}
    unchecked = 0
    for at, reading in enumerate(readings):
        # out of time, or a newer question was asked: what is left is reported unchecked
        if (budget is not None and time.monotonic() - started > budget) or (stop is not None and stop()):
            unchecked = len(readings) - at
            break
        suggestions = _suggestions(reading, base)
        for reading, needs, data in _check(graph, lean, reading, suggestions, vocab, members, elements, real):
            concern = _concern(data["pattern"], data["evidence"])
            if concern in seen:
                continue
            cost = reading.cost + sum(n.cost for n in needs if n.condition)
            entry = grouped.get(concern)
            if entry is None or cost < entry["cost"]:
                grouped[concern] = {"pattern": data["pattern"], "label": data["label"],
                                    "evidence": concern[1], "reading": reading, "needs": needs, "cost": cost}

    def describe(s: _Suggestion) -> dict:
        if s.kind == "category":
            return {"kind": "category", "condition": True, "why": s.why,
                    "element": str(s.element), "elementLabel": label(base, s.element),
                    "category": str(s.category), "categoryLabel": role_label(s.category)}
        if s.kind == "role":
            was = sorted((r for r in base.objects(s.element, PAIR.playsRole)), key=str)
            return {"kind": "role", "condition": s.condition, "why": s.why,
                    "element": str(s.element), "elementLabel": label(base, s.element),
                    "role": str(s.role), "roleLabel": role_label(s.role),
                    "was": [display_label(label(base, r)) for r in was]}
        return {"kind": "add", "cls": s.node["cls"], "label": s.node["label"],
                "role": str(s.role) if s.role is not None else None,
                "roleLabel": role_label(s.role) if s.role is not None else None,
                "links": [{"predicate": p, "outgoing": out, "element": str(o), "elementLabel": label(base, o)}
                          for p, o, out in s.links]}

    risks = []
    for entry in _distinct(list(grouped.values()), seen):
        reading = entry["reading"]
        needs = list({(n.kind, n.element, n.role, n.category): n for n in entry["needs"]}.values())
        risks.append({
            "pattern": str(entry["pattern"]),
            "label": str(entry["label"] or display_label(short(entry["pattern"]))),
            "evidence": sorted(str(e) for e in entry["evidence"]),
            "evidenceLabels": [label(base, e) for e in sorted(entry["evidence"], key=str)],
            "motif": reading.motif,
            "motifLabel": motif_templates()[reading.motif]["label"],
            "cost": entry["cost"],
            "needs": [describe(n) for n in needs],
        })
    # the fewest and smallest asks first: a category tag made precise is the likeliest reading
    risks.sort(key=lambda r: (r["cost"], len(r["needs"]), r["label"], r["evidence"]))
    return {"risks": risks, "readings": len(readings), "unchecked": unchecked}


def apply_needs(data: Graph, needs: list[dict], fresh) -> list[str]:
    """Write a possible risk's suggestions into the submitted graph; returns the new element ids.

    A role replaces any role it refines, which is the refinement B-3 asks for:
    whatever the coarser tag matched, the finer one still matches.
    """
    vocab = _vocabulary()
    touched: list[str] = []
    for need in needs:
        if need.get("kind") == "category":
            element = URIRef(need["element"])
            data.add((element, PAIR.containsDataCategory, URIRef(need["category"])))
            touched.append(str(element))
        elif need.get("kind") == "role":
            element, role = URIRef(need["element"]), URIRef(need["role"])
            above = vocab.ancestors(role) - {role}
            for old in list(data.objects(element, PAIR.playsRole)):
                if old in above:
                    data.remove((element, PAIR.playsRole, old))
            data.add((element, PAIR.playsRole, role))
            touched.append(str(element))
        elif need.get("kind") == "add":
            cls = need["cls"]
            is_step = cls in PROCESS_CLASS_NAMES
            element = fresh()
            data.add((element, RDF.type, BEAM[cls]))
            if is_step and cls != "Process":
                data.add((element, RDF.type, BEAM.Process))
            data.add((element, RDFS.label, Literal(need.get("label") or display_label(cls))))
            if need.get("role"):
                data.add((element, PAIR.playsRole, URIRef(need["role"])))
            for link in need.get("links") or []:
                other = URIRef(link["element"])
                flow = _FLOW[link["predicate"]]
                data.add((element, flow, other) if link["outgoing"] else (other, flow, element))
                for system in data.subjects(None, other):
                    if (system, RDF.type, BEAM.System) in data:
                        data.add((system, BEAM.hasProcess if is_step else BEAM.hasResource, element))
            touched.append(str(element))
    return touched
