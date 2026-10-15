"use strict";

let textarea, highlightCode, gutter, codeScroll;
let changeHandler = null;
let debounceTimer = null;
let errorLine = null;
let markedLines = [];

const DEBOUNCE_MS = 500;

/* Every settled document, so a canvas edit can be undone: writing the
   textarea's value clears the browser's own undo, and canvas edits all write it. */
const UNDO_LIMIT = 50;
let undoStack = [];
let redoStack = [];
let settled = "";

function remember(text) {
  if (text === settled) return;
  undoStack.push(settled);
  if (undoStack.length > UNDO_LIMIT) undoStack.shift();
  redoStack = [];
  settled = text;
}

function step(from, to) {
  if (!from.length) return false;
  to.push(settled);
  settled = from.pop();
  textarea.value = settled;
  errorLine = null;
  refresh();
  if (changeHandler) changeHandler(settled);
  return true;
}

const undo = () => step(undoStack, redoStack);
const redo = () => step(redoStack, undoStack);

function escapeHtml(text) {
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

// One-pass tokenizer: the alternation order defines precedence.
const TOKEN_RE = new RegExp(
  [
    /("""[\s\S]*?""")/.source,            // 1 long string
    /("(?:[^"\\\n]|\\.)*")/.source,       // 2 string
    /(#[^\n]*)/.source,                   // 3 comment
    /(<[^<>\s"{}|^`\\]*>)/.source,        // 4 IRI
    /(@prefix|@base|\bPREFIX\b|\bBASE\b)/.source, // 5 directive
    /((?:[A-Za-z][\w-]*)?:[\w][\w./#-]*)/.source, // 6 prefixed name
    /((?:[A-Za-z][\w-]*)?:(?=\s))/.source,        // 7 bare prefix decl
    /(\ba\b)/.source,                     // 8 rdf:type shorthand
    /([+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)/.source, // 9 number
  ].join("|"),
  "g"
);
const TOKEN_CLASSES = [null, "str", "str", "com", "iri", "kw", "pn", "pn", "kw", "num"];

function highlightTurtle(text) {
  let html = "";
  let last = 0;
  for (const match of text.matchAll(TOKEN_RE)) {
    html += escapeHtml(text.slice(last, match.index));
    let cls = null;
    for (let g = 1; g < TOKEN_CLASSES.length; g += 1) {
      if (match[g] !== undefined) { cls = TOKEN_CLASSES[g]; break; }
    }
    html += cls ? `<span class="tok-${cls}">${escapeHtml(match[0])}</span>` : escapeHtml(match[0]);
    last = match.index + match[0].length;
  }
  html += escapeHtml(text.slice(last));
  return html;
}

function refresh() {
  const text = textarea.value;
  highlightCode.innerHTML = highlightTurtle(text) + "\n";
  const lineCount = text.split("\n").length;
  const rows = [];
  for (let i = 1; i <= lineCount; i += 1) {
    let cls = "";
    if (i === errorLine) cls = ' class="err-line"';
    else if (markedLines.includes(i)) cls = ' class="marked-line"';
    rows.push(`<div${cls}>${i}</div>`);
  }
  gutter.innerHTML = rows.join("");
  syncScroll();
}

function syncScroll() {
  const pre = highlightCode.parentElement;
  pre.scrollTop = textarea.scrollTop;
  pre.scrollLeft = textarea.scrollLeft;
  gutter.scrollTop = textarea.scrollTop;
}

function scheduleChange() {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => {
    remember(textarea.value);
    if (changeHandler) changeHandler(textarea.value);
  }, DEBOUNCE_MS);
}

function handleKeydown(event) {
  if (event.key === "Tab") {
    event.preventDefault();
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    textarea.setRangeText("    ", start, end, "end");
    refresh();
    scheduleChange();
  }
}

function init(options) {
  textarea = document.getElementById("ttl-source");
  highlightCode = document.getElementById("highlight-code");
  gutter = document.getElementById("gutter");
  codeScroll = document.getElementById("code-scroll");
  changeHandler = options.onChange || null;

  textarea.addEventListener("input", () => { errorLine = null; markedLines = []; refresh(); scheduleChange(); });
  textarea.addEventListener("scroll", syncScroll);
  textarea.addEventListener("keydown", handleKeydown);
  settled = textarea.value;
  refresh();
}

function setValue(text, { silent = false } = {}) {
  remember(text);
  textarea.value = text;
  errorLine = null;
  refresh();
  if (!silent && changeHandler) changeHandler(text);
}

function getValue() {
  return textarea.value;
}

function scrollLineIntoView(line) {
  const lineHeight = parseFloat(getComputedStyle(textarea).lineHeight) || 18;
  const target = (line - 1) * lineHeight;
  if (target < textarea.scrollTop || target > textarea.scrollTop + textarea.clientHeight - lineHeight) {
    textarea.scrollTop = Math.max(0, target - textarea.clientHeight / 2);
    syncScroll();
  }
}

function markErrorLine(line) {
  errorLine = line;
  refresh();
  if (line !== null) scrollLineIntoView(line);
}

function revealLines(lines) {
  markedLines = (lines || []).filter((n) => Number.isInteger(n) && n > 0).sort((a, b) => a - b);
  refresh();
  if (markedLines.length) scrollLineIntoView(markedLines[0]);
}

export const Editor = { init, getValue, setValue, markErrorLine, revealLines, undo, redo };