import { beforeEach, describe, expect, it } from "vitest";

import { ApiClient } from "./client";

describe("ApiClient", () => {
  beforeEach(() => localStorage.clear());

  it("url() joins the base URL and path", () => {
    const api = new ApiClient("http://api.test");
    expect(api.url("/projects/1/model.frag")).toBe("http://api.test/projects/1/model.frag");
  });

  it("starts unauthenticated with no stored token", () => {
    const api = new ApiClient("http://api.test");
    expect(api.authed).toBe(false);
    expect(api.authHeaders()).toEqual({});
  });

  it("setToken() authenticates, persists, and sets the bearer header", () => {
    const api = new ApiClient("http://api.test");
    api.setToken("tok123");
    expect(api.authed).toBe(true);
    expect(api.authHeaders()).toEqual({ Authorization: "Bearer tok123" });
    expect(localStorage.getItem("aec-token")).toBe("tok123");
  });

  it("setToken('') clears the token and storage", () => {
    const api = new ApiClient("http://api.test");
    api.setToken("tok123");
    api.setToken("");
    expect(api.authed).toBe(false);
    expect(api.authHeaders()).toEqual({});
    expect(localStorage.getItem("aec-token")).toBeNull();
  });

  it("restores a persisted token from localStorage on construction", () => {
    localStorage.setItem("aec-token", "persisted");
    const api = new ApiClient("http://api.test");
    expect(api.authed).toBe(true);
    expect(api.authHeaders()).toEqual({ Authorization: "Bearer persisted" });
  });
});
