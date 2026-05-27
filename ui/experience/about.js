(function () {
  const tabs = Array.from(document.querySelectorAll("[data-about-tab]"));
  const panels = Array.from(document.querySelectorAll("[data-about-panel]"));

  function activate(tabId) {
    tabs.forEach((tab) => {
      const isActive = tab.getAttribute("data-about-tab") === tabId;
      tab.classList.toggle("is-active", isActive);
      tab.setAttribute("aria-selected", String(isActive));
    });

    panels.forEach((panel) => {
      const isActive = panel.getAttribute("data-about-panel") === tabId;
      panel.classList.toggle("is-active", isActive);
      panel.hidden = !isActive;
    });
  }

  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      const tabId = tab.getAttribute("data-about-tab");
      if (tabId) {
        activate(tabId);
        history.replaceState(null, "", `#${tabId}`);
      }
    });
  });

  const initial = String(window.location.hash || "").replace("#", "");
  if (initial && tabs.some((tab) => tab.getAttribute("data-about-tab") === initial)) {
    activate(initial);
  }
})();
