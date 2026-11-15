import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";

function FilterBar() {
  const [status, setStatus] = useState("open");
  const [severity, setSeverity] = useState<string | null>(null);
  return (
    <div>
      <div role="tablist" aria-label="Status">
        {["open", "resolved", "ignored"].map((value) => (
          <button key={value} role="tab" aria-selected={status === value} onClick={() => setStatus(value)}>
            {value}
          </button>
        ))}
      </div>
      <button onClick={() => setSeverity(severity === "high" ? null : "high")}>high</button>
      <p>
        Showing {status}
        {severity ? ` ${severity}` : ""}
      </p>
    </div>
  );
}

describe("filter bar", () => {
  it("changes status and severity", async () => {
    const user = userEvent.setup();
    render(<FilterBar />);
    await user.click(screen.getByRole("tab", { name: "resolved" }));
    expect(screen.getByText("Showing resolved")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "high" }));
    expect(screen.getByText("Showing resolved high")).toBeInTheDocument();
  });
});
