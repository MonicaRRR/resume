import { blankResume, sourcedText } from "../resume";
import { annotationLocationLabel, annotationTargetForPath } from "./annotationTarget";


test("maps patch paths to annotation targets", () => {
  expect(annotationTargetForPath("/basics/summary")).toBe("basics.summary");
  expect(annotationTargetForPath("/basics/target_role")).toBe("basics.target_role");
  expect(annotationTargetForPath("/work_experience/0/bullets")).toBe("work_experience.0");
  expect(annotationTargetForPath("/projects/2")).toBe("projects.2");
  expect(annotationTargetForPath("/skills")).toBe("skills");
  expect(annotationTargetForPath("/section_order")).toBe("resume");
});


test("builds human-readable location labels", () => {
  const resume = blankResume();
  resume.basics.summary = sourcedText("概述");
  resume.work_experience = [{
    id: "w1",
    company: "星澜科技",
    title: "后端",
    start_date: "2022-01",
    end_date: "至今",
    bullets: [],
  }];
  expect(annotationLocationLabel("basics.summary", resume)).toBe("个人概述");
  expect(annotationLocationLabel("work_experience.0", resume)).toBe("工作 · 星澜科技");
  expect(annotationLocationLabel("skills")).toBe("技能");
});
