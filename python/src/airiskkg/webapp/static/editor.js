"use strict";

/* Lightweight Turtle editor: a textarea with a syntax-highlight overlay,
 * a line-number gutter, and a debounced change callback.
 * Exposes window.Editor = { init, getValue, setValue, markErrorLine, revealLines }.
 */
(function () {
  let textarea, highlightCode, gutter, codeScroll;
  let changeHandler = null;
  let debounceTimer = null;
  let errorLine = null;
  let markedLines = [];

  const DEBOUNCE_MS = 500;

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
    // trailing newline keeps the <pre> height in sync with the textarea
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
    refresh();
  }

  function setValue(text, { silent = false } = {}) {
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

  /* Show where something on the canvas lives in the source.
   *
   * The diagram and the Turtle are two views of one document, and until now
   * there was no way across: you read a label off a box and searched for it.
   * Several lines at once because a motif match is a set of elements, and the
   * first one is what gets scrolled to - scrolling to each in turn would just
   * land on the last.
   */
  function revealLines(lines) {
    markedLines = (lines || []).filter((n) => Number.isInteger(n) && n > 0).sort((a, b) => a - b);
    refresh();
    if (markedLines.length) scrollLineIntoView(markedLines[0]);
  }

  window.Editor = { init, getValue, setValue, markErrorLine, revealLines };
})();
