export const state = {
  lastRun: null,  // { fingerprint, findingIds: Set }

  pendingCause: null,

  level: "architecture",       // "architecture" | "business"

  levelChosenByHand: false,

  levelTrail: [],    // the levels left, newest last, for the browser's Back

  scopedSystem: null,          // narrowed to one architecture; null = all

  openedFrom: null,  // the activity a reader descended through

  highlightOnScope: null,  // what to pick out once a scope change has redrawn the canvas

  lastProcess: null,

  lastAssessment: null,

  lastGraph: null,  // the parsed architecture, for the level decision and the picker
};
