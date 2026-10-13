"use strict";

const $ = (id) => document.getElementById(id);
const state = { selected: null, requestedSelection: null, serial: null, selectionVersion: 0, searchVersion: 0, serialVersion: 0, responses: {}, responseTab: "part" };
const statusLabels = { ready: "Ready", missing: "Missing", not_replaceable: "Not replaceable" };

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}

function notice(message = "", error = false) {
  $("notice").textContent = message;
  $("notice").className = error ? "notice error" : "notice";
  $("notice").hidden = !message;
}

async function request(path, responseKey) {
  const response = await fetch(path, { cache: "no-store" });
  let body;
  try { body = await response.json(); }
  catch { throw new Error(`The server returned an unreadable response (HTTP ${response.status}).`); }
  const record = { path, status: response.status, body };
  if (responseKey) { state.responses[responseKey] = record; showResponse(); }
  if (!response.ok) {
    const error = new Error(`HTTP ${response.status}: ${typeof body.detail === "string" ? body.detail : "The request could not be completed."}`);
    error.response = record;
    throw error;
  }
  return record;
}

function showResponse(tab = state.responseTab) {
  state.responseTab = tab;
  document.querySelectorAll("[data-response]").forEach(button => {
    const active = button.dataset.response === tab;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });
  const response = state.responses[tab];
  $("response-label").textContent = response ? `GET ${response.path} · HTTP ${response.status}` : `No ${tab} request yet`;
  $("response-json").textContent = response ? JSON.stringify(response.body, null, 2) : "Select a part or check a serial to see its response.";
}

function partLink(number, label = number) {
  const button = element("button", label, "chip");
  button.type = "button";
  button.addEventListener("click", () => selectPart(number));
  return button;
}

function markSelected() {
  document.querySelectorAll(".result-button").forEach(button => {
    const selected = button.dataset.part === state.selected;
    button.classList.toggle("selected", selected);
    button.setAttribute("aria-pressed", String(selected));
  });
}

async function search() {
  const version = ++state.searchVersion;
  const query = $("search").value.trim();
  $("search-count").textContent = "Searching…";
  try {
    const { body } = await request(`/demo/search?q=${encodeURIComponent(query)}`);
    if (version !== state.searchVersion) return;
    $("search-count").textContent = `${body.total} matching ${body.total === 1 ? "part" : "parts"}${body.total > body.parts.length ? ` · showing first ${body.parts.length}; refine your search` : ""}`;
    $("search-results").replaceChildren();
    if (!body.parts.length) $("search-results").append(element("li", "No parts found in this machine. Try another number or description.", "empty"));
    body.parts.forEach(part => {
      const row = element("li");
      const button = element("button", undefined, "result-button");
      button.type = "button";
      button.dataset.part = part.part_number;
      const top = element("span", undefined, "result-top");
      const dot = element("i", undefined, `dot ${part.status}`);
      dot.setAttribute("aria-hidden", "true");
      top.append(dot, element("strong", part.part_number));
      button.append(top, element("span", part.description ?? "Missing master record", "result-description"));
      button.setAttribute("aria-label", `${part.part_number}, ${part.description ?? "Missing master record"}, ${statusLabels[part.status]}`);
      button.addEventListener("click", () => selectPart(part.part_number));
      row.append(button);
      $("search-results").append(row);
    });
    markSelected();
  } catch (error) {
    if (version !== state.searchVersion) return;
    $("search-results").replaceChildren();
    $("search-count").textContent = "Search unavailable.";
    notice(error.message, true);
  }
}

function renderCompatibility(explanation) {
  const compatibility = explanation?.compatibility;
  $("compatibility").textContent = compatibility?.reason ?? "Enter a serial to check the selected part.";
  $("compatibility").className = `compatibility${compatibility ? compatibility.applicable ? " yes" : " no" : ""}`;
}

async function selectPart(number) {
  state.requestedSelection = number;
  const version = ++state.selectionVersion;
  const detail = document.querySelector(".detail");
  detail.setAttribute("aria-busy", "true");
  notice();
  try {
    const encoded = encodeURIComponent(number);
    const serialQuery = state.serial === null ? "" : `?serial=${encodeURIComponent(state.serial)}`;
    const [partResponse, pathsResponse, explanationResponse] = await Promise.all([
      request(`/api/parts/${encoded}`), request(`/api/parts/${encoded}/paths`),
      request(`/demo/parts/${encoded}/explanation${serialQuery}`),
    ]);
    if (version !== state.selectionVersion) return;
    const part = partResponse.body;
    const explanation = explanationResponse.body;
    state.selected = part.part_number;
    state.responses.part = partResponse;
    state.responses.paths = pathsResponse;
    $("part-number").textContent = part.part_number;
    $("part-description").textContent = part.description ?? "Description unavailable — no master record";
    $("part-quantity").textContent = part.total_quantity;
    $("part-status").textContent = statusLabels[part.status];
    $("part-status").className = `badge ${part.status}`;
    $("revision-tag").textContent = part.revision ?? "Unknown";
    $("revision-reason").textContent = explanation.revision.reason;
    $("status-reason").textContent = explanation.status.reason;
    $("quantity-reason").textContent = explanation.quantity.reason;
    $("quantity-terms").replaceChildren();
    explanation.quantity.terms.forEach(term => {
      const row = element("tr");
      const parent = element("td");
      parent.append(partLink(term.parent));
      row.append(parent, ...[term.assembly_occurrences, term.per_parent, term.contribution].map(value => element("td", value)));
      $("quantity-terms").append(row);
    });
    $("terms-details").hidden = explanation.quantity.terms.length === 0;
    renderCompatibility(explanation);
    $("parents").replaceChildren(...part.parents.map(parent => partLink(parent)));
    if (!part.parents.length) $("parents").append(element("span", "Machine root", "muted small"));
    $("children").replaceChildren(...part.children.map(child => partLink(child.part_number, `${child.part_number} × ${child.quantity}`)));
    if (!part.children.length) $("children").append(element("span", "No child parts", "muted small"));
    $("path-count").textContent = pathsResponse.body.paths.length;
    $("paths").replaceChildren();
    pathsResponse.body.paths.forEach(path => {
      const row = element("li");
      path.forEach((pn, index) => { if (index) row.append(document.createTextNode(" → ")); row.append(partLink(pn)); });
      $("paths").append(row);
    });
    markSelected();
    showResponse();
  } catch (error) {
    if (version === state.selectionVersion) notice(`${error.message} The previous selection has been retained.`, true);
  } finally {
    if (version === state.selectionVersion) detail.setAttribute("aria-busy", "false");
  }
}

