/* What more than one panel needs to know.
 *
 * One mutated object rather than nine exported variables: an imported
 * binding is read-only for the importer, so `scopedSystem = null` in the
 * findings panel would not reach the canvas that draws the scope - it
 * would not even be legal. Only values that genuinely cross a module
 * boundary live here; what a panel keeps to itself stays in that panel.
 */
export const state = {
  lastRun: null,  // { fingerprint, findingIds: Set }

  pendingCause: null,

 /* Which layer the canvas is showing. "business" only becomes reachable once a
  * process is actually submitted - offering a level with nothing on it reads
  * as a broken feature rather than an empty one. */
  level: "architecture",

  levelChosenByHand: false,

 /* Which architecture the canvas is narrowed to, when a reader descended from
  * a business activity. Null means the whole document, which is right when it
  * holds one architecture and misleading when it holds two. */
  scopedSystem: null,

  openedFrom: null,  // the activity a reader descended through

  lastProcess: null,

  lastAssessment: null,

  lastGraph: null,  // the parsed architecture, for the level decision and the picker
};
