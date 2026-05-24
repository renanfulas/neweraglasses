const lensOverlay = document.getElementById("lens-overlay");
const outcomeNode = document.getElementById("outcome");
const candidateNode = document.getElementById("candidate-created");
const eventCountNode = document.getElementById("event-count");
const deliveredNode = document.getElementById("delivered-count");
const insightLog = document.getElementById("insight-log");
const traceList = document.getElementById("trace-list");
const historyList = document.getElementById("history-list");
const networkStatus = document.getElementById("network-status");
const refreshHistoryButton = document.getElementById("refresh-history-button");
const scopeLatestButton = document.getElementById("scope-latest-button");
const scopeSessionButton = document.getElementById("scope-session-button");
const sessionModuleLabel = document.getElementById("session-module-label");
const syncStateCard = document.getElementById("sync-state-card");
const syncStateLabel = document.getElementById("sync-state-label");
const asyncStateCard = document.getElementById("async-state-card");
const asyncStateLabel = document.getElementById("async-state-label");
const feedbackStateCard = document.getElementById("feedback-state-card");
const feedbackStateLabel = document.getElementById("feedback-state-label");
const feedbackCard = document.getElementById("feedback-card");
const feedbackTargetTitle = document.getElementById("feedback-target-title");
const feedbackBadge = document.getElementById("feedback-badge");
const feedbackCopy = document.getElementById("feedback-copy");
const feedbackUsefulButton = document.getElementById("feedback-useful-button");
const feedbackNotUsefulButton = document.getElementById("feedback-not-useful-button");

const jobStatusBadge = document.getElementById("job-status-badge");
const jobSummary = document.getElementById("job-summary");
const jobIdNode = document.getElementById("job-id");
const jobSourceNode = document.getElementById("job-source");
const jobAnalysisIdNode = document.getElementById("job-analysis-id");
const jobEnqueueButton = document.getElementById("job-enqueue-button");
const jobRunningButton = document.getElementById("job-running-button");
const jobSuccessButton = document.getElementById("job-success-button");
const jobFailedButton = document.getElementById("job-failed-button");
const jobRefreshButton = document.getElementById("job-refresh-button");

const DEMO_USERS = {
  grocery: "demo-grocery-user",
  documents: "demo-documents-user",
};

const DEMO_SESSIONS = {
  grocery: "demo-grocery-session",
  documents: "demo-documents-session",
};

const moduleTabs = Array.from(document.querySelectorAll(".module-tab"));
const moduleForms = {
  grocery: document.getElementById("grocery-form"),
  documents: document.getElementById("document-form"),
};

const appState = {
  activeModule: "grocery",
  historyScope: "latest",
  syncStateByModule: {
    grocery: "idle",
    documents: "idle",
  },
  asyncStateByModule: {
    grocery: "standby",
    documents: "idle",
  },
  feedbackStateByModule: {
    grocery: "idle",
    documents: "idle",
  },
  lastTraceIdByModule: {
    grocery: null,
    documents: null,
  },
  lastCommandByModule: {
    grocery: null,
    documents: null,
  },
  feedbackByCommandId: {},
  currentDocumentJob: null,
  currentDocumentJobId: null,
  currentDocumentJobTraceId: null,
  lastDocumentAnalysisId: null,
};

