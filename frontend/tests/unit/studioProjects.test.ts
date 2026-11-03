import { describe, expect, it } from "vitest";
import { groupProjects, projectId } from "../../src/screens/studioProjects";
import type { StudioVersion } from "../../src/screens/StudioCanvas";

const version = (id: string, parentId: string | null): StudioVersion => ({ id, parentId, imageUrl: "/image", instruction: id, direction: "", createdAt: "", mode: "mock" });

describe("studio idea grouping", () => {
  it("keeps branches with their concept and separates unrelated ideas", () => {
    const all = [version("a", null), version("b", null), version("a1", "a"), version("a2", "a1"), version("b1", "b")];
    expect(groupProjects(all).map((group) => [group.id, group.versions.map((v) => v.id)])).toEqual([
      ["a", ["a", "a1", "a2"]], ["b", ["b", "b1"]],
    ]);
  });

  it("keeps incomplete and cyclic histories visible", () => {
    const all = [version("orphan", "missing"), version("x", "y"), version("y", "x")];
    expect(projectId(all[0]!, all)).toBe("orphan");
    expect(projectId(all[1]!, all)).toBe(projectId(all[2]!, all));
    expect(groupProjects(all).flatMap((group) => group.versions).map((v) => v.id)).toEqual(["orphan", "x", "y"]);
  });
});