async function checkSerial(event) {
  event.preventDefault();
  const version = ++state.serialVersion;
  ++state.selectionVersion; // Invalidate an in-flight explanation for the previous serial.
  document.querySelector(".detail").setAttribute("aria-busy", "false");
  state.serial = null;
  $("serial-total").textContent = "";
  renderCompatibility(null);
  const input = $("serial").value;
  if (!input) { notice("Enter a machine serial number.", true); return; }
  notice();
  $("compatibility").textContent = "Checking serial…";
  try {
    const response = await request(`/api/serial/${encodeURIComponent(input)}`);
    if (version !== state.serialVersion) return;
    state.responses.serial = response;
    state.serial = input; // Keep the original digit string instead of rounding large integers in JS.
    $("serial-total").textContent = `${response.body.applicable_parts} ready parts in the catalogue apply to serial ${input}.`;
    if (state.requestedSelection || state.selected) await selectPart(state.requestedSelection || state.selected);
    else $("compatibility").textContent = "Select a part to check its fit.";
    showResponse();
  } catch (error) {
    if (version !== state.serialVersion) return;
    if (error.response) { state.responses.serial = error.response; showResponse(); }
    $("compatibility").textContent = "Serial check could not be completed.";
    $("compatibility").className = "compatibility no";
    notice(error.message, true);
  }
}

function treeNode(number, quantity) {
  const details = element("details", undefined, "tree-node");
  const summary = element("summary");
  const button = element("button", number);
  button.type = "button";
  button.setAttribute("aria-label", `Inspect ${number}`);
  button.addEventListener("click", event => { event.preventDefault(); selectPart(number); });
  summary.append(button);
  if (quantity !== undefined) summary.append(element("span", ` × ${quantity} each`, "muted small"));
  const children = element("div");
  details.append(summary, children);
  let loaded = false;
  let loading = false;
  details.addEventListener("toggle", async () => {
    if (!details.open || loaded || loading) return;
    loading = true;
    children.replaceChildren(element("p", "Loading…", "muted small"));
    try {
      const { body } = await request(`/api/parts/${encodeURIComponent(number)}`);
      children.replaceChildren(...body.children.map(child => treeNode(child.part_number, child.quantity)));
      if (!body.children.length) children.append(element("p", "No child parts", "muted small"));
      loaded = true;
    } catch (error) { children.replaceChildren(element("p", `${error.message} Close and reopen to retry.`, "small")); }
    finally { loading = false; }
  });
  return details;
}

async function init() {
  try {
    const [validation, health, quality] = await Promise.all([
      request("/api/validation", "validation"), request("/health", "health"), request("/demo/quality"),
    ]);
    Object.entries(validation.body).forEach(([key, value]) => { $(`count-${key}`).textContent = value; });
    $("connection").textContent = health.body.status === "ok" ? "Local catalogue ready" : "Unavailable";
    $("connection").classList.add("connected");
    const data = quality.body;
    const stats = [[data.normalized_cells, "Part-number cells normalized"], [data.duplicate_rows_ignored, "Repeated relationship rows ignored"],
      [data.removed_relationships.length, "Upward relationships removed"], [data.outside_relationships, "Outside-machine relationships excluded"]];
    $("quality-stats").replaceChildren(...stats.map(([count, label]) => {
      const item = element("div", undefined, "quality-stat"); item.append(element("strong", count), element("span", label)); return item;
    }));
    $("removed-edges").replaceChildren(...data.removed_relationships.map(row => element("li", `${row.reason} · ${row.sources.join(", ")}`)));
    if (!data.removed_relationships.length) $("removed-edges").append(element("li", "No upward relationships were removed."));
    $("tree").append(treeNode(data.root));
    await Promise.all([search(), selectPart(data.root)]);
  } catch (error) {
    $("connection").textContent = "Server unavailable";
    notice(`${error.message} Check that the local service is running, then reload.`, true);
  }
}

let searchTimer;
$("search").addEventListener("input", () => { clearTimeout(searchTimer); searchTimer = setTimeout(search, 180); });
$("search-form").addEventListener("submit", event => { event.preventDefault(); clearTimeout(searchTimer); search(); });
$("serial-form").addEventListener("submit", checkSerial);
document.querySelectorAll("[data-response]").forEach(button => button.addEventListener("click", () => showResponse(button.dataset.response)));
init();
