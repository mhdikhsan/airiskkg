/* Which architecture holds a thing, for the panels that list things. */
import { state } from "../state.js";

const SPANNING = "Spans more than one architecture";
const UNCLAIMED = "Belongs to no system";

/** Keep only what belongs to the architecture currently on screen. */
export function onScreen(items, idsOf) {
  const graph = state.lastGraph;
  if (!graph || !graph.nodes) return items || [];
  const drawn = new Set(graph.nodes.map((n) => n.id));
  // `some`, not `every`: an item spanning two architectures stays visible from
  // both, which is the honest answer for something that genuinely spans them.
  return (items || []).filter((item) => (idsOf(item) || []).some((id) => drawn.has(id)));
}

/** element id -> architecture label, from a systems list. */
function ownerMap(systems) {
  const owner = new Map();
  for (const system of systems || []) {
    for (const id of system.members || []) owner.set(id, system.label);
  }
  return owner;
}

/** Group items under the architecture that holds them. */
export function groupBySystem(items, idsOf, systems) {
  const list = systems || (state.lastGraph && state.lastGraph.systems) || [];
  const owner = ownerMap(list);

  const groups = new Map();
  for (const item of items || []) {
    const owners = new Set(
      (idsOf(item) || []).map((id) => owner.get(id)).filter(Boolean)
    );
    let key;
    if (owners.size === 1) [key] = [...owners];
    else if (owners.size > 1) key = SPANNING;
    else key = UNCLAIMED;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(item);
  }

  // Named architectures first, in the order the server gave them; the two
  // catch-alls last, because they are exceptions rather than places.
  const order = [...list.map((s) => s.label), SPANNING, UNCLAIMED];
  const out = [...groups.entries()]
    .sort((a, b) => order.indexOf(a[0]) - order.indexOf(b[0]))
    .map(([label, grouped]) => ({ label, items: grouped }));

  if (out.length < 2) return [{ label: null, items: out.length ? out[0].items : [] }];
  return out;
}
