/**
 * Embedding on the author's website: the demo reports its height to the
 * parent page so the host can size the iframe. Messages go only to the
 * build-time allow-listed origins, never to "*", and nothing is sent when the
 * page is not framed.
 */

import { render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { EmbedHeight, embedOrigins, EMBED_MESSAGE_TYPE } from "@/components/EmbedHeight";

afterEach(() => {
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
});

describe("embed origins", () => {
  it("accepts only https origins, without paths", () => {
    vi.stubEnv("NEXT_PUBLIC_CCS_EMBED_ORIGINS",
      "https://imansgh.me, http://evil.example, https://ok.example/path, *, https://b.example");
    expect(embedOrigins()).toEqual(["https://imansgh.me", "https://b.example"]);
  });

  it("is empty when unset", () => {
    vi.stubEnv("NEXT_PUBLIC_CCS_EMBED_ORIGINS", "");
    expect(embedOrigins()).toEqual([]);
  });
});

describe("EmbedHeight", () => {
  it("posts the page height to each allowed parent origin when framed", () => {
    vi.stubEnv("NEXT_PUBLIC_CCS_EMBED_ORIGINS", "https://imansgh.me");
    const post = vi.fn();
    vi.spyOn(window, "parent", "get").mockReturnValue({ postMessage: post } as unknown as Window);
    render(<EmbedHeight />);
    expect(post).toHaveBeenCalled();
    const [message, target] = post.mock.calls[0];
    expect(target).toBe("https://imansgh.me");
    expect(message).toEqual({ type: EMBED_MESSAGE_TYPE, height: expect.any(Number) });
  });

  it("sends nothing when the page is not framed", () => {
    vi.stubEnv("NEXT_PUBLIC_CCS_EMBED_ORIGINS", "https://imansgh.me");
    const post = vi.spyOn(window, "postMessage");
    render(<EmbedHeight />);
    expect(post).not.toHaveBeenCalled();
  });
});
