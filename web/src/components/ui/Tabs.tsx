import { useRef, type KeyboardEvent } from "react";

import { tabId, tabPanelId } from "./tab-ids";

export interface TabItem {
  id: string;
  label: string;
  count?: number;
}

export function Tabs({
  items,
  active,
  onChange,
  idBase,
  ariaLabel,
}: {
  items: TabItem[];
  active: string;
  onChange: (id: string) => void;
  idBase: string;
  ariaLabel: string;
}) {
  const listRef = useRef<HTMLDivElement>(null);

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const index = items.findIndex((item) => item.id === active);
    if (index < 0) return;
    let next: number;
    if (event.key === "ArrowRight") next = (index + 1) % items.length;
    else if (event.key === "ArrowLeft") next = (index - 1 + items.length) % items.length;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = items.length - 1;
    else return;
    event.preventDefault();
    const target = items[next];
    if (!target) return;
    onChange(target.id);
    listRef.current?.querySelector<HTMLButtonElement>(`#${tabId(idBase, target.id)}`)?.focus();
  }

  return (
    <div ref={listRef} className="tabs" role="tablist" aria-label={ariaLabel} onKeyDown={onKeyDown}>
      {items.map((item) => {
        const selected = active === item.id;
        return (
          <button
            key={item.id}
            id={tabId(idBase, item.id)}
            type="button"
            role="tab"
            aria-selected={selected}
            aria-controls={tabPanelId(idBase, item.id)}
            tabIndex={selected ? 0 : -1}
            className={selected ? "tab tab--active" : "tab"}
            onClick={() => onChange(item.id)}
          >
            {item.label}
            {item.count !== undefined ? <span className="tab__count">{item.count}</span> : null}
          </button>
        );
      })}
    </div>
  );
}