const simulations = {
  grocery: {
    form: moduleForms.grocery,
    button: document.getElementById("grocery-simulate-button"),
    endpoint: "/api/simulations/grocery/missing-item",
    confidenceInput: document.getElementById("grocery-confidence"),
    confidenceOutput: document.getElementById("grocery-confidence-output"),
    buildRequest() {
      return {
        user_id: DEMO_USERS.grocery,
        session_id: DEMO_SESSIONS.grocery,
        item_name: document.getElementById("item-name").value.trim(),
        confidence: Number(document.getElementById("grocery-confidence").value),
        mode: document.getElementById("grocery-mode").value,
        recent_category_count: Number(document.getElementById("grocery-recent-count").value),
      };
    },
    buildInsight(payload, requestBody) {
      const commandText = payload.command
        ? `${escapeHtml(payload.command.title)}: ${escapeHtml(payload.command.body)}`
        : "No lens command was delivered.";
      return `
        <p><strong>Module:</strong> Grocery</p>
        <p><strong>Observation:</strong> Missing ${escapeHtml(requestBody.item_name)}</p>
        <p><strong>Outcome:</strong> ${escapeHtml(payload.outcome)}</p>
        <p><strong>Lens:</strong> ${commandText}</p>
      `;
    },
  },
  documents: {
    form: moduleForms.documents,
    button: document.getElementById("document-simulate-button"),
    endpoint: "/api/simulations/documents/contract-review",
    confidenceInput: document.getElementById("document-confidence"),
    confidenceOutput: document.getElementById("document-confidence-output"),
    async buildRequest() {
      const documentImageInput = document.getElementById("document-image");
      const selectedFile = documentImageInput.files[0];
      const documentImageBase64 = selectedFile ? await fileToBase64(selectedFile) : null;
      return {
        user_id: DEMO_USERS.documents,
        session_id: DEMO_SESSIONS.documents,
        document_text: document.getElementById("document-text").value.trim(),
        document_image_base64: documentImageBase64,
        confidence: Number(document.getElementById("document-confidence").value),
        mode: document.getElementById("document-mode").value,
        recent_category_count: Number(document.getElementById("document-recent-count").value),
      };
    },
    buildInsight(payload, requestBody) {
      const commandText = payload.command
        ? `${escapeHtml(payload.command.title)}: ${escapeHtml(payload.command.body)}`
        : "No contract clause was elevated to the lens.";
      const findings = payload.analysis?.findings?.length
        ? payload.analysis.findings
            .slice(0, 2)
            .map(
              (finding) =>
                `<li><strong>${escapeHtml(finding.label)}:</strong> ${escapeHtml(
                  finding.excerpt,
                )}</li>`,
            )
            .join("")
        : "<li>No highlighted clause excerpt.</li>";
      return `
        <p><strong>Module:</strong> Contracts</p>
        <p><strong>Observation:</strong> ${
          requestBody.document_image_base64 ? "OCR image review requested" : "Contract review requested"
        }</p>
        <p><strong>Outcome:</strong> ${escapeHtml(payload.outcome)}</p>
        <p><strong>Review confidence:</strong> ${escapeHtml(payload.analysis?.review_confidence ?? "n/a")}</p>
        <p><strong>Lens:</strong> ${commandText}</p>
        <p><strong>Summary:</strong> ${escapeHtml(payload.analysis?.summary_body ?? "No analysis available.")}</p>
        <ul>${findings}</ul>
      `;
    },
  },
};

function createId(prefix) {
  return `${prefix}_${Math.random().toString(16).slice(2)}_${Date.now()}`;
}

function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = String(reader.result || "");
      const base64Value = result.includes(",") ? result.split(",")[1] : result;
      resolve(base64Value);
    };
    reader.onerror = () => reject(new Error("Could not read the selected image file."));
    reader.readAsDataURL(file);
  });
}

const MODULE_LABELS = {
  grocery: "Grocery",
  documents: "Contracts",
};

const STATE_LABELS = {
  idle: "Idle",
  standby: "Standby",
  loading: "Running",
  delivered: "Delivered",
  suppressed: "Suppressed",
  error: "Error",
  ready: "Ready",
  submitting: "Saving",
  useful: "Useful",
  not_useful: "Not useful",
  unavailable: "Unavailable",
  queueing: "Queueing",
  queued: "Queued",
  running: "Running",
  succeeded: "Succeeded",
  failed: "Failed",
  updating: "Updating",
};

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => {
    const entities = {
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    };
    return entities[character];
  });
}

function updateConfidenceOutput(input, output) {
  output.textContent = Number(input.value).toFixed(2);
}

function setStatus(message, state = "ready") {
  const hasError = state === true || state === "error";
  networkStatus.classList.toggle("network-error", hasError);
  networkStatus.classList.toggle("network-loading", state === "loading");
  networkStatus.lastElementChild.textContent = message;
}

function setRailState(card, label, state) {
  card.dataset.state = state;
  label.textContent = STATE_LABELS[state] || state;
}

function updateSessionRail() {
  const moduleName = appState.activeModule;
  sessionModuleLabel.textContent = MODULE_LABELS[moduleName];
  setRailState(syncStateCard, syncStateLabel, appState.syncStateByModule[moduleName]);
  setRailState(asyncStateCard, asyncStateLabel, appState.asyncStateByModule[moduleName]);
  setRailState(feedbackStateCard, feedbackStateLabel, appState.feedbackStateByModule[moduleName]);
}

function setSyncState(moduleName, state) {
  appState.syncStateByModule[moduleName] = state;
  if (appState.activeModule === moduleName) {
    updateSessionRail();
  }
}

