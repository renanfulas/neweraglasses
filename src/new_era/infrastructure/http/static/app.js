const lensOverlay = document.getElementById("lens-overlay");
const outcomeNode = document.getElementById("outcome");
const candidateNode = document.getElementById("candidate-created");
const eventCountNode = document.getElementById("event-count");
const deliveredNode = document.getElementById("delivered-count");
const insightLog = document.getElementById("insight-log");
const traceList = document.getElementById("trace-list");
const historyList = document.getElementById("history-list");
const networkStatus = document.getElementById("network-status");
const authBand = document.getElementById("auth-band");
const authTitle = document.getElementById("auth-title");
const authCopy = document.getElementById("auth-copy");
const authUserLabel = document.getElementById("auth-user-label");
const authExpiryLabel = document.getElementById("auth-expiry-label");
const authForm = document.getElementById("auth-form");
const authUserIdInput = document.getElementById("auth-user-id");
const authPasswordInput = document.getElementById("auth-password");
const authLoginButton = document.getElementById("auth-login-button");
const authLogoutButton = document.getElementById("auth-logout-button");
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
const documentImageInput = document.getElementById("document-image");
const documentTextInput = document.getElementById("document-text");
const documentCapturePreview = document.getElementById("document-capture-preview");
const documentCaptureImage = document.getElementById("document-capture-image");
const documentCaptureTitle = document.getElementById("document-capture-title");
const documentCaptureCopy = document.getElementById("document-capture-copy");

const jobStatusBadge = document.getElementById("job-status-badge");
const jobSummary = document.getElementById("job-summary");
const jobPolicyCard = document.getElementById("job-policy-card");
const jobPolicyTitle = document.getElementById("job-policy-title");
const jobPolicyMessage = document.getElementById("job-policy-message");
const jobIdNode = document.getElementById("job-id");
const jobSourceNode = document.getElementById("job-source");
const jobAnalysisIdNode = document.getElementById("job-analysis-id");
const jobEnqueueButton = document.getElementById("job-enqueue-button");
const jobRunningButton = document.getElementById("job-running-button");
const jobSuccessButton = document.getElementById("job-success-button");
const jobFailedButton = document.getElementById("job-failed-button");
const jobRefreshButton = document.getElementById("job-refresh-button");
const openLinkedAnalysisButton = document.getElementById("open-linked-analysis-button");
const jobHistoryList = document.getElementById("job-history-list");
const refreshAnalysesButton = document.getElementById("refresh-analyses-button");
const analysisSearchInput = document.getElementById("analysis-search");
const analysisSortSelect = document.getElementById("analysis-sort");
const analysisList = document.getElementById("analysis-list");
const analysisDetailTitle = document.getElementById("analysis-detail-title");
const analysisRouteCopy = document.getElementById("analysis-route-copy");
const analysisDecisionBadge = document.getElementById("analysis-decision-badge");
const analysisDetailSummary = document.getElementById("analysis-detail-summary");
const analysisDetailId = document.getElementById("analysis-detail-id");
const analysisDetailSource = document.getElementById("analysis-detail-source");
const analysisDetailConfidence = document.getElementById("analysis-detail-confidence");
const analysisDetailFeedback = document.getElementById("analysis-detail-feedback");
const openAnalysisRouteButton = document.getElementById("open-analysis-route-button");
const analysisFeedbackUsefulButton = document.getElementById("analysis-feedback-useful-button");
const analysisFeedbackNotUsefulButton = document.getElementById("analysis-feedback-not-useful-button");
const analysisTimelineCaption = document.getElementById("analysis-timeline-caption");
const analysisTimeline = document.getElementById("analysis-timeline");
const analysisReviewCaption = document.getElementById("analysis-review-caption");
const analysisReviewList = document.getElementById("analysis-review-list");
const analysisFindings = document.getElementById("analysis-findings");

const DEMO_SESSIONS = {
  grocery: "demo-grocery-session",
  documents: "demo-documents-session",
};
const MAX_DOCUMENT_IMAGE_BYTES = 7_500_000;
const AUTH_LOCKED_BODY_CLASS = "app-auth-locked";

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
  documentJobs: [],
  lastDocumentPolicyRejection: null,
  lastDocumentAnalysisId: null,
  documentAnalyses: [],
  selectedDocumentAnalysisId: null,
  currentUserId: null,
  authState: "loading",
  authMessage: "Verifying whether this browser already has a valid companion session.",
  authExpiresAt: null,
  authExpiryTimerId: null,
  shellInitialized: false,
};

function getAnalysisViewPath(analysisId) {
  return `/document-analyses/${encodeURIComponent(analysisId)}/view`;
}

function getSelectedDocumentAnalysis() {
  if (!appState.selectedDocumentAnalysisId) {
    return null;
  }
  return (
    appState.documentAnalyses.find(
      (record) => record.analysis_id === appState.selectedDocumentAnalysisId,
    ) || null
  );
}

function getFindingSeverity(finding) {
  if (!finding) {
    return "low";
  }
  if (finding.confidence >= 0.8) {
    return "high";
  }
  if (finding.confidence >= 0.62) {
    return "medium";
  }
  return "low";
}

function buildReviewChecklist(record, findings) {
  if (!findings.length) {
    return [
      {
        title: "Confirm the visible capture is complete",
        body: "No known risk clause was extracted, so verify the image or text still includes the key commercial terms before signing.",
      },
    ];
  }

  return findings.map((finding) => {
    const severity = getFindingSeverity(finding);
    const guidanceByType = {
      automatic_renewal: "Check when renewal happens, how to cancel before renewal, and whether notice is required.",
      cancellation_fee: "Confirm the exact penalty amount and whether there is any proportional reduction over time.",
      minimum_commitment: "Review the minimum term and whether the agreement locks you in longer than expected.",
      fees_or_interest: "Validate the extra charges, trigger conditions, and whether interest compounds over time.",
    };
    return {
      title: `${severity === "high" ? "Prioritize" : "Review"} ${finding.label || "this clause"}`,
      body:
        guidanceByType[finding.finding_type] ||
        "Read this clause end to end and confirm the practical consequence before signing.",
    };
  });
}

