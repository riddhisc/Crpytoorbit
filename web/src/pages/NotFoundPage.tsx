import { Link } from "react-router-dom";
import { AppShell } from "@/components/shell/AppShell";

export function NotFoundPage() {
  return (
    <AppShell title="Not found">
      <p>That page is not on the desk.</p>
      <Link className="mt-3 inline-flex min-h-11 items-center underline" to="/">Back to Overview</Link>
    </AppShell>
  );
}
