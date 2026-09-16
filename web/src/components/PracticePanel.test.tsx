import { render, screen } from "@testing-library/react";

import type { PracticeSession } from "../types";
import { PracticePanel } from "./PracticePanel";


const writtenSession: PracticeSession = {
  id: "session-1",
  project_id: "project-1",
  kind: "written",
  interview_mode: "technical",
  status: "active",
  current_question: {
    id: "question-1",
    category: "案例题",
    prompt: "如何设计订单幂等方案？",
    hint: "从幂等键和状态机考虑",
    explanation: null,
    requirement_ids: ["req-1"],
    fact_ids: [],
  },
  turns: [],
  weaknesses: [],
  created_at: "2026-08-23T00:00:00Z",
  updated_at: "2026-08-23T00:00:00Z",
};


test("笔试解析在提交答案前不可见", () => {
  render(<PracticePanel session={writtenSession} onAnswer={async () => undefined} />);

  expect(screen.queryByText("参考解析")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "查看提示" })).toBeEnabled();
});
