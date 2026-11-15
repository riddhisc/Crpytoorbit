import { useUi } from "@/stores/ui";

export function Toasts() {
  const toasts = useUi((state) => state.toasts);
  const dismiss = useUi((state) => state.dismissToast);
  return (
    <div aria-live="polite" className="fixed bottom-20 right-4 z-50 flex w-[min(360px,calc(100%-32px))] flex-col gap-2 md:bottom-4">
      {toasts.map((toast) => (
        <div key={toast.id} className="rounded-lg border border-line bg-raised p-3 shadow-soft">
          <p className="text-sm">{toast.message}</p>
          {toast.undo ? (
            <button
              className="mt-2 min-h-11 text-sm text-accent"
              onClick={() => {
                toast.undo?.();
                dismiss(toast.id);
              }}
            >
              Undo
            </button>
          ) : null}
        </div>
      ))}
    </div>
  );
}
