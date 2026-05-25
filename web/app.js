const state = {
  activeTable: "patients",
  search: "",
  selectedPatientId: "",
};

const columns = {
  patients: [
    ["patient_id", "Patient ID"],
    ["full_name", "Name"],
    ["gender", "Gender"],
    ["birth_date", "Birth Date"],
    ["active", "Active"],
  ],
  encounters: [
    ["encounter_id", "Encounter ID"],
    ["patient_id", "Patient ID"],
    ["class_display", "Class"],
    ["type_display", "Type"],
    ["start_datetime", "Start"],
    ["reason_display", "Reason"],
    ["status", "Status"],
  ],
  conditions: [
    ["condition_id", "Condition ID"],
    ["patient_id", "Patient ID"],
    ["display", "Condition"],
    ["code", "Code"],
    ["clinical_status", "Clinical Status"],
    ["recorded_date", "Recorded"],
  ],
  observations: [
    ["observation_id", "Observation ID"],
    ["patient_id", "Patient ID"],
    ["display", "Display"],
    ["code", "Code"],
    ["effective_datetime", "Effective"],
    ["value", "Value"],
    ["status", "Status"],
  ],
  "hl7-messages": [
    ["message_id", "Message ID"],
    ["message_type", "Type"],
    ["trigger_event", "Event"],
    ["sending_application", "Source"],
    ["patient_id", "Patient ID"],
    ["patient_name", "Patient"],
    ["message_timestamp", "Timestamp"],
  ],
  "hl7-results": [
    ["result_id", "Result ID"],
    ["patient_id", "Patient ID"],
    ["observation_name", "Result"],
    ["observation_value", "Value"],
    ["units", "Units"],
    ["abnormal_flag", "Flag"],
    ["observation_timestamp", "Timestamp"],
  ],
};

const $ = (selector) => document.querySelector(selector);

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || "Request failed");
  }
  return payload;
}

function postAuditEvent(payload) {
  fetchJson("/api/audit-event", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }).catch(() => {});
}

function formatNumber(value) {
  return Number(value || 0).toLocaleString();
}

function formatValue(value) {
  if (value === null || value === undefined || value === "") {
    return "Not provided";
  }
  return String(value);
}

