import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import { AppShell } from "@/components/shell/AppShell";
import { Modal } from "@/components/ui/Drawer";
import { useUi } from "@/stores/ui";

export function SettingsPage() {
  const webhook = useQuery({ queryKey: ["webhook"], queryFn: () => api.webhook() });
  const summary = useQuery({ queryKey: ["summary"], queryFn: ({ signal }) => api.summary(signal) });
  const [url, setUrl] = useState("");
  const [secret, setSecret] = useState("");
  const [confirm, setConfirm] = useState(false);
  const [typed, setTyped] = useState("");
  const [message, setMessage] = useState("");
  const theme = useUi((state) => state.theme);
  const toggle = useUi((state) => state.toggleTheme);
  const client = useQueryClient();
  return (
    <AppShell title="Settings">
      {summary.data?.demo_mode ? <p className="mb-4 rounded-lg border border-line p-3 text-sm">DEMO_MODE is on, so the desk accepts writes without an API key and can be reset. Turn it off before sharing the deployment.</p> : null}
      <section className="max-w-xl space-y-3">
        <label className="block text-sm">Webhook URL
          <input className="mt-1 min-h-11 w-full rounded-md border border-line bg-bg px-3" defaultValue={webhook.data?.url} onChange={(event) => setUrl(event.target.value)} />
        </label>
        <label className="block text-sm">Signing secret
          <input className="mt-1 min-h-11 w-full rounded-md border border-line bg-bg px-3" defaultValue={webhook.data?.secret} onChange={(event) => setSecret(event.target.value)} />
        </label>
        <div className="flex flex-wrap gap-2">
          <button className="min-h-11 rounded-md bg-accent px-3 text-accent-ink" onClick={() => void api.saveWebhook({ url: url || webhook.data?.url || "", secret: secret || webhook.data?.secret || "", enabled: true }).then(() => setMessage("Webhook saved."))}>Save webhook</button>
          <button className="min-h-11 rounded-md border border-line px-3" onClick={() => void api.testWebhook().then((result) => setMessage(`Test ${result.status}${result.last_error ? `: ${result.last_error}` : ""}`)).catch((error: Error) => setMessage(error.message))}>Send test event</button>
          <button className="min-h-11 rounded-md border border-line px-3" onClick={toggle}>Theme: {theme}</button>
        </div>
        {message ? <p className="text-sm">{message}</p> : null}
        <button className="min-h-11 rounded-md border border-danger px-3 text-danger" onClick={() => setConfirm(true)}>Reset data</button>
      </section>
      <Modal open={confirm} onOpenChange={setConfirm} title="Reset the desk">
        <p className="text-sm">Type RESET to erase imports, the ledger, and exceptions.</p>
        <input className="mt-2 min-h-11 w-full rounded-md border border-line bg-bg px-3" value={typed} onChange={(event) => setTyped(event.target.value)} />
        <button className="mt-3 min-h-11 rounded-md bg-danger px-3 text-bg" disabled={typed !== "RESET"} onClick={() => void api.reset().then(() => { setConfirm(false); void client.invalidateQueries(); })}>Erase</button>
      </Modal>
    </AppShell>
  );
}
