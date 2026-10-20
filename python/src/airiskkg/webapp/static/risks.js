/* Entry for the risk list page: wiring only. */

import { renderRiskList } from "./panels/risk_list.js";

renderRiskList(document.querySelector("#risk-list")).catch((error) => {
  document.querySelector("#risk-list").textContent = "Could not load the library: " + error.message;
});
