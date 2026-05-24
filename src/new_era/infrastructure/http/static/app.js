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

const jobStatusBadge = document.getElementById("job-status-badge");
const jobSummary = document.getElementById("job-summary");
const jobIdNode = document.getElementById("job-id");
const jobSourceNode = document.getElementById("job-source");
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
  lastTraceIdByModule: {
    grocery: null,
    documents: null,
  },
  currentDocumentJobId: null,
  currentDocumentJobTraceId: null,
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
        ? `${payload.command.title}: ${payload.command.body}`
        : "No lens command was delivered.";
      return `
        <p><strong>Module:</strong> Grocery</p>
        <p><strong>Observation:</strong> Missing ${requestBody.item_name}</p>
        <p><strong>Outcome:</strong> ${payload.outcome}</p>
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
    buildRequest() {
      return {
        user_id: DEMO_USERS.documents,
        session_id: DEMO_SESSIONS.documents,
        document_text: document.getElementById("document-text").value.trim(),
        confidence: Number(document.getElementById("document-confidence").value),
        mode: document.getElementById("document-mode").value,
        recent_category_count: Number(document.getElementById("document-recent-count").value),
      };
    },
    buildInsight(payload) {
      const commandText = payload.command
        ? `${payload.command.title}: ${payload.command.body}`
        : "No contract clause was elevated to the lens.";
      return `
        <p><strong>Module:</strong> Contracts</p>
        <p><strong>Observation:</strong> Contract review requested</p>
        <p><strong>Outcome:</strong> ${payload.outcome}</p>
        <p><strong>Lens:</strong> ${commandText}</p>
      `;
    },
  },
};

function createId(prefix) {
  return `${prefix}_${Math.random().toString(16).slice(2)}_${Date.now()}`;
}

function updateConfidenceOutput(input, output) {
  output.textContent = Number(input.value).toFixed(2);
}

function setStatus(message, hasError = false) {
  networkStatus.classList.toggle("network-error", hasError);
  networkStatus.lastElementChild.textContent = message;
}

function renderLensIdle(message) {
  lensOverlay.className = "lens-overlay lens-overlay-idle";
  lensOverlay.innerHTML = `<p class="lens-label">${message}</p>`;
}

function renderLensCommand(command) {
  if (!command) {
    renderLensIdle("No alert reached the display");
    return;
  }

  lensOverlay.className = "lens-overlay";
  lensOverlay.innerHTML = `
    <h3>${command.title}</h3>
    <p>${command.body}</p>
  `;
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
          <div class="trace-step">${entry.step}</div>
          <div class="trace-content">
            <h3>${entry.title}</h3>
            <p>${entry.detail}</p>
            <span class="trace-event-type">${entry.event_type}</span>
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
  if (!job) {
    jobStatusBadge.textContent = "idle";
    jobSummary.textContent =
      "Queue a simulated analysis job, then move it through running, succeeded, or failed.";
    jobIdNode.textContent = "none";
    jobSourceNode.textContent = "pwa_simulation";
    return;
  }

  jobStatusBadge.textContent = job.status;
  jobSummary.textContent = `Job ${job.job_id} is currently ${job.status}.`;
  jobIdNode.textContent = job.job_id;
  jobSourceNode.textContent = job.metadata.source_type || "pwa_simulation";
}

async function refreshSessionHistory(moduleName) {
  const sessionId = DEMO_SESSIONS[moduleName];
  const traceId = appState.lastTraceIdByModule[moduleName];
  const wantsLatestScope = appState.historyScope === "latest";

  if (wantsLatestScope && !traceId) {
    if (appState.activeModule === moduleName) {
      renderSessionHistory([]);
    }
    return;
  }

  const query =
    wantsLatestScope && traceId ? `?trace_id=${encodeURIComponent(traceId)}` : "";
  try {
    const response = await fetch(`/api/sessions/${sessionId}/trace${query}`);
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

  if (moduleName !== "documents") {
    renderJobState(null);
  }

  refreshSessionHistory(moduleName);
}

async function submitSimulation(moduleName, event) {
  event.preventDefault();
  const config = simulations[moduleName];
  const traceId = createId(`trace_${moduleName}`);
  const requestBody = {
    ...config.buildRequest(),
    trace_id: traceId,
    correlation_id: createId(`corr_${moduleName}`),
  };

  appState.lastTraceIdByModule[moduleName] = traceId;
  config.button.disabled = true;
  setStatus("Running simulation");

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
    outcomeNode.textContent = payload.outcome;
    candidateNode.textContent = payload.candidate_created ? "yes" : "no";
    eventCountNode.textContent = String(payload.event_count);
    deliveredNode.textContent = String(payload.delivered_commands_count);
    renderLensCommand(payload.command);
    insightLog.innerHTML = config.buildInsight(payload, requestBody);
    renderSessionTrace(payload.session_trace);
    await refreshSessionHistory(moduleName);
    setStatus("API ready");
  } catch (error) {
    renderLensIdle("Simulation unavailable");
    insightLog.innerHTML = `<p><strong>Error:</strong> ${error.message}</p>`;
    renderSessionTrace([]);
    setStatus("API error", true);
  } finally {
    config.button.disabled = false;
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
  setStatus("Queueing document job");

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
  } catch (error) {
    jobSummary.textContent = error.message;
    setStatus("API error", true);
  }
}

async function transitionCurrentJob(targetStatus) {
  if (!appState.currentDocumentJobId) {
    jobSummary.textContent = "Queue a job before changing status.";
    return;
  }

  setStatus(`Setting job ${targetStatus}`);

  try {
    const response = await fetch(`/api/jobs/${appState.currentDocumentJobId}/status`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        target_status: targetStatus,
        correlation_id: createId("corr_job_status"),
        trace_id: appState.currentDocumentJobTraceId || createId("trace_job_status"),
      }),
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

setActiveModule("grocery");
setHistoryScope("latest");
renderJobState(null);

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/service-worker.js").catch(() => {
      setStatus("Service worker skipped", true);
    });
  });
}
