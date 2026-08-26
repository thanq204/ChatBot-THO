import { useEffect, useRef } from "react";

const MOVE_KEYS = ["ArrowLeft", "ArrowRight", "Home", "End"];

/**
 * Which tab a movement key lands on. Pure and exported so the wrap-around
 * arithmetic — the part with somewhere to hide an off-by-one — can be checked
 * without a DOM.
 */
export function nextTabIndex(key, current, count) {
  if (count === 0) return -1;
  if (key === "Home") return 0;
  if (key === "End") return count - 1;
  if (key === "ArrowRight") return (current + 1) % count;
  if (key === "ArrowLeft") return (current - 1 + count) % count;
  return current;
}

/**
 * Makes a `role="tablist"` behave the way the role promises.
 *
 * Declaring role="tab" tells assistive tech this is a tab strip, and the ARIA
 * pattern for one is specific: the whole strip is a single tab stop, and the
 * arrow keys move between tabs. Ours had the roles but neither behaviour — a
 * screen reader announced "tab, 1 of 2", the user pressed an arrow by reflex,
 * and nothing happened.
 *
 * Everything is driven off the DOM inside the container rather than a list of
 * tabs passed in, so a call site only has to spread the result onto its
 * container — no per-button changes, and a tablist whose tabs are generated
 * from data (bot commands) works without extra wiring.
 */
export function useTablist() {
  const ref = useRef(null);

  const tabsIn = () => [
    ...(ref.current?.querySelectorAll('[role="tab"]:not([disabled])') ?? []),
  ];

  // Roving tabindex, re-applied every render because it has to track whichever
  // tab is currently selected. No dependency array on purpose.
  useEffect(() => {
    const tabs = tabsIn();
    if (tabs.length === 0) return;
    const selected = tabs.findIndex((tab) => tab.getAttribute("aria-selected") === "true");
    // With nothing selected, every tab would get -1 and the strip would drop
    // out of the tab order entirely. Fall back to making the first one the
    // entry point.
    const entry = selected === -1 ? 0 : selected;
    tabs.forEach((tab, index) => { tab.tabIndex = index === entry ? 0 : -1; });
  });

  const onKeyDown = (event) => {
    if (!MOVE_KEYS.includes(event.key)) return;
    const tabs = tabsIn();
    const current = tabs.indexOf(document.activeElement);
    // Ignore keys pressed on something else inside the container — a tablist
    // may sit next to buttons that are not tabs.
    if (current === -1) return;

    event.preventDefault();
    const next = nextTabIndex(event.key, current, tabs.length);

    // Automatic activation: focus and select together. The ARIA pattern's
    // default, and right here because switching tabs is instant — nothing is
    // fetched, so there is no cost to landing on one.
    tabs[next].focus();
    tabs[next].click();
  };

  return { ref, onKeyDown };
}