function escapeHtml(value) {
  return formatValue(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function showToast(message) {
  const toast = $("#toast");
  toast.textContent = message;
  toast.classList.add("visible");
  window.clearTimeout(showToast.timeout);
  showToast.timeout = window.setTimeout(() => toast.classList.remove("visible"), 4200);
}

function setTable(table, search = "") {
  state.activeTable = table;
  state.search = search;
  $("#search-input").value = search;
  document.querySelectorAll(".tab-button").forEach((item) => {
    item.classList.toggle("active", item.dataset.table === table);
  });
  loadTable();
}

function filterTable(table, search, label) {
  setTable(table, search);
  showToast(`Filtered ${label || table}.`);
  document.querySelector(".table-wrap").scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function renderSummary(summary) {
  $("#patients-count").textContent = formatNumber(summary.patients);
  $("#encounters-count").textContent = formatNumber(summary.encounters);
  $("#conditions-count").textContent = formatNumber(summary.conditions);
  $("#observations-count").textContent = formatNumber(summary.observations);
  $("#hl7-messages-count").textContent = formatNumber(summary.hl7_messages);
  $("#hl7-results-count").textContent = formatNumber(summary.hl7_results);
  $("#codes-count").textContent = formatNumber(summary.observation_codes);
  $("#missing-refs-count").textContent = formatNumber(summary.missing_patient_references);
  $("#coded-rate").textContent = `${formatNumber(summary.coded_observation_rate)}%`;
  $("#valued-rate").textContent = `${formatNumber(summary.valued_observation_rate)}%`;
  $("#health-status").textContent = summary.database_ready ? "Operational" : "No database";

  if (!summary.database_ready) {
    $("#pipeline-status").textContent = "No local database yet. Run ETL to load data.";
    $("#run-extracted").textContent = "0";
    $("#run-loaded").textContent = "0";
    $("#run-time").textContent = "Not available";
    return;
  }

  const run = summary.last_run;
  const sourceLabels = {
    synthetic_fhir: "Synthetic FHIR",
    synthetic_hl7: "Synthetic HL7",
    hapi_fhir: "FHIR API",
  };
  const sourceLabel = run ? (sourceLabels[run.source_mode] || "FHIR API") : "";
  $("#pipeline-status").textContent = run
    ? `${sourceLabel} · ${new Date(run.run_timestamp).toLocaleString()}`
    : "Database ready";

  $("#run-extracted").textContent = run
    ? formatNumber(
        Number(run.patients_extracted || 0) +
        Number(run.observations_extracted || 0) +
        Number(run.encounters_extracted || 0) +
        Number(run.conditions_extracted || 0) +
        Number(run.hl7_messages_extracted || 0) +
        Number(run.hl7_results_extracted || 0)
      )
    : "0";
  $("#run-loaded").textContent = run
    ? formatNumber(
        Number(run.patients_loaded || 0) +
        Number(run.observations_loaded || 0) +
        Number(run.encounters_loaded || 0) +
        Number(run.conditions_loaded || 0) +
        Number(run.hl7_messages_loaded || 0) +
        Number(run.hl7_results_loaded || 0)
      )
    : "0";
  $("#run-time").textContent = run
    ? new Date(run.run_timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    : "Not available";
}

function controlPill(control) {
  return `<span class="control-pill ${escapeHtml(control.status)}">${escapeHtml(control.status)}</span>`;
}

function renderCompliance(posture) {
  $("#compliance-status").textContent = posture.status;
  $("#data-classification").textContent = `Data classification: ${posture.data_classification} · Actor: ${posture.actor}`;
  $("#compliance-controls").innerHTML = posture.controls.slice(0, 4).map((control) => `
    <div>
      ${controlPill(control)}
      <span>${escapeHtml(control.name)}</span>
    </div>
  `).join("");

  $("#control-readiness").innerHTML = posture.controls.map((control) => `
    <div class="control-item">
      <div>
        <strong>${escapeHtml(control.name)}</strong>
        <span>${escapeHtml(control.detail)}</span>
      </div>
      ${controlPill(control)}
    </div>
  `).join("");

  $("#compliance-events").innerHTML = posture.recent_events.length
    ? posture.recent_events.map((event) => `
        <div class="event-item">
          <strong>${escapeHtml(event.action)}</strong>
          <span>${escapeHtml(event.resource_type || "system")}${event.resource_id ? ` · ${escapeHtml(event.resource_id)}` : ""}</span>
          <small>${new Date(event.event_timestamp).toLocaleString()} · ${escapeHtml(event.purpose)}</small>
        </div>
      `).join("")
    : '<p class="empty-state">No compliance events recorded yet.</p>';
}

function renderBarChart(target, rows, labelKey, valueKey, options = {}) {
  const max = Math.max(...rows.map((row) => Number(row[valueKey] || 0)), 1);
  target.innerHTML = rows.length
    ? rows.map((row) => {
        const value = Number(row[valueKey] || 0);
        const width = Math.max((value / max) * 100, 3);
        const filterTableName = options.table || "";
        const filterValue = options.filterValue ? options.filterValue(row) : row[labelKey];
        return `
          <button class="bar-row chart-action" type="button" data-table="${escapeHtml(filterTableName)}" data-filter="${escapeHtml(filterValue)}">
            <span>${escapeHtml(row[labelKey])}</span>
            <div class="bar-track"><div class="bar-fill" style="width: ${width}%"></div></div>
            <strong>${formatNumber(value)}</strong>
          </button>
        `;
      }).join("")
    : '<p class="empty-state">No patient analytics available yet.</p>';
}

function renderRankedList(target, rows) {
  target.innerHTML = rows.length
    ? rows.map((row) => `
        <button class="ranked-item chart-action" type="button" data-table="observations" data-filter="${escapeHtml(row.code === "unknown" ? row.display : row.code)}">
          <span>${escapeHtml(row.display)}</span>
          <strong>${formatNumber(row.observation_count)}</strong>
          <small>Code: ${escapeHtml(row.code)}</small>
        </button>
      `).join("")
    : '<p class="empty-state">No observation analytics available yet.</p>';
}

function renderConditionList(target, rows) {
  target.innerHTML = rows.length
    ? rows.map((row) => `
        <button class="ranked-item chart-action" type="button" data-table="conditions" data-filter="${escapeHtml(row.code === "unknown" ? row.display : row.code)}">
          <span>${escapeHtml(row.display)}</span>
          <strong>${formatNumber(row.condition_count)}</strong>
          <small>SNOMED CT: ${escapeHtml(row.code)}</small>
        </button>
      `).join("")
    : '<p class="empty-state">No condition analytics available yet.</p>';
}

function renderHl7ResultList(target, rows) {
  target.innerHTML = rows.length
    ? rows.map((row) => `
        <button class="ranked-item chart-action" type="button" data-table="hl7-results" data-filter="${escapeHtml(row.code === "unknown" ? row.display : row.code)}">
          <span>${escapeHtml(row.display)}</span>
          <strong>${formatNumber(row.abnormal_count)}</strong>
          <small>OBX: ${escapeHtml(row.code)}</small>
        </button>
      `).join("")
    : '<p class="empty-state">No HL7 abnormal result metrics available yet.</p>';
}

function renderQualityList(target, rows) {
  target.innerHTML = rows.length
    ? rows.map((row) => {
        const total = Number(row.total_count || 0);
        const passed = Number(row.passed_count || 0);
        const rate = total ? Math.round((passed / total) * 1000) / 10 : 0;
        return `
          <div class="quality-item">
            <div class="quality-topline">
              <span>${escapeHtml(row.check_name)}</span>
              <strong>${formatNumber(rate)}%</strong>
            </div>
            <div class="bar-track"><div class="bar-fill" style="width: ${Math.max(rate, 3)}%"></div></div>
            <small>${formatNumber(passed)} of ${formatNumber(total)} records passed</small>
          </div>
        `;
      }).join("")
    : '<p class="empty-state">No quality metrics available yet.</p>';
}

function rowValue(row, key) {
  if (key === "value") {
    const numeric = row.value_numeric === null || row.value_numeric === undefined ? "" : row.value_numeric;
    const unit = row.unit ? ` ${row.unit}` : "";
    return numeric !== "" ? `${numeric}${unit}` : row.value_text;
  }
  return row[key];
}

function riskBadges(row) {
  const badges = [];
  if (Number(row.high_a1c_events || 0) > 0) {
    badges.push('<span class="risk-badge high">A1c risk</span>');
  }
  if (Number(row.high_systolic_events || 0) > 0) {
    badges.push('<span class="risk-badge medium">BP risk</span>');
  }
  if (!badges.length) {
    badges.push('<span class="risk-badge stable">Stable</span>');
  }
  return badges.join("");
}

function renderCareGaps(rows) {
  const target = $("#care-gap-list");
  target.innerHTML = rows.length
    ? rows.map((row) => `
        <button class="care-gap-item" type="button" data-patient-id="${escapeHtml(row.patient_id)}">
          <div>
            <strong>${escapeHtml(row.full_name || row.patient_id)}</strong>
            <span>${escapeHtml(row.gender)} · ${escapeHtml(row.birth_date)}</span>
          </div>
          <div class="risk-stack">
            ${riskBadges(row)}
            <small>${formatNumber(row.condition_count)} conditions · ${formatNumber(row.observation_count)} observations</small>
          </div>
        </button>
      `).join("")
    : '<p class="empty-state">No patient worklist data available.</p>';
}

function compactList(rows, labelKey, metaKey) {
  return rows.length
    ? rows.map((row) => `
        <li>
          <strong>${escapeHtml(row[labelKey])}</strong>
          <span>${escapeHtml(row[metaKey])}</span>
        </li>
      `).join("")
    : '<li><span>Not available</span></li>';
}

async function loadPatientDetail(patientId) {
  if (!patientId) return;
  state.selectedPatientId = patientId;
  postAuditEvent({
    action: "patient_detail_selected",
    resource_type: "Patient",
    resource_id: patientId,
    purpose: "care-operations",
  });
  const detail = await fetchJson(`/api/patient-detail?patient_id=${encodeURIComponent(patientId)}`);
  if (!detail.patient) return;

  $("#patient-detail-title").textContent = detail.patient.full_name || detail.patient.patient_id;
  const signals = detail.signals || {};
  $("#patient-detail").classList.remove("empty-state");
  $("#patient-detail").innerHTML = `
    <div class="patient-signal-grid">
      <div><span>Conditions</span><strong>${formatNumber(signals.condition_count)}</strong></div>
      <div><span>Encounters</span><strong>${formatNumber(signals.encounter_count)}</strong></div>
      <div><span>Observations</span><strong>${formatNumber(signals.observation_count)}</strong></div>
      <div><span>Risk Flags</span><strong>${formatNumber(Number(signals.high_a1c_events || 0) + Number(signals.high_systolic_events || 0))}</strong></div>
    </div>
    <div class="patient-lists">
      <section>
        <h3>Conditions</h3>
        <ul>${compactList(detail.conditions, "display", "recorded_date")}</ul>
      </section>
      <section>
        <h3>Recent Encounters</h3>
        <ul>${compactList(detail.encounters, "type_display", "start_datetime")}</ul>
      </section>
      <section>
        <h3>Latest Observations</h3>
        <ul>${compactList(detail.observations, "display", "effective_datetime")}</ul>
      </section>
      <section>
        <h3>HL7 Results</h3>
        <ul>${compactList(detail.hl7_results || [], "observation_name", "observation_timestamp")}</ul>
      </section>
    </div>
  `;

  document.querySelectorAll(".care-gap-item").forEach((item) => {
    item.classList.toggle("selected", item.dataset.patientId === patientId);
  });
}

function renderTable(rows) {
  const selectedColumns = columns[state.activeTable];
  $("#table-head").innerHTML = `<tr>${selectedColumns.map(([, label]) => `<th>${label}</th>`).join("")}</tr>`;
  $("#table-body").innerHTML = rows.length
    ? rows.map((row) => `
        <tr ${row.patient_id ? `data-patient-id="${escapeHtml(row.patient_id)}"` : ""}>
          ${selectedColumns.map(([key]) => `<td>${escapeHtml(rowValue(row, key))}</td>`).join("")}
        </tr>
      `).join("")
    : `<tr><td colspan="${selectedColumns.length}" class="empty-state">No records found. Run the ETL or adjust the search.</td></tr>`;
}

async function loadConfig() {
  const config = await fetchJson("/api/config");
  $("#fhir-url").textContent = config.fhir_base_url;
}

async function loadSummary() {
  renderSummary(await fetchJson("/api/summary"));
}

async function loadCompliance() {
  renderCompliance(await fetchJson("/api/compliance"));
}

async function loadAnalytics() {
  const analytics = await fetchJson("/api/analytics");
  renderCareGaps(analytics.care_gaps);
  renderBarChart($("#gender-chart"), analytics.patient_count_by_gender, "gender", "patient_count", { table: "patients" });
  renderRankedList($("#code-chart"), analytics.top_observation_codes);
  renderConditionList($("#condition-chart"), analytics.top_conditions);
  renderBarChart($("#encounter-chart"), analytics.encounter_classes, "encounter_class", "encounter_count", { table: "encounters" });
  renderBarChart($("#hl7-message-chart"), analytics.hl7_message_types, "message_type", "message_count", { table: "hl7-messages" });
  renderHl7ResultList($("#hl7-result-chart"), analytics.hl7_abnormal_results);
  renderBarChart($("#age-chart"), analytics.patient_age_bands, "age_band", "patient_count", { table: "patients" });
  renderQualityList($("#quality-chart"), analytics.observation_completeness);
  renderBarChart($("#coverage-chart"), analytics.patient_observation_coverage, "coverage_band", "patient_count", { table: "patients", filterValue: () => "" });

  if (!state.selectedPatientId && analytics.care_gaps.length) {
    await loadPatientDetail(analytics.care_gaps[0].patient_id);
  }
}

async function loadTable() {
  const params = new URLSearchParams({ limit: "75", search: state.search });
  renderTable(await fetchJson(`/api/${state.activeTable}?${params}`));
}

async function refreshDashboard() {
  await Promise.all([loadSummary(), loadAnalytics(), loadCompliance(), loadTable()]);
}

async function runPipeline() {
  const button = $("#run-button");
  button.disabled = true;
  button.textContent = "Running...";
  showToast("Running extraction, transform, and load. Public FHIR test servers can take a moment.");

  try {
    await fetchJson("/api/run-pipeline", { method: "POST" });
    await refreshDashboard();
    showToast("ETL completed and dashboard refreshed.");
  } catch (error) {
    showToast(`ETL failed: ${error.message}`);
  } finally {
    button.disabled = false;
    button.textContent = "Run Live FHIR";
  }
}

async function loadSyntheticData() {
  const button = $("#synthetic-button");
  button.disabled = true;
  button.textContent = "Loading...";
  showToast("Generating and loading local synthetic FHIR bundles.");

  try {
    await fetchJson("/api/load-synthetic", { method: "POST" });
    await refreshDashboard();
    showToast("Synthetic FHIR data loaded and dashboard refreshed.");
  } catch (error) {
    showToast(`Synthetic load failed: ${error.message}`);
  } finally {
    button.disabled = false;
    button.textContent = "Load FHIR Sample";
  }
}

async function loadHl7Data() {
  const button = $("#hl7-button");
  button.disabled = true;
  button.textContent = "Loading...";
  showToast("Generating and loading synthetic HL7 v2 ADT/ORU messages.");

  try {
    await fetchJson("/api/load-hl7", { method: "POST" });
    await refreshDashboard();
    showToast("Synthetic HL7 v2 messages loaded and dashboard refreshed.");
  } catch (error) {
    showToast(`HL7 load failed: ${error.message}`);
  } finally {
    button.disabled = false;
    button.textContent = "Load HL7 Sample";
  }
}

function bindEvents() {
  $("#refresh-button").addEventListener("click", () => {
    refreshDashboard().then(() => showToast("Dashboard refreshed."));
  });

  $("#run-button").addEventListener("click", runPipeline);
  $("#synthetic-button").addEventListener("click", loadSyntheticData);
  $("#hl7-button").addEventListener("click", loadHl7Data);

  $("#search-input").addEventListener("input", (event) => {
    state.search = event.target.value;
    window.clearTimeout(bindEvents.searchTimeout);
    bindEvents.searchTimeout = window.setTimeout(loadTable, 180);
  });

  document.querySelectorAll(".tab-button").forEach((button) => {
    button.addEventListener("click", () => {
      state.activeTable = button.dataset.table;
      document.querySelectorAll(".tab-button").forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      loadTable();
    });
  });

  document.addEventListener("click", (event) => {
    const chartAction = event.target.closest(".chart-action");
    if (chartAction) {
      filterTable(chartAction.dataset.table, chartAction.dataset.filter || "", chartAction.dataset.filter || chartAction.dataset.table);
      return;
    }

    const metricCard = event.target.closest(".metric-card");
    if (metricCard && metricCard.dataset.filterTable) {
      filterTable(metricCard.dataset.filterTable, metricCard.dataset.filterValue || "", metricCard.querySelector("span").textContent);
      return;
    }

    const careItem = event.target.closest(".care-gap-item");
    if (careItem) {
      loadPatientDetail(careItem.dataset.patientId);
      setTable("patients", careItem.dataset.patientId);
      return;
    }

    const tableRow = event.target.closest("tbody tr[data-patient-id]");
    if (tableRow) {
      loadPatientDetail(tableRow.dataset.patientId);
    }
  });
}

async function init() {
  bindEvents();
  await loadConfig();
  await refreshDashboard();
}

init().catch((error) => {
  showToast(`Dashboard failed to load: ${error.message}`);
});
