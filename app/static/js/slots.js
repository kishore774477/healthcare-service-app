// Loads available time slots for the chosen provider + date (booking and rescheduling pages).
(function () {
  const form = document.querySelector("[data-slot-form]");
  if (!form) return;

  const providerSelect = form.querySelector("[data-provider-select]");
  const dateInput = form.querySelector("[data-date-input]");
  const slotSelect = form.querySelector("[data-slot-select]");
  const message = form.querySelector("[data-slot-message]");
  const baseUrl = form.dataset.slotsUrl; // ends with /providers/<id>/slots
  const exclude = form.dataset.exclude;

  function slotsUrl(providerId) {
    const url = providerSelect ? baseUrl.replace(/\/providers\/\d+\/slots$/, `/providers/${providerId}/slots`) : baseUrl;
    const params = new URLSearchParams({ date: dateInput.value });
    if (exclude) params.set("exclude", exclude);
    return `${url}?${params}`;
  }

  function setOptions(slots, placeholder) {
    const previous = slotSelect.value;
    slotSelect.innerHTML = "";
    const first = document.createElement("option");
    first.value = "";
    first.textContent = placeholder;
    slotSelect.appendChild(first);
    for (const s of slots) {
      const opt = document.createElement("option");
      opt.value = s.value;
      opt.textContent = s.label;
      if (s.value === previous) opt.selected = true;
      slotSelect.appendChild(opt);
    }
    slotSelect.disabled = slots.length === 0;
  }

  async function refresh() {
    const providerId = providerSelect ? providerSelect.value : "x";
    if ((providerSelect && (!providerId || providerId === "0")) || !dateInput.value) {
      setOptions([], "Select a provider and date first");
      message.textContent = "";
      return;
    }
    message.textContent = "Checking availability…";
    try {
      const res = await fetch(slotsUrl(providerId), { headers: { Accept: "application/json" } });
      const data = await res.json();
      const slots = data.slots || [];
      setOptions(slots, slots.length ? "Select a time slot" : "No slots available");
      message.textContent = slots.length ? `${slots.length} slot(s) available` : (data.message || data.error || "No slots available");
      message.className = "form-text " + (slots.length ? "text-success" : "text-danger");
    } catch (err) {
      message.textContent = "Could not load slots. Please try again.";
      message.className = "form-text text-danger";
    }
  }

  if (providerSelect) providerSelect.addEventListener("change", refresh);
  dateInput.addEventListener("change", refresh);
  refresh();
})();
