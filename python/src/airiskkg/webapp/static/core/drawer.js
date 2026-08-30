/* The results drawer and its tabs. */

import { $, $$ } from "./dom.js";

export function setTabVisible(name, visible) {
  const tab = document.querySelector(`[data-drawer-tab="${name}"]`);
  if (!tab) return;
  tab.classList.toggle("hidden", !visible);
  // Never hide the tab being read.
  if (!visible && tab.classList.contains("active")) openDrawer("findings");
}

export function openDrawer(tab) {
  $("#drawer").classList.remove("collapsed");
  $("#drawer-toggle").innerHTML = "&#9660;";
  if (tab) switchDrawerTab(tab);
}

export function toggleDrawer() {
  const drawer = $("#drawer");
  drawer.classList.toggle("collapsed");
  $("#drawer-toggle").innerHTML = drawer.classList.contains("collapsed") ? "&#9650;" : "&#9660;";
}

export function switchDrawerTab(name) {
  $$(".drawer-tab").forEach((t) => t.classList.toggle("active", t.dataset.drawerTab === name));
  $$(".drawer-panel").forEach((p) => p.classList.toggle("hidden", p.dataset.drawerPanel !== name));
}
