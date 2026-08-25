/* The results drawer and its tabs.
 */

import { $, $$ } from "../core/dom.js";

export function setTabVisible(name, visible) {
  const tab = document.querySelector(`[data-drawer-tab="${name}"]`);
  if (!tab) return;
  tab.classList.toggle("hidden", !visible);
  /* Hiding the tab someone is reading would leave the drawer showing a panel
   * with no tab above it, which looks like the app lost its place. */
  if (!visible && tab.classList.contains("active")) openDrawer("findings");
}

//  drawer 
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
