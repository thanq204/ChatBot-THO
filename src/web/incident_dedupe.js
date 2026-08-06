(() => {
  const list = document.querySelector("#incidents");
  if (!list) return;
  let running = false;
  function dedupe() {
    if (running) return;
    running = true;
    const seen = new Set();
    list.querySelectorAll(".incident-row").forEach(row => {
      const title = row.querySelector("strong")?.textContent?.trim() || "";
      const summary = row.querySelector("p")?.textContent?.trim() || "";
      const pills = [...row.querySelectorAll(".pill")].map(item => item.textContent.trim());
      const key = `${pills[1] || ""}|${title}|${summary}`;
      if (seen.has(key)) row.remove(); else seen.add(key);
    });
    running = false;
  }
  new MutationObserver(dedupe).observe(list, {childList: true});
  dedupe();
})();
