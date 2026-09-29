import { Search } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { searchEntities } from "../../river/api";
import { fmtAmount, fmtPct, signClass } from "../../river/format";
import type { EntityHit } from "../../river/types";

interface EntityPickerProps {
  value: EntityHit | null;
  asOf: string | null;
  hot: EntityHit[];
  onChange: (entity: EntityHit) => void;
}

/** 板块 / 题材实体选择：精确 + 前缀 + 包含，服务端按成交额排序。 */
export function EntityPicker({ value, asOf, hot, onChange }: EntityPickerProps) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<EntityHit[]>([]);
  const [loading, setLoading] = useState(false);
  const boxRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;
    const q = query.trim();
    if (!q) {
      setItems(hot);
      return;
    }
    let cancelled = false;
    setLoading(true);
    const timer = window.setTimeout(() => {
      searchEntities(q, asOf)
        .then((res) => {
          if (!cancelled) setItems(res.items);
        })
        .catch(() => {
          if (!cancelled) setItems([]);
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
    }, 160);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [query, open, asOf, hot]);

  useEffect(() => {
    if (!open) return;
    const onDoc = (event: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  return (
    <div className="river-entity" ref={boxRef}>
      <label className="river-entity-input">
        <Search aria-hidden="true" size={15} />
        <input
          type="search"
          role="combobox"
          aria-expanded={open}
          aria-label="选择板块或题材"
          placeholder={value ? `${value.name} · ${value.id}` : "输入板块 / 题材名或代码"}
          value={query}
          onFocus={() => setOpen(true)}
          onChange={(event) => {
            setQuery(event.target.value);
            setOpen(true);
          }}
          onKeyDown={(event) => {
            if (event.key === "Enter" && items[0]) {
              onChange(items[0]);
              setQuery("");
              setOpen(false);
            }
            if (event.key === "Escape") setOpen(false);
          }}
        />
      </label>
      {open && (
        <div className="river-entity-menu" role="listbox">
          <div className="river-entity-menu-head">
            {query.trim() ? (loading ? "检索中…" : `匹配 ${items.length} 个（精确匹配优先）`) : "当日成交额靠前的板块"}
          </div>
          {items.length === 0 && !loading && (
            <div className="river-entity-empty">没有精确或包含匹配的板块。长河只做精确解析，不做同义词猜测。</div>
          )}
          {items.map((item) => (
            <button
              type="button"
              role="option"
              aria-selected={value?.id === item.id}
              key={item.id}
              className={value?.id === item.id ? "active" : ""}
              onClick={() => {
                onChange(item);
                setQuery("");
                setOpen(false);
              }}
            >
              <strong>{item.name}</strong>
              <code>{item.id}</code>
              <span className={`river-sign ${signClass(item.pct_chg)}`}>{fmtPct(item.pct_chg)}</span>
              <small>{fmtAmount(item.amount)}</small>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