function setAsyncState(moduleName, state) {
  appState.asyncStateByModule[moduleName] = state;
  if (appState.activeModule === moduleName) {
    updateSessionRail();
  }
}

function setFeedbackState(moduleName, state) {
  appState.feedbackStateByModule[moduleName] = state;
  if (appState.activeModule === moduleName) {
    updateSessionRail();
    renderFeedbackControls();
  }
}

function validateSimulationPayload(payload) {
  if (!payload || typeof payload !== "object") {
    throw new Error("Unexpected API response shape.");
  }
  if (typeof payload.outcome !== "string") {
    throw new Error("Simulation response did not include an outcome.");
  }
  if (typeof payload.candidate_created !== "boolean") {
    throw new Error("Simulation response did not include candidate state.");
  }
  if (!Array.isArray(payload.session_trace)) {
    throw new Error("Simulation response did not include a session trace.");
  }
  if (payload.command !== null && payload.command !== undefined) {
    if (
      typeof payload.command.command_id !== "string" ||
      typeof payload.command.title !== "string" ||
      typeof payload.command.body !== "string"
    ) {
      throw new Error("Simulation response included an invalid lens command.");
    }
  }
  if (payload.outcome === "delivered" && !payload.command) {
    throw new Error("Delivered simulations must include a lens command.");
  }
}

function renderLensMessage(stateClass, title, body) {
  lensOverlay.className = `lens-overlay ${stateClass}`.trim();
  const fragment = document.createDocumentFragment();
  if (title) {
    const titleNode = document.createElement("h3");
    titleNode.textContent = title;
    fragment.append(titleNode);
  }
  const bodyNode = document.createElement("p");
  bodyNode.className = title ? "" : "lens-label";
  bodyNode.textContent = body;
  fragment.append(bodyNode);
  lensOverlay.replaceChildren(fragment);
}

function renderLensIdle(message) {
  renderLensMessage("lens-overlay-idle", "", message);
}

function renderLensCommand(command) {
  if (!command) {
    renderLensMessage(
      "lens-overlay-suppressed",
      "No lens alert",
      "The latest decision did not return a display command.",
    );
    return;
  }

  renderLensMessage("", command.title, command.body);
}

function renderFeedbackControls() {
  const moduleName = appState.activeModule;
  const command = appState.lastCommandByModule[moduleName];
  const recordedFeedback = command ? appState.feedbackByCommandId[command.command_id] : null;
  const canMarkUseful = Boolean(command?.interaction?.can_mark_useful ?? command);
  const feedbackState = recordedFeedback || appState.feedbackStateByModule[moduleName];
  const buttonsDisabled = !command || !canMarkUseful || feedbackState === "submitting" || Boolean(recordedFeedback);

  feedbackCard.dataset.state = feedbackState;
  feedbackBadge.textContent = STATE_LABELS[feedbackState] || feedbackState;
  feedbackTargetTitle.textContent = command ? command.title : "No delivered alert";
  feedbackUsefulButton.disabled = buttonsDisabled;
  feedbackNotUsefulButton.disabled = buttonsDisabled;
  feedbackUsefulButton.classList.toggle("feedback-button-selected", recordedFeedback === "useful");
  feedbackNotUsefulButton.classList.toggle(
    "feedback-button-selected",
    recordedFeedback === "not_useful",
  );

  if (!command) {
    feedbackCopy.textContent = "Feedback unlocks after a command reaches the lens.";
    return;
  }
  if (!canMarkUseful) {
    feedbackCopy.textContent = "This command does not accept usefulness feedback.";
    return;
  }
  if (recordedFeedback === "useful") {
    feedbackCopy.textContent = "Marked useful for this session trace.";
    return;
  }
  if (recordedFeedback === "not_useful") {
    feedbackCopy.textContent = "Marked not useful for this session trace.";
    return;
  }
  if (feedbackState === "submitting") {
    feedbackCopy.textContent = "Saving feedback to the session trace.";
    return;
  }
  if (feedbackState === "error") {
    feedbackCopy.textContent = "Feedback was not saved. Try again with the latest delivered command.";
    return;
  }
  feedbackCopy.textContent = "Rate the latest lens alert.";
}

