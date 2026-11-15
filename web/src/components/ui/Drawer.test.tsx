import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";
import { Drawer } from "./Drawer";

function Harness() {
  const [open, setOpen] = useState(true);
  return (
    <Drawer open={open} onOpenChange={setOpen} title="Exception detail">
      <p>Suggested fix is to import the other wallet.</p>
    </Drawer>
  );
}

describe("Drawer", () => {
  it("shows the title and closes", async () => {
    const user = userEvent.setup();
    render(<Harness />);
    expect(screen.getByText("Exception detail")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Close" }));
    expect(screen.queryByText("Exception detail")).not.toBeInTheDocument();
  });
});
