export interface HomeLearningCard {
  id: string
  topic: string
  title: string
  summary: string
  currentStep: number
  totalSteps: number
  progressPercent: number
}

export interface HomeTopic {
  id: string
  name: string
  description: string
  icon: string
  surfaceColor: string
  knowledgePointCount: number
  coveredThisWeek: boolean
}

export interface HomeKnowledgeFixture {
  weeklyCoveragePercent: number
  coveredTopicCount: number
  pendingReviewCount: number
  learningCards: HomeLearningCard[]
  topics: HomeTopic[]
  initialSelectedTopicId: string
}

export const HOME_KNOWLEDGE_FIXTURE: HomeKnowledgeFixture = {
  weeklyCoveragePercent: 67,
  coveredTopicCount: 4,
  pendingReviewCount: 4,
  learningCards: [
    {
      id: "rag-evaluation",
      topic: "评测与可靠性",
      title: "RAG 评测不能只看答案正确率",
      summary: "上次学到：拆分检索、生成与端到端业务指标。",
      currentStep: 3,
      totalSteps: 8,
      progressPercent: 38,
    },
    {
      id: "agent-tool-boundaries",
      topic: "Agent 系统",
      title: "工具调用必须服从权限与状态边界",
      summary: "继续理解稳定 ID、服务端校验与可追踪执行。",
      currentStep: 5,
      totalSteps: 8,
      progressPercent: 63,
    },
    {
      id: "context-budget",
      topic: "Prompt 与上下文",
      title: "上下文预算需要围绕任务证据分配",
      summary: "复习指令层级、证据选择与长上下文成本。",
      currentStep: 7,
      totalSteps: 8,
      progressPercent: 88,
    },
  ],
  topics: [
    {
      id: "agent-systems",
      name: "Agent 系统",
      description: "规划 · 工具 · 记忆",
      icon: "AG",
      surfaceColor: "#e9e1f7",
      knowledgePointCount: 9,
      coveredThisWeek: true,
    },
    {
      id: "rag",
      name: "RAG",
      description: "检索 · 重排 · 生成",
      icon: "RG",
      surfaceColor: "#d8efea",
      knowledgePointCount: 12,
      coveredThisWeek: true,
    },
    {
      id: "prompt-context",
      name: "Prompt 与上下文",
      description: "指令 · Context",
      icon: "CTX",
      surfaceColor: "#eef3bd",
      knowledgePointCount: 8,
      coveredThisWeek: true,
    },
    {
      id: "model-applications",
      name: "模型应用",
      description: "选型 · 推理 · 成本",
      icon: "LLM",
      surfaceColor: "#f1e5d6",
      knowledgePointCount: 7,
      coveredThisWeek: true,
    },
    {
      id: "evaluation-reliability",
      name: "评测与可靠性",
      description: "指标 · 回归 · 追踪",
      icon: "EV",
      surfaceColor: "#dce9f5",
      knowledgePointCount: 7,
      coveredThisWeek: false,
    },
    {
      id: "engineering",
      name: "工程化",
      description: "部署 · 性能 · 监控",
      icon: "OPS",
      surfaceColor: "#e3ece5",
      knowledgePointCount: 5,
      coveredThisWeek: false,
    },
  ],
  initialSelectedTopicId: "rag",
}
