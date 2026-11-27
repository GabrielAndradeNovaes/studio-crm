import * as React from "react";

export interface AccessibleTabItem {
  id: string;
  label: string;
  content: React.ReactNode;
}

interface AccessibleTabsProps {
  ariaLabel: string;
  tabs: AccessibleTabItem[];
  activeTabId: string;
  onTabChange: (nextId: string) => void;
}

/**
 * Painéis em abas no mesmo documento (nunca para navegação de URLs).
 * Mantém abas em linha única rolável, indicador por sublinhado pseudo-elemento
 * vinculado a `aria-selected="true"` e estilização interna nos `tabpanel`s.
 */
export function AccessibleTabs({
  ariaLabel,
  tabs,
  activeTabId,
  onTabChange,
}: AccessibleTabsProps) {
  const baseId = React.useId();
  const tablistRef = React.useRef<HTMLDivElement | null>(null);
  const tabRefs = React.useRef<Record<string, HTMLButtonElement | null>>({});

  // Configura atributos progressivos `focusgroup` e sincroniza scroll da aba ativa
  React.useEffect(() => {
    const listEl = tablistRef.current;
    if (listEl) {
      listEl.setAttribute("focusgroup", "tablist nomemory");
    }
    for (const tab of tabs) {
      const btn = tabRefs.current[tab.id];
      if (!btn) continue;
      const selected = tab.id === activeTabId;
      btn.toggleAttribute("focusgroupstart", selected);
      if (selected) {
        btn.scrollIntoView({
          block: "nearest",
          inline: "nearest",
        });
      }
    }
  }, [activeTabId, tabs]);

  // Fallback `IntersectionObserver` para dicas visuais de borda caso `animation-timeline: scroll()` não exista
  React.useEffect(() => {
    const scroller = tablistRef.current;
    if (!scroller) return;
    if (
      typeof CSS !== "undefined" &&
      typeof CSS.supports === "function" &&
      CSS.supports("animation-timeline", "scroll()")
    ) {
      return;
    }
    const first = scroller.firstElementChild;
    const last = scroller.lastElementChild;
    if (!first || !last) return;

    const observer = new IntersectionObserver(
      (entries) => {
        for (const { target, intersectionRatio } of entries) {
          scroller.classList.toggle(
            target === first ? "more-start" : "more-end",
            intersectionRatio < 1
          );
        }
      },
      { root: scroller, threshold: 1, rootMargin: "1px" }
    );

    observer.observe(first);
    observer.observe(last);
    return () => observer.disconnect();
  }, [tabs.length]);

  const handleKeyDown = (
    e: React.KeyboardEvent<HTMLButtonElement>,
    currentIndex: number
  ) => {
    // Caso o navegador já trate `focusGroup` nativamente, evita duplicidade
    if (Object.hasOwn(HTMLElement.prototype, "focusGroup")) {
      return;
    }
    let nextIndex = -1;
    if (e.key === "ArrowRight") {
      nextIndex = (currentIndex + 1) % tabs.length;
    } else if (e.key === "ArrowLeft") {
      nextIndex = (currentIndex - 1 + tabs.length) % tabs.length;
    } else if (e.key === "Home") {
      nextIndex = 0;
    } else if (e.key === "End") {
      nextIndex = tabs.length - 1;
    }
    if (nextIndex >= 0) {
      e.preventDefault();
      const targetTab = tabs[nextIndex];
      onTabChange(targetTab.id);
      tabRefs.current[targetTab.id]?.focus();
    }
  };

  return (
    <div>
      <div
        ref={tablistRef}
        role="tablist"
        aria-label={ariaLabel}
        className="mwg-tablist gap-1"
      >
        {tabs.map((tab, index) => {
          const domTabId = `${baseId}-tab-${tab.id}`;
          const isSelected = tab.id === activeTabId;
          return (
            <button
              key={tab.id}
              ref={(el) => {
                tabRefs.current[tab.id] = el;
              }}
              type="button"
              role="tab"
              id={domTabId}
              aria-selected={isSelected}
              tabIndex={isSelected ? 0 : -1}
              onClick={() => onTabChange(tab.id)}
              onKeyDown={(e) => handleKeyDown(e, index)}
              className="min-h-[46px] px-4 py-2.5 text-sm font-semibold transition-colors hover:text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              {tab.label}
            </button>
          );
        })}
      </div>

      {tabs.map((tab) => {
        const domTabId = `${baseId}-tab-${tab.id}`;
        const isSelected = tab.id === activeTabId;
        return (
          <div
            key={tab.id}
            role="tabpanel"
            aria-labelledby={domTabId}
            hidden={!isSelected}
          >
            <div className="pt-5">{tab.content}</div>
          </div>
        );
      })}
    </div>
  );
}