function renderList(targetNode, items, emptyTitle, emptyCopy) {
  if (!items || items.length === 0) {
    targetNode.innerHTML = `
      <li class="trace-item trace-item-idle">
        <div class="trace-step">idle</div>
        <div class="trace-content">
          <h3>${emptyTitle}</h3>
          <p>${emptyCopy}</p>
        </div>
      </li>
    `;
    return;
  }

  targetNode.innerHTML = items
    .map(
      (entry) => `
        <li class="trace-item">
          <div class="trace-step">${escapeHtml(entry.step)}</div>
          <div class="trace-content">
            <h3>${escapeHtml(entry.title)}</h3>
            <p>${escapeHtml(entry.detail)}</p>
            <span class="trace-event-type">${escapeHtml(entry.event_type)}</span>
          </div>
        </li>
      `,
    )
    .join("");
}

function renderSessionTrace(sessionTrace) {
  renderList(
    traceList,
    sessionTrace,
    "Waiting for session events",
    "The observation, candidate, decision, and delivery flow will appear here.",
  );
}

function renderSessionHistory(sessionTrace) {
  renderList(
    historyList,
    sessionTrace,
    appState.historyScope === "latest"
      ? "Waiting for latest execution"
      : "Waiting for stored session history",
    appState.historyScope === "latest"
      ? "Run a simulation in this module to inspect the most recent trace only."
      : "The full session timeline for the active module will appear here.",
  );
}

function setHistoryScope(scope) {
  appState.historyScope = scope;
  scopeLatestButton.classList.toggle("scope-tab-active", scope === "latest");
  scopeSessionButton.classList.toggle("scope-tab-active", scope === "session");
}

function renderJobState(job) {
  appState.currentDocumentJob = job;
  if (!job) {
    jobStatusBadge.textContent = "idle";
    jobStatusBadge.dataset.state = "idle";
    jobSummary.textContent =
      "Queue a simulated analysis job, then move it through running, succeeded, or failed.";
    jobIdNode.textContent = "none";
    jobSourceNode.textContent = "pwa_simulation";
    jobAnalysisIdNode.textContent = appState.lastDocumentAnalysisId || "none";
    setAsyncState("documents", "idle");
    return;
  }

  jobStatusBadge.textContent = job.status;
  jobStatusBadge.dataset.state = job.status;
  jobSummary.textContent = `Job ${job.job_id} is currently ${job.status}.`;
  jobIdNode.textContent = job.job_id;
  jobSourceNode.textContent = job.metadata.source_type || "pwa_simulation";
  jobAnalysisIdNode.textContent = job.metadata.analysis_id || appState.lastDocumentAnalysisId || "none";
  setAsyncState("documents", job.status);
}

async function refreshSessionHistory(moduleName) {
  const userId = DEMO_USERS[moduleName];
  const sessionId = DEMO_SESSIONS[moduleName];
  const traceId = appState.lastTraceIdByModule[moduleName];
  const wantsLatestScope = appState.historyScope === "latest";

  if (wantsLatestScope && !traceId) {
    if (appState.activeModule === moduleName) {
      renderSessionHistory([]);
    }
    return;
  }

  const query = new URLSearchParams({
    module: moduleName,
    limit: "50",
  });
  if (wantsLatestScope && traceId) {
    query.set("trace_id", traceId);
  }
  try {
    const response = await fetch(
      `/api/users/${encodeURIComponent(userId)}/sessions/${encodeURIComponent(
        sessionId,
      )}/trace?${query.toString()}`,
    );
    if (!response.ok) {
      throw new Error(`History failed with status ${response.status}`);
    }
    const payload = await response.json();
    if (appState.activeModule === moduleName) {
      renderSessionHistory(payload.session_trace);
    }
  } catch (error) {
    if (appState.activeModule === moduleName) {
      renderSessionHistory([]);
    }
  }
}

function setActiveModule(moduleName) {
  appState.activeModule = moduleName;

  moduleTabs.forEach((tab) => {
    const active = tab.dataset.module === moduleName;
    tab.classList.toggle("module-tab-active", active);
  });

  Object.entries(moduleForms).forEach(([name, form]) => {
    form.classList.toggle("module-form-hidden", name !== moduleName);
  });

  updateSessionRail();
  renderFeedbackControls();

  if (moduleName === "documents") {
    if (appState.currentDocumentJobId) {
      refreshCurrentJobStatus();
    } else {
      renderJobState(null);
    }
  }

  refreshSessionHistory(moduleName);
}

