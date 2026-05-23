const lensOverlay = document.getElementById("lens-overlay");
const outcomeNode = document.getElementById("outcome");
const candidateNode = document.getElementById("candidate-created");
const eventCountNode = document.getElementById("event-count");
const deliveredNode = document.getElementById("delivered-count");
const insightLog = document.getElementById("insight-log");
const traceList = document.getElementById("trace-list");
const networkStatus = document.getElementById("network-status");

const moduleTabs = Array.from(document.querySelectorAll(".module-tab"));
const moduleForms = {
  grocery: document.getElementById("grocery-form"),
  documents: document.getElementById("document-form"),
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
        user_id: "demo-user",
        session_id: "demo-session",
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
        user_id: "demo-user",
        session_id: "demo-session",
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

function renderSessionTrace(sessionTrace) {
  if (!sessionTrace || sessionTrace.length === 0) {
    traceList.innerHTML = `
      <li class="trace-item trace-item-idle">
        <div class="trace-step">idle</div>
        <div class="trace-content">
          <h3>Waiting for session events</h3>
          <p>The observation, candidate, decision, and delivery flow will appear here.</p>
        </div>
      </li>
    `;
    return;
  }

  traceList.innerHTML = sessionTrace
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

function setActiveModule(moduleName) {
  moduleTabs.forEach((tab) => {
    const active = tab.dataset.module === moduleName;
    tab.classList.toggle("module-tab-active", active);
  });

  Object.entries(moduleForms).forEach(([name, form]) => {
    form.classList.toggle("module-form-hidden", name !== moduleName);
  });
}

async function submitSimulation(moduleName, event) {
  event.preventDefault();
  const config = simulations[moduleName];
  const requestBody = config.buildRequest();

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

setActiveModule("grocery");

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/service-worker.js").catch(() => {
      setStatus("Service worker skipped", true);
    });
  });
}
