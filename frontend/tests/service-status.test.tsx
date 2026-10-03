/**
 * The page probes /ready on load. A hosted demo may be asleep (free hosting
 * suspends idle services), so a slow answer is explained instead of leaving
 * the first calculation hanging silently, and an unreachable service says so.
 */

import { act, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ServiceStatus } from "@/components/ServiceStatus";

beforeEach(() => vi.useFakeTimers({ shouldAdvanceTime: true }));
afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

const ready = () => new Response(JSON.stringify({ status: "ready" }), { status: 200 });

describe("ServiceStatus", () => {
  it("shows nothing when the service answers promptly", async () => {
    const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValue(ready());
    const { container } = render(<ServiceStatus />);
    await waitFor(() => expect(fetch).toHaveBeenCalled());
    expect(String(fetch.mock.calls[0][0])).toMatch(/\/ready$/);
    await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
    expect(container).toBeEmptyDOMElement();
  });

  it("explains a slow start, then clears once the service is ready", async () => {
    let answer!: (r: Response) => void;
    vi.spyOn(globalThis, "fetch").mockReturnValue(new Promise((r) => (answer = r)));
    render(<ServiceStatus />);
    await act(async () => { await vi.advanceTimersByTimeAsync(3500); });
    expect(screen.getByRole("status")).toHaveTextContent(/starting up.*up to a minute/i);
    await act(async () => { answer(ready()); });
    await waitFor(() => expect(screen.queryByRole("status")).not.toBeInTheDocument());
  });

  it("says when the service cannot be reached", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("Failed to fetch"));
    render(<ServiceStatus />);
    expect(await screen.findByRole("alert")).toHaveTextContent(/not reachable/i);
  });
});