async function submitSimulation(moduleName, event) {
  event.preventDefault();
  const config = simulations[moduleName];
  const traceId = createId(`trace_${moduleName}`);
  const requestBody = {
    ...(await config.buildRequest()),
    trace_id: traceId,
    correlation_id: createId(`corr_${moduleName}`),
  };

  appState.lastTraceIdByModule[moduleName] = traceId;
  appState.lastCommandByModule[moduleName] = null;
  config.button.disabled = true;
  setSyncState(moduleName, "loading");
  setFeedbackState(moduleName, "idle");
  renderLensMessage("lens-overlay-loading", "Processing", "Waiting for backend decision.");
  setStatus("Running simulation", "loading");

  try {
    const response = await fetch(config.endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(requestBody),
    });

    if (!response.ok) {
      throw new Error(`Simulation failed with status ${response.status}`);
    }

    const payload = await response.json();
    validateSimulationPayload(payload);
    if (moduleName === "documents" && payload.analysis_id) {
      appState.lastDocumentAnalysisId = payload.analysis_id;
    }
    appState.lastCommandByModule[moduleName] = payload.command;
    outcomeNode.textContent = payload.outcome;
    candidateNode.textContent = payload.candidate_created ? "yes" : "no";
    eventCountNode.textContent = String(payload.event_count);
    deliveredNode.textContent = String(payload.delivered_commands_count);
    renderLensCommand(payload.command);
    const syncState = payload.outcome === "delivered" ? "delivered" : "suppressed";
    setSyncState(moduleName, syncState);
    setFeedbackState(moduleName, payload.command ? "ready" : "unavailable");
    insightLog.innerHTML = config.buildInsight(payload, requestBody);
    renderSessionTrace(payload.session_trace);
    await refreshSessionHistory(moduleName);
    setStatus("API ready");
  } catch (error) {
    appState.lastCommandByModule[moduleName] = null;
    renderLensMessage("lens-overlay-error", "Simulation unavailable", error.message);
    insightLog.innerHTML = `<p><strong>Error:</strong> ${escapeHtml(error.message)}</p>`;
    renderSessionTrace([]);
    setSyncState(moduleName, "error");
    setFeedbackState(moduleName, "unavailable");
    setStatus("API error", true);
  } finally {
    config.button.disabled = false;
  }
}

