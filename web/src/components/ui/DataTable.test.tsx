import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { DataTable } from "./DataTable";

describe("DataTable", () => {
  it("renders rows and calls the row handler", async () => {
    const user = userEvent.setup();
    const rows = [{ id: "1", asset: "BTC" }];
    let opened = "";
    render(
      <DataTable
        rows={rows}
        onRow={(row) => {
          opened = row.id;
        }}
        columns={[{ key: "asset", header: "Asset", render: (row) => row.asset }]}
      />,
    );
    expect(screen.getAllByText("BTC").length).toBeGreaterThan(0);
    await user.click(screen.getAllByText("BTC")[0]);
    expect(opened).toBe("1");
  });
});