const simulations = {
  grocery: {
    form: moduleForms.grocery,
    button: document.getElementById("grocery-simulate-button"),
    endpoint: "/api/simulations/grocery/missing-item",
    confidenceInput: document.getElementById("grocery-confidence"),
    confidenceOutput: document.getElementById("grocery-confidence-output"),
    buildRequest() {
      return {
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
      const inputPayload = await buildDocumentInputPayload();
      return {
        session_id: DEMO_SESSIONS.documents,
        document_text: inputPayload.documentText,
        document_image_base64: inputPayload.documentImageBase64,
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

function fileToDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(new Error("Could not read the selected image file."));
    reader.readAsDataURL(file);
  });
}

async function fileToBase64(file) {
  const dataUrl = await fileToDataUrl(file);
  return dataUrl.includes(",") ? dataUrl.split(",")[1] : dataUrl;
}

function validateDocumentImageFile(file) {
  if (!file) {
    return;
  }
  if (!["image/png", "image/jpeg", "image/webp"].includes(file.type)) {
    throw new Error("Select a PNG, JPEG, or WebP image.");
  }
  if (file.size > MAX_DOCUMENT_IMAGE_BYTES) {
    throw new Error("Selected image is too large for the local MVP intake.");
  }
}

async function buildDocumentInputPayload() {
  const selectedFile = documentImageInput.files[0] || null;
  validateDocumentImageFile(selectedFile);
  const documentText = documentTextInput.value.trim();
  const documentImageBase64 = selectedFile ? await fileToBase64(selectedFile) : null;
  if (!documentText && !documentImageBase64) {
    throw new Error("Add contract text or capture/upload an image before processing.");
  }
  return {
    selectedFile,
    documentText: documentText || null,
    documentImageBase64,
  };
}

async function renderDocumentCapturePreview() {
  const selectedFile = documentImageInput.files[0] || null;
  if (!selectedFile) {
    documentCapturePreview.dataset.state = "empty";
    documentCaptureImage.removeAttribute("src");
    documentCaptureTitle.textContent = "Camera/upload ready";
    documentCaptureCopy.textContent = "Use the file picker or camera capture to feed OCR.";
    return;
  }

  try {
    validateDocumentImageFile(selectedFile);
    documentCaptureImage.src = await fileToDataUrl(selectedFile);
    documentCapturePreview.dataset.state = "ready";
    documentCaptureTitle.textContent = selectedFile.name || "Captured contract image";
    documentCaptureCopy.textContent = `${Math.round(selectedFile.size / 1024)} KB image ready for OCR and async analysis.`;
  } catch (error) {
    documentCapturePreview.dataset.state = "empty";
    documentCaptureImage.removeAttribute("src");
    documentCaptureTitle.textContent = "Image cannot be used";
    documentCaptureCopy.textContent = error.message;
  }
}

function buildAuthHeaders(_userId, includeJson = false) {
  const headers = {};
  if (includeJson) {
    headers["Content-Type"] = "application/json";
  }
  return headers;
}

function getCurrentUserId() {
  return appState.currentUserId;
}

function getCurrentUserSessionBasePath(sessionId) {
  return `/api/current-user/sessions/${encodeURIComponent(sessionId)}`;
}

class AuthRequiredError extends Error {}

function formatAuthExpiry(expiresAt) {
  if (!expiresAt) {
    return "unknown";
  }
  const parsed = new Date(expiresAt);
  if (Number.isNaN(parsed.getTime())) {
    return "unknown";
  }
  return parsed.toLocaleString();
}

function clearAuthExpiryTimer() {
  if (appState.authExpiryTimerId !== null) {
    window.clearTimeout(appState.authExpiryTimerId);
    appState.authExpiryTimerId = null;
  }
}

function setAuthRequired(message, state = "unauthenticated") {
  clearAuthExpiryTimer();
  appState.currentUserId = null;
  appState.authExpiresAt = null;
  appState.authState = state;
  appState.authMessage = message;
  renderAuthState();
}

function scheduleAuthExpiry(expiresAt) {
  clearAuthExpiryTimer();
  if (!expiresAt) {
    return;
  }
  const expiresAtTime = new Date(expiresAt).getTime();
  if (Number.isNaN(expiresAtTime)) {
    return;
  }
  const delayMs = expiresAtTime - Date.now();
  if (delayMs <= 0) {
    setAuthRequired("Your session expired. Sign in again to continue.", "reauth-required");
    return;
  }
  appState.authExpiryTimerId = window.setTimeout(() => {
    setStatus("Session expired. Sign in again.", true);
    setAuthRequired("Your session expired. Sign in again to continue.", "reauth-required");
  }, delayMs);
}

function renderAuthState() {
  const titleByState = {
    loading: "Checking session",
    authenticated: "Companion session active",
    unauthenticated: "Sign in to continue",
    "reauth-required": "Session expired",
    error: "Sign-in unavailable",
  };
  const userId = getCurrentUserId();
  const isAuthenticated = appState.authState === "authenticated";
  authBand.dataset.state = appState.authState;
  authTitle.textContent = titleByState[appState.authState] || "Companion access";
  authCopy.textContent = appState.authMessage;
  authUserLabel.textContent = userId || "not signed in";
  authExpiryLabel.textContent = isAuthenticated ? formatAuthExpiry(appState.authExpiresAt) : "not signed in";
  authForm.hidden = isAuthenticated || appState.authState === "loading";
  authLogoutButton.hidden = !isAuthenticated;
  authLoginButton.disabled = appState.authState === "loading";
  document.body.classList.toggle(AUTH_LOCKED_BODY_CLASS, !isAuthenticated);
}

function applyAuthenticatedSession(payload) {
  appState.currentUserId = payload.current_user?.user_id || null;
  appState.authExpiresAt = payload.auth_session?.expires_at || null;
  appState.authState = "authenticated";
  appState.authMessage = "This browser has an active local companion session.";
  authPasswordInput.value = "";
  scheduleAuthExpiry(appState.authExpiresAt);
  renderAuthState();
}

async function apiFetch(input, init = {}, { allow401 = false, trapAuthFailure = true } = {}) {
  const response = await fetch(input, {
    credentials: "same-origin",
    ...init,
  });
  if (response.status === 401 && !allow401 && trapAuthFailure) {
    setStatus("Session expired. Sign in again.", true);
    setAuthRequired("Your session expired. Sign in again to continue.", "reauth-required");
    throw new AuthRequiredError("Session expired. Sign in again.");
  }
  return response;
}

async function loadAuthenticatedSession({ silent401 = false } = {}) {
  const sessionResponse = await apiFetch("/api/auth/session", {}, { allow401: true, trapAuthFailure: false });
  if (sessionResponse.ok) {
    const payload = await sessionResponse.json();
    applyAuthenticatedSession(payload);
    return true;
  }
  if (sessionResponse.status === 401) {
    setAuthRequired(
      "Sign in with the local companion credentials configured on this runtime.",
      "unauthenticated",
    );
    return false;
  }
  throw new Error(`Auth bootstrap failed with status ${sessionResponse.status}`);
}

async function loginWithCredentials(userId, password) {
  authLoginButton.disabled = true;
  authBand.dataset.state = "loading";
  authCopy.textContent = "Opening a fresh companion session for this browser.";
  setStatus("Signing in", "loading");
  try {
    const loginResponse = await apiFetch(
      "/api/auth/login",
      {
        method: "POST",
        headers: buildAuthHeaders(null, true),
        body: JSON.stringify({ user_id: userId, password }),
      },
      { allow401: true, trapAuthFailure: false },
    );
    if (!loginResponse.ok) {
      throw await buildApiError(loginResponse, `Auth login failed with status ${loginResponse.status}`);
    }
    const payload = await loginResponse.json();
    applyAuthenticatedSession(payload);
    setStatus("API ready");
    await enterAuthenticatedShell();
  } catch (error) {
    authBand.dataset.state = "error";
    authTitle.textContent = "Sign-in unavailable";
    authCopy.textContent = error.message;
    setStatus("Sign-in failed", true);
  } finally {
    authLoginButton.disabled = false;
  }
}

async function logoutCurrentSession() {
  authLogoutButton.disabled = true;
  setStatus("Signing out", "loading");
  try {
    await apiFetch(
      "/api/auth/logout",
      {
        method: "POST",
      },
      { allow401: true, trapAuthFailure: false },
    );
  } finally {
    authLogoutButton.disabled = false;
  }
  setAuthRequired("Sign in with the local companion credentials configured on this runtime.", "unauthenticated");
  setStatus("Signed out");
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
  blocked: "Blocked",
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

function isPolicyRejection(detail) {
  return Boolean(
    detail &&
      typeof detail === "object" &&
      typeof detail.code === "string" &&
      typeof detail.message === "string",
  );
}

function getApiErrorMessage(detail, fallbackMessage) {
  if (isPolicyRejection(detail)) {
    return detail.message;
  }
  if (typeof detail === "string" && detail.trim()) {
    return detail;
  }
  if (detail && typeof detail === "object" && typeof detail.message === "string") {
    return detail.message;
  }
  return fallbackMessage;
}

async function buildApiError(response, fallbackMessage) {
  const errorPayload = await response.json().catch(() => null);
  const detail = errorPayload?.detail;
  const error = new Error(getApiErrorMessage(detail, fallbackMessage));
  error.status = response.status;
  error.detail = detail;
  error.payload = errorPayload;
  return error;
}

function clearDocumentPolicyRejection() {
  appState.lastDocumentPolicyRejection = null;
}

function setDocumentPolicyRejection(detail) {
  appState.lastDocumentPolicyRejection = isPolicyRejection(detail) ? detail : null;
}

function getJobsEndpointPolicyRejection(payload) {
  if (!payload || typeof payload !== "object") {
    return null;
  }
  if (isPolicyRejection(payload.blocked_reason)) {
    return payload.blocked_reason;
  }
  if (isPolicyRejection(payload.policy_rejection)) {
    return payload.policy_rejection;
  }
  return null;
}

function renderJobPolicyNotice() {
  const detail = appState.lastDocumentPolicyRejection;
  if (!detail) {
    jobPolicyCard.hidden = true;
    jobPolicyCard.dataset.state = "idle";
    jobPolicyTitle.textContent = "Session ready";
    jobPolicyMessage.textContent =
      "The backend will explain when a document upload or job is blocked.";
    return;
  }

  const isQuotaBlock = detail.reason === "quota_exceeded";
  const limitText =
    typeof detail.current === "number" && typeof detail.limit === "number"
      ? ` (${detail.current}/${detail.limit})`
      : "";
  jobPolicyCard.hidden = false;
  jobPolicyCard.dataset.state = isQuotaBlock ? "blocked" : "error";
  jobPolicyTitle.textContent = `${detail.code}${limitText}`;
  jobPolicyMessage.textContent = detail.message;
}

function renderJobState(job) {
  appState.currentDocumentJob = job;
  if (!job) {
    jobStatusBadge.textContent = appState.lastDocumentPolicyRejection ? "blocked" : "idle";
    jobStatusBadge.dataset.state = appState.lastDocumentPolicyRejection ? "blocked" : "idle";
    jobSummary.textContent = appState.lastDocumentPolicyRejection
      ? appState.lastDocumentPolicyRejection.message
      : "Queue a simulated analysis job, then move it through running, succeeded, or failed.";
    jobIdNode.textContent = "none";
    jobSourceNode.textContent = "pwa_simulation";
    jobAnalysisIdNode.textContent = appState.lastDocumentAnalysisId || "none";
    openLinkedAnalysisButton.disabled = !appState.lastDocumentAnalysisId;
    setAsyncState("documents", appState.lastDocumentPolicyRejection ? "blocked" : "idle");
    renderJobPolicyNotice();
    return;
  }

  const linkedAnalysisId = job.metadata.analysis_id || job.result_id || appState.lastDocumentAnalysisId || null;
  jobStatusBadge.textContent = job.status;
  jobStatusBadge.dataset.state = job.status;
  jobSummary.textContent = `Job ${job.job_id} is currently ${job.status}.`;
  jobIdNode.textContent = job.job_id;
  jobSourceNode.textContent = job.metadata.source_type || "pwa_simulation";
  jobAnalysisIdNode.textContent = linkedAnalysisId || "none";
  openLinkedAnalysisButton.disabled = !linkedAnalysisId;
  setAsyncState("documents", job.status);
  renderJobPolicyNotice();
}

function renderJobHistory(jobs) {
  if (!jobs.length) {
    jobHistoryList.innerHTML = `
      <li class="analysis-list-empty">
        <h4>No document jobs yet</h4>
        <p>Queued uploads and text jobs will appear here.</p>
      </li>
    `;
    return;
  }

  jobHistoryList.innerHTML = jobs
    .map((job) => {
      const linkedAnalysisId = job.metadata?.analysis_id || job.result_id || null;
      const source = job.metadata?.artifact_label || job.metadata?.source_type || "document job";
      const activeClass =
        job.job_id === appState.currentDocumentJobId
          ? "analysis-list-item analysis-list-item-active"
          : "analysis-list-item";
      return `
        <li>
          <button type="button" class="${activeClass}" data-job-id="${escapeHtml(job.job_id)}">
            <h4>${escapeHtml(job.status)} · ${escapeHtml(source)}</h4>
            <p>${escapeHtml(job.job_id)}</p>
            ${
              isPolicyRejection(job.metadata?.blocked_reason)
                ? `<p>${escapeHtml(job.metadata.blocked_reason.message)}</p>`
                : ""
            }
            <div class="analysis-list-item-meta">
              <span>Attempts ${escapeHtml(job.attempts)}/${escapeHtml(job.max_attempts)}</span>
              <span>${linkedAnalysisId ? "Result ready" : "No result yet"}</span>
            </div>
          </button>
        </li>
      `;
    })
    .join("");

  jobHistoryList.querySelectorAll("[data-job-id]").forEach((button) => {
    button.addEventListener("click", () => {
      const job = appState.documentJobs.find((entry) => entry.job_id === button.dataset.jobId);
      if (!job) {
        return;
      }
      appState.currentDocumentJobId = job.job_id;
      appState.currentDocumentJobTraceId = null;
      if (job.result_id) {
        appState.lastDocumentAnalysisId = job.result_id;
        appState.selectedDocumentAnalysisId = job.result_id;
      }
      renderJobState(job);
      renderJobHistory(appState.documentJobs);
    });
  });
}

function getVisibleDocumentAnalyses(records) {
  const searchTerm = analysisSearchInput.value.trim().toLowerCase();
  const ordered = [...records].sort((left, right) => {
    const leftDate = Date.parse(left.created_at || "") || 0;
    const rightDate = Date.parse(right.created_at || "") || 0;
    return analysisSortSelect.value === "oldest" ? leftDate - rightDate : rightDate - leftDate;
  });

  if (!searchTerm) {
    return ordered;
  }

  return ordered.filter((record) => {
    const haystack = [
      record.analysis?.summary_title,
      record.analysis?.summary_body,
      record.source_type,
      ...(Array.isArray(record.analysis?.findings)
        ? record.analysis.findings.flatMap((finding) => [finding.label, finding.excerpt])
        : []),
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return haystack.includes(searchTerm);
  });
}

function renderAnalysisDetail(record) {
  if (!record) {
    analysisDetailTitle.textContent = "Waiting for a saved review";
    analysisRouteCopy.textContent =
      "Pick a persisted contract analysis to inspect the findings, excerpts, confidence, and timeline.";
    analysisDecisionBadge.textContent = "Awaiting review";
    analysisDecisionBadge.dataset.state = "idle";
    analysisDetailSummary.textContent =
      "Pick a persisted contract analysis to inspect the findings, excerpts, and confidence.";
    analysisDetailId.textContent = "none";
    analysisDetailSource.textContent = "unknown";
    analysisDetailConfidence.textContent = "n/a";
    analysisDetailFeedback.textContent = "none";
    openAnalysisRouteButton.disabled = true;
    analysisFeedbackUsefulButton.disabled = true;
    analysisFeedbackNotUsefulButton.disabled = true;
    analysisFindings.innerHTML = '<li class="analysis-findings-empty">No findings loaded.</li>';
    analysisReviewCaption.textContent = "Action guidance will appear here.";
    analysisReviewList.innerHTML =
      '<li class="analysis-findings-empty">No review checklist loaded.</li>';
    return;
  }

  analysisDetailTitle.textContent = record.analysis.summary_title || "Contract review";
  analysisRouteCopy.textContent =
    "Use this view to decide quickly whether the clause deserves a second pass before signing.";
  analysisDetailSummary.textContent =
    record.analysis.summary_body || "No summary body was stored for this analysis.";
  analysisDetailId.textContent = record.analysis_id;
  analysisDetailSource.textContent = record.source_type || "unknown";
  analysisDetailConfidence.textContent =
    typeof record.analysis.review_confidence === "number"
      ? record.analysis.review_confidence.toFixed(2)
      : "n/a";
  analysisDetailFeedback.textContent = record.feedback || "none";
  const hasFindings = Array.isArray(record.analysis.findings) && record.analysis.findings.length > 0;
  analysisDecisionBadge.textContent = hasFindings ? "Needs attention" : "No key risk found";
  analysisDecisionBadge.dataset.state = hasFindings ? "attention" : "clear";
  openAnalysisRouteButton.disabled = false;
  analysisFeedbackUsefulButton.disabled = false;
  analysisFeedbackNotUsefulButton.disabled = false;
  analysisFeedbackUsefulButton.classList.toggle("feedback-button-selected", record.feedback === "useful");
  analysisFeedbackNotUsefulButton.classList.toggle(
    "feedback-button-selected",
    record.feedback === "not_useful",
  );

  const findings = Array.isArray(record.analysis.findings) ? record.analysis.findings : [];
  if (findings.length === 0) {
    analysisFindings.innerHTML =
      '<li class="analysis-findings-empty">No findings were extracted for this contract.</li>';
  } else {
    analysisFindings.innerHTML = findings
      .map((finding) => {
        const severity = getFindingSeverity(finding);
        const confidence =
          typeof finding.confidence === "number" ? finding.confidence.toFixed(2) : "n/a";
        return `
          <li class="analysis-finding-card" data-severity="${escapeHtml(severity)}">
            <div class="analysis-finding-header">
              <strong>${escapeHtml(finding.label || "Finding")}</strong>
              <div class="analysis-finding-meta">
                <span class="analysis-severity-badge" data-severity="${escapeHtml(severity)}">${escapeHtml(
                  severity,
                )} severity</span>
                <span class="analysis-confidence-badge">Confidence ${escapeHtml(confidence)}</span>
              </div>
            </div>
            <p class="analysis-excerpt">${escapeHtml(finding.excerpt || "No excerpt available.")}</p>
          </li>
        `;
      })
      .join("");
  }

  const checklist = buildReviewChecklist(record, findings);
  analysisReviewCaption.textContent = `${checklist.length} review checkpoints before signing`;
  analysisReviewList.innerHTML = checklist
    .map(
      (item) => `
        <li>
          <strong>${escapeHtml(item.title)}</strong>
          <p>${escapeHtml(item.body)}</p>
        </li>
      `,
    )
    .join("");
}

async function openDocumentAnalysis(analysisId, { pushRoute = false } = {}) {
  if (!analysisId) {
    return;
  }

  const cachedRecord = appState.documentAnalyses.find((record) => record.analysis_id === analysisId);
  if (cachedRecord) {
    appState.selectedDocumentAnalysisId = analysisId;
    renderAnalysisList(appState.documentAnalyses);
    if (pushRoute) {
      history.pushState({ analysisId }, "", getAnalysisViewPath(analysisId));
    }
    return;
  }

  try {
    const response = await apiFetch(`/api/document-analyses/${encodeURIComponent(analysisId)}`, {
      headers: buildAuthHeaders(null),
    });
    if (!response.ok) {
      throw new Error(`Analysis lookup failed with status ${response.status}`);
    }

    const payload = await response.json();
    appState.documentAnalyses = [payload, ...appState.documentAnalyses.filter((record) => record.analysis_id !== payload.analysis_id)];
    appState.selectedDocumentAnalysisId = analysisId;
    renderAnalysisList(appState.documentAnalyses);
    if (pushRoute) {
      history.pushState({ analysisId }, "", getAnalysisViewPath(analysisId));
    }
  } catch (error) {
    if (error instanceof AuthRequiredError) {
      return;
    }
    setStatus("API error", true);
    analysisDetailTitle.textContent = "Analysis lookup unavailable";
    analysisDetailSummary.textContent = error.message;
    analysisDetailId.textContent = analysisId;
    analysisDetailSource.textContent = "unknown";
    analysisDetailConfidence.textContent = "n/a";
    analysisFindings.innerHTML =
      '<li class="analysis-findings-empty">The linked analysis could not be loaded right now.</li>';
  }
}

async function submitDocumentAnalysisFeedback(feedback) {
  const record = getSelectedDocumentAnalysis();
  if (!record) {
    return;
  }

  analysisFeedbackUsefulButton.disabled = true;
  analysisFeedbackNotUsefulButton.disabled = true;
  setStatus("Saving analysis feedback", "loading");
  try {
    const response = await apiFetch(
      `/api/document-analyses/${encodeURIComponent(record.analysis_id)}/feedback`,
      {
        method: "POST",
        headers: buildAuthHeaders(null, true),
        body: JSON.stringify({
          session_id: record.session_id,
          feedback,
          correlation_id: createId("corr_analysis_feedback"),
          trace_id: record.trace_id,
        }),
      },
    );
    if (!response.ok) {
      throw await buildApiError(response, `Analysis feedback failed with status ${response.status}`);
    }

    appState.documentAnalyses = appState.documentAnalyses.map((entry) =>
      entry.analysis_id === record.analysis_id ? { ...entry, feedback } : entry,
    );
    renderAnalysisList(appState.documentAnalyses);
    await refreshSessionHistory("documents");
    setStatus("API ready");
  } catch (error) {
    if (error instanceof AuthRequiredError) {
      return;
    }
    setStatus("API error", true);
    analysisDetailSummary.textContent = error.message;
    renderAnalysisDetail(getSelectedDocumentAnalysis());
  }
}

async function refreshAnalysisTimeline(record) {
  if (!record) {
    analysisTimelineCaption.textContent = "The review path will appear here.";
    analysisTimeline.innerHTML = '<li class="analysis-findings-empty">No timeline loaded.</li>';
    return;
  }

  try {
    const query = new URLSearchParams({
      trace_id: record.trace_id,
      module: "documents",
    });
    const response = await apiFetch(
      `${getCurrentUserSessionBasePath(record.session_id)}/trace?${query.toString()}`,
      {
        headers: buildAuthHeaders(null),
      },
    );
    if (!response.ok) {
      throw new Error(`Timeline failed with status ${response.status}`);
    }

    const payload = await response.json();
    analysisTimelineCaption.textContent = `${payload.event_count} events in this review trace`;
    const entries = Array.isArray(payload.session_trace) ? payload.session_trace : [];
    if (!entries.length) {
      analysisTimeline.innerHTML = '<li class="analysis-findings-empty">No timeline loaded.</li>';
      return;
    }

    analysisTimeline.innerHTML = entries
      .map(
        (entry) => `
          <li>
            <span class="analysis-timeline-step">${escapeHtml(entry.step || "step")}</span>
            <h4>${escapeHtml(entry.title || entry.event_type || "Event")}</h4>
            <p>${escapeHtml(entry.detail || "No detail available.")}</p>
          </li>
        `,
      )
      .join("");
  } catch (error) {
    if (error instanceof AuthRequiredError) {
      return;
    }
    analysisTimelineCaption.textContent = "Timeline unavailable";
    analysisTimeline.innerHTML = `
      <li class="analysis-findings-empty">${escapeHtml(error.message)}</li>
    `;
  }
}

function renderAnalysisList(records) {
  const visibleRecords = getVisibleDocumentAnalyses(records || []);
  if (!visibleRecords.length) {
    analysisList.innerHTML = `
      <li class="analysis-list-empty">
        <h4>${records && records.length ? "No analyses match the current filters" : "No persisted analyses yet"}</h4>
        <p>${
          records && records.length
            ? "Try another search term or switch the recency order."
            : "Run a contract simulation or complete a document job to build a reusable review history."
        }</p>
      </li>
    `;
    if (!records || records.length === 0) {
      renderAnalysisDetail(null);
    }
    return;
  }

  const selectedId =
    appState.selectedDocumentAnalysisId &&
    visibleRecords.some((record) => record.analysis_id === appState.selectedDocumentAnalysisId)
      ? appState.selectedDocumentAnalysisId
      : visibleRecords[0].analysis_id;
  appState.selectedDocumentAnalysisId = selectedId;

  analysisList.innerHTML = visibleRecords
    .map((record) => {
      const activeClass =
        record.analysis_id === selectedId ? "analysis-list-item analysis-list-item-active" : "analysis-list-item";
      const confidence =
        typeof record.analysis.review_confidence === "number"
          ? record.analysis.review_confidence.toFixed(2)
          : "n/a";
      return `
        <li>
          <button
            type="button"
            class="${activeClass}"
            data-analysis-id="${escapeHtml(record.analysis_id)}"
          >
            <h4>${escapeHtml(record.analysis.summary_title || "Contract review")}</h4>
            <p>${escapeHtml(record.analysis.summary_body || "No summary available.")}</p>
            <div class="analysis-list-item-meta">
              <span>${escapeHtml(record.source_type || "unknown")}</span>
              <span>Confidence ${escapeHtml(confidence)}</span>
            </div>
          </button>
        </li>
      `;
    })
    .join("");

  analysisList.querySelectorAll("[data-analysis-id]").forEach((button) => {
    button.addEventListener("click", () => {
      appState.selectedDocumentAnalysisId = button.dataset.analysisId;
      renderAnalysisList(appState.documentAnalyses);
    });
  });

  const selectedRecord =
    visibleRecords.find((record) => record.analysis_id === selectedId) || visibleRecords[0];
  renderAnalysisDetail(selectedRecord);
  refreshAnalysisTimeline(selectedRecord);
}

async function refreshDocumentAnalyses() {
  try {
    const response = await apiFetch(
      `/api/sessions/${encodeURIComponent(DEMO_SESSIONS.documents)}/document-analyses`,
      {
        headers: buildAuthHeaders(null),
      },
    );
    if (!response.ok) {
      throw new Error(`Analyses failed with status ${response.status}`);
    }

    const payload = await response.json();
    appState.documentAnalyses = Array.isArray(payload) ? payload : [];
    renderAnalysisList(appState.documentAnalyses);
  } catch (error) {
    if (error instanceof AuthRequiredError) {
      return;
    }
    appState.documentAnalyses = [];
    analysisList.innerHTML = `
      <li class="analysis-list-empty">
        <h4>Analysis history unavailable</h4>
        <p>${escapeHtml(error.message)}</p>
      </li>
    `;
    renderAnalysisDetail(null);
  }
}

async function refreshDocumentJobs() {
  try {
    const response = await apiFetch(
      `${getCurrentUserSessionBasePath(DEMO_SESSIONS.documents)}/jobs?module=documents&limit=10`,
      {
        headers: buildAuthHeaders(null),
      },
    );
    if (!response.ok) {
      throw await buildApiError(response, `Jobs failed with status ${response.status}`);
    }

    const payload = await response.json();
    const jobsPolicyRejection = getJobsEndpointPolicyRejection(payload);
    if (jobsPolicyRejection) {
      setDocumentPolicyRejection(jobsPolicyRejection);
    }
    appState.documentJobs = Array.isArray(payload.jobs) ? payload.jobs : [];
    renderJobHistory(appState.documentJobs);
    renderJobPolicyNotice();
  } catch (error) {
    if (error instanceof AuthRequiredError) {
      return;
    }
    setDocumentPolicyRejection(error.detail);
    appState.documentJobs = [];
    jobHistoryList.innerHTML = `
      <li class="analysis-list-empty">
        <h4>Job history unavailable</h4>
        <p>${escapeHtml(error.message)}</p>
      </li>
    `;
    renderJobPolicyNotice();
  }
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

  const query = new URLSearchParams({
    module: moduleName,
    limit: "50",
  });
  if (wantsLatestScope && traceId) {
    query.set("trace_id", traceId);
  }
  try {
    const response = await apiFetch(
      `${getCurrentUserSessionBasePath(sessionId)}/trace?${query.toString()}`,
      {
        headers: buildAuthHeaders(null),
      },
    );
    if (!response.ok) {
      throw new Error(`History failed with status ${response.status}`);
    }
    const payload = await response.json();
    if (appState.activeModule === moduleName) {
      renderSessionHistory(payload.session_trace);
    }
  } catch (error) {
    if (error instanceof AuthRequiredError) {
      return;
    }
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
    refreshDocumentJobs();
    refreshDocumentAnalyses();
  }

  refreshSessionHistory(moduleName);
}

async function handleAnalysisRoute() {
  const match = window.location.pathname.match(/^\/document-analyses\/([^/]+)\/view\/?$/);
  if (!match) {
    document.body.classList.remove("analysis-route-active");
    return;
  }

  document.body.classList.add("analysis-route-active");
  setActiveModule("documents");
  await openDocumentAnalysis(decodeURIComponent(match[1]));
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
    const response = await apiFetch(config.endpoint, {
      method: "POST",
      headers: buildAuthHeaders(null, true),
      body: JSON.stringify(requestBody),
    });

    if (!response.ok) {
      throw await buildApiError(response, `Simulation failed with status ${response.status}`);
    }

    const payload = await response.json();
    validateSimulationPayload(payload);
    if (moduleName === "documents" && payload.analysis_id) {
      appState.lastDocumentAnalysisId = payload.analysis_id;
      appState.selectedDocumentAnalysisId = payload.analysis_id;
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
    if (moduleName === "documents") {
      await refreshDocumentAnalyses();
    }
    setStatus("API ready");
  } catch (error) {
    if (error instanceof AuthRequiredError) {
      return;
    }
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
    const response = await apiFetch(`/api/lens-commands/${encodeURIComponent(command.command_id)}/feedback`, {
      method: "POST",
      headers: buildAuthHeaders(null, true),
      body: JSON.stringify({
        session_id: DEMO_SESSIONS[moduleName],
        feedback,
        correlation_id: createId(`corr_feedback_${moduleName}`),
        trace_id: appState.lastTraceIdByModule[moduleName],
      }),
    });

    if (!response.ok) {
      throw await buildApiError(response, `Feedback failed with status ${response.status}`);
    }

    appState.feedbackByCommandId[command.command_id] = feedback;
    setFeedbackState(moduleName, feedback);
    await refreshSessionHistory(moduleName);
    const traceId = appState.lastTraceIdByModule[moduleName];
    if (traceId) {
      const traceResponse = await apiFetch(
        `${getCurrentUserSessionBasePath(DEMO_SESSIONS[moduleName])}/trace?trace_id=${encodeURIComponent(traceId)}&module=${encodeURIComponent(moduleName)}`,
        {
          headers: buildAuthHeaders(null),
        },
      );
      if (traceResponse.ok) {
        const tracePayload = await traceResponse.json();
        renderSessionTrace(tracePayload.session_trace);
      }
    }
    setStatus("API ready");
  } catch (error) {
    if (error instanceof AuthRequiredError) {
      return;
    }
    setFeedbackState(moduleName, "error");
    feedbackCopy.textContent = error.message;
    setStatus("API error", true);
  }
}

async function enqueueDocumentJob() {
  const traceId = createId("trace_job");
  jobEnqueueButton.disabled = true;
  setAsyncState("documents", "queueing");
  setStatus("Queueing document job", "loading");

  try {
    const inputPayload = await buildDocumentInputPayload();
    let response;
    if (inputPayload.selectedFile) {
      const formData = new FormData();
      formData.append("session_id", DEMO_SESSIONS.documents);
      formData.append("artifact", inputPayload.selectedFile);
      formData.append("idempotency_key", createId("idem_upload"));
      formData.append("confidence", document.getElementById("document-confidence").value);
      formData.append("mode", document.getElementById("document-mode").value);
      formData.append("recent_category_count", document.getElementById("document-recent-count").value);
      formData.append("observation_id", createId("obs_document_upload"));
      formData.append("correlation_id", createId("corr_upload_job"));
      formData.append("trace_id", traceId);
      if (inputPayload.documentText) {
        formData.append("document_text", inputPayload.documentText);
      }
      response = await apiFetch("/api/uploads/documents/contract-analysis", {
        method: "POST",
        headers: buildAuthHeaders(null),
        body: formData,
      });
    } else {
      const requestBody = {
        session_id: DEMO_SESSIONS.documents,
        artifact_label: "contract-text-entry.txt",
        source_type: "pwa_text_entry",
        idempotency_key: createId("idem_document"),
        document_text: inputPayload.documentText,
        confidence: Number(document.getElementById("document-confidence").value),
        mode: document.getElementById("document-mode").value,
        recent_category_count: Number(document.getElementById("document-recent-count").value),
        observation_id: createId("obs_document_job"),
        correlation_id: createId("corr_job"),
        trace_id: traceId,
      };
      response = await apiFetch("/api/jobs/documents/contract-analysis", {
        method: "POST",
        headers: buildAuthHeaders(null, true),
        body: JSON.stringify(requestBody),
      });
    }
    if (!response.ok) {
      throw await buildApiError(response, `Job enqueue failed with status ${response.status}`);
    }

    const payload = await response.json();
    clearDocumentPolicyRejection();
    appState.currentDocumentJobId = payload.job_id;
    appState.currentDocumentJobTraceId = traceId;
    renderJobState(payload);
    await refreshDocumentJobs();
    await refreshSessionHistory("documents");
    setStatus(inputPayload.selectedFile ? "Upload job queued" : "Text job queued");
  } catch (error) {
    if (error instanceof AuthRequiredError) {
      return;
    }
    setDocumentPolicyRejection(error.detail);
    jobSummary.textContent = error.message;
    renderJobPolicyNotice();
    renderJobHistory(appState.documentJobs);
    setAsyncState("documents", isPolicyRejection(error.detail) ? "blocked" : "error");
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
    const response = await apiFetch(`/api/jobs/${appState.currentDocumentJobId}`, {
      headers: buildAuthHeaders(null),
    });
    if (!response.ok) {
      throw await buildApiError(response, `Job status failed with status ${response.status}`);
    }
    const payload = await response.json();
    renderJobState(payload);
    if (payload.status === "succeeded" && payload.result_id) {
      appState.lastDocumentAnalysisId = payload.result_id;
      appState.selectedDocumentAnalysisId = payload.result_id;
      await refreshDocumentAnalyses();
    }
    await refreshDocumentJobs();
    setStatus("API ready");
  } catch (error) {
    if (error instanceof AuthRequiredError) {
      return;
    }
    setDocumentPolicyRejection(error.detail);
    jobSummary.textContent = error.message;
    renderJobPolicyNotice();
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
    const response = await apiFetch(`/api/jobs/${appState.currentDocumentJobId}/status`, {
      method: "POST",
      headers: buildAuthHeaders(null, true),
      body: JSON.stringify(requestBody),
    });
    if (!response.ok) {
      throw await buildApiError(response, `Job transition failed with status ${response.status}`);
    }

    const payload = await response.json();
    renderJobState(payload);
    await refreshSessionHistory("documents");
    if (payload.status === "succeeded" && payload.result_id) {
      appState.lastDocumentAnalysisId = payload.result_id;
      appState.selectedDocumentAnalysisId = payload.result_id;
      await refreshDocumentAnalyses();
    }
    await refreshDocumentJobs();
    setStatus("API ready");
  } catch (error) {
    if (error instanceof AuthRequiredError) {
      return;
    }
    setDocumentPolicyRejection(error.detail);
    jobSummary.textContent = error.message;
    renderJobPolicyNotice();
    setAsyncState("documents", isPolicyRejection(error.detail) ? "blocked" : "error");
    setStatus("API error", true);
  }
}

async function enterAuthenticatedShell() {
  if (!appState.shellInitialized) {
    setHistoryScope("latest");
    renderJobState(null);
    renderJobHistory([]);
    updateSessionRail();
    renderFeedbackControls();
    renderDocumentCapturePreview();
    appState.shellInitialized = true;
  }

  const routeTargetsAnalysis = /^\/document-analyses\/[^/]+\/view\/?$/.test(window.location.pathname);
  if (routeTargetsAnalysis) {
    await handleAnalysisRoute();
    return;
  }

  setActiveModule(appState.activeModule || "grocery");
}

Object.values(simulations).forEach((config) => {
  updateConfidenceOutput(config.confidenceInput, config.confidenceOutput);
  config.confidenceInput.addEventListener("input", () =>
    updateConfidenceOutput(config.confidenceInput, config.confidenceOutput),
  );
});

documentImageInput.addEventListener("change", renderDocumentCapturePreview);
authForm.addEventListener("submit", (event) => {
  event.preventDefault();
  loginWithCredentials(authUserIdInput.value.trim(), authPasswordInput.value);
});
authLogoutButton.addEventListener("click", logoutCurrentSession);

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
openLinkedAnalysisButton.addEventListener("click", () =>
  openDocumentAnalysis(jobAnalysisIdNode.textContent !== "none" ? jobAnalysisIdNode.textContent : null, {
    pushRoute: true,
  }),
);
refreshAnalysesButton.addEventListener("click", refreshDocumentAnalyses);
analysisSearchInput.addEventListener("input", () => renderAnalysisList(appState.documentAnalyses));
analysisSortSelect.addEventListener("change", () => renderAnalysisList(appState.documentAnalyses));
openAnalysisRouteButton.addEventListener("click", () => {
  const record = getSelectedDocumentAnalysis();
  if (record) {
    history.pushState({ analysisId: record.analysis_id }, "", getAnalysisViewPath(record.analysis_id));
  }
});
analysisFeedbackUsefulButton.addEventListener("click", () => submitDocumentAnalysisFeedback("useful"));
analysisFeedbackNotUsefulButton.addEventListener("click", () =>
  submitDocumentAnalysisFeedback("not_useful"),
);
feedbackUsefulButton.addEventListener("click", () => submitLensFeedback("useful"));
feedbackNotUsefulButton.addEventListener("click", () => submitLensFeedback("not_useful"));

window.addEventListener("popstate", () => {
  handleAnalysisRoute();
});

async function initializeApp() {
  renderAuthState();
  try {
    const hasSession = await loadAuthenticatedSession({ silent401: true });
    if (hasSession) {
      await enterAuthenticatedShell();
      setStatus("API ready");
    } else {
      setStatus("Sign in required");
    }
  } catch (error) {
    setStatus(error.message, true);
  }
}

initializeApp();

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/service-worker.js").catch(() => {
      setStatus("Service worker skipped", true);
    });
  });
}