async function submitLensFeedback(feedback) {
  const moduleName = appState.activeModule;
  const command = appState.lastCommandByModule[moduleName];
  if (!command) {
    setFeedbackState(moduleName, "unavailable");
    return;
  }

  setFeedbackState(moduleName, "submitting");
  setStatus("Saving feedback", "loading");

  try {
    const response = await fetch(`/api/lens-commands/${encodeURIComponent(command.command_id)}/feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user_id: DEMO_USERS[moduleName],
        session_id: DEMO_SESSIONS[moduleName],
        feedback,
        correlation_id: createId(`corr_feedback_${moduleName}`),
        trace_id: appState.lastTraceIdByModule[moduleName],
      }),
    });

    if (!response.ok) {
      const errorPayload = await response.json().catch(() => null);
      throw new Error(errorPayload?.detail || `Feedback failed with status ${response.status}`);
    }

    appState.feedbackByCommandId[command.command_id] = feedback;
    setFeedbackState(moduleName, feedback);
    await refreshSessionHistory(moduleName);
    const traceId = appState.lastTraceIdByModule[moduleName];
    if (traceId) {
      const traceResponse = await fetch(
        `/api/users/${encodeURIComponent(DEMO_USERS[moduleName])}/sessions/${encodeURIComponent(
          DEMO_SESSIONS[moduleName],
        )}/trace?trace_id=${encodeURIComponent(traceId)}&module=${encodeURIComponent(moduleName)}`,
      );
      if (traceResponse.ok) {
        const tracePayload = await traceResponse.json();
        renderSessionTrace(tracePayload.session_trace);
      }
    }
    setStatus("API ready");
  } catch (error) {
    setFeedbackState(moduleName, "error");
    feedbackCopy.textContent = error.message;
    setStatus("API error", true);
  }
}

async function enqueueDocumentJob() {
  const traceId = createId("trace_job");
  const requestBody = {
    user_id: DEMO_USERS.documents,
    session_id: DEMO_SESSIONS.documents,
    artifact_label: "contract-simulation.txt",
    source_type: "pwa_simulation",
    idempotency_key: `idem_${DEMO_SESSIONS.documents}`,
    correlation_id: createId("corr_job"),
    trace_id: traceId,
  };

  jobEnqueueButton.disabled = true;
  setAsyncState("documents", "queueing");
  setStatus("Queueing document job", "loading");

  try {
    const response = await fetch("/api/jobs/documents/contract-analysis", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(requestBody),
    });
    if (!response.ok) {
      throw new Error(`Job enqueue failed with status ${response.status}`);
    }

    const payload = await response.json();
    appState.currentDocumentJobId = payload.job_id;
    appState.currentDocumentJobTraceId = traceId;
    renderJobState(payload);
    await refreshSessionHistory("documents");
    setStatus("API ready");
  } catch (error) {
    jobSummary.textContent = error.message;
    setAsyncState("documents", "error");
    setStatus("API error", true);
  } finally {
    jobEnqueueButton.disabled = false;
  }
}

async function refreshCurrentJobStatus() {
  if (!appState.currentDocumentJobId) {
    renderJobState(null);
    return;
  }

  try {
    const response = await fetch(`/api/jobs/${appState.currentDocumentJobId}`);
    if (!response.ok) {
      throw new Error(`Job status failed with status ${response.status}`);
    }
    const payload = await response.json();
    renderJobState(payload);
    setStatus("API ready");
  } catch (error) {
    jobSummary.textContent = error.message;
    setAsyncState("documents", "error");
    setStatus("API error", true);
  }
}

async function transitionCurrentJob(targetStatus) {
  if (!appState.currentDocumentJobId) {
    jobSummary.textContent = "Queue a job before changing status.";
    return;
  }
  if (targetStatus === "succeeded" && !appState.lastDocumentAnalysisId) {
    jobSummary.textContent =
      "Run a contract simulation first so the completed job can link to a persisted analysis.";
    return;
  }

  setAsyncState("documents", "updating");
  setStatus(`Setting job ${targetStatus}`, "loading");

  try {
    const requestBody = {
      target_status: targetStatus,
      correlation_id: createId("corr_job_status"),
      trace_id: appState.currentDocumentJobTraceId || createId("trace_job_status"),
    };
    if (targetStatus === "succeeded" && appState.lastDocumentAnalysisId) {
      requestBody.analysis_id = appState.lastDocumentAnalysisId;
    }
    const response = await fetch(`/api/jobs/${appState.currentDocumentJobId}/status`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(requestBody),
    });
    if (!response.ok) {
      const errorPayload = await response.json().catch(() => null);
      const detail = errorPayload?.detail || `Job transition failed with status ${response.status}`;
      throw new Error(detail);
    }

    const payload = await response.json();
    renderJobState(payload);
    await refreshSessionHistory("documents");
    setStatus("API ready");
  } catch (error) {
    jobSummary.textContent = error.message;
    setAsyncState("documents", "error");
    setStatus("API error", true);
  }
}

Object.values(simulations).forEach((config) => {
  updateConfidenceOutput(config.confidenceInput, config.confidenceOutput);
  config.confidenceInput.addEventListener("input", () =>
    updateConfidenceOutput(config.confidenceInput, config.confidenceOutput),
  );
});

moduleTabs.forEach((tab) => {
  tab.addEventListener("click", () => setActiveModule(tab.dataset.module));
});

simulations.grocery.form.addEventListener("submit", (event) => submitSimulation("grocery", event));
simulations.documents.form.addEventListener("submit", (event) => submitSimulation("documents", event));
refreshHistoryButton.addEventListener("click", () => refreshSessionHistory(appState.activeModule));
scopeLatestButton.addEventListener("click", () => {
  setHistoryScope("latest");
  refreshSessionHistory(appState.activeModule);
});
scopeSessionButton.addEventListener("click", () => {
  setHistoryScope("session");
  refreshSessionHistory(appState.activeModule);
});

jobEnqueueButton.addEventListener("click", enqueueDocumentJob);
jobRunningButton.addEventListener("click", () => transitionCurrentJob("running"));
jobSuccessButton.addEventListener("click", () => transitionCurrentJob("succeeded"));
jobFailedButton.addEventListener("click", () => transitionCurrentJob("failed"));
jobRefreshButton.addEventListener("click", refreshCurrentJobStatus);
feedbackUsefulButton.addEventListener("click", () => submitLensFeedback("useful"));
feedbackNotUsefulButton.addEventListener("click", () => submitLensFeedback("not_useful"));

setActiveModule("grocery");
setHistoryScope("latest");
renderJobState(null);
updateSessionRail();
renderFeedbackControls();

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/service-worker.js").catch(() => {
      setStatus("Service worker skipped", true);
    });
  });
}
