(() => {
  const boot = window.QUOTE_EDITOR_DATA;
  const state = { draft: structuredClone(boot.draft), timer: null };
  const byId = (id) => document.getElementById(id);
  const coverageList = byId("coverage-list");
  const planList = byId("plan-list");
  const presetByCode = Object.fromEntries(boot.presets.map((item) => [item.code, item]));
  const coverageNames = {
    bodily_injury: "人身傷害責任險", property_damage: "財產損害責任險",
    uninsured_motorist: "未投保／保額不足駕駛人", collision_deductible: "碰撞險自付額",
    comprehensive_deductible: "綜合險自付額", medical_payments: "醫療費用保障",
    rental_reimbursement: "租車費用補償", roadside_assistance: "道路救援",
    glass_coverage: "玻璃保障", gap_coverage: "貸款差額保障"
  };
  const planNames = { auto_only: "Auto Only", auto_renters: "Auto + Renters", alternative: "Alternative" };

  function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>'"]/g, (char) => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[char]));
  }

  function renderCoverages() {
    coverageList.innerHTML = state.draft.coverages.map((item, index) => {
      const preset = presetByCode[item.code] || { values: [] };
      const custom = item.value && !preset.values.includes(item.value);
      const options = preset.values.map((value) => `<option value="${escapeHtml(value)}"${!custom && item.value === value ? " selected" : ""}>${escapeHtml(value)}</option>`).join("");
      return `<div class="dynamic-card" data-coverage-index="${index}"><div class="dynamic-card-grid">
        <label>Coverage<select class="coverage-code">${boot.presets.map((p) => `<option value="${p.code}"${p.code === item.code ? " selected" : ""}>${escapeHtml(coverageNames[p.code] || p.code)}</option>`).join("")}</select></label>
        <label>額度／自付額<select class="coverage-value-select">${options}<option value="__custom__"${custom ? " selected" : ""}>Custom 自訂</option></select><input class="custom-value" value="${custom ? escapeHtml(item.value) : ""}" placeholder="輸入自訂值"${custom ? "" : " hidden"}></label>
        <button class="icon-button remove-coverage" type="button" aria-label="刪除">×</button>
      </div></div>`;
    }).join("");
  }

  function renderPlans() {
    planList.innerHTML = state.draft.plans.map((item, index) => `<div class="dynamic-card" data-plan-index="${index}"><div class="dynamic-card-grid plan-card-grid">
      <label>方案<select class="plan-code">${Object.entries(planNames).map(([code, name]) => `<option value="${code}"${code === item.plan_code ? " selected" : ""}>${name}</option>`).join("")}</select></label>
      <label>總保費<input class="plan-premium" type="number" min="0" step="0.01" value="${item.premium_total ?? ""}" placeholder="0.00"></label>
      <label>保費期間<select class="plan-period"><option value="6_month_policy"${item.premium_period === "6_month_policy" ? " selected" : ""}>6 個月保單</option><option value="annual_policy"${item.premium_period === "annual_policy" ? " selected" : ""}>年度保單</option></select></label>
      <div class="visibility-row"><label><input class="plan-recommended" type="checkbox"${item.recommended ? " checked" : ""}>推薦</label></div>
      <button class="icon-button remove-plan" type="button" aria-label="刪除">×</button>
    </div></div>`).join("");
  }

  function populateStaticFields() {
    byId("locale").value = state.draft.locale;
    byId("customer-name").value = state.draft.customer.name;
    byId("carrier").value = state.draft.policy.carrier;
    byId("quote-date").value = state.draft.policy.quote_date;
    byId("expiration-date").value = state.draft.policy.expiration_date;
    byId("term-months").value = state.draft.policy.term_months;
    byId("vehicle-summary").value = state.draft.policy.vehicle_summary;
    byId("vehicle-count").value = state.draft.policy.vehicle_count;
    byId("driver-count").value = state.draft.policy.driver_count;
    byId("garaging-zip").value = state.draft.policy.garaging_zip || "";
    byId("customer-note").value = state.draft.customer_facing_note || "";
    byId("internal-note").value = state.draft.internal_note || "";
  }

  function collectDraft() {
    const coverages = [...coverageList.querySelectorAll("[data-coverage-index]")].map((row, index) => {
      const selected = row.querySelector(".coverage-value-select").value;
      return {
        code: row.querySelector(".coverage-code").value,
        value: selected === "__custom__" ? row.querySelector(".custom-value").value.trim() : selected,
        sort_order: (index + 1) * 10,
        custom_label: null, custom_description: null
      };
    });
    const plans = [...planList.querySelectorAll("[data-plan-index]")].map((row, index) => ({
      plan_code: row.querySelector(".plan-code").value,
      premium_total: row.querySelector(".plan-premium").value || null,
      premium_period: row.querySelector(".plan-period").value,
      recommended: row.querySelector(".plan-recommended").checked,
      short_note: "", sort_order: (index + 1) * 10, display_name: null
    }));
    state.draft = {
      ...state.draft,
      locale: byId("locale").value,
      customer: { name: byId("customer-name").value.trim() },
      policy: {
        carrier: byId("carrier").value.trim(), term_months: Number(byId("term-months").value),
        quote_date: byId("quote-date").value, expiration_date: byId("expiration-date").value,
        vehicle_summary: byId("vehicle-summary").value.trim(), vehicle_count: Number(byId("vehicle-count").value || 0),
        driver_count: Number(byId("driver-count").value || 0), garaging_zip: byId("garaging-zip").value.trim()
      },
      coverages, plans,
      customer_facing_note: byId("customer-note").value.trim(), internal_note: byId("internal-note").value.trim()
    };
    return state.draft;
  }

  function setDirty() {
    const status = byId("save-status");
    status.textContent = "尚未儲存"; status.classList.add("dirty");
    clearTimeout(state.timer); state.timer = setTimeout(updatePreview, 450);
  }

  async function api(path, options = {}) {
    const response = await fetch(path, { headers: { "Content-Type": "application/json", ...(options.headers || {}) }, ...options });
    const type = response.headers.get("content-type") || "";
    const body = type.includes("application/json") ? await response.json() : await response.text();
    if (!response.ok) { const error = new Error(body.message || body.detail || "Request failed"); error.response = response; error.body = body; throw error; }
    return body;
  }

  async function saveDraft() {
    const button = byId("save-button"); button.disabled = true;
    try {
      await api(`/api/quotes/${boot.quoteId}`, { method: "PUT", body: JSON.stringify(collectDraft()) });
      const status = byId("save-status"); status.textContent = "已儲存"; status.classList.remove("dirty");
    } catch (error) { showValidation({ errors: [{ message: `無法儲存：${error.message}` }], warnings: [] }); }
    finally { button.disabled = false; }
  }

  async function updatePreview() {
    collectDraft();
    const loading = byId("preview-empty");
    const frame = byId("preview-frame");
    loading.textContent = "正在建立預覽…";
    loading.hidden = false;
    try {
      const html = await api(`/api/quotes/${boot.quoteId}/preview?output_type=mobile_png`, { method: "POST", body: JSON.stringify(state.draft) });
      frame.onload = () => {
        requestAnimationFrame(() => {
          fitPreviewFrame();
          loading.hidden = true;
        });
      };
      frame.srcdoc = html;
    } catch (error) { loading.textContent = "請完成必要日期與數字欄位後再預覽。"; }
    const labels = {"zh-TW":"繁體中文","zh-CN":"简体中文","en-US":"English"};
    byId("preview-locale").textContent = labels[state.draft.locale];
  }

  function fitPreviewFrame() {
    const frame = byId("preview-frame");
    const wrapper = byId("preview-frame-wrap");
    const stage = byId("preview-stage");
    const documentRoot = frame.contentDocument?.documentElement;
    const documentBody = frame.contentDocument?.body;
    if (!documentRoot || !documentBody || !wrapper.clientWidth) return;
    const baseWidth = 720;
    const contentHeight = Math.max(documentRoot.scrollHeight, documentBody.scrollHeight, 900);
    const scale = wrapper.clientWidth / baseWidth;
    frame.style.width = `${baseWidth}px`;
    frame.style.height = `${contentHeight}px`;
    frame.style.transform = `scale(${scale})`;
    stage.style.height = `${Math.ceil(contentHeight * scale)}px`;
  }

  function showValidation(result) {
    const box = byId("validation-summary");
    const issues = [...(result.errors || []), ...(result.warnings || [])];
    if (!issues.length) { box.hidden = true; return; }
    box.hidden = false; box.classList.toggle("warning-only", !(result.errors || []).length);
    box.innerHTML = `<strong>${result.errors?.length ? "請修正以下問題" : "請確認以下提醒"}</strong><ul>${issues.map((item) => `<li>${escapeHtml(item.message)}</li>`).join("")}</ul>`;
    box.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  async function generate(acknowledgeWarnings = false) {
    const button = byId("generate-button"); button.disabled = true; button.textContent = "產出中…";
    try {
      const body = await api(`/api/quotes/${boot.quoteId}/generate`, { method: "POST", body: JSON.stringify({ draft: collectDraft(), acknowledge_warnings: acknowledgeWarnings, change_note: "" }) });
      window.location.href = body.detail_url;
    } catch (error) {
      if (error.response?.status === 409) {
        showValidation(error.body);
        if (window.confirm("系統偵測到提醒。確認內容後仍要建立正式版本嗎？")) await generate(true);
      } else if (error.body?.errors) showValidation(error.body);
      else showValidation({ errors: [{ message: error.message }], warnings: [] });
    } finally { button.disabled = false; button.textContent = "檢查並產出"; }
  }

  coverageList.addEventListener("change", (event) => {
    const row = event.target.closest("[data-coverage-index]");
    if (event.target.classList.contains("coverage-code")) {
      collectDraft(); const item = state.draft.coverages[Number(row.dataset.coverageIndex)];
      item.code = event.target.value; item.value = presetByCode[item.code].values[0] || ""; renderCoverages();
    } else if (event.target.classList.contains("coverage-value-select")) {
      row.querySelector(".custom-value").hidden = event.target.value !== "__custom__";
    }
    setDirty();
  });
  coverageList.addEventListener("click", (event) => { if (event.target.classList.contains("remove-coverage")) { collectDraft(); state.draft.coverages.splice(Number(event.target.closest("[data-coverage-index]").dataset.coverageIndex), 1); renderCoverages(); setDirty(); } });
  planList.addEventListener("click", (event) => { if (event.target.classList.contains("remove-plan")) { collectDraft(); state.draft.plans.splice(Number(event.target.closest("[data-plan-index]").dataset.planIndex), 1); renderPlans(); setDirty(); } });
  byId("add-coverage").addEventListener("click", () => { collectDraft(); const unused = boot.presets.find((p) => !state.draft.coverages.some((c) => c.code === p.code)) || boot.presets[0]; state.draft.coverages.push({ code: unused.code, value: unused.values[0], sort_order: 999 }); renderCoverages(); setDirty(); });
  byId("add-plan").addEventListener("click", () => { collectDraft(); if (state.draft.plans.length >= 3) return alert("第一版最多支援 3 個方案。"); state.draft.plans.push({ plan_code: "alternative", premium_total: null, premium_period: "6_month_policy", recommended: false, short_note: "", sort_order: 999 }); renderPlans(); setDirty(); });
  byId("save-button").addEventListener("click", saveDraft);
  byId("generate-button").addEventListener("click", () => generate(false));
  document.querySelector(".form-column").addEventListener("input", setDirty);
  document.querySelector(".form-column").addEventListener("change", setDirty);
  byId("locale").addEventListener("change", setDirty);
  window.addEventListener("resize", fitPreviewFrame);
  populateStaticFields(); renderCoverages(); renderPlans(); updatePreview();
})();
