import { useRef } from "react";

export function FileDropzone({ onFiles, onText }: { onFiles: (files: File[]) => void; onText?: (text: string) => void }) {
  const input = useRef<HTMLInputElement>(null);
  return (
    <div
      className="rounded-lg border border-dashed border-line p-8 text-center"
      onDragOver={(event) => event.preventDefault()}
      onDrop={(event) => {
        event.preventDefault();
        onFiles(Array.from(event.dataTransfer.files));
      }}
    >
      <p>Drop CSV or JSON files, or paste a CSV.</p>
      <div className="mt-3 flex flex-wrap justify-center gap-2">
        <button className="min-h-11 rounded-md bg-accent px-4 text-accent-ink" type="button" onClick={() => input.current?.click()}>
          Choose files
        </button>
      </div>
      <input ref={input} className="sr-only" type="file" multiple accept=".csv,.json,.txt,text/csv,application/json" onChange={(event) => onFiles(Array.from(event.target.files ?? []))} />
      {onText ? (
        <textarea
          aria-label="Paste CSV text"
          className="mt-4 w-full rounded-md border border-line bg-bg p-2 text-sm"
          rows={4}
          placeholder="Or paste CSV text here"
          onBlur={(event) => {
            if (event.target.value.trim()) onText(event.target.value);
          }}
        />
      ) : null}
      <p className="mt-3 text-xs text-muted">Public addresses and CSV files only.</p>
    </div>
  );
}

export function SearchInput({ value, onChange, label = "Search" }: { value: string; onChange: (value: string) => void; label?: string }) {
  return (
    <label className="block text-sm">
      <span className="text-muted">{label}</span>
      <input className="mt-1 min-h-11 w-full rounded-md border border-line bg-bg px-3" value={value} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}

export function CopyButton({ text }: { text: string }) {
  return (
    <button className="min-h-11 rounded-md border border-line px-3 text-sm" type="button" onClick={() => void navigator.clipboard.writeText(text)}>
      Copy
    </button>
  );
}

export function Kbd({ children }: { children: string }) {
  return <kbd className="rounded border border-line px-1.5 py-0.5 font-mono text-xs">{children}</kbd>;
}
